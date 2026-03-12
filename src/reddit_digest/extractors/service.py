"""Extraction orchestration and persistence."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json

from reddit_digest.extractors.approaches import APPROACH_PATTERNS
from reddit_digest.extractors.common import comment_source
from reddit_digest.extractors.common import match_patterns
from reddit_digest.extractors.common import post_source
from reddit_digest.extractors.guides import GUIDE_PATTERNS
from reddit_digest.extractors.testing_insights import TESTING_PATTERNS
from reddit_digest.extractors.tools import TOOL_PATTERNS
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
        source = post_source(post)
        extracted.extend(match_patterns(source, TOOL_PATTERNS))
        extracted.extend(match_patterns(source, APPROACH_PATTERNS))
        extracted.extend(match_patterns(source, GUIDE_PATTERNS))
        extracted.extend(match_patterns(source, TESTING_PATTERNS))

    for comment in comments:
        source = comment_source(comment)
        extracted.extend(match_patterns(source, TOOL_PATTERNS))
        extracted.extend(match_patterns(source, APPROACH_PATTERNS))
        extracted.extend(match_patterns(source, GUIDE_PATTERNS))
        extracted.extend(match_patterns(source, TESTING_PATTERNS))

    deduped: dict[tuple[str, str, str], Insight] = {}
    for insight in extracted:
        key = (insight.category, insight.title, insight.source_id)
        deduped[key] = insight

    return sorted(
        deduped.values(),
        key=lambda insight: (insight.category, insight.title, insight.source_id),
    )
