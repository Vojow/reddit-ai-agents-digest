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


def test_daily_workflow_uses_oidc_for_google_auth() -> None:
    workflow = load_workflow()
    job = workflow["jobs"]["run-digest"]
    permissions = job["permissions"]
    env = job["env"]
    steps = job["steps"]

    assert permissions == {"contents": "read", "id-token": "write"}
    assert env["GOOGLE_SHEETS_SPREADSHEET_ID"] == "${{ vars.GOOGLE_SHEETS_SPREADSHEET_ID }}"
    assert "GOOGLE_SERVICE_ACCOUNT_JSON" not in env

    auth_step = next(step for step in steps if step.get("uses") == "google-github-actions/auth@v3")
    assert auth_step["with"] == {
        "workload_identity_provider": "${{ vars.GCP_WORKLOAD_IDENTITY_PROVIDER }}",
        "service_account": "${{ vars.GCP_SERVICE_ACCOUNT_EMAIL }}",
        "create_credentials_file": True,
        "export_environment_variables": True,
    }


def test_daily_workflow_remains_manually_runnable() -> None:
    workflow = load_workflow()

    assert "workflow_dispatch" in workflow_triggers(workflow)
