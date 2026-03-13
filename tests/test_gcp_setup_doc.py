from __future__ import annotations

from pathlib import Path


def test_gcp_setup_doc_covers_required_wif_topics() -> None:
    document = (Path.cwd() / "docs" / "gcp-wif-setup.md").read_text()

    assert "Workload Identity Federation" in document
    assert "token.actions.githubusercontent.com" in document
    assert "roles/iam.workloadIdentityUser" in document
    assert "GCP_WORKLOAD_IDENTITY_PROVIDER" in document
    assert "GCP_SERVICE_ACCOUNT_EMAIL" in document
    assert "GOOGLE_SHEETS_SPREADSHEET_ID" in document
    assert "google-github-actions/auth" in document
    assert "Vojow/reddit-ai-agents-digest" in document
    assert "Repository variables used by the current self-hosted markdown workflow" in document
    assert "Additional repository variables required once Sheets export is re-enabled in" in document


def test_readme_and_operations_link_to_gcp_setup_doc() -> None:
    readme = (Path.cwd() / "README.md").read_text()
    operations = (Path.cwd() / "docs" / "operations.md").read_text()

    assert "docs/gcp-wif-setup.md" in readme
    assert "docs/gcp-wif-setup.md" in operations
