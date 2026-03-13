"""Structured digest artifact shared by downstream outputs."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import re

from reddit_digest.config import ScoringConfig
from reddit_digest.models.insight import Insight
from reddit_digest.ranking.impact import score_insight
from reddit_digest.ranking.impact import ScoreBreakdown
from reddit_digest.ranking.threads import ThreadSelection


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


@dataclass(frozen=True)
class DigestThread:
    title: str
    url: str
    subreddit: str
    impact_score: float


@dataclass(frozen=True)
class EmergingTheme:
    label: str
    evidence: str
    support_count: int
    total_impact: float
    evidence_titles: tuple[str, ...]


@dataclass(frozen=True)
class DigestArtifact:
    run_date: str
    total_posts: int
    total_insights: int
    represented_subreddits: tuple[str, ...]
    top_topic_title: str | None
    top_tool: str
    top_approach: str
    top_guide: str
    top_testing_insight: str
    topics: tuple[RankedTopic, ...]
    notable_threads: tuple[DigestThread, ...]
    emerging_themes: tuple[EmergingTheme, ...]
    watch_next: tuple[str, ...]

    @property
    def top_thread(self) -> DigestThread | None:
        return self.notable_threads[0] if self.notable_threads else None


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


def build_digest_artifact(
    *,
    run_date: str,
    insights: tuple[Insight, ...],
    scoring: ScoringConfig,
    thread_selection: ThreadSelection,
    watch_next: tuple[str, ...] = (),
    topics: tuple[RankedTopic, ...] | None = None,
) -> DigestArtifact:
    scored_insights = sorted(
        [(insight, score_insight(insight, scoring)) for insight in insights],
        key=lambda item: (item[0].category, -item[1].total, item[0].title, item[0].source_id),
    )
    selected_topics = topics or select_digest_topics(
        insights=insights,
        scoring=scoring,
        thread_selection=thread_selection,
    )
    represented = tuple(dict.fromkeys(item.post.subreddit for item in thread_selection.ranked_posts))

    top_by_category = {category: "" for category in ("tools", "approaches", "guides", "testing")}
    for insight, _breakdown in scored_insights:
        if not top_by_category.get(insight.category):
            top_by_category[insight.category] = insight.title

    emerging_themes = select_emerging_themes_from_scored(scored_insights)
    resolved_watch_next = select_watch_next_items(
        watch_next=watch_next,
        insights=tuple(insight for insight, _ in scored_insights),
    )

    notable_threads = tuple(
        DigestThread(
            title=ranked.post.title,
            url=ranked.post.url,
            subreddit=ranked.post.subreddit,
            impact_score=ranked.breakdown.total,
        )
        for ranked in thread_selection.notable_threads
    )

    return DigestArtifact(
        run_date=run_date,
        total_posts=len(thread_selection.ranked_posts),
        total_insights=len(insights),
        represented_subreddits=represented,
        top_topic_title=selected_topics[0].title if selected_topics else None,
        top_tool=top_by_category["tools"],
        top_approach=top_by_category["approaches"],
        top_guide=top_by_category["guides"],
        top_testing_insight=top_by_category["testing"],
        topics=selected_topics,
        notable_threads=notable_threads,
        emerging_themes=emerging_themes,
        watch_next=resolved_watch_next,
    )


def select_watch_next_items(*, watch_next: tuple[str, ...], insights: tuple[Insight, ...]) -> tuple[str, ...]:
    if watch_next:
        return watch_next
    return tuple(insight.title for insight in insights if insight.novelty == "new")[:3]


def select_emerging_themes(
    *,
    insights: tuple[Insight, ...],
    scoring: ScoringConfig,
    limit: int = 3,
) -> tuple[EmergingTheme, ...]:
    scored_insights = [
        (insight, score_insight(insight, scoring))
        for insight in insights
    ]
    return select_emerging_themes_from_scored(scored_insights, limit=limit)


def select_emerging_themes_from_scored(
    scored_insights: list[tuple[Insight, ScoreBreakdown]],
    *,
    limit: int = 3,
) -> tuple[EmergingTheme, ...]:
    theme_entries: dict[str, dict[str, tuple[float, str]]] = defaultdict(dict)
    for insight, breakdown in scored_insights:
        normalized_title = _normalize_theme_title(insight.title)
        display_title = _clean_theme_title(insight.title)
        for tag in {_canonicalize_theme_tag(tag) for tag in insight.tags}:
            existing = theme_entries[tag].get(normalized_title)
            if existing is None:
                theme_entries[tag][normalized_title] = (breakdown.total, display_title)
                continue

            best_score = max(existing[0], breakdown.total)
            best_title = min(existing[1], display_title, key=lambda item: item.casefold())
            theme_entries[tag][normalized_title] = (best_score, best_title)

    themes: list[EmergingTheme] = []
    for tag, entries in theme_entries.items():
        ordered_titles = sorted(
            entries.values(),
            key=lambda item: (-item[0], item[1]),
        )
        evidence_titles = tuple(title for _score, title in ordered_titles[:3])
        themes.append(
            EmergingTheme(
                label=tag.replace("-", " ").title(),
                evidence=", ".join(evidence_titles),
                support_count=len(entries),
                total_impact=sum(score for score, _title in entries.values()),
                evidence_titles=evidence_titles,
            )
        )

    ordered_themes = sorted(
        themes,
        key=lambda item: (-item.support_count, -item.total_impact, item.label.casefold()),
    )
    return tuple(ordered_themes[:limit])


def _canonicalize_theme_tag(tag: str) -> str:
    if tag == "coding-agents":
        return "ai-agents"
    return tag


def _normalize_theme_title(title: str) -> str:
    return re.sub(r"\s+", " ", title.strip().casefold())


def _clean_theme_title(title: str) -> str:
    return re.sub(r"\s+", " ", title.strip())
