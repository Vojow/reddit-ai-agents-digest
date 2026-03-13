from __future__ import annotations

import pytest

from reddit_digest.models.base import ModelError
from reddit_digest.models.insight import Insight


def test_insight_from_raw_rejects_invalid_source_kind() -> None:
    with pytest.raises(ModelError, match="must be 'post' or 'comment'"):
        Insight.from_raw(
            {
                "category": "tools",
                "title": "Codex",
                "summary": "summary",
                "tags": ["ai-agents"],
                "evidence": "evidence",
                "source_kind": "thread",
                "source_id": "x",
                "source_post_id": "x",
                "source_permalink": "https://reddit.com/r/Codex/comments/x",
                "subreddit": "Codex",
            }
        )
