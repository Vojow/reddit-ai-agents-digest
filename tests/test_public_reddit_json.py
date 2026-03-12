from __future__ import annotations

from reddit_digest.collectors.reddit_comments import PublicRedditCommentSource
from reddit_digest.collectors.reddit_posts import PublicRedditPostSource
from reddit_digest.config import RuntimeConfig
from reddit_digest.models.post import Post


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.headers: dict[str, str] = {}

    def get(self, url, params=None, timeout=20):
        return FakeResponse(self.payload)


def runtime() -> RuntimeConfig:
    return RuntimeConfig(
        reddit_client_id=None,
        reddit_client_secret=None,
        reddit_user_agent="reddit-ai-agents-digest/0.1.0",
        openai_api_key=None,
        openai_model="gpt-5-mini",
        gcp_workload_identity_provider=None,
        gcp_service_account_email=None,
        google_service_account_json=None,
        google_sheets_spreadsheet_id=None,
    )


def test_public_post_source_parses_listing() -> None:
    payload = {
        "data": {
            "children": [
                {
                    "kind": "t3",
                    "data": {
                        "id": "post_001",
                        "subreddit": "Codex",
                        "title": "Codex workflow",
                        "author": "builder",
                        "score": 11,
                        "num_comments": 4,
                        "created_utc": 1773315600,
                        "url": "https://reddit.com/r/Codex/comments/post_001",
                        "permalink": "/r/Codex/comments/post_001/codex_workflow/",
                        "selftext": "Useful workflow details.",
                    },
                }
            ]
        }
    }

    source = PublicRedditPostSource(runtime(), session=FakeSession(payload))
    posts = source.fetch_posts("Codex", "new", 10)

    assert posts[0]["id"] == "post_001"
    assert posts[0]["subreddit"] == "Codex"


def test_public_comment_source_flattens_nested_replies(sample_posts_payload: list[dict[str, object]]) -> None:
    payload = [
        {"data": {"children": []}},
        {
            "data": {
                "children": [
                    {
                        "kind": "t1",
                        "data": {
                            "id": "comment_001",
                            "parent_id": "t3_post_001",
                            "author": "commenter",
                            "body": "Top-level comment",
                            "score": 5,
                            "created_utc": 1773316500,
                            "permalink": "/r/Codex/comments/post_001/comment_001/",
                            "replies": {
                                "data": {
                                    "children": [
                                        {
                                            "kind": "t1",
                                            "data": {
                                                "id": "comment_002",
                                                "parent_id": "t1_comment_001",
                                                "author": "replying_user",
                                                "body": "Nested reply",
                                                "score": 3,
                                                "created_utc": 1773316600,
                                                "permalink": "/r/Codex/comments/post_001/comment_002/",
                                            },
                                        }
                                    ]
                                }
                            },
                        },
                    }
                ]
            }
        },
    ]

    source = PublicRedditCommentSource(runtime(), session=FakeSession(payload))
    post = Post.from_raw(sample_posts_payload[0])
    comments = source.fetch_comments(post, 10)

    assert [comment["id"] for comment in comments] == ["comment_001", "comment_002"]


def test_public_post_source_ignores_non_post_listing_items() -> None:
    payload = {"data": {"children": [{"kind": "more", "data": {}}]}}

    source = PublicRedditPostSource(runtime(), session=FakeSession(payload))

    assert source.fetch_posts("Codex", "new", 10) == []


def test_public_post_source_handles_malformed_listing() -> None:
    source = PublicRedditPostSource(runtime(), session=FakeSession(["not-a-dict"]))

    assert source.fetch_posts("Codex", "new", 10) == []


def test_public_comment_source_handles_malformed_listing(sample_posts_payload: list[dict[str, object]]) -> None:
    source = PublicRedditCommentSource(runtime(), session=FakeSession([{}, "not-a-dict"]))
    post = Post.from_raw(sample_posts_payload[0])

    assert source.fetch_comments(post, 10) == []


def test_public_comment_source_handles_malformed_listing_data(sample_posts_payload: list[dict[str, object]]) -> None:
    source = PublicRedditCommentSource(runtime(), session=FakeSession([{}, {"data": ["not-a-dict"]}]))
    post = Post.from_raw(sample_posts_payload[0])

    assert source.fetch_comments(post, 10) == []
