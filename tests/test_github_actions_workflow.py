from __future__ import annotations

from pathlib import Path

import yaml


def load_workflow() -> dict[str, object]:
    path = Path.cwd() / ".github" / "workflows" / "daily-digest.yml"
    return yaml.safe_load(path.read_text())


def workflow_triggers(workflow: dict[str, object]) -> dict[str, object]:
    triggers = workflow.get("on", workflow.get(True))
    assert isinstance(triggers, dict)
    return triggers


def test_daily_workflow_runs_markdown_without_google_auth() -> None:
    workflow = load_workflow()
    job = workflow["jobs"]["run-digest"]
    env = job["env"]
    steps = job["steps"]

    assert job["runs-on"] == "self-hosted"
    assert "permissions" not in job
    assert env["REDDIT_USER_AGENT"] == "${{ vars.REDDIT_USER_AGENT }}"
    assert env["OPENAI_MODEL"] == "${{ vars.OPENAI_MODEL }}"
    assert env["OPENAI_API_KEY"] == "${{ secrets.OPENAI_API_KEY }}"
    assert "GOOGLE_SHEETS_SPREADSHEET_ID" not in env
    assert "GOOGLE_SERVICE_ACCOUNT_JSON" not in env
    assert all(step.get("uses") != "google-github-actions/auth@v3" for step in steps)

    run_step = next(step for step in steps if step.get("name") == "Run daily digest pipeline")
    assert run_step["run"] == "make run-markdown"


def test_daily_workflow_remains_manually_runnable() -> None:
    workflow = load_workflow()

    assert "workflow_dispatch" in workflow_triggers(workflow)


def test_daily_workflow_remains_scheduled_and_uploads_failure_artifacts() -> None:
    workflow = load_workflow()
    triggers = workflow_triggers(workflow)
    job = workflow["jobs"]["run-digest"]
    upload_step = next(step for step in job["steps"] if step.get("uses") == "actions/upload-artifact@v4")

    assert triggers["schedule"] == [{"cron": "0 7 * * *"}]
    assert upload_step["if"] == "failure()"
    assert "reports/" in upload_step["with"]["path"]
    assert "data/processed/" in upload_step["with"]["path"]
    assert "data/state/" in upload_step["with"]["path"]
