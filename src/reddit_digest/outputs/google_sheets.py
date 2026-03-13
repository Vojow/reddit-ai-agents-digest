"""Google Sheets export with per-run idempotency."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
import json
import google.auth
import logging
from typing import Any
from typing import Protocol

import gspread
from gspread.exceptions import WorksheetNotFound
from google.auth.credentials import Credentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials

from reddit_digest.config import RuntimeConfig
from reddit_digest.config import ScoringConfig
from reddit_digest.models.insight import Insight
from reddit_digest.models.post import Post
from reddit_digest.outputs.digest import DigestArtifact
from reddit_digest.ranking.impact import score_insight
from reddit_digest.ranking.impact import score_post


LOGGER = logging.getLogger(__name__)

RAW_POSTS_TAB = "Raw_Posts"
INSIGHTS_TAB = "Insights"
DAILY_DIGEST_TAB = "Daily_Digest"
GOOGLE_SHEETS_SCOPES = ("https://www.googleapis.com/auth/spreadsheets",)


class WorksheetLike(Protocol):
    title: str

    def get_all_records(self) -> list[dict[str, Any]]:
        ...

    def get_all_values(self) -> list[list[Any]]:
        ...

    def update(self, range_name: str, values: list[list[Any]]) -> None:
        ...

    def append_rows(self, values: list[list[Any]]) -> None:
        ...

    def delete_rows(self, start_index: int, end_index: int | None = None) -> None:
        ...


class WorkbookLike(Protocol):
    def worksheet(self, title: str) -> WorksheetLike:
        ...

    def add_worksheet(self, title: str, rows: int, cols: int) -> WorksheetLike:
        ...


@dataclass(frozen=True)
class ExportCounts:
    raw_posts: int
    insights: int
    daily_digest: int


class GoogleSheetsExporter:
    def __init__(self, workbook: WorkbookLike) -> None:
        self._workbook = workbook

    @classmethod
    def from_runtime(cls, runtime: RuntimeConfig) -> "GoogleSheetsExporter":
        credentials = load_google_sheets_credentials(runtime)
        client = gspread.authorize(credentials)
        workbook = client.open_by_key(runtime.google_sheets_spreadsheet_id)
        return cls(workbook)

    def export(
        self,
        *,
        run_date: str,
        posts: tuple[Post, ...],
        insights: tuple[Insight, ...],
        digest: DigestArtifact,
        scoring: ScoringConfig,
        lookback_hours: int,
        run_at: datetime | None = None,
    ) -> ExportCounts:
        effective_run_at = run_at or datetime.now(tz=UTC)
        raw_post_rows = _build_raw_post_rows(posts, scoring, run_date=run_date, lookback_hours=lookback_hours, run_at=effective_run_at)
        insight_rows = _build_insight_rows(insights, scoring, run_date=run_date)
        digest_row = _build_daily_digest_row(digest)

        self._upsert_rows(RAW_POSTS_TAB, RAW_POST_HEADERS, run_date, ("run_date", "post_id"), raw_post_rows)
        self._upsert_rows(
            INSIGHTS_TAB,
            INSIGHT_HEADERS,
            run_date,
            ("run_date", "source_id", "category", "title"),
            insight_rows,
        )
        self._upsert_rows(DAILY_DIGEST_TAB, DAILY_DIGEST_HEADERS, run_date, ("run_date",), [digest_row])

        LOGGER.info("Exported %s raw post rows to %s", len(raw_post_rows), RAW_POSTS_TAB)
        LOGGER.info("Exported %s insight rows to %s", len(insight_rows), INSIGHTS_TAB)
        LOGGER.info("Exported daily digest row to %s for %s", DAILY_DIGEST_TAB, run_date)

        return ExportCounts(raw_posts=len(raw_post_rows), insights=len(insight_rows), daily_digest=1)

    def _upsert_rows(
        self,
        tab_name: str,
        headers: list[str],
        run_date: str,
        key_fields: tuple[str, ...],
        new_rows: list[dict[str, Any]],
    ) -> None:
        worksheet = self._ensure_worksheet(tab_name, cols=len(headers))
        existing_values = worksheet.get_all_values()
        if not existing_values:
            worksheet.update(_row_range(1, len(headers)), [headers])
            existing_records: list[dict[str, Any]] = []
        else:
            if existing_values[0] != headers:
                worksheet.update(_row_range(1, len(headers)), [headers])
            existing_records = worksheet.get_all_records()

        existing_by_key = {
            _row_key(row, key_fields): index
            for index, row in enumerate(existing_records, start=2)
            if _row_key(row, key_fields) is not None
        }
        new_by_key = {
            _row_key(row, key_fields): row
            for row in new_rows
            if _row_key(row, key_fields) is not None
        }

        stale_rows = sorted(
            [
                row_index
                for key, row_index in existing_by_key.items()
                if key is not None
                and key[0] == run_date
                and key not in new_by_key
            ],
            reverse=True,
        )
        for row_index in stale_rows:
            worksheet.delete_rows(row_index)

        if stale_rows:
            existing_records = worksheet.get_all_records()
            existing_by_key = {
                _row_key(row, key_fields): index
                for index, row in enumerate(existing_records, start=2)
                if _row_key(row, key_fields) is not None
            }
            surviving_existing = existing_by_key
        else:
            surviving_existing = existing_by_key

        append_values: list[list[Any]] = []
        for row in new_rows:
            key = _row_key(row, key_fields)
            if key is None:
                continue
            values = [[row.get(header, "") for header in headers]]
            row_index = surviving_existing.get(key)
            if row_index is None:
                append_values.append(values[0])
            else:
                worksheet.update(_row_range(row_index, len(headers)), values)

        if append_values:
            worksheet.append_rows(append_values)

    def _ensure_worksheet(self, title: str, *, cols: int) -> WorksheetLike:
        try:
            return self._workbook.worksheet(title)
        except WorksheetNotFound:
            LOGGER.info("Creating missing worksheet %s", title)
            return self._workbook.add_worksheet(title=title, rows=100, cols=cols)


def load_google_sheets_credentials(runtime: RuntimeConfig) -> Credentials:
    if runtime.google_service_account_json:
        LOGGER.info("Using GOOGLE_SERVICE_ACCOUNT_JSON fallback for Google Sheets auth")
        try:
            credentials_info = json.loads(runtime.google_service_account_json)
        except json.JSONDecodeError as exc:
            raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON must contain valid JSON") from exc
        return ServiceAccountCredentials.from_service_account_info(
            credentials_info,
            scopes=list(GOOGLE_SHEETS_SCOPES),
        )

    LOGGER.info("Using Application Default Credentials for Google Sheets auth")
    credentials, _ = google.auth.default(scopes=list(GOOGLE_SHEETS_SCOPES))
    return credentials


RAW_POST_HEADERS = [
    "run_date",
    "post_id",
    "subreddit",
    "title",
    "url",
    "permalink",
    "score",
    "num_comments",
    "created_utc",
    "impact_score",
]

INSIGHT_HEADERS = [
    "run_date",
    "category",
    "title",
    "subreddit",
    "source_kind",
    "source_id",
    "source_post_id",
    "source_permalink",
    "novelty",
    "tags",
    "impact_score",
    "why_it_matters",
]

DAILY_DIGEST_HEADERS = [
    "run_date",
    "total_posts",
    "total_insights",
    "top_thread_title",
    "top_thread_url",
    "top_tool",
    "top_approach",
    "top_guide",
    "top_testing_insight",
    "watch_next",
]


def _build_raw_post_rows(
    posts: tuple[Post, ...],
    scoring: ScoringConfig,
    *,
    run_date: str,
    lookback_hours: int,
    run_at: datetime,
) -> list[dict[str, Any]]:
    rows = []
    for post in posts:
        breakdown = score_post(post, scoring, run_at=run_at, lookback_hours=lookback_hours)
        rows.append(
            {
                "run_date": run_date,
                "post_id": post.id,
                "subreddit": post.subreddit,
                "title": post.title,
                "url": post.url,
                "permalink": post.permalink,
                "score": post.score,
                "num_comments": post.num_comments,
                "created_utc": post.created_utc,
                "impact_score": breakdown.total,
            }
        )
    return sorted(rows, key=lambda row: row["post_id"])


def _build_insight_rows(insights: tuple[Insight, ...], scoring: ScoringConfig, *, run_date: str) -> list[dict[str, Any]]:
    rows = []
    for insight in insights:
        breakdown = score_insight(insight, scoring)
        rows.append(
            {
                "run_date": run_date,
                "category": insight.category,
                "title": insight.title,
                "subreddit": insight.subreddit,
                "source_kind": insight.source_kind,
                "source_id": insight.source_id,
                "source_post_id": insight.source_post_id,
                "source_permalink": insight.source_permalink,
                "novelty": insight.novelty or "",
                "tags": ", ".join(insight.tags),
                "impact_score": breakdown.total,
                "why_it_matters": insight.why_it_matters or insight.summary,
            }
        )
    return sorted(rows, key=lambda row: (row["category"], row["title"], row["source_id"]))


def _build_daily_digest_row(
    digest: DigestArtifact,
) -> dict[str, Any]:
    top_thread = digest.top_thread
    return {
        "run_date": digest.run_date,
        "total_posts": digest.total_posts,
        "total_insights": digest.total_insights,
        "top_thread_title": "" if top_thread is None else top_thread.title,
        "top_thread_url": "" if top_thread is None else top_thread.url,
        "top_tool": digest.top_tool,
        "top_approach": digest.top_approach,
        "top_guide": digest.top_guide,
        "top_testing_insight": digest.top_testing_insight,
        "watch_next": " | ".join(digest.watch_next[:3]),
    }


def _row_key(row: dict[str, Any], key_fields: tuple[str, ...]) -> tuple[str, ...] | None:
    values: list[str] = []
    for field in key_fields:
        value = row.get(field)
        if value in (None, ""):
            return None
        values.append(str(value))
    return tuple(values)


def _row_range(row_index: int, column_count: int) -> str:
    return f"A{row_index}:{_column_label(column_count)}{row_index}"


def _column_label(column_index: int) -> str:
    label = ""
    current = column_index
    while current > 0:
        current, remainder = divmod(current - 1, 26)
        label = chr(65 + remainder) + label
    return label
