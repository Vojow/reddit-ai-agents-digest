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

Key runtime environment variables:
- `REDDIT_USER_AGENT`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_SERVICE_ACCOUNT_EMAIL`
- `GOOGLE_SERVICE_ACCOUNT_JSON`
- `GOOGLE_SHEETS_SPREADSHEET_ID`

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
`GOOGLE_SERVICE_ACCOUNT_JSON` input remains a backward-compatible fallback until
the workflow migration is completed.

## Repository layout

The project uses a `src/` layout and stores:
- raw fetches in `data/raw/`
- normalized artifacts in `data/processed/`
- run state in `data/state/`
- generated reports in `reports/`
