from __future__ import annotations

from datetime import UTC
from datetime import datetime
from pathlib import Path

from reddit_digest.config import load_scoring_config
from reddit_digest.extractors.service import extract_insights
from reddit_digest.models.comment import Comment
from reddit_digest.models.post import Post
from reddit_digest.outputs.markdown import render_markdown_digest
from reddit_digest.ranking.novelty import apply_novelty
from reddit_digest.ranking.threads import select_threads


def test_render_markdown_digest_writes_daily_and_latest(
    sample_posts_payload: list[dict[str, object]],
    sample_comments_payload: list[dict[str, object]],
    tmp_path: Path,
) -> None:
    posts = tuple(Post.from_raw(item) for item in sample_posts_payload)
    comments = tuple(Comment.from_raw(item) for item in sample_comments_payload)
    extracted = extract_insights(posts, comments, processed_root=tmp_path / "processed", run_date="2026-03-12")
    novelty = apply_novelty(tmp_path / "processed", run_date="2026-03-12", insights=extracted.insights)
    scoring = load_scoring_config(Path.cwd() / "config" / "scoring.yaml")
    thread_selection = select_threads(
        posts,
        scoring=scoring,
        enabled_subreddits=("Codex", "ClaudeCode", "Vibecoding"),
        run_at=datetime(2026, 3, 12, 12, 0, tzinfo=UTC),
        lookback_hours=24,
    )

    result = render_markdown_digest(
        run_date="2026-03-12",
        insights=novelty.insights,
        scoring=scoring,
        thread_selection=thread_selection,
        reports_root=tmp_path / "reports",
    )

    assert result.daily_path.exists()
    assert result.latest_path.exists()
    assert result.daily_path.read_text() == result.latest_path.read_text()
    assert "## Executive Summary" in result.content
    assert "## Top Tools Mentioned" in result.content
    assert "## Notable Threads" in result.content
    assert "## Emerging Themes" in result.content


def test_markdown_digest_section_order(
    sample_posts_payload: list[dict[str, object]],
    sample_comments_payload: list[dict[str, object]],
    tmp_path: Path,
) -> None:
    posts = tuple(Post.from_raw(item) for item in sample_posts_payload)
    comments = tuple(Comment.from_raw(item) for item in sample_comments_payload)
    extracted = extract_insights(posts, comments, processed_root=tmp_path / "processed", run_date="2026-03-12")
    novelty = apply_novelty(tmp_path / "processed", run_date="2026-03-12", insights=extracted.insights)
    scoring = load_scoring_config(Path.cwd() / "config" / "scoring.yaml")
    thread_selection = select_threads(
        posts,
        scoring=scoring,
        enabled_subreddits=("Codex", "ClaudeCode", "Vibecoding"),
        run_at=datetime(2026, 3, 12, 12, 0, tzinfo=UTC),
        lookback_hours=24,
    )

    result = render_markdown_digest(
        run_date="2026-03-12",
        insights=novelty.insights,
        scoring=scoring,
        thread_selection=thread_selection,
        reports_root=tmp_path / "reports",
        watch_next=("Monitor prompt-state snapshots",),
    )

    sections = [
        "## Executive Summary",
        "## Top Tools Mentioned",
        "## Top Approaches / Workflows",
        "## Top Guides / Resources",
        "## Testing and Quality Insights",
        "## Notable Threads",
        "## Emerging Themes",
        "## Watch Next",
    ]
    positions = [result.content.index(section) for section in sections]
    assert positions == sorted(positions)
