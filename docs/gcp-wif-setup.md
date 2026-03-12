# GCP Setup For GitHub OIDC And Workload Identity Federation

This runbook covers the Google Cloud setup required for GitHub Actions in this
repository to access Google Sheets without storing a long-lived service account
JSON key in GitHub.

The target repository identity is `Vojow/reddit-ai-agents-digest`.

## Values You Need

Choose or collect these values before you start:

- `PROJECT_ID`: your Google Cloud project ID
- `PROJECT_NUMBER`: the numeric project ID for `PROJECT_ID`
- `SERVICE_ACCOUNT_ID`: a short service account name such as `reddit-digest-bot`
- `SERVICE_ACCOUNT_EMAIL`: the final service account email
- `POOL_ID`: a workload identity pool name such as `github-digest-pool`
- `PROVIDER_ID`: a provider name such as `github-repo-provider`
- `SPREADSHEET_ID`: the target Google Sheets spreadsheet ID

You can resolve the project number with:

```bash
gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)"
```

## 1. Enable Required APIs

Enable the APIs used by this repository:

```bash
gcloud services enable \
  iam.googleapis.com \
  iamcredentials.googleapis.com \
  sheets.googleapis.com \
  --project="$PROJECT_ID"
```

## 2. Create Or Reuse A Service Account

Create a dedicated service account if you do not already have one:

```bash
gcloud iam service-accounts create "$SERVICE_ACCOUNT_ID" \
  --display-name="Reddit Digest GitHub Actions" \
  --project="$PROJECT_ID"
```

Its email address will be:

```text
${SERVICE_ACCOUNT_ID}@${PROJECT_ID}.iam.gserviceaccount.com
```

This service account is the identity that needs spreadsheet access.

## 3. Create A Workload Identity Pool

Create a workload identity pool for GitHub-issued OIDC tokens:

```bash
gcloud iam workload-identity-pools create "$POOL_ID" \
  --location="global" \
  --display-name="GitHub Actions pool" \
  --project="$PROJECT_ID"
```

## 4. Create The GitHub OIDC Provider

Create a provider that trusts GitHub's OIDC issuer and maps repository
attributes into Google IAM:

```bash
gcloud iam workload-identity-pools providers create-oidc "$PROVIDER_ID" \
  --location="global" \
  --workload-identity-pool="$POOL_ID" \
  --display-name="GitHub repository provider" \
  --issuer-uri="https://token.actions.githubusercontent.com" \
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.repository_owner=assertion.repository_owner,attribute.ref=assertion.ref,attribute.actor=assertion.actor" \
  --attribute-condition="assertion.repository=='Vojow/reddit-ai-agents-digest'" \
  --project="$PROJECT_ID"
```

The resulting provider resource name becomes the GitHub repository variable
`GCP_WORKLOAD_IDENTITY_PROVIDER`. It has this shape:

```text
projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/POOL_ID/providers/PROVIDER_ID
```

## 5. Allow The GitHub Repository To Impersonate The Service Account

Grant `roles/iam.workloadIdentityUser` on the service account to the principal
set representing this repository:

```bash
gcloud iam service-accounts add-iam-policy-binding "$SERVICE_ACCOUNT_EMAIL" \
  --role="roles/iam.workloadIdentityUser" \
  --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/attribute.repository/Vojow/reddit-ai-agents-digest" \
  --project="$PROJECT_ID"
```

If you want to restrict usage further, tighten the provider's
`--attribute-condition` to a specific branch or environment after the basic flow
is working.

## 6. Share The Spreadsheet With The Service Account

Google Sheets access is controlled by the spreadsheet itself. Share the target
sheet with `SERVICE_ACCOUNT_EMAIL` and grant at least `Editor` access.

If this step is skipped, the workflow may authenticate correctly and still fail
with a Sheets `403`.

## 7. Configure The GitHub Repository

Set these repository variables:

- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_SERVICE_ACCOUNT_EMAIL`
- `GOOGLE_SHEETS_SPREADSHEET_ID`

Set these repository secrets:

- `REDDIT_USER_AGENT`
- `OPENAI_API_KEY` if you want `Watch Next` suggestions
- `OPENAI_MODEL` if you want to override the default model

The workflow in [`.github/workflows/daily-digest.yml`](../.github/workflows/daily-digest.yml)
uses `google-github-actions/auth` with:

- `workload_identity_provider`
- `service_account`
- `create_credentials_file: true`
- `export_environment_variables: true`

That makes Application Default Credentials available to the Python Sheets
exporter at runtime.

## 8. Validate The Setup

1. Confirm the spreadsheet is shared with `SERVICE_ACCOUNT_EMAIL`.
2. Confirm the three GitHub repository variables are set.
3. Confirm `id-token: write` is present in the workflow permissions.
4. Run the workflow manually from the GitHub Actions UI.
5. Check that the `Daily_Digest`, `Insights`, and `Raw_Posts` tabs update for
   the new run date.

## Troubleshooting

`403 PERMISSION_DENIED` from Sheets:
- The spreadsheet is not shared with the service account.
- The Google Sheets API is not enabled.

`google.auth.exceptions.DefaultCredentialsError` in the Python step:
- The `google-github-actions/auth` step did not run.
- `id-token: write` is missing.
- The provider or service account repository variable is empty or incorrect.

`iam.serviceAccounts.getAccessToken` or impersonation failures:
- The service account is missing `roles/iam.workloadIdentityUser` for the
  repository principal set.
- The provider resource name is wrong.

OIDC auth works locally but not on GitHub:
- The provider `attribute-condition` may be too restrictive.
- Repository, owner, or branch values may not match the actual workflow run.

Recent IAM changes do not work immediately:
- Wait a few minutes for IAM and provider changes to propagate, then retry the
  workflow.
