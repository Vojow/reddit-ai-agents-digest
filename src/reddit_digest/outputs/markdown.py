"""Markdown digest rendering."""

from __future__ import annotations

from collections.abc import Mapping
from collections import Counter
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from reddit_digest.config import ScoringConfig
from reddit_digest.models.insight import Insight
from reddit_digest.ranking.impact import score_insight
from reddit_digest.ranking.threads import ThreadSelection


@dataclass(frozen=True)
class MarkdownDigestResult:
    daily_path: Path
    latest_path: Path
    content: str


@dataclass(frozen=True)
class RankedTopic:
    topic_key: str
    title: str
    executive_summary: str
    relevance_for_user: str
    source_title: str
    source_url: str
    source_subreddit: str
    impact_score: float
    support_count: int


def render_markdown_digest(
    *,
    run_date: str,
    insights: tuple[Insight, ...],
    scoring: ScoringConfig,
    thread_selection: ThreadSelection,
    reports_root: Path,
    watch_next: tuple[str, ...] = (),
    topics: tuple[RankedTopic, ...] | None = None,
    topic_rewrites: Mapping[str, tuple[str, str]] | None = None,
    variant_suffix: str = "",
) -> MarkdownDigestResult:
    scored_insights = sorted(
        [(insight, score_insight(insight, scoring)) for insight in insights],
        key=lambda item: (item[0].category, -item[1].total, item[0].title, item[0].source_id),
    )
    selected_topics = topics or select_digest_topics(
        insights=insights,
        scoring=scoring,
        thread_selection=thread_selection,
    )

    lines = [f"# Daily Reddit Digest — {run_date}", ""]
    lines.extend(_render_executive_summary(thread_selection, selected_topics))
    lines.extend(_render_picked_topics(selected_topics, topic_rewrites=topic_rewrites))
    lines.extend(_render_emerging_themes(scored_insights))
    watch_next_lines = _render_watch_next(watch_next=watch_next, scored_insights=scored_insights)
    if watch_next_lines:
        lines.extend(watch_next_lines)

    content = "\n".join(lines).strip() + "\n"
    daily_path, latest_path = _build_output_paths(reports_root=reports_root, run_date=run_date, variant_suffix=variant_suffix)
    daily_path.parent.mkdir(parents=True, exist_ok=True)
    daily_path.write_text(content)
    latest_path.write_text(content)
    return MarkdownDigestResult(daily_path=daily_path, latest_path=latest_path, content=content)


def select_digest_topics(
    *,
    insights: tuple[Insight, ...],
    scoring: ScoringConfig,
    thread_selection: ThreadSelection,
    limit: int = 6,
) -> tuple[RankedTopic, ...]:
    scored_insights = sorted(
        [(insight, score_insight(insight, scoring)) for insight in insights],
        key=lambda item: (item[0].category, -item[1].total, item[0].title, item[0].source_id),
    )
    grouped: dict[tuple[str, str], list[tuple[Insight, object]]] = defaultdict(list)
    for insight, breakdown in scored_insights:
        grouped[(insight.category, insight.title.casefold())].append((insight, breakdown))

    post_lookup = {ranked.post.id: ranked.post for ranked in thread_selection.ranked_posts}
    topics: list[RankedTopic] = []
    for entries in grouped.values():
        best_insight, best_breakdown = sorted(
            entries,
            key=lambda item: (-item[1].total, item[0].title, item[0].source_id),
        )[0]
        source_post = post_lookup.get(best_insight.source_post_id)
        source_title = source_post.title if source_post is not None else best_insight.title
        source_url = source_post.url if source_post is not None else best_insight.source_permalink
        source_subreddit = source_post.subreddit if source_post is not None else best_insight.subreddit
        support_count = len({insight.source_post_id for insight, _ in entries})
        topics.append(
            RankedTopic(
                topic_key="",
                title=best_insight.title,
                executive_summary=best_insight.summary,
                relevance_for_user=best_insight.why_it_matters or best_insight.summary,
                source_title=source_title,
                source_url=source_url,
                source_subreddit=source_subreddit,
                impact_score=best_breakdown.total,
                support_count=support_count,
            )
        )

    ordered_topics = sorted(topics, key=lambda item: (-item.impact_score, item.title, item.source_url))[:limit]
    return tuple(
        RankedTopic(
            topic_key=f"topic_{index}",
            title=topic.title,
            executive_summary=topic.executive_summary,
            relevance_for_user=topic.relevance_for_user,
            source_title=topic.source_title,
            source_url=topic.source_url,
            source_subreddit=topic.source_subreddit,
            impact_score=topic.impact_score,
            support_count=topic.support_count,
        )
        for index, topic in enumerate(ordered_topics, start=1)
    )


def _render_executive_summary(thread_selection: ThreadSelection, topics: tuple[RankedTopic, ...]) -> list[str]:
    represented = tuple(dict.fromkeys(item.post.subreddit for item in thread_selection.ranked_posts))
    top_topic = topics[0] if topics else None
    bullets = [
        "## Executive Summary",
        *(f"- Picked {len(topics)} topics from {len(represented)} subreddit(s): {', '.join(f'r/{name}' for name in represented)}" for _ in [0] if represented),
        *(f"- Highest-signal topic: {top_topic.title}" for _ in [0] if top_topic is not None),
        f"- Total posts analyzed: {len(thread_selection.ranked_posts)}",
        "",
    ]
    return bullets


def _render_picked_topics(
    topics: tuple[RankedTopic, ...],
    *,
    topic_rewrites: Mapping[str, tuple[str, str]] | None = None,
) -> list[str]:
    lines = ["## Picked Topics"]
    if not topics:
        lines.append("- No picked topics today.")
        lines.append("")
        return lines

    for index, topic in enumerate(topics, start=1):
        executive_summary = topic.executive_summary
        relevance_for_user = topic.relevance_for_user
        if topic_rewrites and topic.topic_key in topic_rewrites:
            executive_summary, relevance_for_user = topic_rewrites[topic.topic_key]
        lines.append(f"### {index}. {topic.title}")
        lines.append(f"- Executive summary: {executive_summary}")
        lines.append(f"- Relevance for you: {relevance_for_user}")
        lines.append(f"- Original post: [{topic.source_title}]({topic.source_url})")
        lines.append(f"- Source subreddit: r/{topic.source_subreddit}")
        lines.append(f"- Supporting threads: {topic.support_count}")
        lines.append(f"- Impact score: {topic.impact_score:.2f}")
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


def _build_output_paths(*, reports_root: Path, run_date: str, variant_suffix: str) -> tuple[Path, Path]:
    suffix = f".{variant_suffix}" if variant_suffix else ""
    daily_path = reports_root / "daily" / f"{run_date}{suffix}.md"
    latest_path = reports_root / f"latest{suffix}.md"
    return daily_path, latest_path
