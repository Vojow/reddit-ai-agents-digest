from pathlib import Path


def test_markdown_automation_helper_exists_and_uses_canonical_target() -> None:
    helper_path = Path("scripts/run_markdown_with_env.sh")

    assert helper_path.exists()

    content = helper_path.read_text()

    assert 'source "${ENV_FILE}"' in content
    assert "exec make run-markdown" in content
