"""Run state persistence."""

from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from pathlib import Path
import json

from reddit_digest.models.openai_usage import OpenAIUsageSummary


@dataclass(frozen=True)
class RunState:
    run_date: str
    completed_at: str
    raw_posts_path: str
    raw_comments_path: str
    insights_path: str
    report_path: str
    sheets_exported: bool
    teams_published: bool
    teams_error: str | None
    openai_usage: OpenAIUsageSummary


def write_run_state(state_root: Path, state: RunState) -> None:
    state_root.mkdir(parents=True, exist_ok=True)
    dated_path = state_root / f"{state.run_date}.json"
    latest_path = state_root / "latest.json"
    payload = json.dumps(asdict(state), indent=2, sort_keys=True)
    dated_path.write_text(payload)
    latest_path.write_text(payload)
