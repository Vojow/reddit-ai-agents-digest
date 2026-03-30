from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from pathlib import Path


def _copy_setup_script(repo_root: Path) -> Path:
    source = Path.cwd() / "scripts" / "configure_codex_worktree_env.sh"
    target = repo_root / "scripts" / "configure_codex_worktree_env.sh"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source.read_text())
    target.chmod(0o755)
    return target


def _write_fake_uv(bin_dir: Path) -> Path:
    uv_path = bin_dir / "uv"
    uv_path.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "printf '%q ' \"$@\" >> \"$FAKE_UV_LOG\"\n"
        "printf '\\n' >> \"$FAKE_UV_LOG\"\n"
        "printf 'REDDIT_USER_AGENT=%s\\n' \"${REDDIT_USER_AGENT:-}\" >> \"$FAKE_UV_ENV_LOG\"\n"
        "printf 'PATH=%s\\n' \"${PATH:-}\" >> \"$FAKE_UV_ENV_LOG\"\n"
        "printf 'UV_CACHE_DIR=%s\\n' \"${UV_CACHE_DIR:-}\" >> \"$FAKE_UV_ENV_LOG\"\n"
        "printf 'UV_PYTHON=%s\\n' \"${UV_PYTHON:-}\" >> \"$FAKE_UV_ENV_LOG\"\n"
        "if [[ \"${FAKE_UV_FAIL_PREFLIGHT:-0}\" == \"1\" && \"$*\" == *\"reddit-digest preflight\"* ]]; then\n"
        "  exit 12\n"
        "fi\n"
    )
    uv_path.chmod(0o755)
    return uv_path


def _write_fake_git(bin_dir: Path, primary_root: Path) -> Path:
    git_path = bin_dir / "git"
    git_path.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "if [[ \"$*\" == *\"worktree list --porcelain\"* ]]; then\n"
        f"  printf 'worktree {primary_root}\\n'\n"
        "  printf 'HEAD 0000000000000000000000000000000000000000\\n'\n"
        "  printf 'branch refs/heads/main\\n'\n"
        "  exit 0\n"
        "fi\n"
        "exit 1\n"
    )
    git_path.chmod(0o755)
    return git_path


def _run_setup_script(script_path: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["/bin/bash", str(script_path)],
        cwd=script_path.parent.parent,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _read_logged_env_values(env_log_path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in env_log_path.read_text().strip().splitlines():
        key, value = line.split("=", maxsplit=1)
        values[key] = value
    return values


def _clean_bootstrap_env(env: dict[str, str]) -> dict[str, str]:
    cleaned = env.copy()
    cleaned.pop("UV_CACHE_DIR", None)
    cleaned.pop("UV_PYTHON", None)
    return cleaned


def test_codex_environment_toml_points_to_setup_script() -> None:
    config_path = Path(".codex/environments/environment.toml")
    assert config_path.exists()

    content = config_path.read_text()
    assert "version = 1" in content
    assert 'name = "reddit-ai-agents-digest"' in content
    assert "[setup]" in content
    assert 'script = "./scripts/configure_codex_worktree_env.sh"' in content


def test_makefile_markdown_targets_use_direct_cli_commands() -> None:
    content = Path("Makefile").read_text()

    assert not Path("scripts/run_markdown_with_env.sh").exists()
    assert "preflight:" in content
    assert "run-markdown:" in content
    assert "run-ai:" in content
    assert ".PHONY: install test lint run preflight run-markdown run-ai" in content
    assert "uv run reddit-digest preflight --base-path . --skip-sheets --markdown-only" in content
    assert "uv run reddit-digest run-daily --base-path . --skip-sheets --markdown-only" in content
    assert "uv run reddit-digest preflight --base-path . --skip-sheets" in content
    assert "uv run reddit-digest run-daily --base-path . --skip-sheets" in content
    run_ai_block = content.split("run-ai:", maxsplit=1)[1]
    assert "--markdown-only" not in run_ai_block
    assert "run_markdown_with_env.sh" not in content


def test_codex_setup_script_uses_current_worktree_env_and_path_uv(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    script_path = _copy_setup_script(repo_root)

    env_file = repo_root / ".env"
    env_file.write_text("REDDIT_USER_AGENT=current-worktree-agent\n")

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    uv_path = _write_fake_uv(fake_bin)
    log_path = tmp_path / "uv.log"
    env_log_path = tmp_path / "uv.env.log"

    env = _clean_bootstrap_env(os.environ)
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["FAKE_UV_LOG"] = str(log_path)
    env["FAKE_UV_ENV_LOG"] = str(env_log_path)

    result = _run_setup_script(script_path, env)

    assert result.returncode == 0, result.stderr
    assert f"CODEX_ENV_SETUP START: repo={repo_root}" in result.stdout
    assert f"CODEX_ENV_SETUP OK: repo={repo_root} env={env_file} uv={uv_path}" in result.stdout

    calls = log_path.read_text().strip().splitlines()
    assert len(calls) == 1
    preflight_args = shlex.split(calls[0])
    assert preflight_args == [
        "run",
        "reddit-digest",
        "preflight",
        "--base-path",
        str(repo_root),
        "--skip-sheets",
        "--markdown-only",
    ]
    env_values = _read_logged_env_values(env_log_path)
    assert env_values["REDDIT_USER_AGENT"] == "current-worktree-agent"
    assert env_values["PATH"].startswith(f"{fake_bin}:")
    assert env_values["UV_CACHE_DIR"] == str(repo_root / ".cache" / "uv")
    assert env_values["UV_PYTHON"] != ""


def test_codex_setup_script_falls_back_to_primary_worktree_env(tmp_path: Path) -> None:
    repo_root = tmp_path / "linked-worktree"
    script_path = _copy_setup_script(repo_root)

    primary_root = tmp_path / "primary-worktree"
    primary_root.mkdir(parents=True, exist_ok=True)
    primary_env = primary_root / ".env"
    primary_env.write_text("REDDIT_USER_AGENT=primary-worktree-agent\n")

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_fake_uv(fake_bin)
    _write_fake_git(fake_bin, primary_root)
    log_path = tmp_path / "uv.log"
    env_log_path = tmp_path / "uv.env.log"

    env = _clean_bootstrap_env(os.environ)
    env["PATH"] = f"{fake_bin}:/usr/bin:/bin"
    env["FAKE_UV_LOG"] = str(log_path)
    env["FAKE_UV_ENV_LOG"] = str(env_log_path)

    result = _run_setup_script(script_path, env)

    assert result.returncode == 0, result.stderr
    local_env = repo_root / ".env"
    assert local_env.read_text() == primary_env.read_text()
    assert f"CODEX_ENV_SETUP OK: repo={repo_root} env={local_env}" in result.stdout
    env_values = _read_logged_env_values(env_log_path)
    assert env_values["REDDIT_USER_AGENT"] == "primary-worktree-agent"
    assert env_values["PATH"].startswith(f"{fake_bin}:")
    assert env_values["UV_CACHE_DIR"] == str(repo_root / ".cache" / "uv")


def test_codex_setup_script_preserves_existing_worktree_env(tmp_path: Path) -> None:
    repo_root = tmp_path / "linked-worktree"
    script_path = _copy_setup_script(repo_root)

    local_env = repo_root / ".env"
    local_env.write_text("REDDIT_USER_AGENT=worktree-agent\n")

    primary_root = tmp_path / "primary-worktree"
    primary_root.mkdir(parents=True, exist_ok=True)
    (primary_root / ".env").write_text("REDDIT_USER_AGENT=primary-worktree-agent\n")

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_fake_uv(fake_bin)
    _write_fake_git(fake_bin, primary_root)
    log_path = tmp_path / "uv.log"
    env_log_path = tmp_path / "uv.env.log"

    env = _clean_bootstrap_env(os.environ)
    env["PATH"] = f"{fake_bin}:/usr/bin:/bin"
    env["FAKE_UV_LOG"] = str(log_path)
    env["FAKE_UV_ENV_LOG"] = str(env_log_path)

    result = _run_setup_script(script_path, env)

    assert result.returncode == 0, result.stderr
    assert local_env.read_text() == "REDDIT_USER_AGENT=worktree-agent\n"
    assert f"CODEX_ENV_SETUP OK: repo={repo_root} env={local_env}" in result.stdout
    env_values = _read_logged_env_values(env_log_path)
    assert env_values["REDDIT_USER_AGENT"] == "worktree-agent"


def test_codex_setup_script_resolves_uv_from_common_home_location(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    script_path = _copy_setup_script(repo_root)

    (repo_root / ".env").write_text("REDDIT_USER_AGENT=agent\n")

    fake_home = tmp_path / "home"
    uv_bin_dir = fake_home / ".local" / "bin"
    uv_bin_dir.mkdir(parents=True, exist_ok=True)
    uv_path = _write_fake_uv(uv_bin_dir)
    log_path = tmp_path / "uv.log"
    env_log_path = tmp_path / "uv.env.log"

    env = _clean_bootstrap_env(os.environ)
    env["HOME"] = str(fake_home)
    env["PATH"] = "/usr/bin:/bin"
    env["FAKE_UV_LOG"] = str(log_path)
    env["FAKE_UV_ENV_LOG"] = str(env_log_path)

    result = _run_setup_script(script_path, env)

    assert result.returncode == 0, result.stderr
    assert f"uv={uv_path}" in result.stdout
    env_values = _read_logged_env_values(env_log_path)
    assert env_values["PATH"].startswith(f"{uv_bin_dir}:")
    assert env_values["UV_CACHE_DIR"] == str(repo_root / ".cache" / "uv")


def test_codex_setup_script_uses_repo_venv_python_fallback_when_python312_not_on_path(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    script_path = _copy_setup_script(repo_root)

    (repo_root / ".env").write_text("REDDIT_USER_AGENT=agent\n")
    venv_python = repo_root / ".venv" / "bin" / "python"
    venv_python.parent.mkdir(parents=True, exist_ok=True)
    venv_python.write_text("#!/usr/bin/env bash\nexit 0\n")
    venv_python.chmod(0o755)

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_fake_uv(fake_bin)
    support_bin = tmp_path / "support-bin"
    support_bin.mkdir()
    dirname_path = shutil.which("dirname")
    bash_path = shutil.which("bash")
    assert dirname_path is not None
    assert bash_path is not None
    (support_bin / "dirname").symlink_to(dirname_path)
    (support_bin / "bash").symlink_to(bash_path)
    log_path = tmp_path / "uv.log"
    env_log_path = tmp_path / "uv.env.log"

    env = _clean_bootstrap_env(os.environ)
    env["PATH"] = f"{fake_bin}:{support_bin}"
    env["FAKE_UV_LOG"] = str(log_path)
    env["FAKE_UV_ENV_LOG"] = str(env_log_path)

    result = _run_setup_script(script_path, env)

    assert result.returncode == 0, result.stderr
    env_values = _read_logged_env_values(env_log_path)
    assert env_values["PATH"].startswith(f"{fake_bin}:")
    assert env_values["UV_CACHE_DIR"] == str(repo_root / ".cache" / "uv")
    assert env_values["UV_PYTHON"] == str(venv_python)


def test_codex_setup_script_fails_with_deterministic_line_when_preflight_fails(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    script_path = _copy_setup_script(repo_root)
    (repo_root / ".env").write_text("REDDIT_USER_AGENT=agent\n")

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_fake_uv(fake_bin)
    log_path = tmp_path / "uv.log"
    env_log_path = tmp_path / "uv.env.log"

    env = _clean_bootstrap_env(os.environ)
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["FAKE_UV_LOG"] = str(log_path)
    env["FAKE_UV_ENV_LOG"] = str(env_log_path)
    env["FAKE_UV_FAIL_PREFLIGHT"] = "1"

    result = _run_setup_script(script_path, env)

    assert result.returncode == 1
    assert "CODEX_ENV_SETUP FAIL: preflight command failed" in result.stdout
