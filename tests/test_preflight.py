from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from reddit_digest.preflight import format_preflight_result
from reddit_digest.preflight import run_preflight


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def write_repo_files(root: Path) -> None:
    write_text(root / "pyproject.toml", "[project]\nname = 'test'\nversion = '0.1.0'\n")
    write_text(
        root / "config" / "subreddits.yaml",
        (Path.cwd() / "config" / "subreddits.yaml").read_text(),
    )
    write_text(
        root / "config" / "scoring.yaml",
        (Path.cwd() / "config" / "scoring.yaml").read_text(),
    )


def test_run_preflight_passes_for_markdown_only_repo(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    write_repo_files(tmp_path)
    write_text(tmp_path / ".env", "REDDIT_USER_AGENT=reddit-ai-agents-digest/0.1.0")
    monkeypatch.delenv("REDDIT_USER_AGENT", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("TEAMS_WEBHOOK_URL", raising=False)

    result = run_preflight(base_path=tmp_path, skip_sheets=True, markdown_only=True)

    assert result.ok is True
    assert result.errors == ()
    assert format_preflight_result(result) == "Preflight passed.\n"


def test_run_preflight_fails_without_required_reddit_user_agent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    write_repo_files(tmp_path)
    monkeypatch.delenv("REDDIT_USER_AGENT", raising=False)

    result = run_preflight(base_path=tmp_path, skip_sheets=True, markdown_only=True)

    assert result.ok is False
    assert any("REDDIT_USER_AGENT" in error for error in result.errors)


def test_run_preflight_reports_invalid_dotenv(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    write_repo_files(tmp_path)
    write_text(tmp_path / ".env", "NOT A VALID LINE")
    monkeypatch.delenv("REDDIT_USER_AGENT", raising=False)

    result = run_preflight(base_path=tmp_path, skip_sheets=True, markdown_only=True)

    assert result.ok is False
    assert any("expected KEY=VALUE" in error for error in result.errors)


def test_run_preflight_uses_primary_worktree_dotenv(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    primary_root = tmp_path / "primary"
    worktree_root = tmp_path / "feature"
    write_repo_files(worktree_root)
    write_text(primary_root / ".env", "REDDIT_USER_AGENT=from-primary-worktree")
    monkeypatch.delenv("REDDIT_USER_AGENT", raising=False)

    def fake_run(command: list[str], *, capture_output: bool, check: bool, text: bool) -> subprocess.CompletedProcess[str]:
        assert command == ["git", "-C", str(worktree_root), "worktree", "list", "--porcelain"]
        assert capture_output is True
        assert check is True
        assert text is True
        return subprocess.CompletedProcess(
            args=command,
            returncode=0,
            stdout=f"worktree {primary_root}\nworktree {worktree_root}\n",
            stderr="",
        )

    monkeypatch.setattr("reddit_digest.config.subprocess.run", fake_run)

    result = run_preflight(base_path=worktree_root, skip_sheets=True, markdown_only=True)

    assert result.ok is True
    assert result.errors == ()


def test_run_preflight_fails_when_write_access_is_unavailable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    write_repo_files(tmp_path)
    write_text(tmp_path / ".env", "REDDIT_USER_AGENT=reddit-ai-agents-digest/0.1.0")
    original_access = __import__("os").access

    def fake_access(path: object, mode: int) -> bool:
        if Path(path) == tmp_path:
            return False
        return original_access(path, mode)

    monkeypatch.setattr("reddit_digest.preflight.os.access", fake_access)

    result = run_preflight(base_path=tmp_path, skip_sheets=True, markdown_only=True)

    assert result.ok is False
    assert any("Write access is not available" in error for error in result.errors)
