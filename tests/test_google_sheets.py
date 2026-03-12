from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import Any

from reddit_digest.config import load_scoring_config
from reddit_digest.extractors.service import extract_insights
from reddit_digest.models.comment import Comment
from reddit_digest.models.post import Post
from reddit_digest.outputs.google_sheets import DAILY_DIGEST_TAB
from reddit_digest.outputs.google_sheets import GoogleSheetsExporter
from reddit_digest.outputs.google_sheets import INSIGHTS_TAB
from reddit_digest.outputs.google_sheets import RAW_POSTS_TAB
from reddit_digest.outputs.markdown import render_markdown_digest
from reddit_digest.ranking.novelty import apply_novelty


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
            raise KeyError(title)
        return self.worksheets[title]

    def add_worksheet(self, title: str, rows: int, cols: int) -> FakeWorksheet:
        worksheet = FakeWorksheet(title=title, rows=[])
        self.worksheets[title] = worksheet
        return worksheet


def build_inputs(sample_posts_payload: list[dict[str, object]], sample_comments_payload: list[dict[str, object]], tmp_path: Path):
    posts = tuple(Post.from_raw(item) for item in sample_posts_payload)
    comments = tuple(Comment.from_raw(item) for item in sample_comments_payload)
    scoring = load_scoring_config(Path.cwd() / "config" / "scoring.yaml")
    extracted = extract_insights(posts, comments, processed_root=tmp_path / "processed", run_date="2026-03-12")
    novelty = apply_novelty(tmp_path / "processed", run_date="2026-03-12", insights=extracted.insights)
    markdown = render_markdown_digest(
        run_date="2026-03-12",
        posts=posts,
        insights=novelty.insights,
        scoring=scoring,
        reports_root=tmp_path / "reports",
        lookback_hours=24,
        watch_next=("Monitor prompt-state snapshots",),
        run_at=datetime(2026, 3, 12, 12, 0, tzinfo=UTC),
    )
    return posts, novelty.insights, scoring, markdown.content


def test_google_sheets_export_creates_expected_tabs(
    sample_posts_payload: list[dict[str, object]],
    sample_comments_payload: list[dict[str, object]],
    tmp_path: Path,
) -> None:
    workbook = FakeWorkbook()
    exporter = GoogleSheetsExporter(workbook)
    posts, insights, scoring, markdown_content = build_inputs(sample_posts_payload, sample_comments_payload, tmp_path)

    counts = exporter.export(
        run_date="2026-03-12",
        posts=posts,
        insights=insights,
        markdown_content=markdown_content,
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
    posts, insights, scoring, markdown_content = build_inputs(sample_posts_payload, sample_comments_payload, tmp_path)

    exporter.export(
        run_date="2026-03-12",
        posts=posts,
        insights=insights,
        markdown_content=markdown_content,
        scoring=scoring,
        lookback_hours=24,
        run_at=datetime(2026, 3, 12, 12, 0, tzinfo=UTC),
    )
    exporter.export(
        run_date="2026-03-12",
        posts=posts,
        insights=insights,
        markdown_content=markdown_content,
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
