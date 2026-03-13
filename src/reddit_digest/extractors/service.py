"""Extraction orchestration and persistence."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json

from reddit_digest.extractors.common import comment_source
from reddit_digest.extractors.common import match_patterns
from reddit_digest.extractors.common import post_source
from reddit_digest.extractors.common import TextSource
from reddit_digest.extractors.registry import RULESETS
from reddit_digest.models.comment import Comment
from reddit_digest.models.insight import Insight
from reddit_digest.models.post import Post


@dataclass(frozen=True)
class ExtractedInsights:
    path: Path
    insights: tuple[Insight, ...]


def extract_insights(
    posts: tuple[Post, ...],
    comments: tuple[Comment, ...],
    *,
    processed_root: Path,
    run_date: str,
) -> ExtractedInsights:
    insights = _extract(posts, comments)
    path = processed_root / "insights" / f"{run_date}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([item.to_dict() for item in insights], indent=2, sort_keys=True))
    return ExtractedInsights(path=path, insights=tuple(insights))


def _extract(posts: tuple[Post, ...], comments: tuple[Comment, ...]) -> list[Insight]:
    extracted: list[Insight] = []
    for post in posts:
        extracted.extend(_match_rulesets(post_source(post)))

    for comment in comments:
        extracted.extend(_match_rulesets(comment_source(comment)))

    deduped: dict[tuple[str, str, str], Insight] = {}
    for insight in extracted:
        key = (insight.category, insight.title, insight.source_id)
        deduped[key] = insight

    return sorted(
        deduped.values(),
        key=lambda insight: (insight.category, insight.title, insight.source_id),
    )


def _match_rulesets(source: TextSource) -> list[Insight]:
    extracted: list[Insight] = []
    for ruleset in RULESETS:
        extracted.extend(match_patterns(source, ruleset.patterns))
    return extracted
