from __future__ import annotations

from datetime import UTC
from datetime import datetime
from pathlib import Path
import json
from typing import Any

from reddit_digest.collectors.reddit_posts import PostCollector
from reddit_digest.config import FetchConfig
from reddit_digest.config import SubredditConfig


class StubPostSource:
    def __init__(self, payloads: dict[tuple[str, str], list[dict[str, Any]]]) -> None:
        self.payloads = payloads

    def fetch_posts(self, subreddit: str, sort_mode: str, limit: int) -> list[dict[str, Any]]:
        return self.payloads.get((subreddit, sort_mode), [])[:limit]


def build_config() -> SubredditConfig:
    return SubredditConfig(
        primary=("Codex", "ClaudeCode"),
        secondary=(),
        include_secondary=False,
        fetch=FetchConfig(
            lookback_hours=24,
            sort_modes=("new", "top"),
            min_post_score=5,
            min_comments=3,
            max_posts_per_subreddit=2,
            max_comments_per_post=50,
        ),
    )


def build_config_with_secondary(*, include_secondary: bool) -> SubredditConfig:
    return SubredditConfig(
        primary=("Codex",),
        secondary=("LocalLLaMA",),
        include_secondary=include_secondary,
        fetch=FetchConfig(
            lookback_hours=24,
            sort_modes=("new",),
            min_post_score=5,
            min_comments=3,
            max_posts_per_subreddit=2,
            max_comments_per_post=50,
        ),
    )


def test_collect_posts_filters_and_persists(sample_posts_payload: list[dict[str, Any]], tmp_path: Path) -> None:
    old_post = dict(sample_posts_payload[0])
    old_post["id"] = "post_old"
    old_post["created_utc"] = 1773200000

    low_score_post = dict(sample_posts_payload[1])
    low_score_post["id"] = "post_low_score"
    low_score_post["score"] = 1

    source = StubPostSource(
        {
            ("Codex", "new"): [sample_posts_payload[0], old_post],
            ("Codex", "top"): [sample_posts_payload[0]],
            ("ClaudeCode", "new"): [sample_posts_payload[1], low_score_post],
            ("ClaudeCode", "top"): [],
        }
    )
    collector = PostCollector(source, tmp_path / "raw", tmp_path / "processed")

    result = collector.collect(
        build_config(),
        run_at=datetime(2026, 3, 12, 12, 0, tzinfo=UTC),
    )

    assert result.run_date == "2026-03-12"
    assert [post.id for post in result.posts] == ["post_001", "post_002"]

    raw_payload = json.loads(result.raw_path.read_text())
    processed_payload = json.loads(result.processed_path.read_text())

    assert "Codex" in raw_payload
    assert processed_payload[0]["id"] == "post_001"
    assert processed_payload[1]["id"] == "post_002"


def test_collect_posts_handles_empty_results(tmp_path: Path) -> None:
    collector = PostCollector(StubPostSource({}), tmp_path / "raw", tmp_path / "processed")

    result = collector.collect(
        build_config(),
        run_at=datetime(2026, 3, 12, 12, 0, tzinfo=UTC),
    )

    assert result.posts == ()
    assert json.loads(result.processed_path.read_text()) == []


def test_collect_posts_respects_max_posts_per_subreddit(sample_posts_payload: list[dict[str, Any]], tmp_path: Path) -> None:
    payloads = []
    for index in range(4):
        item = dict(sample_posts_payload[0])
        item["id"] = f"codex_{index}"
        item["created_utc"] = 1773315600 - index
        payloads.append(item)

    collector = PostCollector(
        StubPostSource({("Codex", "new"): payloads, ("Codex", "top"): [], ("ClaudeCode", "new"): [], ("ClaudeCode", "top"): []}),
        tmp_path / "raw",
        tmp_path / "processed",
    )

    result = collector.collect(
        build_config(),
        run_at=datetime(2026, 3, 12, 12, 0, tzinfo=UTC),
    )

    assert [post.id for post in result.posts] == ["codex_0", "codex_1"]


def test_collect_posts_excludes_secondary_subreddits_by_default(
    sample_posts_payload: list[dict[str, Any]],
    tmp_path: Path,
) -> None:
    local_payload = dict(sample_posts_payload[0])
    local_payload["id"] = "local_001"
    local_payload["subreddit"] = "LocalLLaMA"

    collector = PostCollector(
        StubPostSource(
            {
                ("Codex", "new"): [sample_posts_payload[0]],
                ("LocalLLaMA", "new"): [local_payload],
            }
        ),
        tmp_path / "raw",
        tmp_path / "processed",
    )

    result = collector.collect(
        build_config_with_secondary(include_secondary=False),
        run_at=datetime(2026, 3, 12, 12, 0, tzinfo=UTC),
    )

    assert [post.id for post in result.posts] == ["post_001"]


def test_collect_posts_can_include_secondary_subreddits(
    sample_posts_payload: list[dict[str, Any]],
    tmp_path: Path,
) -> None:
    local_payload = dict(sample_posts_payload[0])
    local_payload["id"] = "local_001"
    local_payload["subreddit"] = "LocalLLaMA"

    collector = PostCollector(
        StubPostSource(
            {
                ("Codex", "new"): [sample_posts_payload[0]],
                ("LocalLLaMA", "new"): [local_payload],
            }
        ),
        tmp_path / "raw",
        tmp_path / "processed",
    )

    result = collector.collect(
        build_config_with_secondary(include_secondary=True),
        run_at=datetime(2026, 3, 12, 12, 0, tzinfo=UTC),
    )

    assert [post.subreddit for post in result.posts] == ["Codex", "LocalLLaMA"]


def test_collect_posts_normalizes_subreddit_to_configured_casing(
    sample_posts_payload: list[dict[str, Any]],
    tmp_path: Path,
) -> None:
    lowercase_codex = dict(sample_posts_payload[0])
    lowercase_codex["subreddit"] = "codex"

    collector = PostCollector(
        StubPostSource(
            {
                ("Codex", "new"): [lowercase_codex],
                ("ClaudeCode", "new"): [],
                ("Codex", "top"): [],
                ("ClaudeCode", "top"): [],
            }
        ),
        tmp_path / "raw",
        tmp_path / "processed",
    )

    result = collector.collect(
        build_config(),
        run_at=datetime(2026, 3, 12, 12, 0, tzinfo=UTC),
    )

    assert [post.subreddit for post in result.posts] == ["Codex"]
    processed_payload = json.loads(result.processed_path.read_text())
    assert processed_payload[0]["subreddit"] == "Codex"
