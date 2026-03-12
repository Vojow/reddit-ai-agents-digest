"""Novelty comparison against the most recent prior run."""

from __future__ import annotations

from dataclasses import replace
from dataclasses import dataclass
from pathlib import Path
import json
import re

from reddit_digest.models.insight import Insight


@dataclass(frozen=True)
class NoveltyResult:
    path: Path
    insights: tuple[Insight, ...]


def apply_novelty(processed_root: Path, *, run_date: str, insights: tuple[Insight, ...]) -> NoveltyResult:
    previous_insights = _load_previous_insights(processed_root, run_date=run_date)
    previous_keys = {_match_key(insight) for insight in previous_insights}

    updated = tuple(
        replace(
            insight,
            novelty="ongoing" if _match_key(insight) in previous_keys else "new",
        )
        for insight in insights
    )

    path = processed_root / "insights" / f"{run_date}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([insight.to_dict() for insight in updated], indent=2, sort_keys=True))
    return NoveltyResult(path=path, insights=updated)


def _load_previous_insights(processed_root: Path, *, run_date: str) -> tuple[Insight, ...]:
    insight_dir = processed_root / "insights"
    if not insight_dir.exists():
        return ()

    prior_paths = sorted(path for path in insight_dir.glob("*.json") if path.stem < run_date)
    if not prior_paths:
        return ()

    payload = json.loads(prior_paths[-1].read_text())
    return tuple(Insight.from_raw(item) for item in payload)


def _match_key(insight: Insight) -> tuple[str, str, str]:
    return (
        insight.category,
        _normalize_text(insight.title),
        _normalize_text(insight.summary),
    )


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())
