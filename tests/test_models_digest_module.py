from __future__ import annotations

from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

import pytest

from src.reddit_digest.models.digest import DigestItem


def test_models_digest_module_accepts_valid_payload() -> None:
    item = DigestItem.from_raw(
        {
            "category": "tools",
            "title": "Codex",
            "subreddit": "Codex",
            "permalink": "https://reddit.com/r/Codex/comments/post-1",
            "why_it_matters": "Useful for testing.",
            "impact_score": 1.0,
            "tags": ["ai-agents"],
            "source_post_ids": ["post-1"],
        }
    )

    assert item.title == "Codex"
    assert item.impact_score == 1.0


def test_models_digest_module_rejects_non_absolute_permalink() -> None:
    with pytest.raises(ValueError, match="absolute URL"):
        DigestItem.from_raw(
            {
                "category": "tools",
                "title": "Codex",
                "subreddit": "Codex",
                "permalink": "/r/Codex/comments/post-1",
                "why_it_matters": "Useful for testing.",
                "impact_score": 1.0,
                "tags": ["ai-agents"],
                "source_post_ids": ["post-1"],
            }
        )
