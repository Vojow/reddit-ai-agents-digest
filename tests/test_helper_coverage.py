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
from reddit_digest.outputs.digest import _canonicalize_theme_tag
from reddit_digest.outputs.digest import _clean_theme_title
from reddit_digest.outputs.digest import _derive_specific_tool_topic_label
from reddit_digest.outputs.digest import _normalize_theme_title
from reddit_digest.outputs.digest import _resolve_topic_relevance
from reddit_digest.outputs.digest import _resolve_topic_summary
from reddit_digest.outputs.digest import DigestArtifact
from reddit_digest.outputs.digest import DigestThread
from reddit_digest.outputs.digest import EmergingTheme
from reddit_digest.outputs.digest import RankedTopic
from reddit_digest.outputs.digest import select_watch_next_items
from reddit_digest.outputs.markdown import _build_output_paths
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


def _digest(topics: tuple[RankedTopic, ...] = ()) -> DigestArtifact:
    return DigestArtifact(
        run_date="2026-03-13",
        total_posts=4,
        total_insights=3,
        represented_subreddits=("Codex", "ClaudeCode"),
        top_topic_title=topics[0].title if topics else None,
        top_tool="Codex",
        top_approach="Context snapshots",
        top_guide="Prompt recovery checklist",
        top_testing_insight="Deterministic prompting",
        topics=topics,
        notable_threads=(
            DigestThread(title="Thread 1", url="https://reddit.com/t1", subreddit="Codex", impact_score=8.2),
        ),
        emerging_themes=(
            EmergingTheme(
                label="Ai Agents",
                evidence="Codex workflow, Claude Code workflow",
                support_count=2,
                total_impact=16.0,
                evidence_titles=("Codex workflow", "Claude Code workflow"),
            ),
        ),
        watch_next=("Watch one",),
    )


def test_model_base_helpers_validate_and_serialize() -> None:
    @dataclass(frozen=True)
    class ExampleModel(BaseModel):
        value: str

    assert require_string({"name": "  Codex  "}, "name") == "Codex"
    assert optional_string({"name": "  "}, "name") is None
    assert require_int({"count": 3}, "count") == 3
    assert require_non_negative_int({"count": 0}, "count") == 0
    assert require_string_list({"tags": [" one ", "two"]}, "tags") == ("one", "two")
    assert ExampleModel("ok").to_dict() == {"value": "ok"}

    with pytest.raises(ModelError, match="must be a non-empty string"):
        require_string({"name": ""}, "name")
    with pytest.raises(ModelError, match="must be greater than or equal to 0"):
        require_non_negative_int({"count": -1}, "count")


def test_openai_usage_summary_empty_returns_zeroed_summary() -> None:
    assert OpenAIUsageSummary.empty() == OpenAIUsageSummary(
        total_calls=0,
        input_tokens=0,
        output_tokens=0,
        total_tokens=0,
        operations=(),
    )


def test_digest_and_insight_models_cover_validation_edges() -> None:
    item = DigestItem.from_raw(
        {
            "category": "tools",
            "title": "Codex",
            "subreddit": "Codex",
            "permalink": "https://reddit.com/r/Codex/comments/post-1",
            "why_it_matters": "Useful for testing.",
            "impact_score": 1,
            "tags": ["ai-agents"],
            "source_post_ids": ["post-1"],
            "evidence": "  concrete evidence  ",
        }
    )
    assert item.evidence == "concrete evidence"

    with pytest.raises(ModelError, match="must be greater than or equal to 0"):
        DigestItem.from_raw(
            {
                "category": "tools",
                "title": "Codex",
                "subreddit": "Codex",
                "permalink": "https://reddit.com/r/Codex/comments/post-1",
                "why_it_matters": "Useful for testing.",
                "impact_score": -0.1,
                "tags": ["ai-agents"],
                "source_post_ids": ["post-1"],
            }
        )

    with pytest.raises(ModelError, match="must be 'post' or 'comment'"):
        Insight.from_raw(
            {
                "category": "tools",
                "title": "Codex",
                "summary": "summary",
                "tags": ["ai-agents"],
                "evidence": "evidence",
                "source_kind": "thread",
                "source_id": "x",
                "source_post_id": "x",
                "source_permalink": "https://reddit.com/r/Codex/comments/x",
                "subreddit": "Codex",
            }
        )

    assert Suggestion.from_raw(
        {
            "category": "content",
            "title": "Prompt stability follow-up",
            "rationale": "Track whether prompt reproducibility remains a recurring issue.",
        }
    ) == Suggestion(
        category="content",
        title="Prompt stability follow-up",
        rationale="Track whether prompt reproducibility remains a recurring issue.",
    )

    with pytest.raises(ModelError, match="must be 'content' or 'source'"):
        Suggestion.from_raw(
            {
                "category": "invalid",
                "title": "Bad",
                "rationale": "Bad",
            }
        )


def test_extractor_common_builds_sources_and_matches_patterns() -> None:
    post = _post(title="Codex system prompt workflow")
    comment = _comment()

    post_text = post_source(post)
    comment_text = comment_source(comment)

    assert "Codex system prompt workflow" in post_text.text
    assert comment_text.permalink.startswith("https://reddit.com/r/Codex/comments/")

    patterns = (
        InsightPattern(
            title="System prompting",
            category="tools",
            summary="summary",
            why_it_matters="why",
            tags=("tooling",),
            regex=re.compile(r"system prompt"),
        ),
    )

    matched = match_patterns(post_text, patterns)
    assert [item.title for item in matched] == ["System prompting"]
    assert match_patterns(
        TextSource(
            source_kind="post",
            source_id="p2",
            source_post_id="p2",
            subreddit="Codex",
            permalink="https://reddit.com/r/Codex/comments/p2",
            text="plain unrelated text",
        ),
        patterns,
    ) == []


def test_extract_dedupes_and_sorts_insights() -> None:
    post = _post(title="Codex workflow")
    comments = (
        Comment.from_raw(
            {
                "id": "comment-a",
                "post_id": post.id,
                "parent_id": f"t3_{post.id}",
                "subreddit": post.subreddit,
                "author": "commenter",
                "body": "Codex workflow is deterministic and codex is useful.",
                "score": 1,
                "created_utc": 1_741_780_900,
                "permalink": f"/r/{post.subreddit}/comments/{post.id}/comment-a",
            }
        ),
    )

    extracted = _extract((post,), comments)

    assert extracted == sorted(extracted, key=lambda insight: (insight.category, insight.title, insight.source_id))
    assert len({(item.category, item.title, item.source_id) for item in extracted}) == len(extracted)


def test_registry_rejects_unknown_ruleset() -> None:
    with pytest.raises(KeyError, match="unknown"):
        patterns_for_ruleset("unknown")


def test_digest_helper_functions_cover_generic_topic_paths() -> None:
    assert _canonicalize_theme_tag("coding-agents") == "ai-agents"
    assert _normalize_theme_title("  Codex   Limits ") == "codex limits"
    assert _clean_theme_title("  Codex   Limits ") == "Codex Limits"
    assert _derive_specific_tool_topic_label("Codex", "Bad news: Codex limits are tighter") == "Codex plan and quota changes"
    assert _derive_specific_tool_topic_label("Codex", "Neutral announcement") is None

    quota_title = "Codex plan and quota changes"
    assert _resolve_topic_summary(_insight(), topic_title=quota_title).startswith("Threads focus on usage limits")
    assert _resolve_topic_relevance(_insight(), topic_title=quota_title).startswith("Useful for planning tool usage")
    assert select_watch_next_items(watch_next=("Use explicit list",), insights=(_insight(),)) == ("Use explicit list",)
    assert select_watch_next_items(watch_next=(), insights=(_insight(title="One"), _insight(title="Two", novelty="ongoing"))) == ("One",)


def test_digest_artifact_top_thread_and_markdown_paths() -> None:
    topic = RankedTopic(
        topic_key="topic_1",
        title="Codex plan and quota changes",
        executive_summary="summary",
        relevance_for_user="relevance",
        source_title="Original thread",
        source_url="https://reddit.com/t1",
        source_subreddit="Codex",
        impact_score=8.8,
        support_count=2,
    )
    digest = _digest((topic,))

    daily_path, latest_path = _build_output_paths(
        reports_root=Path("/tmp/reports"),
        run_date="2026-03-13",
        variant_suffix="llm",
    )

    assert digest.top_thread == digest.notable_threads[0]
    assert daily_path == Path("/tmp/reports/daily/2026-03-13.llm.md")
    assert latest_path == Path("/tmp/reports/latest.llm.md")


def test_scoring_private_helpers_cover_edge_cases() -> None:
    scoring = _scoring()
    assert _term_density("agent workflow prompt automation", ("agent", "workflow", "prompt")) == 1.0
    assert _recency_score(1_741_780_800, run_at=datetime(2025, 3, 12, tzinfo=UTC), lookback_hours=0) == 0.0
    assert _novelty_component("ongoing") == 0.25
    assert _novelty_component(None) == 0.5
    assert _weighted_total({"relevance": 1.0, "comment_depth": 0.5}, scoring) == 4.0


def test_pipeline_openai_warning_helpers_cover_main_branches(caplog: pytest.LogCaptureFixture) -> None:
    response = httpx.Response(429, request=httpx.Request("POST", "https://api.openai.com/v1/responses"))
    quota_error = APIStatusError(
        "quota",
        response=response,
        body={"error": {"code": "insufficient_quota"}},
    )
    rate_limit_error = RateLimitError("rate limited", response=response, body=None)

    assert _is_openai_quota_error(quota_error) is True
    assert _is_openai_quota_error(Exception("insufficient_quota")) is True
    assert _build_openai_warning(quota_error, skipped_steps="rewrites") == (
        "OPENAI QUOTA EXHAUSTED: rewrites were skipped. "
        "The deterministic markdown below was generated successfully without OpenAI enhancements."
    )
    assert _build_openai_warning(rate_limit_error, skipped_steps="rewrites") == (
        "OPENAI RATE LIMITED: rewrites were skipped. "
        "The deterministic markdown below was generated successfully without OpenAI enhancements."
    )
    assert _build_openai_warning(RuntimeError("boom"), skipped_steps="rewrites") is None

    usage = OpenAIUsageSummary(
        total_calls=3,
        input_tokens=12,
        output_tokens=8,
        total_tokens=20,
        operations=(
            OpenAIOperationUsage(
                operation="topic_rewrites",
                calls=1,
                input_tokens=5,
                output_tokens=3,
                total_tokens=8,
            ),
        ),
    )
    with caplog.at_level(logging.INFO):
        _log_openai_usage_summary(usage)
    assert "OpenAI usage totals: calls=3 input_tokens=12 output_tokens=8 total_tokens=20" in caplog.text
    assert "OpenAI usage for topic_rewrites: calls=1 input_tokens=5 output_tokens=3 total_tokens=8" in caplog.text


def test_configure_logging_forwards_to_basic_config(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_basic_config(**kwargs: object) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(logging, "basicConfig", fake_basic_config)

    configure_logging(level=logging.DEBUG)

    assert captured["level"] == logging.DEBUG
    assert captured["format"] == "%(asctime)s %(levelname)s %(name)s %(message)s"


def test_public_reddit_transport_falls_back_to_default_user_agent() -> None:
    session = type("FakeSession", (), {"headers": {}, "get": lambda self, *_args, **_kwargs: None})()
    PublicRedditTransport(RuntimeConfig(**{**_runtime().__dict__, "reddit_user_agent": None}), session=session)
    assert session.headers["User-Agent"] == "reddit-ai-agents-digest/0.1.0"


def test_cli_main_runs_pipeline_and_prints_help(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    calls: dict[str, object] = {}

    class FakeRunner:
        def __init__(self, *, base_path: Path) -> None:
            calls["base_path"] = base_path

        def run(self, *, run_date: str, skip_sheets: bool) -> None:
            calls["run"] = (run_date, skip_sheets)

    monkeypatch.setattr(cli, "PipelineRunner", FakeRunner)
    monkeypatch.setattr(cli, "configure_logging", lambda: calls.setdefault("logging", True))

    assert cli.main(["run-daily", "--date", "2026-03-13", "--base-path", "/tmp/repo", "--skip-sheets"]) == 0
    assert calls["base_path"] == Path("/tmp/repo")
    assert calls["run"] == ("2026-03-13", True)
    assert calls["logging"] is True

    assert cli.main([]) == 0
    assert "reddit-digest" in capsys.readouterr().out


def test_cli_build_parser_defaults_to_today_and_known_command() -> None:
    parser = cli.build_parser()
    args = parser.parse_args(["run-daily"])
    assert args.command == "run-daily"
    assert args.base_path == "."
    assert isinstance(args.run_date, str)
