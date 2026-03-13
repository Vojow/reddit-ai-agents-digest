from __future__ import annotations

import pytest

from reddit_digest.models.base import ModelError
from reddit_digest.models.suggestion import Suggestion


def test_suggestion_from_raw_validates_category() -> None:
    assert Suggestion.from_raw(
        {
            "category": "content",
            "title": "Prompt stability follow-up",
            "rationale": "Track whether prompt reproducibility remains a recurring issue.",
        }
    ) == Suggestion(
        category="content",
        title="Prompt stability follow-up",
        rationale="Track whether prompt reproducibility remains a recurring issue.",
    )

    with pytest.raises(ModelError, match="must be 'content' or 'source'"):
        Suggestion.from_raw(
            {
                "category": "invalid",
                "title": "Bad",
                "rationale": "Bad",
            }
        )
