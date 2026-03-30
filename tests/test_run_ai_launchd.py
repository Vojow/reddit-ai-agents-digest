from __future__ import annotations

import os
import subprocess
from pathlib import Path


def _copy_run_ai_launchd_script(repo_root: Path) -> Path:
    source = Path.cwd() / "scripts" / "run_ai_launchd.sh"
    target = repo_root / "scripts" / "run_ai_launchd.sh"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source.read_text())
    target.chmod(0o755)
    return target


def _write_fake_git(bin_dir: Path) -> None:
    git_path = bin_dir / "git"
    git_path.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "printf '%q ' \"$@\" >> \"$FAKE_GIT_LOG\"\n"
        "printf '\\n' >> \"$FAKE_GIT_LOG\"\n"
        "if [[ \"${1:-}\" == \"-C\" ]]; then\n"
        "  shift 2\n"
        "fi\n"
        "case \"${1:-}\" in\n"
        "  rev-parse)\n"
        "    printf '%s\\n' \"${FAKE_GIT_BRANCH:-main}\"\n"
        "    ;;\n"
        "  status)\n"
        "    if [[ \"${FAKE_GIT_DIRTY:-0}\" == \"1\" ]]; then\n"
        "      printf ' M README.md\\n'\n"
        "    fi\n"
        "    ;;\n"
        "  fetch)\n"
        "    if [[ \"${FAKE_GIT_FAIL_FETCH:-0}\" == \"1\" ]]; then\n"
        "      exit 21\n"
        "    fi\n"
        "    ;;\n"
        "  pull)\n"
        "    if [[ \"${FAKE_GIT_FAIL_PULL:-0}\" == \"1\" ]]; then\n"
        "      exit 22\n"
        "    fi\n"
        "    ;;\n"
        "esac\n"
    )
    git_path.chmod(0o755)


def _write_fake_make(bin_dir: Path) -> None:
    make_path = bin_dir / "make"
    make_path.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "printf '%q ' \"$@\" >> \"$FAKE_MAKE_LOG\"\n"
        "printf '\\n' >> \"$FAKE_MAKE_LOG\"\n"
        "if [[ \"${FAKE_MAKE_FAIL:-0}\" == \"1\" ]]; then\n"
        "  exit 31\n"
        "fi\n"
    )
    make_path.chmod(0o755)


def _write_fake_osascript(bin_dir: Path) -> None:
    osascript_path = bin_dir / "osascript"
    osascript_path.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "printf '%q ' \"$@\" >> \"$FAKE_OSASCRIPT_LOG\"\n"
        "printf '\\n' >> \"$FAKE_OSASCRIPT_LOG\"\n"
    )
    osascript_path.chmod(0o755)


def _run_launchd_wrapper(script_path: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["/bin/bash", str(script_path)],
        cwd=script_path.parent.parent,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _base_env(tmp_path: Path, fake_bin: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["FAKE_GIT_LOG"] = str(tmp_path / "git.log")
    env["FAKE_MAKE_LOG"] = str(tmp_path / "make.log")
    env["FAKE_OSASCRIPT_LOG"] = str(tmp_path / "osascript.log")
    return env


def test_run_ai_launchd_rejects_non_main_branch(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    script_path = _copy_run_ai_launchd_script(repo_root)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_fake_git(fake_bin)
    _write_fake_make(fake_bin)
    _write_fake_osascript(fake_bin)

    env = _base_env(tmp_path, fake_bin)
    env["FAKE_GIT_BRANCH"] = "feature/testing"

    result = _run_launchd_wrapper(script_path, env)

    assert result.returncode == 1
    assert "RUN_AI_LAUNCHD FAIL: expected main branch, got feature/testing" in result.stdout
    osascript_log = Path(env["FAKE_OSASCRIPT_LOG"]).read_text()
    assert "reddit-ai-agents-digest" in osascript_log


def test_run_ai_launchd_rejects_dirty_repo(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    script_path = _copy_run_ai_launchd_script(repo_root)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_fake_git(fake_bin)
    _write_fake_make(fake_bin)
    _write_fake_osascript(fake_bin)

    env = _base_env(tmp_path, fake_bin)
    env["FAKE_GIT_BRANCH"] = "main"
    env["FAKE_GIT_DIRTY"] = "1"

    result = _run_launchd_wrapper(script_path, env)

    assert result.returncode == 1
    assert "RUN_AI_LAUNCHD FAIL: worktree is dirty" in result.stdout
    osascript_log = Path(env["FAKE_OSASCRIPT_LOG"]).read_text()
    assert "reddit-ai-agents-digest" in osascript_log


def test_run_ai_launchd_fetches_pulls_and_runs_make_run_ai(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    script_path = _copy_run_ai_launchd_script(repo_root)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_fake_git(fake_bin)
    _write_fake_make(fake_bin)
    _write_fake_osascript(fake_bin)

    env = _base_env(tmp_path, fake_bin)
    env["FAKE_GIT_BRANCH"] = "main"

    result = _run_launchd_wrapper(script_path, env)

    assert result.returncode == 0, result.stdout
    assert "RUN_AI_LAUNCHD OK: make run-ai completed" in result.stdout
    git_log = Path(env["FAKE_GIT_LOG"]).read_text()
    make_log = Path(env["FAKE_MAKE_LOG"]).read_text()
    assert "fetch origin main" in git_log
    assert "pull --ff-only origin main" in git_log
    assert "run-ai" in make_log


def test_run_ai_launchd_triggers_osascript_on_make_failure(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    script_path = _copy_run_ai_launchd_script(repo_root)
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_fake_git(fake_bin)
    _write_fake_make(fake_bin)
    _write_fake_osascript(fake_bin)

    env = _base_env(tmp_path, fake_bin)
    env["FAKE_GIT_BRANCH"] = "main"
    env["FAKE_MAKE_FAIL"] = "1"

    result = _run_launchd_wrapper(script_path, env)

    assert result.returncode == 1
    assert "RUN_AI_LAUNCHD FAIL: make run-ai failed" in result.stdout
    osascript_log = Path(env["FAKE_OSASCRIPT_LOG"]).read_text()
    assert "reddit-ai-agents-digest" in osascript_log
