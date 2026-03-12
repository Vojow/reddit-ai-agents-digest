from __future__ import annotations

from pathlib import Path


def test_env_example_prefers_wif_variables_over_json_key() -> None:
    lines = (Path.cwd() / ".env.example").read_text().splitlines()

    assert "GCP_WORKLOAD_IDENTITY_PROVIDER=" in lines
    assert "GCP_SERVICE_ACCOUNT_EMAIL=" in lines
    assert "GOOGLE_SHEETS_SPREADSHEET_ID=" in lines
    assert "# GOOGLE_SERVICE_ACCOUNT_JSON=" in lines
    assert "GOOGLE_SERVICE_ACCOUNT_JSON=" not in [line for line in lines if not line.startswith("#")]


def test_google_auth_docs_match_current_workflow_model() -> None:
    readme = (Path.cwd() / "README.md").read_text()
    operations = (Path.cwd() / "docs" / "operations.md").read_text()
    architecture = (Path.cwd() / "docs" / "architecture.md").read_text()

    assert "GitHub Actions repository variables for Sheets" in readme
    assert "GCP_WORKLOAD_IDENTITY_PROVIDER" in readme
    assert "GOOGLE_SERVICE_ACCOUNT_JSON" in readme
    assert "Repository variables required for the GitHub Actions Sheets path" in operations
    assert "GOOGLE_SERVICE_ACCOUNT_JSON` in GitHub secrets" in operations
    assert "GitHub Actions automation is not yet added." not in architecture
