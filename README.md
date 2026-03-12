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

Run the markdown-only digest locally:

```bash
make run-markdown
```

Run tests:

```bash
uv run pytest
```

Copy `.env.example` to `.env` for local reference, then export the values in your
shell or load them with your preferred environment tool before running commands.

Required environment variables for local markdown-only runs:
- `REDDIT_USER_AGENT`

Additional environment variables for local Sheets export:
- `GOOGLE_SHEETS_SPREADSHEET_ID`

Optional runtime environment variables:
- `OPENAI_API_KEY`
- `OPENAI_MODEL`

Google Sheets authentication for local runs can come from:
- Application Default Credentials
- `GOOGLE_SERVICE_ACCOUNT_JSON` as a backward-compatible local fallback

GitHub Actions repository variables for the current markdown-only workflow:
- `REDDIT_USER_AGENT`
- `OPENAI_MODEL`

GitHub Actions repository variables for future Sheets export:
- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_SERVICE_ACCOUNT_EMAIL`
- `GOOGLE_SHEETS_SPREADSHEET_ID`

GitHub Actions secrets:
- `OPENAI_API_KEY`

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

The supported automated execution path is now a GitHub Actions `self-hosted`
runner or a direct local run on the same machine. GitHub-hosted runners are not
supported for live Reddit collection because Reddit blocks the public JSON
requests from those runner IPs. The canonical markdown-only command is
`make run-markdown`.

The self-hosted GitHub Actions workflow runs the markdown pipeline only with
`--skip-sheets`, so it does not require Google credentials. When you want to
re-enable Google Sheets export in self-hosted CI, use the setup runbook in
[`docs/gcp-wif-setup.md`](docs/gcp-wif-setup.md).
Google Sheets export in CI is currently disabled by design.

## Digest ranking behavior

Thread ranking only uses enabled subreddits from `config/subreddits.yaml`.
Primary subreddits are always included, and secondary subreddits only
participate when `INCLUDE_SECONDARY_SUBREDDITS=true`.

The digest renders:
- `## Notable Threads` as a diversified global top 5 across enabled
  subreddits
- `## Top Threads By Subreddit` as the top 3 threads for each enabled
  subreddit

The global top 5 uses the existing deterministic score formula and applies a
minimal diversity rule: if ranked candidates exist in more than one enabled
subreddit, the final top 5 will include at least 2 distinct subreddits.

## Repository layout

The project uses a `src/` layout and stores:
- raw fetches in `data/raw/`
- normalized artifacts in `data/processed/`
- run state in `data/state/`
- generated reports in `reports/`
