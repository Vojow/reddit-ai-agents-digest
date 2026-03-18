from __future__ import annotations

from datetime import UTC
from datetime import datetime

from reddit_digest.config import ScoringConfig
from reddit_digest.ranking.impact import _novelty_component
from reddit_digest.ranking.impact import _recency_score
from reddit_digest.ranking.impact import _term_density
from reddit_digest.ranking.impact import _weighted_total


def test_scoring_private_helpers_cover_edge_cases() -> None:
    scoring = ScoringConfig(
        weights={
            "relevance": 0.3,
            "comment_depth": 0.2,
            "actionability": 0.2,
            "novelty": 0.1,
            "engagement": 0.1,
            "recency": 0.1,
        },
        tags=("ai-agents", "tooling", "prompting"),
    )
    assert _term_density("agent workflow prompt automation", ("agent", "workflow", "prompt")) == 1.0
    assert _recency_score(1_741_780_800, run_at=datetime(2025, 3, 12, tzinfo=UTC), lookback_hours=0) == 0.0
    assert _novelty_component("ongoing") == 0.25
    assert _novelty_component(None) == 0.5
    assert _weighted_total({"relevance": 1.0, "comment_depth": 0.5}, scoring) == 4.0
