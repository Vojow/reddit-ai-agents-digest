from __future__ import annotations

from datetime import UTC
from datetime import datetime
import httpx
from pathlib import Path
from types import SimpleNamespace

import logging
from openai import RateLimitError
import pytest

import reddit_digest.pipeline as pipeline_module
from reddit_digest.config import AppConfig
from reddit_digest.config import FetchConfig
from reddit_digest.config import RuntimeConfig
from reddit_digest.config import SubredditConfig
from reddit_digest.config import load_scoring_config
from reddit_digest.models.insight import Insight
from reddit_digest.models.post import Post
from reddit_digest.pipeline import PipelineRunner
from reddit_digest.utils.retries import retry_call
from reddit_digest.utils.state import RunState
from reddit_digest.utils.state import write_run_state


def test_retry_call_retries_until_success(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("retry-test")
    attempts = {"count": 0}

    def flaky() -> str:
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise RuntimeError("temporary")
        return "ok"

    with caplog.at_level(logging.WARNING):
        result = retry_call(flaky, operation="flaky_op", logger=logger, attempts=3, delay_seconds=0)

    assert result == "ok"
    assert attempts["count"] == 3
    assert "flaky_op failed on attempt 1/3" in caplog.text


def test_write_run_state_updates_dated_and_latest_files(tmp_path: Path) -> None:
    state = RunState(
        run_date="2026-03-12",
        completed_at="2026-03-12T12:00:00+00:00",
        raw_posts_path="data/raw/posts/2026-03-12.json",
        raw_comments_path="data/raw/comments/2026-03-12.json",
        insights_path="data/processed/insights/2026-03-12.json",
        report_path="reports/daily/2026-03-12.md",
        sheets_exported=True,
    )

    write_run_state(tmp_path, state)

    assert (tmp_path / "2026-03-12.json").exists()
    assert (tmp_path / "latest.json").read_text() == (tmp_path / "2026-03-12.json").read_text()


def test_pipeline_keeps_deterministic_markdown_when_llm_variant_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    raw_posts_path = tmp_path / "data" / "raw" / "posts" / "2026-03-12.json"
    raw_comments_path = tmp_path / "data" / "raw" / "comments" / "2026-03-12.json"
    insights_path = tmp_path / "data" / "processed" / "insights" / "2026-03-12.json"
    for path in (raw_posts_path, raw_comments_path, insights_path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("[]")

    posts = (
        Post.from_raw(
            {
                "id": "post_001",
                "subreddit": "Codex",
                "title": "Codex agent keeps a local context file for every task",
                "author": "tester",
                "score": 42,
                "num_comments": 8,
                "created_utc": 1_773_316_800,
                "url": "https://reddit.com/r/Codex/comments/post_001",
                "permalink": "/r/Codex/comments/post_001",
                "selftext": "Store task context locally to resume agent runs cleanly.",
            }
        ),
    )
    insights = (
        Insight.from_raw(
            {
                "category": "approaches",
                "title": "Local task context",
                "summary": "Teams are persisting task context between agent runs.",
                "tags": ["workflow", "context-management"],
                "evidence": "The thread recommends a context file per task.",
                "source_kind": "post",
                "source_id": "post_001",
                "source_post_id": "post_001",
                "source_permalink": "https://reddit.com/r/Codex/comments/post_001",
                "subreddit": "Codex",
                "why_it_matters": "This directly supports a reusable digest around agent workflows.",
                "novelty": "new",
            }
        ),
    )

    config = AppConfig(
        subreddits=SubredditConfig(
            primary=("Codex",),
            secondary=(),
            include_secondary=False,
            fetch=FetchConfig(
                lookback_hours=24,
                sort_modes=("new",),
                min_post_score=0,
                min_comments=0,
                max_posts_per_subreddit=5,
                max_comments_per_post=5,
            ),
        ),
        scoring=load_scoring_config(Path.cwd() / "config" / "scoring.yaml"),
        runtime=RuntimeConfig(
            reddit_client_id=None,
            reddit_client_secret=None,
            reddit_user_agent="digest-test",
            openai_api_key="test-key",
            openai_model="gpt-5-mini",
            gcp_workload_identity_provider=None,
            gcp_service_account_email=None,
            google_service_account_json=None,
            google_sheets_spreadsheet_id=None,
        ),
    )

    class FakePostCollector:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def collect(self, *_args, **_kwargs):
            return SimpleNamespace(posts=posts, raw_path=raw_posts_path)

    class FakeCommentCollector:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def collect(self, *_args, **_kwargs):
            return SimpleNamespace(comments=(), raw_path=raw_comments_path)

    monkeypatch.setattr(pipeline_module, "load_config", lambda *_args, **_kwargs: config)
    monkeypatch.setattr(pipeline_module, "PostCollector", FakePostCollector)
    monkeypatch.setattr(pipeline_module, "CommentCollector", FakeCommentCollector)
    monkeypatch.setattr(
        pipeline_module,
        "extract_insights",
        lambda *_args, **_kwargs: SimpleNamespace(insights=insights),
    )
    monkeypatch.setattr(
        pipeline_module,
        "apply_novelty",
        lambda *_args, **_kwargs: SimpleNamespace(insights=insights, path=insights_path),
    )
    monkeypatch.setattr(
        pipeline_module,
        "build_openai_client",
        lambda *_args, **_kwargs: object(),
    )
    monkeypatch.setattr(
        pipeline_module,
        "generate_suggestions",
        lambda *_args, **_kwargs: SimpleNamespace(suggestions=()),
    )
    monkeypatch.setattr(
        pipeline_module,
        "generate_topic_rewrites",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("rewrite failed")),
    )
    monkeypatch.setattr(
        pipeline_module,
        "retry_call",
        lambda func, **_kwargs: func(),
    )

    with caplog.at_level(logging.WARNING):
        state = PipelineRunner(base_path=tmp_path).run(run_date="2026-03-12", skip_sheets=True)

    assert state.report_path == "reports/daily/2026-03-12.md"
    assert (tmp_path / "reports" / "daily" / "2026-03-12.md").exists()
    assert (tmp_path / "reports" / "latest.md").exists()
    assert not (tmp_path / "reports" / "daily" / "2026-03-12.llm.md").exists()
    assert "Skipping LLM markdown variant for 2026-03-12 after topic rewrite failure" in caplog.text


def test_pipeline_keeps_deterministic_markdown_when_openai_quota_is_exhausted(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    raw_posts_path = tmp_path / "data" / "raw" / "posts" / "2026-03-12.json"
    raw_comments_path = tmp_path / "data" / "raw" / "comments" / "2026-03-12.json"
    insights_path = tmp_path / "data" / "processed" / "insights" / "2026-03-12.json"
    for path in (raw_posts_path, raw_comments_path, insights_path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("[]")

    posts = (
        Post.from_raw(
            {
                "id": "post_001",
                "subreddit": "Codex",
                "title": "Codex agent keeps a local context file for every task",
                "author": "tester",
                "score": 42,
                "num_comments": 8,
                "created_utc": 1_773_316_800,
                "url": "https://reddit.com/r/Codex/comments/post_001",
                "permalink": "/r/Codex/comments/post_001",
                "selftext": "Store task context locally to resume agent runs cleanly.",
            }
        ),
    )
    insights = (
        Insight.from_raw(
            {
                "category": "approaches",
                "title": "Local task context",
                "summary": "Teams are persisting task context between agent runs.",
                "tags": ["workflow", "context-management"],
                "evidence": "The thread recommends a context file per task.",
                "source_kind": "post",
                "source_id": "post_001",
                "source_post_id": "post_001",
                "source_permalink": "https://reddit.com/r/Codex/comments/post_001",
                "subreddit": "Codex",
                "why_it_matters": "This directly supports a reusable digest around agent workflows.",
                "novelty": "new",
            }
        ),
    )

    config = AppConfig(
        subreddits=SubredditConfig(
            primary=("Codex",),
            secondary=(),
            include_secondary=False,
            fetch=FetchConfig(
                lookback_hours=24,
                sort_modes=("new",),
                min_post_score=0,
                min_comments=0,
                max_posts_per_subreddit=5,
                max_comments_per_post=5,
            ),
        ),
        scoring=load_scoring_config(Path.cwd() / "config" / "scoring.yaml"),
        runtime=RuntimeConfig(
            reddit_client_id=None,
            reddit_client_secret=None,
            reddit_user_agent="digest-test",
            openai_api_key="test-key",
            openai_model="gpt-5-mini",
            gcp_workload_identity_provider=None,
            gcp_service_account_email=None,
            google_service_account_json=None,
            google_sheets_spreadsheet_id=None,
        ),
    )

    class FakePostCollector:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def collect(self, *_args, **_kwargs):
            return SimpleNamespace(posts=posts, raw_path=raw_posts_path)

    class FakeCommentCollector:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def collect(self, *_args, **_kwargs):
            return SimpleNamespace(comments=(), raw_path=raw_comments_path)

    def raise_quota_error(*_args, **_kwargs):
        response = httpx.Response(status_code=429, request=httpx.Request("POST", "https://api.openai.com/v1/responses"))
        raise RateLimitError(
            "Error code: 429 - {'error': {'code': 'insufficient_quota', 'message': 'insufficient quota'}}",
            response=response,
            body={"error": {"code": "insufficient_quota", "message": "insufficient quota"}},
        )

    monkeypatch.setattr(pipeline_module, "load_config", lambda *_args, **_kwargs: config)
    monkeypatch.setattr(pipeline_module, "PostCollector", FakePostCollector)
    monkeypatch.setattr(pipeline_module, "CommentCollector", FakeCommentCollector)
    monkeypatch.setattr(
        pipeline_module,
        "extract_insights",
        lambda *_args, **_kwargs: SimpleNamespace(insights=insights),
    )
    monkeypatch.setattr(
        pipeline_module,
        "apply_novelty",
        lambda *_args, **_kwargs: SimpleNamespace(insights=insights, path=insights_path),
    )
    monkeypatch.setattr(
        pipeline_module,
        "build_openai_client",
        lambda *_args, **_kwargs: object(),
    )
    monkeypatch.setattr(pipeline_module, "generate_suggestions", raise_quota_error)
    monkeypatch.setattr(
        pipeline_module,
        "generate_topic_rewrites",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("topic rewrites should be skipped")),
    )
    monkeypatch.setattr(
        pipeline_module,
        "retry_call",
        lambda func, **_kwargs: func(),
    )

    with caplog.at_level(logging.WARNING):
        state = PipelineRunner(base_path=tmp_path).run(run_date="2026-03-12", skip_sheets=True)

    report_path = tmp_path / "reports" / "daily" / "2026-03-12.md"
    content = report_path.read_text()

    assert state.report_path == "reports/daily/2026-03-12.md"
    assert report_path.exists()
    assert (tmp_path / "reports" / "latest.md").exists()
    assert not (tmp_path / "reports" / "daily" / "2026-03-12.llm.md").exists()
    assert "## Warnings" in content
    assert "OPENAI QUOTA EXHAUSTED" in content
    assert "The deterministic markdown below was generated successfully without OpenAI enhancements." in content
    assert "Skipping OpenAI suggestions for 2026-03-12 after failure" in caplog.text
