"""Typed digest item model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from reddit_digest.models.base import BaseModel
from reddit_digest.models.base import ModelError
from reddit_digest.models.base import optional_string
from reddit_digest.models.base import require_string
from reddit_digest.models.base import require_string_list


@dataclass(frozen=True)
class DigestItem(BaseModel):
    category: str
    title: str
    subreddit: str
    permalink: str
    why_it_matters: str
    impact_score: float
    tags: tuple[str, ...]
    source_post_ids: tuple[str, ...]
    evidence: str | None = None

    @classmethod
    def from_raw(cls, payload: dict[str, Any]) -> "DigestItem":
        impact_score = payload.get("impact_score")
        if not isinstance(impact_score, (int, float)):
            raise ModelError("'impact_score' must be numeric")

        item = cls(
            category=require_string(payload, "category"),
            title=require_string(payload, "title"),
            subreddit=require_string(payload, "subreddit"),
            permalink=require_string(payload, "permalink"),
            why_it_matters=require_string(payload, "why_it_matters"),
            impact_score=float(impact_score),
            tags=require_string_list(payload, "tags"),
            source_post_ids=require_string_list(payload, "source_post_ids"),
            evidence=optional_string(payload, "evidence"),
        )

        if item.impact_score < 0:
            raise ModelError("'impact_score' must be greater than or equal to 0")
        return item

    def __post_init__(self) -> None:
        if not self.permalink.startswith("http"):
            raise ModelError("'permalink' must be an absolute URL")
