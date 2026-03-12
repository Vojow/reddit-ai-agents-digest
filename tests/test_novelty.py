from __future__ import annotations

from pathlib import Path
import json

from reddit_digest.models.insight import Insight
from reddit_digest.ranking.novelty import apply_novelty


def build_insight(**overrides: str) -> Insight:
    base = {
        "category": "tools",
        "title": "Codex",
        "summary": "Codex is being used as an agentic coding tool in real workflows.",
        "tags": ["ai-agents", "tooling"],
        "evidence": "Codex shows up in the thread and the comments.",
        "source_kind": "post",
        "source_id": "post_001",
        "source_post_id": "post_001",
        "source_permalink": "https://reddit.com/r/Codex/comments/post_001",
        "subreddit": "Codex",
        "why_it_matters": "It appears in practical coding discussions.",
    }
    return Insight.from_raw({**base, **overrides})


def test_apply_novelty_marks_all_items_new_without_prior_run(tmp_path: Path) -> None:
    result = apply_novelty(tmp_path, run_date="2026-03-12", insights=(build_insight(),))

    assert [insight.novelty for insight in result.insights] == ["new"]
    assert json.loads(result.path.read_text())[0]["novelty"] == "new"


def test_apply_novelty_marks_matching_items_ongoing(tmp_path: Path) -> None:
    prior_path = tmp_path / "insights" / "2026-03-11.json"
    prior_path.parent.mkdir(parents=True, exist_ok=True)
    prior_path.write_text(json.dumps([build_insight().to_dict()], indent=2, sort_keys=True))

    current_items = (
        build_insight(source_id="post_002", source_post_id="post_002"),
        build_insight(
            category="testing",
            title="Snapshot markdown tests",
            summary="Snapshot-style output tests are being used to catch formatting regressions.",
            tags=["ai-testing", "reliability"],
            evidence="Snapshot markdown tests catch regressions.",
            source_kind="comment",
            source_id="comment_001",
            source_post_id="post_001",
            source_permalink="https://reddit.com/r/Codex/comments/post_001/comment_001/",
            why_it_matters="Deterministic output remains enforceable.",
        ),
    )

    result = apply_novelty(tmp_path, run_date="2026-03-12", insights=current_items)

    novelty_by_title = {insight.title: insight.novelty for insight in result.insights}
    assert novelty_by_title["Codex"] == "ongoing"
    assert novelty_by_title["Snapshot markdown tests"] == "new"
