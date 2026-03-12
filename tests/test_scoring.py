from __future__ import annotations

from datetime import UTC
from datetime import datetime
from pathlib import Path

from reddit_digest.config import load_scoring_config
from reddit_digest.extractors.service import extract_insights
from reddit_digest.models.comment import Comment
from reddit_digest.models.insight import Insight
from reddit_digest.models.post import Post
from reddit_digest.ranking.impact import score_insight
from reddit_digest.ranking.impact import score_post


CONFIG_PATH = Path.cwd() / "config" / "scoring.yaml"


def test_score_post_returns_deterministic_breakdown(sample_posts_payload: list[dict[str, object]]) -> None:
    post = Post.from_raw(sample_posts_payload[0])
    scoring = load_scoring_config(CONFIG_PATH)

    first = score_post(
        post,
        scoring,
        run_at=datetime(2026, 3, 12, 12, 0, tzinfo=UTC),
        lookback_hours=24,
    )
    second = score_post(
        post,
        scoring,
        run_at=datetime(2026, 3, 12, 12, 0, tzinfo=UTC),
        lookback_hours=24,
    )

    assert first == second
    assert set(first.components) == {"relevance", "comment_depth", "actionability", "novelty", "engagement", "recency"}
    assert first.total > 0


def test_score_insight_uses_config_weights(
    sample_posts_payload: list[dict[str, object]],
    sample_comments_payload: list[dict[str, object]],
    tmp_path,
) -> None:
    scoring = load_scoring_config(CONFIG_PATH)
    extraction = extract_insights(
        tuple(Post.from_raw(item) for item in sample_posts_payload),
        tuple(Comment.from_raw(item) for item in sample_comments_payload),
        processed_root=tmp_path,
        run_date="2026-03-12",
    )
    insight = next(item for item in extraction.insights if item.title == "Codex")

    breakdown = score_insight(insight, scoring)

    assert breakdown.components["relevance"] > 0
    assert breakdown.total > 0
    assert round(sum(scoring.weights.values()), 2) == 1.0


def test_ongoing_novelty_scores_lower_than_new(sample_posts_payload: list[dict[str, object]]) -> None:
    scoring = load_scoring_config(CONFIG_PATH)
    base_payload = {
        "category": "testing",
        "title": "Snapshot markdown tests",
        "summary": "Snapshot-style output tests are being used to catch regressions.",
        "tags": ["ai-testing", "reliability"],
        "evidence": "Snapshot markdown tests catch regressions.",
        "source_kind": "comment",
        "source_id": "comment_001",
        "source_post_id": "post_001",
        "source_permalink": "https://reddit.com/r/Codex/comments/post_001/comment_001/",
        "subreddit": "Codex",
        "why_it_matters": "Deterministic output becomes enforceable.",
    }
    new_item = Insight.from_raw({**base_payload, "novelty": "new"})
    ongoing_item = Insight.from_raw({**base_payload, "novelty": "ongoing"})

    assert score_insight(new_item, scoring).total > score_insight(ongoing_item, scoring).total
