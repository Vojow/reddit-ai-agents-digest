"""Markdown digest rendering."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from reddit_digest.config import ScoringConfig
from reddit_digest.models.insight import Insight
from reddit_digest.ranking.impact import score_insight
from reddit_digest.ranking.threads import RankedPost
from reddit_digest.ranking.threads import ThreadSelection


@dataclass(frozen=True)
class MarkdownDigestResult:
    daily_path: Path
    latest_path: Path
    content: str


def render_markdown_digest(
    *,
    run_date: str,
    insights: tuple[Insight, ...],
    scoring: ScoringConfig,
    thread_selection: ThreadSelection,
    reports_root: Path,
    watch_next: tuple[str, ...] = (),
) -> MarkdownDigestResult:
    scored_insights = sorted(
        [(insight, score_insight(insight, scoring)) for insight in insights],
        key=lambda item: (item[0].category, -item[1].total, item[0].title, item[0].source_id),
    )

    lines = [f"# Daily Reddit Digest — {run_date}", ""]
    lines.extend(_render_executive_summary(thread_selection.ranked_posts, scored_insights))
    lines.extend(_render_insight_section("Top Tools Mentioned", "tools", scored_insights))
    lines.extend(_render_insight_section("Top Approaches / Workflows", "approaches", scored_insights))
    lines.extend(_render_insight_section("Top Guides / Resources", "guides", scored_insights))
    lines.extend(_render_insight_section("Testing and Quality Insights", "testing", scored_insights))
    lines.extend(_render_notable_threads(thread_selection.notable_threads, scored_insights))
    lines.extend(_render_emerging_themes(scored_insights))
    watch_next_lines = _render_watch_next(watch_next=watch_next, scored_insights=scored_insights)
    if watch_next_lines:
        lines.extend(watch_next_lines)

    content = "\n".join(lines).strip() + "\n"
    daily_path = reports_root / "daily" / f"{run_date}.md"
    latest_path = reports_root / "latest.md"
    daily_path.parent.mkdir(parents=True, exist_ok=True)
    daily_path.write_text(content)
    latest_path.write_text(content)
    return MarkdownDigestResult(daily_path=daily_path, latest_path=latest_path, content=content)


def _render_executive_summary(ranked_posts: tuple[RankedPost, ...], scored_insights: list[tuple[Insight, object]]) -> list[str]:
    top_post = ranked_posts[0].post if ranked_posts else None
    top_insights = [insight.title for insight, _ in scored_insights[:2]]
    bullets = [
        "## Executive Summary",
        *(f"- Top thread: {top_post.title}" for _ in [0] if top_post is not None),
        *(f"- Leading insights: {', '.join(top_insights)}" for _ in [0] if top_insights),
        f"- Total posts analyzed: {len(ranked_posts)}",
        f"- Total insights extracted: {len(scored_insights)}",
        "",
    ]
    return bullets


def _render_insight_section(
    heading: str,
    category: str,
    scored_insights: list[tuple[Insight, object]],
) -> list[str]:
    lines = [f"## {heading}"]
    matching = [(insight, breakdown) for insight, breakdown in scored_insights if insight.category == category][:3]
    if not matching:
        lines.append("- No significant items today.")
        lines.append("")
        return lines

    for insight, breakdown in matching:
        lines.append(f"- {insight.title}")
        lines.append(f"  - Why it matters: {insight.why_it_matters or insight.summary}")
        lines.append(f"  - Source threads: 1")
        lines.append(f"  - Impact score: {breakdown.total:.2f}")
    lines.append("")
    return lines


def _render_notable_threads(
    ranked_posts: tuple[RankedPost, ...],
    scored_insights: list[tuple[Insight, object]],
) -> list[str]:
    lines = ["## Notable Threads"]
    if not ranked_posts:
        lines.append("- No notable threads today.")
        lines.append("")
        return lines

    for ranked_post in ranked_posts:
        post = ranked_post.post
        related = [insight for insight, _ in scored_insights if insight.source_post_id == post.id]
        why_it_matters = related[0].why_it_matters if related and related[0].why_it_matters else "Relevant discussion for AI-assisted development workflows."
        tags = sorted({tag for insight in related for tag in insight.tags})
        summary = (post.selftext or post.title).strip()
        lines.append(f"- [{post.title}]({post.url})")
        lines.append(f"  - Subreddit: r/{post.subreddit}")
        lines.append(f"  - Summary: {summary}")
        lines.append(f"  - Why it matters: {why_it_matters}")
        lines.append(f"  - Impact score: {ranked_post.breakdown.total:.2f}")
        lines.append(f"  - Extracted tags: {', '.join(tags) if tags else 'none'}")
    lines.append("")
    return lines


def _render_emerging_themes(scored_insights: list[tuple[Insight, object]]) -> list[str]:
    lines = ["## Emerging Themes"]
    tags = Counter(tag for insight, _ in scored_insights for tag in insight.tags)
    if not tags:
        lines.append("- No emerging themes today.")
        lines.append("")
        return lines

    for tag, _count in tags.most_common(3):
        evidence = ", ".join(insight.title for insight, _ in scored_insights if tag in insight.tags)
        lines.append(f"- {tag.replace('-', ' ').title()}")
        lines.append(f"  - Evidence: {evidence}")
    lines.append("")
    return lines


def _render_watch_next(
    *,
    watch_next: tuple[str, ...],
    scored_insights: list[tuple[Insight, object]],
) -> list[str]:
    suggestions = list(watch_next)
    if not suggestions:
        suggestions = [insight.title for insight, _ in scored_insights if insight.novelty == "new"][:3]
    if not suggestions:
        return []

    lines = ["## Watch Next"]
    for item in suggestions:
        lines.append(f"- {item}")
    lines.append("")
    return lines
