from __future__ import annotations

from pathlib import Path

import pytest

import reddit_digest.cli as cli


def test_cli_main_runs_pipeline_and_prints_help(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    calls: dict[str, object] = {}

    class FakeRunner:
        def __init__(self, *, base_path: Path) -> None:
            calls["base_path"] = base_path

        def run(self, *, run_date: str, skip_sheets: bool) -> None:
            calls["run"] = (run_date, skip_sheets)

    monkeypatch.setattr(cli, "PipelineRunner", FakeRunner)
    monkeypatch.setattr(cli, "configure_logging", lambda: calls.setdefault("logging", True))

    assert cli.main(["run-daily", "--date", "2026-03-13", "--base-path", "/tmp/repo", "--skip-sheets"]) == 0
    assert calls["base_path"] == Path("/tmp/repo")
    assert calls["run"] == ("2026-03-13", True)
    assert calls["logging"] is True

    assert cli.main([]) == 0
    assert "reddit-digest" in capsys.readouterr().out


def test_cli_build_parser_defaults_to_today_and_known_command() -> None:
    parser = cli.build_parser()
    args = parser.parse_args(["run-daily"])
    assert args.command == "run-daily"
    assert args.base_path == "."
    assert isinstance(args.run_date, str)
