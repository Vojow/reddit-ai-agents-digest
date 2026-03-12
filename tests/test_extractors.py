from __future__ import annotations

from pathlib import Path
import json

from reddit_digest.extractors.service import extract_insights
from reddit_digest.models.comment import Comment
from reddit_digest.models.post import Post


def build_posts(sample_posts_payload: list[dict[str, object]]) -> tuple[Post, ...]:
    return tuple(Post.from_raw(item) for item in sample_posts_payload)


def build_comments(sample_comments_payload: list[dict[str, object]]) -> tuple[Comment, ...]:
    return tuple(Comment.from_raw(item) for item in sample_comments_payload)


def test_extract_insights_from_posts_and_comments(
    sample_posts_payload: list[dict[str, object]],
    sample_comments_payload: list[dict[str, object]],
    tmp_path: Path,
) -> None:
    result = extract_insights(
        build_posts(sample_posts_payload),
        build_comments(sample_comments_payload),
        processed_root=tmp_path,
        run_date="2026-03-12",
    )

    assert result.path == tmp_path / "insights" / "2026-03-12.json"
    assert result.path.exists()
    assert {insight.category for insight in result.insights} >= {"approaches", "testing", "tools"}
    assert any(insight.title == "Codex" for insight in result.insights)
    assert any(insight.source_kind == "comment" for insight in result.insights)

    persisted = json.loads(result.path.read_text())
    assert persisted[0]["category"] <= persisted[-1]["category"]


def test_extract_insights_handles_no_matches(sample_posts_payload: list[dict[str, object]], tmp_path: Path) -> None:
    bland_post = dict(sample_posts_payload[0])
    bland_post["title"] = "Weekend check-in"
    bland_post["selftext"] = "Just saying hi."

    result = extract_insights(
        (Post.from_raw(bland_post),),
        (),
        processed_root=tmp_path,
        run_date="2026-03-12",
    )

    assert result.insights == ()
    assert json.loads(result.path.read_text()) == []
