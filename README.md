# reddit-ai-agents-digest

Daily Reddit intelligence pipeline for:
- AI agents
- AI-enhanced development
- AI-enhanced testing

## Local setup

Requirements:
- Python 3.12
- `uv`

Install dependencies:

```bash
uv sync --dev
```

Run the package entrypoint:

```bash
uv run reddit-digest --help
```

Run the full daily pipeline locally without Sheets export:

```bash
uv run reddit-digest run-daily --date 2026-03-12 --skip-sheets
```

Run tests:

```bash
uv run pytest
```

Copy `.env.example` to `.env` for local reference, then export the values in your
shell or load them with your preferred environment tool before running commands.

Core runtime environment variables:
- `REDDIT_USER_AGENT`
- `GOOGLE_SHEETS_SPREADSHEET_ID`

Optional runtime environment variables:
- `OPENAI_API_KEY`
- `OPENAI_MODEL`

Google Sheets authentication for local runs can come from:
- Application Default Credentials
- `GOOGLE_SERVICE_ACCOUNT_JSON` as a backward-compatible local fallback

GitHub Actions repository variables for Sheets:
- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_SERVICE_ACCOUNT_EMAIL`
- `GOOGLE_SHEETS_SPREADSHEET_ID`

GitHub Actions secrets:
- `REDDIT_USER_AGENT`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`

Supported runtime overrides:
- `INCLUDE_SECONDARY_SUBREDDITS`
- `LOOKBACK_HOURS`
- `MIN_POST_SCORE`
- `MIN_COMMENTS`
- `MAX_POSTS_PER_SUBREDDIT`
- `MAX_COMMENTS_PER_POST`

If `OPENAI_API_KEY` is set, the pipeline will also generate additive `Watch Next`
content suggestions and candidate new sources based only on the day’s collected
findings.

For MVP ingestion, Reddit app credentials are not required. The live collectors
use Reddit's public JSON endpoints with a configurable `REDDIT_USER_AGENT`.

Google Sheets export now supports ambient Google credentials from Application
Default Credentials, including Workload Identity Federation in CI. The existing
`GOOGLE_SERVICE_ACCOUNT_JSON` input remains a backward-compatible local
fallback.

The GitHub Actions workflow now authenticates to Google Cloud with OIDC via
`google-github-actions/auth`. Set `GCP_WORKLOAD_IDENTITY_PROVIDER`,
`GCP_SERVICE_ACCOUNT_EMAIL`, and `GOOGLE_SHEETS_SPREADSHEET_ID` as repository
variables for CI; do not store a Google service account JSON key in GitHub.

## Repository layout

The project uses a `src/` layout and stores:
- raw fetches in `data/raw/`
- normalized artifacts in `data/processed/`
- run state in `data/state/`
- generated reports in `reports/`
