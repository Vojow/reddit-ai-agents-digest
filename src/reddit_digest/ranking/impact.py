"""Deterministic post and insight scoring."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC
from datetime import datetime

from reddit_digest.config import ScoringConfig
from reddit_digest.models.insight import Insight
from reddit_digest.models.post import Post


RELEVANCE_TERMS = ("agent", "codex", "claude", "workflow", "test", "eval", "prompt", "automation")
ACTIONABLE_TERMS = ("guide", "how", "workflow", "template", "snapshot", "checklist", "refactor", "context")


@dataclass(frozen=True)
class ScoreBreakdown:
    components: dict[str, float]
    total: float


def score_post(post: Post, scoring: ScoringConfig, *, run_at: datetime, lookback_hours: int) -> ScoreBreakdown:
    text = " ".join(part for part in [post.title, post.selftext or ""] if part).lower()
    components = {
        "relevance": _term_density(text, RELEVANCE_TERMS),
        "comment_depth": min(post.num_comments / 20, 1.0),
        "actionability": _term_density(text, ACTIONABLE_TERMS),
        "novelty": 0.5,
        "engagement": min(max(post.score, 0) / 100, 1.0),
        "recency": _recency_score(post.created_utc, run_at=run_at, lookback_hours=lookback_hours),
    }
    return ScoreBreakdown(components=components, total=_weighted_total(components, scoring))


def score_insight(insight: Insight, scoring: ScoringConfig) -> ScoreBreakdown:
    tags = set(insight.tags)
    configured_tags = set(scoring.tags)
    overlap = len(tags & configured_tags)
    actionability_signal = " ".join(
        part for part in [insight.summary, insight.why_it_matters or "", insight.evidence] if part
    ).lower()
    components = {
        "relevance": min(overlap / max(len(tags), 1), 1.0),
        "comment_depth": 1.0 if insight.source_kind == "comment" else 0.6,
        "actionability": _term_density(actionability_signal, ACTIONABLE_TERMS),
        "novelty": _novelty_component(insight.novelty),
        "engagement": min(len(insight.evidence.split()) / 25, 1.0),
        "recency": 1.0,
    }
    return ScoreBreakdown(components=components, total=_weighted_total(components, scoring))


def _term_density(text: str, terms: tuple[str, ...]) -> float:
    matches = sum(1 for term in terms if term in text)
    return min(matches / 3, 1.0)


def _recency_score(created_utc: int, *, run_at: datetime, lookback_hours: int) -> float:
    age_hours = max((run_at - datetime.fromtimestamp(created_utc, tz=UTC)).total_seconds() / 3600, 0)
    if lookback_hours <= 0:
        return 0.0
    return max(0.0, 1 - (age_hours / lookback_hours))


def _novelty_component(novelty: str | None) -> float:
    if novelty == "new":
        return 1.0
    if novelty == "ongoing":
        return 0.25
    return 0.5


def _weighted_total(components: dict[str, float], scoring: ScoringConfig) -> float:
    total = 0.0
    for name, weight in scoring.weights.items():
        total += components.get(name, 0.0) * weight
    return round(total * 10, 2)
