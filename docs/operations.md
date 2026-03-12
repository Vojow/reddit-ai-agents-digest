# Operations

## Local setup

```bash
uv sync --dev
```

Required environment variables for the full pipeline:
- `REDDIT_USER_AGENT`
- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_SERVICE_ACCOUNT_EMAIL`
- `GOOGLE_SERVICE_ACCOUNT_JSON`
- `GOOGLE_SHEETS_SPREADSHEET_ID`

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

Repository secrets required for the full automated run:
- `REDDIT_USER_AGENT`
- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_SERVICE_ACCOUNT_EMAIL`
- `GOOGLE_SERVICE_ACCOUNT_JSON`
- `GOOGLE_SHEETS_SPREADSHEET_ID`

Optional secrets:
- `OPENAI_API_KEY`
- `OPENAI_MODEL`

On workflow failure, the action uploads `reports/`, `data/processed/`, and
`data/state/` as an artifact for debugging.
