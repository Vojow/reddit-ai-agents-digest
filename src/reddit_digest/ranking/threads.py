"""Ranked thread selection for digest rendering."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from reddit_digest.config import ScoringConfig
from reddit_digest.models.post import Post
from reddit_digest.ranking.impact import ScoreBreakdown
from reddit_digest.ranking.impact import score_post


@dataclass(frozen=True)
class RankedPost:
    post: Post
    breakdown: ScoreBreakdown


@dataclass(frozen=True)
class SubredditThreadRanking:
    subreddit: str
    posts: tuple[RankedPost, ...]


@dataclass(frozen=True)
class ThreadSelection:
    ranked_posts: tuple[RankedPost, ...]
    notable_threads: tuple[RankedPost, ...]
    by_subreddit: tuple[SubredditThreadRanking, ...]


def select_threads(
    posts: tuple[Post, ...],
    *,
    scoring: ScoringConfig,
    enabled_subreddits: tuple[str, ...],
    run_at: datetime,
    lookback_hours: int,
    global_limit: int = 5,
    per_subreddit_limit: int = 3,
) -> ThreadSelection:
    enabled = tuple(dict.fromkeys(enabled_subreddits))
    enabled_lookup = {subreddit.casefold(): subreddit for subreddit in enabled}
    ranked_posts = tuple(
        sorted(
            (
                RankedPost(
                    post=post,
                    breakdown=score_post(post, scoring, run_at=run_at, lookback_hours=lookback_hours),
                )
                for post in posts
                if post.subreddit.casefold() in enabled_lookup
            ),
            key=lambda item: (-item.breakdown.total, item.post.subreddit.lower(), item.post.id),
        )
    )

    by_subreddit = tuple(
        SubredditThreadRanking(
            subreddit=subreddit,
            posts=tuple(ranked for ranked in ranked_posts if ranked.post.subreddit.casefold() == subreddit.casefold())[
                :per_subreddit_limit
            ],
        )
        for subreddit in enabled
        if any(ranked.post.subreddit.casefold() == subreddit.casefold() for ranked in ranked_posts)
    )

    return ThreadSelection(
        ranked_posts=ranked_posts,
        notable_threads=_select_notable_threads(ranked_posts, limit=global_limit),
        by_subreddit=by_subreddit,
    )


def _select_notable_threads(ranked_posts: tuple[RankedPost, ...], *, limit: int) -> tuple[RankedPost, ...]:
    selected = list(ranked_posts[:limit])
    if len(selected) < 2:
        return tuple(selected)

    represented = {item.post.subreddit for item in selected}
    if len(represented) >= 2:
        return tuple(selected)

    replacement = next((item for item in ranked_posts[limit:] if item.post.subreddit not in represented), None)
    if replacement is None:
        return tuple(selected)

    selected[-1] = replacement
    return tuple(selected)
