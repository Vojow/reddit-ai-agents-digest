from __future__ import annotations

from datetime import UTC
from datetime import datetime
from dataclasses import dataclass
import httpx
import logging
import re
from pathlib import Path

from openai import APIStatusError
from openai import RateLimitError
import pytest

import reddit_digest.cli as cli
from reddit_digest.collectors.shared import PublicRedditTransport
from reddit_digest.config import FetchConfig
from reddit_digest.config import RuntimeConfig
from reddit_digest.config import ScoringConfig
from reddit_digest.extractors.common import comment_source
from reddit_digest.extractors.common import InsightPattern
from reddit_digest.extractors.common import match_patterns
from reddit_digest.extractors.common import post_source
from reddit_digest.extractors.common import TextSource
from reddit_digest.extractors.registry import patterns_for_ruleset
from reddit_digest.extractors.service import _extract
from reddit_digest.models.base import BaseModel
from reddit_digest.models.base import ModelError
from reddit_digest.models.base import optional_string
from reddit_digest.models.base import require_int
from reddit_digest.models.base import require_non_negative_int
from reddit_digest.models.base import require_string
from reddit_digest.models.base import require_string_list
from reddit_digest.models.comment import Comment
from reddit_digest.models.digest import DigestItem
from reddit_digest.models.insight import Insight
from reddit_digest.models.openai_usage import OpenAIOperationUsage
from reddit_digest.models.openai_usage import OpenAIUsageSummary
from reddit_digest.models.post import Post
from reddit_digest.models.suggestion import Suggestion
from reddit_digest.pipeline import _build_openai_warning
from reddit_digest.pipeline import _is_openai_quota_error
from reddit_digest.pipeline import _log_openai_usage_summary
from reddit_digest.ranking.impact import _novelty_component
from reddit_digest.ranking.impact import _recency_score
from reddit_digest.ranking.impact import _term_density
from reddit_digest.ranking.impact import _weighted_total
from reddit_digest.utils.logging import configure_logging


def _runtime() -> RuntimeConfig:
    return RuntimeConfig(
        reddit_client_id=None,
        reddit_client_secret=None,
        reddit_user_agent="digest-test-agent",
        openai_api_key=None,
        openai_model="gpt-5-mini",
        teams_webhook_url=None,
        gcp_workload_identity_provider=None,
        gcp_service_account_email=None,
        google_service_account_json=None,
        google_sheets_spreadsheet_id=None,
    )


def _scoring() -> ScoringConfig:
    return ScoringConfig(
        weights={
            "relevance": 0.3,
            "comment_depth": 0.2,
            "actionability": 0.2,
            "novelty": 0.1,
            "engagement": 0.1,
            "recency": 0.1,
        },
        tags=("ai-agents", "tooling", "prompting"),
    )


def _post(*, post_id: str = "post-1", subreddit: str = "Codex", title: str = "Codex workflow") -> Post:
    return Post.from_raw(
        {
            "id": post_id,
            "subreddit": subreddit,
            "title": title,
            "author": "tester",
            "score": 12,
            "num_comments": 3,
            "created_utc": 1_741_780_800,
            "url": f"https://reddit.com/r/{subreddit}/comments/{post_id}",
            "permalink": f"/r/{subreddit}/comments/{post_id}",
            "selftext": "system prompt workflow guide",
        }
    )


def _comment(*, comment_id: str = "comment-1", subreddit: str = "Codex", post_id: str = "post-1") -> Comment:
    return Comment.from_raw(
        {
            "id": comment_id,
            "post_id": post_id,
            "parent_id": f"t3_{post_id}",
            "subreddit": subreddit,
            "author": "commenter",
            "body": "Codex workflow is deterministic",
            "score": 5,
            "created_utc": 1_741_780_900,
            "permalink": f"/r/{subreddit}/comments/{post_id}/{comment_id}",
        }
    )


def _insight(
    *,
    title: str = "Codex",
    source_id: str = "post-1",
    source_post_id: str = "post-1",
    novelty: str | None = "new",
) -> Insight:
    return Insight.from_raw(
        {
            "category": "tools",
            "title": title,
            "summary": "Codex is being used in practical workflows.",
            "tags": ["ai-agents", "tooling"],
            "evidence": "Codex workflow evidence",
            "source_kind": "post",
            "source_id": source_id,
            "source_post_id": source_post_id,
            "source_permalink": "https://reddit.com/r/Codex/comments/post-1",
            "subreddit": "Codex",
            "why_it_matters": "Useful for agent workflow evaluation.",
            "novelty": novelty,
        }
    )

def test_scoring_private_helpers_cover_edge_cases() -> None:
    scoring = _scoring()
    assert _term_density("agent workflow prompt automation", ("agent", "workflow", "prompt")) == 1.0
    assert _recency_score(1_741_780_800, run_at=datetime(2025, 3, 12, tzinfo=UTC), lookback_hours=0) == 0.0
    assert _novelty_component("ongoing") == 0.25
    assert _novelty_component(None) == 0.5
    assert _weighted_total({"relevance": 1.0, "comment_depth": 0.5}, scoring) == 4.0


def test_configure_logging_forwards_to_basic_config(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_basic_config(**kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(logging, "basicConfig", fake_basic_config)

    configure_logging(level=logging.DEBUG)

    assert captured["level"] == logging.DEBUG
    assert captured["format"] == "%(asctime)s %(levelname)s %(name)s %(message)s"

