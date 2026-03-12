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
import requests

from reddit_digest.config import RuntimeConfig
from reddit_digest.models.base import ModelError
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


class PublicRedditCommentSource:
    """Live Reddit comment source backed by public JSON endpoints."""

    def __init__(self, runtime: RuntimeConfig, *, session: requests.Session | None = None) -> None:
        self._session = session or requests.Session()
        self._session.headers.update(
            {
                "User-Agent": runtime.reddit_user_agent or "reddit-ai-agents-digest/0.1.0",
                "Accept": "application/json",
            }
        )

    def fetch_comments(self, post: Post, limit: int) -> list[dict[str, Any]]:
        url = f"https://www.reddit.com/comments/{post.id}.json"
        response = self._session.get(url, params={"limit": limit, "raw_json": 1}, timeout=20)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list) or len(payload) < 2:
            return []
        return self._flatten_comment_listing(payload[1], post=post)[:limit]

    def _flatten_comment_listing(self, listing: Any, *, post: Post) -> list[dict[str, Any]]:
        if not isinstance(listing, dict):
            return []
        listing_data = listing.get("data", {})
        if not isinstance(listing_data, dict):
            return []
        children = listing_data.get("children", [])
        if not isinstance(children, list):
            return []
        flattened: list[dict[str, Any]] = []
        for child in children:
            if not isinstance(child, dict):
                continue
            flattened.extend(self._flatten_comment_node(child, post=post))
        return flattened

    def _flatten_comment_node(self, node: Any, *, post: Post) -> list[dict[str, Any]]:
        if not isinstance(node, dict):
            return []
        if node.get("kind") != "t1":
            return []
        data = node.get("data", {})
        if not isinstance(data, dict):
            return []

        current = {
            "id": data.get("id"),
            "post_id": post.id,
            "parent_id": data.get("parent_id"),
            "subreddit": post.subreddit,
            "author": data.get("author"),
            "body": data.get("body"),
            "score": data.get("score", 0),
            "created_utc": int(data.get("created_utc", 0)),
            "permalink": data.get("permalink"),
        }

        children = [current]
        replies = data.get("replies")
        if isinstance(replies, dict):
            reply_data = replies.get("data", {})
            if not isinstance(reply_data, dict):
                return children
            reply_children = reply_data.get("children", [])
            if not isinstance(reply_children, list):
                return children
            for reply in reply_children:
                children.extend(self._flatten_comment_node(reply, post=post))
        return children


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
            try:
                normalized.append(Comment.from_raw(item))
            except ModelError:
                continue
            if len(normalized) >= max_comments_per_post:
                break
        return normalized

    def _write_json(self, path: Path, payload: Any) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True))
        return path
