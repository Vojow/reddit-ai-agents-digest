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
from google.auth.credentials import Credentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials

from reddit_digest.config import RuntimeConfig
from reddit_digest.config import ScoringConfig
from reddit_digest.models.insight import Insight
from reddit_digest.models.post import Post
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

    def clear(self) -> None:
        ...

    def update(self, values: list[list[Any]]) -> None:
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
        markdown_content: str,
        scoring: ScoringConfig,
        lookback_hours: int,
        run_at: datetime | None = None,
    ) -> ExportCounts:
        effective_run_at = run_at or datetime.now(tz=UTC)
        raw_post_rows = _build_raw_post_rows(posts, scoring, run_date=run_date, lookback_hours=lookback_hours, run_at=effective_run_at)
        insight_rows = _build_insight_rows(insights, scoring, run_date=run_date)
        digest_row = _build_daily_digest_row(run_date=run_date, posts=posts, insights=insights, markdown_content=markdown_content)

        self._upsert_rows(RAW_POSTS_TAB, RAW_POST_HEADERS, run_date, raw_post_rows)
        self._upsert_rows(INSIGHTS_TAB, INSIGHT_HEADERS, run_date, insight_rows)
        self._upsert_rows(DAILY_DIGEST_TAB, DAILY_DIGEST_HEADERS, run_date, [digest_row])

        LOGGER.info("Exported %s raw post rows to %s", len(raw_post_rows), RAW_POSTS_TAB)
        LOGGER.info("Exported %s insight rows to %s", len(insight_rows), INSIGHTS_TAB)
        LOGGER.info("Exported daily digest row to %s for %s", DAILY_DIGEST_TAB, run_date)

        return ExportCounts(raw_posts=len(raw_post_rows), insights=len(insight_rows), daily_digest=1)

    def _upsert_rows(self, tab_name: str, headers: list[str], run_date: str, new_rows: list[dict[str, Any]]) -> None:
        worksheet = self._ensure_worksheet(tab_name, cols=len(headers))
        existing = worksheet.get_all_records()
        preserved = [row for row in existing if row.get("run_date") != run_date]
        merged_rows = preserved + new_rows
        sheet_rows = [headers] + [[row.get(header, "") for header in headers] for row in merged_rows]
        worksheet.clear()
        worksheet.update(sheet_rows)

    def _ensure_worksheet(self, title: str, *, cols: int) -> WorksheetLike:
        try:
            return self._workbook.worksheet(title)
        except Exception:
            LOGGER.info("Creating missing worksheet %s", title)
            return self._workbook.add_worksheet(title=title, rows=100, cols=cols)


def load_google_sheets_credentials(runtime: RuntimeConfig) -> Credentials:
    if runtime.google_service_account_json:
        try:
            credentials_info = json.loads(runtime.google_service_account_json)
        except json.JSONDecodeError as exc:
            raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON must contain valid JSON") from exc
        return ServiceAccountCredentials.from_service_account_info(
            credentials_info,
            scopes=list(GOOGLE_SHEETS_SCOPES),
        )

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
    *,
    run_date: str,
    posts: tuple[Post, ...],
    insights: tuple[Insight, ...],
    markdown_content: str,
) -> dict[str, Any]:
    top_thread = posts[0] if posts else None
    top_by_category = {category: "" for category in ("tools", "approaches", "guides", "testing")}
    for insight in insights:
        if not top_by_category.get(insight.category):
            top_by_category[insight.category] = insight.title

    watch_next_lines = _extract_watch_next_lines(markdown_content)
    return {
        "run_date": run_date,
        "total_posts": len(posts),
        "total_insights": len(insights),
        "top_thread_title": "" if top_thread is None else top_thread.title,
        "top_thread_url": "" if top_thread is None else top_thread.url,
        "top_tool": top_by_category["tools"],
        "top_approach": top_by_category["approaches"],
        "top_guide": top_by_category["guides"],
        "top_testing_insight": top_by_category["testing"],
        "watch_next": " | ".join(watch_next_lines[:3]),
    }


def _extract_watch_next_lines(markdown_content: str) -> list[str]:
    lines = markdown_content.splitlines()
    in_watch_next = False
    collected: list[str] = []
    for line in lines:
        if line == "## Watch Next":
            in_watch_next = True
            continue
        if in_watch_next and line.startswith("## "):
            break
        if in_watch_next and line.startswith("- "):
            collected.append(line[2:])
    return collected
