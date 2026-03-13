from __future__ import annotations

from reddit_digest.models.base import ModelError
from reddit_digest.models.post import Post


def test_post_from_raw_normalizes_strings_and_rejects_negative_counts() -> None:
    post = Post.from_raw(
        {
            "id": "post-1",
            "subreddit": " Codex ",
            "title": " Codex workflow ",
            "author": " tester ",
            "score": 12,
            "num_comments": 3,
            "created_utc": 1_741_780_800,
            "url": " https://reddit.com/r/Codex/comments/post-1 ",
            "permalink": " /r/Codex/comments/post-1 ",
            "selftext": " details ",
        }
    )

    assert post.subreddit == "Codex"
    assert post.title == "Codex workflow"
    assert post.author == "tester"
    assert post.url == "https://reddit.com/r/Codex/comments/post-1"
    assert post.selftext == "details"

    try:
        Post.from_raw(
            {
                "id": "post-2",
                "subreddit": "Codex",
                "title": "Bad row",
                "author": "tester",
                "score": 1,
                "num_comments": -1,
                "created_utc": 1_741_780_800,
                "url": "https://reddit.com/r/Codex/comments/post-2",
                "permalink": "/r/Codex/comments/post-2",
                "selftext": "",
            }
        )
    except ModelError as exc:
        assert "must be greater than or equal to 0" in str(exc)
    else:
        raise AssertionError("Expected negative num_comments to fail validation")
