"""Markdown digest rendering."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from reddit_digest.config import ScoringConfig
from reddit_digest.outputs.digest import build_digest_artifact
from reddit_digest.outputs.digest import DigestArtifact
from reddit_digest.outputs.digest import RankedTopic
from reddit_digest.outputs.digest import select_digest_topics
from reddit_digest.models.insight import Insight
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
    warnings: tuple[str, ...] = (),
    topics: tuple[RankedTopic, ...] | None = None,
    digest: DigestArtifact | None = None,
    topic_rewrites: Mapping[str, tuple[str, str]] | None = None,
    variant_suffix: str = "",
) -> MarkdownDigestResult:
    artifact = digest or build_digest_artifact(
        run_date=run_date,
        insights=insights,
        scoring=scoring,
        thread_selection=thread_selection,
        watch_next=watch_next,
        topics=topics,
    )

    lines = [f"# Daily Reddit Digest — {run_date}", ""]
    if warnings:
        lines.extend(_render_warnings(warnings))
    lines.extend(_render_executive_summary(artifact))
    lines.extend(_render_picked_topics(artifact.topics, topic_rewrites=topic_rewrites))
    lines.extend(_render_emerging_themes(artifact))
    watch_next_lines = _render_watch_next(artifact)
    if watch_next_lines:
        lines.extend(watch_next_lines)

    content = "\n".join(lines).strip() + "\n"
    daily_path, latest_path = _build_output_paths(reports_root=reports_root, run_date=run_date, variant_suffix=variant_suffix)
    daily_path.parent.mkdir(parents=True, exist_ok=True)
    daily_path.write_text(content)
    latest_path.write_text(content)
    return MarkdownDigestResult(daily_path=daily_path, latest_path=latest_path, content=content)


def _render_warnings(warnings: tuple[str, ...]) -> list[str]:
    lines = ["## Warnings"]
    for item in warnings:
        lines.append(f"- {item}")
    lines.append("")
    return lines


def _render_executive_summary(digest: DigestArtifact) -> list[str]:
    bullets = [
        "## Executive Summary",
        *(
            f"- Picked {len(digest.topics)} topics from {len(digest.represented_subreddits)} subreddit(s): "
            f"{', '.join(f'r/{name}' for name in digest.represented_subreddits)}"
            for _ in [0]
            if digest.represented_subreddits
        ),
        *(f"- Highest-signal topic: {digest.top_topic_title}" for _ in [0] if digest.top_topic_title is not None),
        f"- Total posts analyzed: {digest.total_posts}",
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


def _render_emerging_themes(digest: DigestArtifact) -> list[str]:
    lines = ["## Emerging Themes"]
    if not digest.emerging_themes:
        lines.append("- No emerging themes today.")
        lines.append("")
        return lines

    for theme in digest.emerging_themes:
        lines.append(f"- {theme.label}")
        lines.append(f"  - Evidence: {theme.evidence}")
    lines.append("")
    return lines


def _render_watch_next(digest: DigestArtifact) -> list[str]:
    if not digest.watch_next:
        return []

    lines = ["## Watch Next"]
    for item in digest.watch_next:
        lines.append(f"- {item}")
    lines.append("")
    return lines


def _build_output_paths(*, reports_root: Path, run_date: str, variant_suffix: str) -> tuple[Path, Path]:
    suffix = f".{variant_suffix}" if variant_suffix else ""
    daily_path = reports_root / "daily" / f"{run_date}{suffix}.md"
    latest_path = reports_root / f"latest{suffix}.md"
    return daily_path, latest_path
