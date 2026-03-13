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
from reddit_digest.outputs.markdown import select_emerging_themes
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
            "OPENAI QUOTA EXHAUSTED: Watch Next suggestions, LLM topic rewrites, and LLM executive summary rewrites were skipped. The deterministic markdown below was generated successfully without OpenAI enhancements.",
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
        executive_summary_rewrite="Three specific workflow topics stand out today across Codex and ClaudeCode.",
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
    assert "Three specific workflow topics stand out today across Codex and ClaudeCode." in result.content
    assert "Sharper summary for the picked topic." in result.content
    assert "This matters because it maps directly to your agent workflow." in result.content
    assert "- Original post:" in result.content


def test_select_digest_topics_prefers_specific_tool_issue_titles(tmp_path: Path) -> None:
    scoring = load_scoring_config(Path.cwd() / "config" / "scoring.yaml")
    posts = (
        _build_post(
            post_id="claude-1",
            subreddit="ClaudeCode",
            score=99,
            num_comments=26,
            title='Claude Code is not "stupid now": it is being system prompted to act like that',
        ),
        _build_post(
            post_id="codex-1",
            subreddit="Codex",
            score=97,
            num_comments=24,
            title="Bad news: Codex limits were tightened again",
        ),
        _build_post(
            post_id="hybrid-1",
            subreddit="ClaudeCode",
            score=95,
            num_comments=22,
            title="Hybrid Claude Code / Codex",
        ),
    )
    insights = (
        _build_tool_insight(posts[0], title="Claude Code"),
        _build_tool_insight(posts[1], title="Codex"),
        _build_tool_insight(posts[2], title="Codex"),
    )
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

    titles = {topic.title for topic in topics}
    assert "Claude Code" not in titles
    assert "Codex" not in titles
    assert "Claude Code system prompting behavior" in titles
    assert "Codex plan and quota changes" in titles
    assert "Hybrid Claude Code and Codex workflows" in titles


def test_select_digest_topics_groups_similar_tool_issue_threads(tmp_path: Path) -> None:
    scoring = load_scoring_config(Path.cwd() / "config" / "scoring.yaml")
    posts = (
        _build_post(
            post_id="codex-1",
            subreddit="Codex",
            score=99,
            num_comments=25,
            title="Bad news: Codex limits are getting tighter",
        ),
        _build_post(
            post_id="codex-2",
            subreddit="Codex",
            score=95,
            num_comments=21,
            title="Codex quota tightened again this week",
        ),
    )
    insights = tuple(_build_tool_insight(post, title="Codex") for post in posts)
    thread_selection = select_threads(
        posts,
        scoring=scoring,
        enabled_subreddits=("Codex",),
        run_at=datetime(2026, 3, 12, 12, 0, tzinfo=UTC),
        lookback_hours=24,
    )

    topics = select_digest_topics(
        insights=insights,
        scoring=scoring,
        thread_selection=thread_selection,
    )

    assert len(topics) == 1
    assert topics[0].title == "Codex plan and quota changes"
    assert topics[0].support_count == 2
    assert "limits, quotas, and plan changes" in topics[0].executive_summary


def test_select_digest_topics_keeps_generic_tool_title_when_discussion_is_tool_wide(tmp_path: Path) -> None:
    scoring = load_scoring_config(Path.cwd() / "config" / "scoring.yaml")
    post = _build_post(
        post_id="codex-1",
        subreddit="Codex",
        score=99,
        num_comments=25,
        title="Codex is better than before",
    )
    insight = _build_tool_insight(post, title="Codex")
    thread_selection = select_threads(
        (post,),
        scoring=scoring,
        enabled_subreddits=("Codex",),
        run_at=datetime(2026, 3, 12, 12, 0, tzinfo=UTC),
        lookback_hours=24,
    )

    topics = select_digest_topics(
        insights=(insight,),
        scoring=scoring,
        thread_selection=thread_selection,
    )

    assert len(topics) == 1
    assert topics[0].title == "Codex"
    assert topics[0].executive_summary == insight.summary


def test_select_emerging_themes_dedupes_titles_merges_overlapping_tags_and_caps_evidence() -> None:
    scoring = load_scoring_config(Path.cwd() / "config" / "scoring.yaml")
    insights = (
        Insight.from_raw(
            {
                "category": "approaches",
                "title": "Agent Memory Patterns",
                "summary": "Agent workflow guide with reusable template and checklist.",
                "tags": ["coding-agents"],
                "evidence": "Detailed workflow checklist guide template context snapshot refactor automation.",
                "source_kind": "post",
                "source_id": "post_001",
                "source_post_id": "post_001",
                "source_permalink": "https://reddit.com/r/Codex/comments/post_001",
                "subreddit": "Codex",
                "why_it_matters": "Useful workflow checklist for agent systems.",
                "novelty": "new",
            }
        ),
        Insight.from_raw(
            {
                "category": "approaches",
                "title": " agent   memory patterns ",
                "summary": "Another agent workflow guide with template details.",
                "tags": ["ai-agents"],
                "evidence": "Workflow template guide context automation.",
                "source_kind": "comment",
                "source_id": "comment_001",
                "source_post_id": "post_002",
                "source_permalink": "https://reddit.com/r/ClaudeCode/comments/post_002/comment_001",
                "subreddit": "ClaudeCode",
                "why_it_matters": "Keeps agent workflows repeatable.",
                "novelty": "new",
            }
        ),
        Insight.from_raw(
            {
                "category": "approaches",
                "title": "Tooling For Agents",
                "summary": "Agent automation guide for test workflows.",
                "tags": ["ai-agents"],
                "evidence": "Automation workflow test guide.",
                "source_kind": "post",
                "source_id": "post_003",
                "source_post_id": "post_003",
                "source_permalink": "https://reddit.com/r/Codex/comments/post_003",
                "subreddit": "Codex",
                "why_it_matters": "Useful for agent development loops.",
                "novelty": "new",
            }
        ),
        Insight.from_raw(
            {
                "category": "approaches",
                "title": "Eval Harnesses",
                "summary": "Guide for test eval workflow and agent checks.",
                "tags": ["ai-agents"],
                "evidence": "Guide workflow test eval checklist automation template.",
                "source_kind": "post",
                "source_id": "post_004",
                "source_post_id": "post_004",
                "source_permalink": "https://reddit.com/r/Vibecoding/comments/post_004",
                "subreddit": "Vibecoding",
                "why_it_matters": "Directly helps testing agents.",
                "novelty": "new",
            }
        ),
        Insight.from_raw(
            {
                "category": "approaches",
                "title": "Workflow Docs",
                "summary": "Guide for documenting agent workflow and context handoffs.",
                "tags": ["ai-agents"],
                "evidence": "Workflow documentation guide checklist template automation context.",
                "source_kind": "post",
                "source_id": "post_005",
                "source_post_id": "post_005",
                "source_permalink": "https://reddit.com/r/Codex/comments/post_005",
                "subreddit": "Codex",
                "why_it_matters": "Makes agent operations easier to reuse.",
                "novelty": "new",
            }
        ),
    )

    themes = select_emerging_themes(insights=insights, scoring=scoring)

    assert themes[0].label == "Ai Agents"
    assert themes[0].support_count == 4
    assert len(themes[0].evidence_titles) == 3
    assert themes[0].evidence_titles.count("Agent Memory Patterns") == 1
    assert "Coding Agents" not in [theme.label for theme in themes]


def _build_post(*, post_id: str, subreddit: str, score: int, num_comments: int, title: str | None = None) -> Post:
    return Post.from_raw(
        {
            "id": post_id,
            "subreddit": subreddit,
            "title": title or f"{subreddit} thread {post_id}",
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


def _build_tool_insight(post: Post, *, title: str) -> Insight:
    return Insight.from_raw(
        {
            "category": "tools",
            "title": title,
            "summary": f"{title} is being used as an agentic coding tool in real workflows.",
            "tags": ["ai-agents", "tooling"],
            "evidence": f"Evidence from {post.id}",
            "source_kind": "post",
            "source_id": post.id,
            "source_post_id": post.id,
            "source_permalink": post.url,
            "subreddit": post.subreddit,
            "why_it_matters": f"{title} appears in hands-on discussions about practical agent-assisted coding.",
        }
    )


def _section_lines(content: str, start_heading: str, end_heading: str) -> str:
    return content.split(start_heading + "\n", maxsplit=1)[1].split("\n" + end_heading, maxsplit=1)[0]
