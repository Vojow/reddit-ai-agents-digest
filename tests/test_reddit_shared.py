from __future__ import annotations

from pathlib import Path
import json

from reddit_digest.collectors.shared import PublicRedditTransport
from reddit_digest.collectors.shared import write_json_artifact
from reddit_digest.config import RuntimeConfig


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
        self.calls: list[tuple[str, dict[str, object], int]] = []

    def get(self, url, params=None, timeout=20):
        self.calls.append((url, params or {}, timeout))
        return FakeResponse(self.payload)


def runtime() -> RuntimeConfig:
    return RuntimeConfig(
        reddit_client_id=None,
        reddit_client_secret=None,
        reddit_user_agent="digest-test-agent",
        openai_api_key=None,
        openai_model="gpt-5-mini",
        gcp_workload_identity_provider=None,
        gcp_service_account_email=None,
        google_service_account_json=None,
        google_sheets_spreadsheet_id=None,
    )


def test_public_reddit_transport_applies_shared_request_policy() -> None:
    session = FakeSession({"ok": True})
    transport = PublicRedditTransport(runtime(), session=session)

    payload = transport.get_json("/r/Codex/new.json", params={"limit": 5, "raw_json": 1})

    assert payload == {"ok": True}
    assert session.headers["User-Agent"] == "digest-test-agent"
    assert session.headers["Accept"] == "application/json"
    assert session.calls == [("https://www.reddit.com/r/Codex/new.json", {"limit": 5, "raw_json": 1}, 20)]


def test_write_json_artifact_persists_sorted_payload(tmp_path: Path) -> None:
    path = write_json_artifact(tmp_path / "processed" / "posts" / "2026-03-12.json", {"b": 2, "a": 1})

    assert path.exists()
    assert json.loads(path.read_text()) == {"a": 1, "b": 2}
