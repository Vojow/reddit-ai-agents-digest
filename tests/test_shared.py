from __future__ import annotations

from reddit_digest.collectors.shared import PublicRedditTransport
from reddit_digest.config import RuntimeConfig


def test_public_reddit_transport_falls_back_to_default_user_agent() -> None:
    session = type("FakeSession", (), {"headers": {}, "get": lambda self, *_args, **_kwargs: None})()
    PublicRedditTransport(
        RuntimeConfig(
            reddit_client_id=None,
            reddit_client_secret=None,
            reddit_user_agent=None,
            openai_api_key=None,
            openai_model="gpt-5-mini",
            teams_webhook_url=None,
            gcp_workload_identity_provider=None,
            gcp_service_account_email=None,
            google_service_account_json=None,
            google_sheets_spreadsheet_id=None,
        ),
        session=session,
    )
    assert session.headers["User-Agent"] == "reddit-ai-agents-digest/0.1.0"
