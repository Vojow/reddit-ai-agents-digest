"""Reddit comment collection and persistence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from pathlib import Path
import json
from typing import Any
from typing import Protocol

from praw.models import Submission

from reddit_digest.models.comment import Comment
from reddit_digest.models.post import Post


class RedditCommentSource(Protocol):
    """Interface for fetching raw comments for a post."""

    def fetch_comments(self, post: Post, limit: int) -> list[dict[str, Any]]:
        """Return raw comment payloads for a post."""


@dataclass(frozen=True)
class CollectedComments:
    run_date: str
    raw_path: Path
    processed_path: Path
    comments: tuple[Comment, ...]


class PrawRedditCommentSource:
    """Live Reddit comment source backed by PRAW submissions."""

    def __init__(self, submission_loader: callable[[str], Submission]) -> None:
        self._submission_loader = submission_loader

    def fetch_comments(self, post: Post, limit: int) -> list[dict[str, Any]]:
        submission = self._submission_loader(post.id)
        submission.comments.replace_more(limit=0)
        serialized: list[dict[str, Any]] = []
        for comment in submission.comments.list():
            serialized.append(
                {
                    "id": comment.id,
                    "post_id": post.id,
                    "parent_id": comment.parent_id,
                    "subreddit": post.subreddit,
                    "author": None if comment.author is None else str(comment.author),
                    "body": comment.body,
                    "score": comment.score,
                    "created_utc": int(comment.created_utc),
                    "permalink": comment.permalink,
                }
            )
            if len(serialized) >= limit:
                break
        return serialized


class CommentCollector:
    """Collect, normalize, and persist comments for shortlisted posts."""

    def __init__(self, source: RedditCommentSource, raw_root: Path, processed_root: Path) -> None:
        self._source = source
        self._raw_root = raw_root
        self._processed_root = processed_root

    def collect(
        self,
        posts: tuple[Post, ...],
        *,
        max_comments_per_post: int,
        run_at: datetime | None = None,
    ) -> CollectedComments:
        current_time = run_at or datetime.now(tz=UTC)
        run_date = current_time.date().isoformat()
        raw_payload: dict[str, list[dict[str, Any]]] = {}
        normalized_comments: list[Comment] = []

        for post in posts:
            raw_comments = self._source.fetch_comments(post, max_comments_per_post)
            raw_payload[post.id] = raw_comments
            normalized_comments.extend(
                self._normalize_comments(raw_comments, max_comments_per_post=max_comments_per_post)
            )

        raw_path = self._write_json(self._raw_root / "comments" / f"{run_date}.json", raw_payload)
        processed_path = self._write_json(
            self._processed_root / "comments" / f"{run_date}.json",
            [comment.to_dict() for comment in normalized_comments],
        )
        return CollectedComments(
            run_date=run_date,
            raw_path=raw_path,
            processed_path=processed_path,
            comments=tuple(normalized_comments),
        )

    def _normalize_comments(self, payloads: list[dict[str, Any]], *, max_comments_per_post: int) -> list[Comment]:
        normalized: list[Comment] = []
        for item in sorted(payloads, key=lambda payload: (payload.get("created_utc", 0), payload.get("id", ""))):
            body = item.get("body")
            if not isinstance(body, str) or not body.strip() or body.strip() in {"[deleted]", "[removed]"}:
                continue
            normalized.append(Comment.from_raw(item))
            if len(normalized) >= max_comments_per_post:
                break
        return normalized

    def _write_json(self, path: Path, payload: Any) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True))
        return path
