"""Normalized Reddit comment model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from reddit_digest.models.base import BaseModel
from reddit_digest.models.base import ModelError
from reddit_digest.models.base import optional_string
from reddit_digest.models.base import require_int
from reddit_digest.models.base import require_non_negative_int
from reddit_digest.models.base import require_string


@dataclass(frozen=True)
class Comment(BaseModel):
    id: str
    post_id: str
    parent_id: str
    subreddit: str
    author: str | None
    body: str
    score: int
    created_utc: int
    permalink: str

    @classmethod
    def from_raw(cls, payload: dict[str, Any]) -> "Comment":
        body = require_string(payload, "body")
        if body in {"[deleted]", "[removed]"}:
            raise ModelError("'body' must contain comment text")
        return cls(
            id=require_string(payload, "id"),
            post_id=require_string(payload, "post_id"),
            parent_id=require_string(payload, "parent_id"),
            subreddit=require_string(payload, "subreddit"),
            author=optional_string(payload, "author"),
            body=body,
            score=require_int(payload, "score"),
            created_utc=require_non_negative_int(payload, "created_utc"),
            permalink=require_string(payload, "permalink"),
        )

    def __post_init__(self) -> None:
        if not self.permalink.startswith("/r/"):
            raise ModelError("'permalink' must start with '/r/'")
