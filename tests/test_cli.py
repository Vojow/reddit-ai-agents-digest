from __future__ import annotations

from pathlib import Path

import pytest

import reddit_digest.cli as cli
from reddit_digest.preflight import PreflightResult


def test_cli_main_runs_pipeline_and_prints_help(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    calls: dict[str, object] = {}

    class FakeRunner:
        def __init__(self, *, base_path: Path) -> None:
            calls["base_path"] = base_path

        def run(self, *, run_date: str, skip_sheets: bool, skip_openai: bool) -> None:
            calls["run"] = (run_date, skip_sheets, skip_openai)

    monkeypatch.setattr(cli, "PipelineRunner", FakeRunner)
    monkeypatch.setattr(cli, "configure_logging", lambda: calls.setdefault("logging", True))

    assert cli.main(
        ["run-daily", "--date", "2026-03-13", "--base-path", "/tmp/repo", "--skip-sheets", "--markdown-only"]
    ) == 0
    assert calls["base_path"] == Path("/tmp/repo")
    assert calls["run"] == ("2026-03-13", True, True)
    assert calls["logging"] is True

    assert cli.main([]) == 0
    assert "reddit-digest" in capsys.readouterr().out


def test_cli_build_parser_defaults_to_today_and_known_command() -> None:
    parser = cli.build_parser()
    args = parser.parse_args(["run-daily"])
    assert args.command == "run-daily"
    assert args.base_path == "."
    assert isinstance(args.run_date, str)
    assert args.markdown_only is False

    preflight = parser.parse_args(["preflight", "--base-path", "/tmp/repo", "--skip-sheets", "--markdown-only"])
    assert preflight.command == "preflight"
    assert preflight.base_path == "/tmp/repo"
    assert preflight.skip_sheets is True
    assert preflight.markdown_only is True


def test_cli_main_runs_preflight_and_returns_result(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    calls: dict[str, object] = {}

    def fake_run_preflight(*, base_path: Path, skip_sheets: bool, markdown_only: bool) -> PreflightResult:
        calls["preflight"] = (base_path, skip_sheets, markdown_only)
        return PreflightResult(ok=True, errors=())

    monkeypatch.setattr(cli, "run_preflight", fake_run_preflight)

    assert cli.main(["preflight", "--base-path", "/tmp/repo", "--skip-sheets", "--markdown-only"]) == 0
    assert calls["preflight"] == (Path("/tmp/repo"), True, True)
    assert capsys.readouterr().out == "Preflight passed.\n"


def test_cli_main_returns_non_zero_when_preflight_fails(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(
        cli,
        "run_preflight",
        lambda **_: PreflightResult(ok=False, errors=("Missing required environment variable: REDDIT_USER_AGENT",)),
    )

    assert cli.main(["preflight", "--base-path", "/tmp/repo", "--skip-sheets", "--markdown-only"]) == 1
    assert "Preflight failed." in capsys.readouterr().out
