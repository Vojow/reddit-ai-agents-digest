from __future__ import annotations

from datetime import UTC
from datetime import datetime
from pathlib import Path

from reddit_digest.config import load_scoring_config
from reddit_digest.extractors.service import extract_insights
from reddit_digest.models.comment import Comment
from reddit_digest.models.insight import Insight
from reddit_digest.models.post import Post
from reddit_digest.outputs.markdown import render_markdown_digest
from reddit_digest.outputs.markdown import select_digest_topics
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
    assert "## Picked Topics" in result.content
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
        "## Picked Topics",
        "## Emerging Themes",
        "## Watch Next",
    ]
    positions = [result.content.index(section) for section in sections]
    assert positions == sorted(positions)


def test_markdown_digest_renders_warnings_before_executive_summary(tmp_path: Path) -> None:
    scoring = load_scoring_config(Path.cwd() / "config" / "scoring.yaml")
    posts = (
        _build_post(post_id="codex-1", subreddit="Codex", score=99, num_comments=25),
        _build_post(post_id="claude-1", subreddit="ClaudeCode", score=96, num_comments=23),
    )
    insights = tuple(_build_insight(post) for post in posts)
    thread_selection = select_threads(
        posts,
        scoring=scoring,
        enabled_subreddits=("Codex", "ClaudeCode"),
        run_at=datetime(2026, 3, 12, 12, 0, tzinfo=UTC),
        lookback_hours=24,
    )

    result = render_markdown_digest(
        run_date="2026-03-12",
        insights=insights,
        scoring=scoring,
        thread_selection=thread_selection,
        reports_root=tmp_path / "reports",
        warnings=(
            "OPENAI QUOTA EXHAUSTED: Watch Next suggestions and LLM topic rewrites were skipped. The deterministic markdown below was generated successfully without OpenAI enhancements.",
        ),
    )

    assert result.content.index("## Warnings") < result.content.index("## Executive Summary")
    assert "OPENAI QUOTA EXHAUSTED" in result.content


def test_markdown_digest_renders_picked_topics_with_summary_relevance_and_source(tmp_path: Path) -> None:
    scoring = load_scoring_config(Path.cwd() / "config" / "scoring.yaml")
    posts = tuple(
        _build_post(post_id=f"codex-{index}", subreddit="Codex", score=120 - index, num_comments=30 - index)
        for index in range(1, 6)
    ) + tuple(
        _build_post(post_id=f"claude-{index}", subreddit="ClaudeCode", score=90 - index, num_comments=20 - index)
        for index in range(1, 5)
    )
    insights = tuple(_build_insight(post) for post in posts)
    thread_selection = select_threads(
        posts,
        scoring=scoring,
        enabled_subreddits=("Codex", "ClaudeCode"),
        run_at=datetime(2026, 3, 12, 12, 0, tzinfo=UTC),
        lookback_hours=24,
    )

    result = render_markdown_digest(
        run_date="2026-03-12",
        insights=insights,
        scoring=scoring,
        thread_selection=thread_selection,
        reports_root=tmp_path / "reports",
    )

    topic_lines = _section_lines(result.content, "## Picked Topics", "## Emerging Themes")
    assert topic_lines.count("### ") == 6
    assert "- Executive summary:" in topic_lines
    assert "- Relevance for you:" in topic_lines
    assert "- Original post:" in topic_lines
    assert "- Source subreddit: r/Codex" in topic_lines
    assert "- Source subreddit: r/ClaudeCode" in topic_lines
    assert "Picked 6 topics from 2 subreddit(s): r/Codex, r/ClaudeCode" in result.content


def test_markdown_digest_is_deterministic_for_same_inputs(tmp_path: Path) -> None:
    scoring = load_scoring_config(Path.cwd() / "config" / "scoring.yaml")
    posts = (
        _build_post(post_id="codex-1", subreddit="Codex", score=99, num_comments=25),
        _build_post(post_id="claude-1", subreddit="ClaudeCode", score=96, num_comments=23),
        _build_post(post_id="codex-2", subreddit="Codex", score=92, num_comments=19),
    )
    insights = tuple(_build_insight(post) for post in posts)
    thread_selection = select_threads(
        posts,
        scoring=scoring,
        enabled_subreddits=("Codex", "ClaudeCode"),
        run_at=datetime(2026, 3, 12, 12, 0, tzinfo=UTC),
        lookback_hours=24,
    )

    first = render_markdown_digest(
        run_date="2026-03-12",
        insights=insights,
        scoring=scoring,
        thread_selection=thread_selection,
        reports_root=tmp_path / "reports-one",
    )
    second = render_markdown_digest(
        run_date="2026-03-12",
        insights=insights,
        scoring=scoring,
        thread_selection=thread_selection,
        reports_root=tmp_path / "reports-two",
    )

    assert first.content == second.content


def test_render_markdown_digest_writes_llm_variant_with_rewritten_topics(tmp_path: Path) -> None:
    scoring = load_scoring_config(Path.cwd() / "config" / "scoring.yaml")
    posts = (
        _build_post(post_id="codex-1", subreddit="Codex", score=99, num_comments=25),
        _build_post(post_id="claude-1", subreddit="ClaudeCode", score=96, num_comments=23),
        _build_post(post_id="codex-2", subreddit="Codex", score=92, num_comments=19),
    )
    insights = tuple(_build_insight(post) for post in posts)
    thread_selection = select_threads(
        posts,
        scoring=scoring,
        enabled_subreddits=("Codex", "ClaudeCode"),
        run_at=datetime(2026, 3, 12, 12, 0, tzinfo=UTC),
        lookback_hours=24,
    )
    topics = select_digest_topics(
        insights=insights,
        scoring=scoring,
        thread_selection=thread_selection,
    )

    result = render_markdown_digest(
        run_date="2026-03-12",
        insights=insights,
        scoring=scoring,
        thread_selection=thread_selection,
        reports_root=tmp_path / "reports",
        topics=topics,
        topic_rewrites={
            topics[0].topic_key: (
                "Sharper summary for the picked topic.",
                "This matters because it maps directly to your agent workflow.",
            )
        },
        variant_suffix="llm",
    )

    assert result.daily_path.name == "2026-03-12.llm.md"
    assert result.latest_path.name == "latest.llm.md"
    assert "Sharper summary for the picked topic." in result.content
    assert "This matters because it maps directly to your agent workflow." in result.content
    assert "- Original post:" in result.content


def _build_post(*, post_id: str, subreddit: str, score: int, num_comments: int) -> Post:
    return Post.from_raw(
        {
            "id": post_id,
            "subreddit": subreddit,
            "title": f"{subreddit} thread {post_id}",
            "author": "tester",
            "score": score,
            "num_comments": num_comments,
            "created_utc": 1_773_316_800,
            "url": f"https://reddit.com/r/{subreddit}/comments/{post_id}",
            "permalink": f"/r/{subreddit}/comments/{post_id}",
            "selftext": "workflow guide eval automation test prompt",
        }
    )


def _build_insight(post: Post) -> Insight:
    return Insight.from_raw(
        {
            "category": "approaches",
            "title": f"{post.subreddit} insight {post.id}",
            "summary": f"{post.title} contains workflow guidance.",
            "tags": ["workflow", "testing"],
            "evidence": f"Evidence from {post.id}",
            "source_kind": "post",
            "source_id": post.id,
            "source_post_id": post.id,
            "source_permalink": post.url,
            "subreddit": post.subreddit,
            "why_it_matters": f"{post.subreddit} guidance stays actionable.",
        }
    )


def _section_lines(content: str, start_heading: str, end_heading: str) -> str:
    return content.split(start_heading + "\n", maxsplit=1)[1].split("\n" + end_heading, maxsplit=1)[0]
