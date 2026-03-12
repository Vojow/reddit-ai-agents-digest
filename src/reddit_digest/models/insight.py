"""Typed extracted insight model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from reddit_digest.models.base import BaseModel
from reddit_digest.models.base import ModelError
from reddit_digest.models.base import optional_string
from reddit_digest.models.base import require_string
from reddit_digest.models.base import require_string_list


@dataclass(frozen=True)
class Insight(BaseModel):
    category: str
    title: str
    summary: str
    tags: tuple[str, ...]
    evidence: str
    source_kind: str
    source_id: str
    source_permalink: str
    source_post_id: str
    subreddit: str
    novelty: str | None = None
    why_it_matters: str | None = None

    @classmethod
    def from_raw(cls, payload: dict[str, Any]) -> "Insight":
        item = cls(
            category=require_string(payload, "category"),
            title=require_string(payload, "title"),
            summary=require_string(payload, "summary"),
            tags=require_string_list(payload, "tags"),
            evidence=require_string(payload, "evidence"),
            source_kind=require_string(payload, "source_kind"),
            source_id=require_string(payload, "source_id"),
            source_permalink=require_string(payload, "source_permalink"),
            source_post_id=require_string(payload, "source_post_id"),
            subreddit=require_string(payload, "subreddit"),
            novelty=optional_string(payload, "novelty"),
            why_it_matters=optional_string(payload, "why_it_matters"),
        )
        if item.source_kind not in {"post", "comment"}:
            raise ModelError("'source_kind' must be 'post' or 'comment'")
        if not item.source_permalink:
            raise ModelError("'source_permalink' must be populated")
        return item
