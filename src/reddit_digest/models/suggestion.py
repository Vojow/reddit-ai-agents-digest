"""Typed LLM suggestion model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from reddit_digest.models.base import BaseModel
from reddit_digest.models.base import ModelError
from reddit_digest.models.base import require_string


@dataclass(frozen=True)
class Suggestion(BaseModel):
    category: str
    title: str
    rationale: str

    @classmethod
    def from_raw(cls, payload: dict[str, Any]) -> "Suggestion":
        suggestion = cls(
            category=require_string(payload, "category"),
            title=require_string(payload, "title"),
            rationale=require_string(payload, "rationale"),
        )
        if suggestion.category not in {"content", "source"}:
            raise ModelError("'category' must be 'content' or 'source'")
        return suggestion
