# Operations

## Local setup

```bash
uv sync --dev
```

Required environment variables for the full pipeline:
- `REDDIT_USER_AGENT`
- `GOOGLE_SHEETS_SPREADSHEET_ID`

Google authentication for local Sheets export can come from either:
- ambient Application Default Credentials, including Workload Identity Federation in CI
- `GOOGLE_SERVICE_ACCOUNT_JSON` as a backward-compatible local fallback

Local development differs from CI:
- CI gets short-lived Google credentials from GitHub OIDC and Workload Identity Federation.
- Local runs should use Application Default Credentials first, for example via `gcloud auth application-default login`.
- `GOOGLE_SERVICE_ACCOUNT_JSON` is only a local fallback when ADC is not available.

Optional environment variables:
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `INCLUDE_SECONDARY_SUBREDDITS`
- `LOOKBACK_HOURS`
- `MIN_POST_SCORE`
- `MIN_COMMENTS`
- `MAX_POSTS_PER_SUBREDDIT`
- `MAX_COMMENTS_PER_POST`

## Run locally

Run the full pipeline without Sheets export:

```bash
uv run reddit-digest run-daily --date 2026-03-12 --skip-sheets
```

Run the full pipeline including Sheets export:

```bash
uv run reddit-digest run-daily --date 2026-03-12
```

## Output locations

- Raw posts: `data/raw/posts/YYYY-MM-DD.json`
- Raw comments: `data/raw/comments/YYYY-MM-DD.json`
- Processed posts: `data/processed/posts/YYYY-MM-DD.json`
- Processed comments: `data/processed/comments/YYYY-MM-DD.json`
- Processed insights: `data/processed/insights/YYYY-MM-DD.json`
- OpenAI suggestions: `data/processed/suggestions/YYYY-MM-DD.json`
- Daily digest: `reports/daily/YYYY-MM-DD.md`
- Latest digest: `reports/latest.md`
- Run state: `data/state/YYYY-MM-DD.json`

## Failure handling

- Networked stages retry up to three times.
- Same-day reruns overwrite file outputs deterministically.
- Sheets export replaces existing rows for the same `run_date`.
- The latest completed state is mirrored into `data/state/latest.json`.

## GitHub Actions

The scheduled workflow lives at `.github/workflows/daily-digest.yml`.

It supports:
- daily scheduled runs at `07:00 UTC`
- manual dispatch from the GitHub Actions UI
- markdown generation without Google Sheets export

Repository secrets required for the full automated run:
- `REDDIT_USER_AGENT`

Optional secrets:
- `OPENAI_API_KEY`
- `OPENAI_MODEL`

The workflow currently runs `uv run reddit-digest run-daily --skip-sheets`, so
Google auth is not required in CI. If you later want Sheets export in GitHub
Actions, use the runbook in [`docs/gcp-wif-setup.md`](gcp-wif-setup.md) and
reintroduce the OIDC auth step.

On workflow failure, the action uploads `reports/`, `data/processed/`, and
`data/state/` as an artifact for debugging.
