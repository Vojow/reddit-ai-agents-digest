from pathlib import Path


def test_markdown_automation_helper_resolves_shared_env_and_uv() -> None:
    helper_path = Path("scripts/run_markdown_with_env.sh")

    assert helper_path.exists()

    content = helper_path.read_text()

    assert 'source "${ENV_FILE}"' in content
    assert "git -C \"${REPO_ROOT}\" worktree list --porcelain" in content
    assert "command -v uv" in content
    assert '"${UV_BIN}" run reddit-digest preflight --base-path "${REPO_ROOT}" --skip-sheets --markdown-only' in content
    assert 'exec "${UV_BIN}" run reddit-digest run-daily --base-path "${REPO_ROOT}" --skip-sheets --markdown-only "${FORWARD_ARGS[@]}"' in content
    assert '--preflight-only' in content


def test_makefile_run_markdown_uses_automation_helper() -> None:
    content = Path("Makefile").read_text()

    assert "preflight:" in content
    assert "./scripts/run_markdown_with_env.sh --preflight-only" in content
    assert "./scripts/run_markdown_with_env.sh" in content
