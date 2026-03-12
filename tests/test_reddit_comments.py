from __future__ import annotations

from datetime import UTC
from datetime import datetime
from pathlib import Path
import json
from typing import Any

from reddit_digest.collectors.reddit_comments import CommentCollector
from reddit_digest.models.post import Post


class StubCommentSource:
    def __init__(self, payloads: dict[str, list[dict[str, Any]]]) -> None:
        self.payloads = payloads

    def fetch_comments(self, post: Post, limit: int) -> list[dict[str, Any]]:
        return self.payloads.get(post.id, [])[:limit]


def sample_posts(sample_posts_payload: list[dict[str, Any]]) -> tuple[Post, ...]:
    return tuple(Post.from_raw(item) for item in sample_posts_payload)


def test_collect_comments_filters_deleted_and_persists(
    sample_posts_payload: list[dict[str, Any]],
    sample_comments_payload: list[dict[str, Any]],
    tmp_path: Path,
) -> None:
    deleted_comment = dict(sample_comments_payload[0])
    deleted_comment["id"] = "comment_deleted"
    deleted_comment["body"] = "[deleted]"

    collector = CommentCollector(
        StubCommentSource(
            {
                "post_001": [sample_comments_payload[0], deleted_comment],
                "post_002": [sample_comments_payload[1]],
            }
        ),
        tmp_path / "raw",
        tmp_path / "processed",
    )

    result = collector.collect(
        sample_posts(sample_posts_payload),
        max_comments_per_post=5,
        run_at=datetime(2026, 3, 12, 12, 0, tzinfo=UTC),
    )

    assert [comment.id for comment in result.comments] == ["comment_001", "comment_002"]
    assert json.loads(result.raw_path.read_text())["post_001"][1]["id"] == "comment_deleted"
    assert len(json.loads(result.processed_path.read_text())) == 2


def test_collect_comments_respects_max_per_post(
    sample_posts_payload: list[dict[str, Any]],
    sample_comments_payload: list[dict[str, Any]],
    tmp_path: Path,
) -> None:
    comments: list[dict[str, Any]] = []
    for index in range(4):
        comment = dict(sample_comments_payload[0])
        comment["id"] = f"comment_{index}"
        comment["created_utc"] = 1773316500 + index
        comments.append(comment)

    collector = CommentCollector(
        StubCommentSource({"post_001": comments, "post_002": []}),
        tmp_path / "raw",
        tmp_path / "processed",
    )

    result = collector.collect(
        sample_posts(sample_posts_payload),
        max_comments_per_post=2,
        run_at=datetime(2026, 3, 12, 12, 0, tzinfo=UTC),
    )

    assert [comment.id for comment in result.comments] == ["comment_0", "comment_1"]


def test_collect_comments_handles_empty_results(sample_posts_payload: list[dict[str, Any]], tmp_path: Path) -> None:
    collector = CommentCollector(StubCommentSource({}), tmp_path / "raw", tmp_path / "processed")

    result = collector.collect(
        sample_posts(sample_posts_payload),
        max_comments_per_post=2,
        run_at=datetime(2026, 3, 12, 12, 0, tzinfo=UTC),
    )

    assert result.comments == ()
    assert json.loads(result.processed_path.read_text()) == []
