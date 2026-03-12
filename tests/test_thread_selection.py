from __future__ import annotations

from datetime import UTC
from datetime import datetime
from pathlib import Path

from reddit_digest.config import load_scoring_config
from reddit_digest.models.post import Post
from reddit_digest.ranking.threads import select_threads


RUN_AT = datetime(2026, 3, 12, 12, 0, tzinfo=UTC)


def build_post(
    *,
    post_id: str,
    subreddit: str,
    title: str,
    score: int,
    num_comments: int,
    created_utc: int = 1_741_780_800,
) -> Post:
    return Post.from_raw(
        {
            "id": post_id,
            "subreddit": subreddit,
            "title": title,
            "author": "builder",
            "score": score,
            "num_comments": num_comments,
            "created_utc": created_utc,
            "url": f"https://reddit.com/{post_id}",
            "permalink": f"/r/{subreddit}/comments/{post_id}",
            "selftext": "workflow guide eval automation test prompt",
        }
    )


def test_select_threads_enforces_minimal_subreddit_diversity() -> None:
    scoring = load_scoring_config(Path.cwd() / "config" / "scoring.yaml")
    posts = (
        build_post(post_id="a1", subreddit="Codex", title="Codex 1", score=95, num_comments=28),
        build_post(post_id="a2", subreddit="Codex", title="Codex 2", score=90, num_comments=24),
        build_post(post_id="a3", subreddit="Codex", title="Codex 3", score=88, num_comments=22),
        build_post(post_id="a4", subreddit="Codex", title="Codex 4", score=86, num_comments=20),
        build_post(post_id="a5", subreddit="Codex", title="Codex 5", score=84, num_comments=18),
        build_post(post_id="b1", subreddit="ClaudeCode", title="ClaudeCode 1", score=70, num_comments=16),
    )

    selection = select_threads(
        posts,
        scoring=scoring,
        enabled_subreddits=("Codex", "ClaudeCode"),
        run_at=RUN_AT,
        lookback_hours=24,
    )

    assert len(selection.notable_threads) == 5
    assert {item.post.subreddit for item in selection.notable_threads} == {"Codex", "ClaudeCode"}
    assert selection.notable_threads[-1].post.id == "b1"


def test_select_threads_uses_only_enabled_subreddits() -> None:
    scoring = load_scoring_config(Path.cwd() / "config" / "scoring.yaml")
    posts = (
        build_post(post_id="a1", subreddit="Codex", title="Codex 1", score=95, num_comments=28),
        build_post(post_id="b1", subreddit="ClaudeCode", title="ClaudeCode 1", score=90, num_comments=24),
        build_post(post_id="c1", subreddit="Vibecoding", title="Vibecoding 1", score=92, num_comments=26),
    )

    selection = select_threads(
        posts,
        scoring=scoring,
        enabled_subreddits=("Codex", "Vibecoding"),
        run_at=RUN_AT,
        lookback_hours=24,
    )

    assert tuple(item.post.subreddit for item in selection.ranked_posts) == ("Codex", "Vibecoding")
    assert tuple(group.subreddit for group in selection.by_subreddit) == ("Codex", "Vibecoding")


def test_select_threads_keeps_single_subreddit_when_no_alternative_exists() -> None:
    scoring = load_scoring_config(Path.cwd() / "config" / "scoring.yaml")
    posts = tuple(
        build_post(post_id=f"a{index}", subreddit="Codex", title=f"Codex {index}", score=100 - index, num_comments=20 - index)
        for index in range(1, 5)
    )

    selection = select_threads(
        posts,
        scoring=scoring,
        enabled_subreddits=("Codex", "ClaudeCode"),
        run_at=RUN_AT,
        lookback_hours=24,
    )

    assert len(selection.notable_threads) == 4
    assert {item.post.subreddit for item in selection.notable_threads} == {"Codex"}


def test_select_threads_is_deterministic_for_ties() -> None:
    scoring = load_scoring_config(Path.cwd() / "config" / "scoring.yaml")
    posts = (
        build_post(post_id="b2", subreddit="ClaudeCode", title="same", score=80, num_comments=12),
        build_post(post_id="a1", subreddit="Codex", title="same", score=80, num_comments=12),
        build_post(post_id="a2", subreddit="Codex", title="same", score=80, num_comments=12),
    )

    first = select_threads(
        posts,
        scoring=scoring,
        enabled_subreddits=("Codex", "ClaudeCode"),
        run_at=RUN_AT,
        lookback_hours=24,
    )
    second = select_threads(
        posts,
        scoring=scoring,
        enabled_subreddits=("Codex", "ClaudeCode"),
        run_at=RUN_AT,
        lookback_hours=24,
    )

    assert tuple(item.post.id for item in first.ranked_posts) == tuple(item.post.id for item in second.ranked_posts)
    assert tuple(item.post.id for item in first.notable_threads) == tuple(item.post.id for item in second.notable_threads)


def test_select_threads_limits_per_subreddit_rankings() -> None:
    scoring = load_scoring_config(Path.cwd() / "config" / "scoring.yaml")
    posts = tuple(
        build_post(post_id=f"a{index}", subreddit="Codex", title=f"Codex {index}", score=120 - index, num_comments=25 - index)
        for index in range(1, 6)
    ) + (
        build_post(post_id="b1", subreddit="ClaudeCode", title="ClaudeCode 1", score=90, num_comments=18),
    )

    selection = select_threads(
        posts,
        scoring=scoring,
        enabled_subreddits=("Codex", "ClaudeCode"),
        run_at=RUN_AT,
        lookback_hours=24,
    )

    codex_group = next(group for group in selection.by_subreddit if group.subreddit == "Codex")
    assert len(codex_group.posts) == 3
