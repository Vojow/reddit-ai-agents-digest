"""Reddit post collection and persistence."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from pathlib import Path
import json
from typing import Any
from typing import Protocol

import praw
import requests

from reddit_digest.config import RuntimeConfig
from reddit_digest.config import SubredditConfig
from reddit_digest.models.base import ModelError
from reddit_digest.models.post import Post


class RedditPostSource(Protocol):
    """Interface for fetching raw subreddit posts."""

    def fetch_posts(self, subreddit: str, sort_mode: str, limit: int) -> list[dict[str, Any]]:
        """Return raw post payloads for a subreddit."""


@dataclass(frozen=True)
class CollectedPosts:
    run_date: str
    raw_path: Path
    processed_path: Path
    posts: tuple[Post, ...]


class PrawRedditPostSource:
    """Live Reddit source backed by PRAW."""

    def __init__(self, runtime: RuntimeConfig) -> None:
        self._reddit = praw.Reddit(
            client_id=runtime.reddit_client_id,
            client_secret=runtime.reddit_client_secret,
            user_agent=runtime.reddit_user_agent,
        )
        self._reddit.read_only = True

    def fetch_posts(self, subreddit: str, sort_mode: str, limit: int) -> list[dict[str, Any]]:
        subreddit_ref = self._reddit.subreddit(subreddit)
        listing = self._listing_for_mode(subreddit_ref, sort_mode, limit)
        return [self._serialize_submission(submission) for submission in listing]

    def _listing_for_mode(self, subreddit_ref: Any, sort_mode: str, limit: int) -> Iterable[Any]:
        if sort_mode == "new":
            return subreddit_ref.new(limit=limit)
        if sort_mode == "top":
            return subreddit_ref.top(time_filter="day", limit=limit)
        raise ValueError(f"Unsupported sort mode: {sort_mode}")

    def _serialize_submission(self, submission: Any) -> dict[str, Any]:
        return {
            "id": submission.id,
            "subreddit": submission.subreddit.display_name,
            "title": submission.title,
            "author": None if submission.author is None else str(submission.author),
            "score": submission.score,
            "num_comments": submission.num_comments,
            "created_utc": int(submission.created_utc),
            "url": submission.url,
            "permalink": submission.permalink,
            "selftext": submission.selftext,
        }


class PublicRedditPostSource:
    """Live Reddit source backed by public JSON endpoints."""

    def __init__(self, runtime: RuntimeConfig, *, session: requests.Session | None = None) -> None:
        self._session = session or requests.Session()
        self._session.headers.update(
            {
                "User-Agent": runtime.reddit_user_agent or "reddit-ai-agents-digest/0.1.0",
                "Accept": "application/json",
            }
        )

    def fetch_posts(self, subreddit: str, sort_mode: str, limit: int) -> list[dict[str, Any]]:
        url = f"https://www.reddit.com/r/{subreddit}/{sort_mode}.json"
        params: dict[str, Any] = {"limit": limit, "raw_json": 1}
        if sort_mode == "top":
            params["t"] = "day"
        response = self._session.get(url, params=params, timeout=20)
        response.raise_for_status()
        payload = response.json()
        return self._parse_listing(payload)

    def _parse_listing(self, payload: Any) -> list[dict[str, Any]]:
        if not isinstance(payload, dict):
            return []
        data = payload.get("data", {})
        if not isinstance(data, dict):
            return []
        children = data.get("children", [])
        if not isinstance(children, list):
            return []
        items: list[dict[str, Any]] = []
        for child in children:
            if not isinstance(child, dict):
                continue
            if child.get("kind") != "t3":
                continue
            raw = child.get("data", {})
            if not isinstance(raw, dict):
                continue
            items.append(
                {
                    "id": raw.get("id"),
                    "subreddit": raw.get("subreddit"),
                    "title": raw.get("title"),
                    "author": raw.get("author"),
                    "score": raw.get("score", 0),
                    "num_comments": raw.get("num_comments", 0),
                    "created_utc": int(raw.get("created_utc", 0)),
                    "url": raw.get("url") or f"https://www.reddit.com{raw.get('permalink', '')}",
                    "permalink": raw.get("permalink"),
                    "selftext": raw.get("selftext"),
                }
            )
        return items


class PostCollector:
    """Collect, normalize, and persist subreddit posts."""

    def __init__(self, source: RedditPostSource, raw_root: Path, processed_root: Path) -> None:
        self._source = source
        self._raw_root = raw_root
        self._processed_root = processed_root

    def collect(self, config: SubredditConfig, *, run_at: datetime | None = None) -> CollectedPosts:
        current_time = run_at or datetime.now(tz=UTC)
        run_date = current_time.date().isoformat()
        minimum_created_utc = int(current_time.timestamp()) - (config.fetch.lookback_hours * 3600)
        raw_payload = self._fetch_and_filter(config, minimum_created_utc=minimum_created_utc)
        posts = self._normalize_posts(raw_payload)
        raw_path = self._write_json(self._raw_root / "posts" / f"{run_date}.json", raw_payload)
        processed_path = self._write_json(
            self._processed_root / "posts" / f"{run_date}.json",
            [post.to_dict() for post in posts],
        )
        return CollectedPosts(
            run_date=run_date,
            raw_path=raw_path,
            processed_path=processed_path,
            posts=tuple(posts),
        )

    def _fetch_and_filter(self, config: SubredditConfig, *, minimum_created_utc: int) -> dict[str, Any]:
        by_subreddit: dict[str, Any] = {}
        for subreddit in config.enabled_subreddits:
            deduped: dict[str, dict[str, Any]] = {}
            raw_by_mode: dict[str, list[dict[str, Any]]] = {}
            for sort_mode in config.fetch.sort_modes:
                raw_items = self._source.fetch_posts(
                    subreddit=subreddit,
                    sort_mode=sort_mode,
                    limit=config.fetch.max_posts_per_subreddit,
                )
                raw_by_mode[sort_mode] = raw_items
                for item in raw_items:
                    try:
                        post = Post.from_raw(item)
                    except ModelError:
                        continue
                    if post.created_utc < minimum_created_utc:
                        continue
                    if post.score < config.fetch.min_post_score:
                        continue
                    if post.num_comments < config.fetch.min_comments:
                        continue
                    deduped[post.id] = {**post.to_dict(), "subreddit": subreddit}

            selected = sorted(
                deduped.values(),
                key=lambda item: (-item["created_utc"], -item["score"], item["id"]),
            )[: config.fetch.max_posts_per_subreddit]
            by_subreddit[subreddit] = {
                "sort_modes": raw_by_mode,
                "selected": selected,
            }

        return by_subreddit

    def _normalize_posts(self, raw_payload: dict[str, Any]) -> list[Post]:
        posts: list[Post] = []
        for subreddit_payload in raw_payload.values():
            for item in subreddit_payload["selected"]:
                posts.append(Post.from_raw(item))
        return posts

    def _write_json(self, path: Path, payload: Any) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True))
        return path
