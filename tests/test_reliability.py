from __future__ import annotations

from pathlib import Path

import logging
import pytest

from reddit_digest.utils.retries import retry_call
from reddit_digest.utils.state import RunState
from reddit_digest.utils.state import write_run_state


def test_retry_call_retries_until_success(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("retry-test")
    attempts = {"count": 0}

    def flaky() -> str:
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise RuntimeError("temporary")
        return "ok"

    with caplog.at_level(logging.WARNING):
        result = retry_call(flaky, operation="flaky_op", logger=logger, attempts=3, delay_seconds=0)

    assert result == "ok"
    assert attempts["count"] == 3
    assert "flaky_op failed on attempt 1/3" in caplog.text


def test_write_run_state_updates_dated_and_latest_files(tmp_path: Path) -> None:
    state = RunState(
        run_date="2026-03-12",
        completed_at="2026-03-12T12:00:00+00:00",
        raw_posts_path="data/raw/posts/2026-03-12.json",
        raw_comments_path="data/raw/comments/2026-03-12.json",
        insights_path="data/processed/insights/2026-03-12.json",
        report_path="reports/daily/2026-03-12.md",
        sheets_exported=True,
    )

    write_run_state(tmp_path, state)

    assert (tmp_path / "2026-03-12.json").exists()
    assert (tmp_path / "latest.json").read_text() == (tmp_path / "2026-03-12.json").read_text()
