from __future__ import annotations

from reddit_digest.models.base import ModelError
from reddit_digest.models.comment import Comment


def test_comment_from_raw_normalizes_strings_and_rejects_invalid_body() -> None:
    comment = Comment.from_raw(
        {
            "id": "comment-1",
            "post_id": "post-1",
            "parent_id": "t3_post-1",
            "subreddit": " Codex ",
            "author": " commenter ",
            "body": " Deterministic prompting helps ",
            "score": 5,
            "created_utc": 1_741_780_900,
            "permalink": " /r/Codex/comments/post-1/comment-1 ",
        }
    )

    assert comment.subreddit == "Codex"
    assert comment.author == "commenter"
    assert comment.body == "Deterministic prompting helps"
    assert comment.permalink == "/r/Codex/comments/post-1/comment-1"

    try:
        Comment.from_raw(
            {
                "id": "comment-2",
                "post_id": "post-1",
                "parent_id": "t3_post-1",
                "subreddit": "Codex",
                "author": "commenter",
                "body": "",
                "score": 1,
                "created_utc": 1_741_780_900,
                "permalink": "/r/Codex/comments/post-1/comment-2",
            }
        )
    except ModelError as exc:
        assert "must be a non-empty string" in str(exc)
    else:
        raise AssertionError("Expected empty comment body to fail validation")
