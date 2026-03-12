"""Normalized Reddit post model."""

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
class Post(BaseModel):
    id: str
    subreddit: str
    title: str
    author: str | None
    score: int
    num_comments: int
    created_utc: int
    url: str
    permalink: str
    selftext: str | None

    @classmethod
    def from_raw(cls, payload: dict[str, Any]) -> "Post":
        created_utc = require_non_negative_int(payload, "created_utc")
        return cls(
            id=require_string(payload, "id"),
            subreddit=require_string(payload, "subreddit"),
            title=require_string(payload, "title"),
            author=optional_string(payload, "author"),
            score=require_int(payload, "score"),
            num_comments=require_non_negative_int(payload, "num_comments"),
            created_utc=created_utc,
            url=require_string(payload, "url"),
            permalink=require_string(payload, "permalink"),
            selftext=optional_string(payload, "selftext"),
        )

    def __post_init__(self) -> None:
        if not self.permalink.startswith("/r/"):
            raise ModelError("'permalink' must start with '/r/'")
