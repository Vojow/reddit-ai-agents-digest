from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from gspread.exceptions import WorksheetNotFound

from reddit_digest.config import RuntimeConfig
from reddit_digest.config import load_scoring_config
from reddit_digest.extractors.service import extract_insights
from reddit_digest.models.comment import Comment
from reddit_digest.models.post import Post
from reddit_digest.outputs.digest import build_digest_artifact
from reddit_digest.outputs.google_sheets import DAILY_DIGEST_TAB
from reddit_digest.outputs.google_sheets import GoogleSheetsExporter
from reddit_digest.outputs.google_sheets import INSIGHTS_TAB
from reddit_digest.outputs.google_sheets import RAW_POSTS_TAB
from reddit_digest.outputs.google_sheets import load_google_sheets_credentials
from reddit_digest.ranking.novelty import apply_novelty
from reddit_digest.ranking.threads import select_threads


@dataclass
class FakeWorksheet:
    title: str
    rows: list[list[Any]]

    def get_all_records(self) -> list[dict[str, Any]]:
        if not self.rows:
            return []
        header = self.rows[0]
        return [dict(zip(header, row, strict=False)) for row in self.rows[1:]]

    def clear(self) -> None:
        self.rows = []

    def update(self, values: list[list[Any]]) -> None:
        self.rows = values


class FakeWorkbook:
    def __init__(self) -> None:
        self.worksheets: dict[str, FakeWorksheet] = {}

    def worksheet(self, title: str) -> FakeWorksheet:
        if title not in self.worksheets:
            raise WorksheetNotFound(title)
        return self.worksheets[title]

    def add_worksheet(self, title: str, rows: int, cols: int) -> FakeWorksheet:
        worksheet = FakeWorksheet(title=title, rows=[])
        self.worksheets[title] = worksheet
        return worksheet


class FakeClient:
    def __init__(self, workbook: FakeWorkbook) -> None:
        self._workbook = workbook
        self.opened_key: str | None = None

    def open_by_key(self, key: str) -> FakeWorkbook:
        self.opened_key = key
        return self._workbook


class ErroringWorkbook(FakeWorkbook):
    def __init__(self, error: Exception) -> None:
        super().__init__()
        self.error = error
        self.add_calls: list[tuple[str, int, int]] = []

    def worksheet(self, title: str) -> FakeWorksheet:
        raise self.error

    def add_worksheet(self, title: str, rows: int, cols: int) -> FakeWorksheet:
        self.add_calls.append((title, rows, cols))
        return super().add_worksheet(title, rows, cols)


def build_inputs(sample_posts_payload: list[dict[str, object]], sample_comments_payload: list[dict[str, object]], tmp_path: Path):
    posts = tuple(Post.from_raw(item) for item in sample_posts_payload)
    comments = tuple(Comment.from_raw(item) for item in sample_comments_payload)
    scoring = load_scoring_config(Path.cwd() / "config" / "scoring.yaml")
    extracted = extract_insights(posts, comments, processed_root=tmp_path / "processed", run_date="2026-03-12")
    novelty = apply_novelty(tmp_path / "processed", run_date="2026-03-12", insights=extracted.insights)
    thread_selection = select_threads(
        posts,
        scoring=scoring,
        enabled_subreddits=("Codex", "ClaudeCode", "Vibecoding"),
        run_at=datetime(2026, 3, 12, 12, 0, tzinfo=UTC),
        lookback_hours=24,
    )
    digest = build_digest_artifact(
        run_date="2026-03-12",
        insights=novelty.insights,
        scoring=scoring,
        thread_selection=thread_selection,
        watch_next=("Monitor prompt-state snapshots",),
    )
    return posts, novelty.insights, scoring, digest


def build_runtime(**overrides: object) -> RuntimeConfig:
    values: dict[str, object] = {
        "reddit_client_id": None,
        "reddit_client_secret": None,
        "reddit_user_agent": "reddit-ai-agents-digest/0.1.0",
        "openai_api_key": None,
        "openai_model": "gpt-5-mini",
        "gcp_workload_identity_provider": None,
        "gcp_service_account_email": None,
        "google_service_account_json": None,
        "google_sheets_spreadsheet_id": "sheet-123",
    }
    values.update(overrides)
    return RuntimeConfig(**values)


def test_google_sheets_export_creates_expected_tabs(
    sample_posts_payload: list[dict[str, object]],
    sample_comments_payload: list[dict[str, object]],
    tmp_path: Path,
) -> None:
    workbook = FakeWorkbook()
    exporter = GoogleSheetsExporter(workbook)
    posts, insights, scoring, digest = build_inputs(sample_posts_payload, sample_comments_payload, tmp_path)

    counts = exporter.export(
        run_date="2026-03-12",
        posts=posts,
        insights=insights,
        digest=digest,
        scoring=scoring,
        lookback_hours=24,
        run_at=datetime(2026, 3, 12, 12, 0, tzinfo=UTC),
    )

    assert counts.raw_posts == len(posts)
    assert counts.insights == len(insights)
    assert set(workbook.worksheets) == {RAW_POSTS_TAB, INSIGHTS_TAB, DAILY_DIGEST_TAB}
    assert workbook.worksheet(RAW_POSTS_TAB).get_all_records()[0]["run_date"] == "2026-03-12"
    assert workbook.worksheet(DAILY_DIGEST_TAB).get_all_records()[0]["watch_next"] == "Monitor prompt-state snapshots"


def test_google_sheets_export_is_idempotent_for_same_run_date(
    sample_posts_payload: list[dict[str, object]],
    sample_comments_payload: list[dict[str, object]],
    tmp_path: Path,
) -> None:
    workbook = FakeWorkbook()
    exporter = GoogleSheetsExporter(workbook)
    posts, insights, scoring, digest = build_inputs(sample_posts_payload, sample_comments_payload, tmp_path)

    exporter.export(
        run_date="2026-03-12",
        posts=posts,
        insights=insights,
        digest=digest,
        scoring=scoring,
        lookback_hours=24,
        run_at=datetime(2026, 3, 12, 12, 0, tzinfo=UTC),
    )
    exporter.export(
        run_date="2026-03-12",
        posts=posts,
        insights=insights,
        digest=digest,
        scoring=scoring,
        lookback_hours=24,
        run_at=datetime(2026, 3, 12, 12, 0, tzinfo=UTC),
    )

    raw_rows = workbook.worksheet(RAW_POSTS_TAB).get_all_records()
    insight_rows = workbook.worksheet(INSIGHTS_TAB).get_all_records()
    digest_rows = workbook.worksheet(DAILY_DIGEST_TAB).get_all_records()

    assert len(raw_rows) == len(posts)
    assert len(insight_rows) == len(insights)
    assert len(digest_rows) == 1


def test_google_sheets_daily_digest_uses_structured_top_thread_not_collection_order(tmp_path: Path) -> None:
    scoring = load_scoring_config(Path.cwd() / "config" / "scoring.yaml")
    posts = (
        Post.from_raw(
            {
                "id": "low",
                "subreddit": "Codex",
                "title": "Lower ranked first in collection order",
                "author": "tester",
                "score": 8,
                "num_comments": 2,
                "created_utc": 1_773_316_800,
                "url": "https://reddit.com/r/Codex/comments/low",
                "permalink": "/r/Codex/comments/low",
                "selftext": "basic update",
            }
        ),
        Post.from_raw(
            {
                "id": "high",
                "subreddit": "ClaudeCode",
                "title": "Higher ranked thread should win",
                "author": "tester",
                "score": 120,
                "num_comments": 30,
                "created_utc": 1_773_316_810,
                "url": "https://reddit.com/r/ClaudeCode/comments/high",
                "permalink": "/r/ClaudeCode/comments/high",
                "selftext": "workflow deterministic testing prompt",
            }
        ),
    )
    insights = ()
    thread_selection = select_threads(
        posts,
        scoring=scoring,
        enabled_subreddits=("Codex", "ClaudeCode"),
        run_at=datetime(2026, 3, 12, 12, 0, tzinfo=UTC),
        lookback_hours=24,
    )
    digest = build_digest_artifact(
        run_date="2026-03-12",
        insights=insights,
        scoring=scoring,
        thread_selection=thread_selection,
        watch_next=("Monitor ranked thread selection",),
    )
    workbook = FakeWorkbook()

    GoogleSheetsExporter(workbook).export(
        run_date="2026-03-12",
        posts=posts,
        insights=insights,
        digest=digest,
        scoring=scoring,
        lookback_hours=24,
        run_at=datetime(2026, 3, 12, 12, 0, tzinfo=UTC),
    )

    row = workbook.worksheet(DAILY_DIGEST_TAB).get_all_records()[0]
    assert row["top_thread_title"] == "Higher ranked thread should win"
    assert row["watch_next"] == "Monitor ranked thread selection"


def test_load_google_sheets_credentials_prefers_service_account_json(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = build_runtime(google_service_account_json='{"type":"service_account","client_email":"bot@example.com"}')
    captured: dict[str, object] = {}

    def fake_from_service_account_info(info: dict[str, object], scopes: list[str]) -> str:
        captured["info"] = info
        captured["scopes"] = scopes
        return "json-creds"

    monkeypatch.setattr(
        "reddit_digest.outputs.google_sheets.ServiceAccountCredentials.from_service_account_info",
        fake_from_service_account_info,
    )

    credentials = load_google_sheets_credentials(runtime)

    assert credentials == "json-creds"
    assert captured["info"] == {"type": "service_account", "client_email": "bot@example.com"}
    assert captured["scopes"] == ["https://www.googleapis.com/auth/spreadsheets"]


def test_load_google_sheets_credentials_uses_application_default_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = build_runtime()

    monkeypatch.setattr(
        "reddit_digest.outputs.google_sheets.google.auth.default",
        lambda *, scopes: ("adc-creds", "project-id"),
    )

    credentials = load_google_sheets_credentials(runtime)

    assert credentials == "adc-creds"


def test_load_google_sheets_credentials_rejects_invalid_json() -> None:
    runtime = build_runtime(google_service_account_json="{not-json}")

    with pytest.raises(ValueError, match="GOOGLE_SERVICE_ACCOUNT_JSON"):
        load_google_sheets_credentials(runtime)


def test_google_sheets_exporter_from_runtime_uses_loaded_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    workbook = FakeWorkbook()
    client = FakeClient(workbook)

    monkeypatch.setattr(
        "reddit_digest.outputs.google_sheets.load_google_sheets_credentials",
        lambda runtime: "loaded-creds",
    )
    monkeypatch.setattr(
        "reddit_digest.outputs.google_sheets.gspread.authorize",
        lambda credentials: client if credentials == "loaded-creds" else None,
    )

    exporter = GoogleSheetsExporter.from_runtime(build_runtime())

    assert isinstance(exporter, GoogleSheetsExporter)
    assert client.opened_key == "sheet-123"


def test_google_sheets_exporter_from_runtime_supports_wif_backed_adc(monkeypatch: pytest.MonkeyPatch) -> None:
    workbook = FakeWorkbook()
    client = FakeClient(workbook)
    captured: dict[str, object] = {}
    runtime = build_runtime(
        gcp_workload_identity_provider="projects/123/locations/global/workloadIdentityPools/pool/providers/provider",
        gcp_service_account_email="digest-bot@example.iam.gserviceaccount.com",
    )

    def fake_default(*, scopes: list[str]) -> tuple[str, str]:
        captured["scopes"] = scopes
        return "adc-creds", "project-id"

    monkeypatch.setattr("reddit_digest.outputs.google_sheets.google.auth.default", fake_default)
    monkeypatch.setattr(
        "reddit_digest.outputs.google_sheets.gspread.authorize",
        lambda credentials: client if credentials == "adc-creds" else None,
    )

    exporter = GoogleSheetsExporter.from_runtime(runtime)

    assert isinstance(exporter, GoogleSheetsExporter)
    assert client.opened_key == "sheet-123"
    assert captured["scopes"] == ["https://www.googleapis.com/auth/spreadsheets"]


def test_ensure_worksheet_creates_missing_tab() -> None:
    workbook = FakeWorkbook()
    exporter = GoogleSheetsExporter(workbook)

    worksheet = exporter._ensure_worksheet("Missing_Tab", cols=4)

    assert worksheet.title == "Missing_Tab"
    assert workbook.worksheet("Missing_Tab") is worksheet


def test_ensure_worksheet_propagates_non_missing_errors() -> None:
    workbook = ErroringWorkbook(RuntimeError("permission denied"))
    exporter = GoogleSheetsExporter(workbook)

    with pytest.raises(RuntimeError, match="permission denied"):
        exporter._ensure_worksheet("Insights", cols=4)

    assert workbook.add_calls == []
