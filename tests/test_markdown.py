from __future__ import annotations

from pathlib import Path

from reddit_digest.outputs.markdown import _build_output_paths


def test_build_output_paths_supports_default_and_llm_variants() -> None:
    daily_path, latest_path = _build_output_paths(
        reports_root=Path("/tmp/reports"),
        run_date="2026-03-13",
        variant_suffix="",
    )
    llm_daily_path, llm_latest_path = _build_output_paths(
        reports_root=Path("/tmp/reports"),
        run_date="2026-03-13",
        variant_suffix="llm",
    )

    assert daily_path == Path("/tmp/reports/daily/2026-03-13.md")
    assert latest_path == Path("/tmp/reports/latest.md")
    assert llm_daily_path == Path("/tmp/reports/daily/2026-03-13.llm.md")
    assert llm_latest_path == Path("/tmp/reports/latest.llm.md")
