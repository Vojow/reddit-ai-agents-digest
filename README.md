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

## Documentation

- [Architecture](docs/architecture.md)
- [Repo invariants](docs/invariants.md)
- [Pipeline stage contracts](docs/pipeline-stages.md)
- [Operations](docs/operations.md)
- [Digest format](docs/digest-format.md)
- [GCP WIF setup](docs/gcp-wif-setup.md)
Copy `.env.example` to `.env` for local reference. The CLI now auto-loads
`<repo>/.env` when it reads config. Exported shell variables still take
precedence over values from `.env`.

Required environment variables for local markdown-only runs:
- `REDDIT_USER_AGENT`

Additional environment variables for local Sheets export:
- `GOOGLE_SHEETS_SPREADSHEET_ID`

Optional runtime environment variables:
- `OPENAI_API_KEY`
- `OPENAI_MODEL` (defaults to `gpt-5-mini`)
- `TEAMS_WEBHOOK_URL`

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

If `TEAMS_WEBHOOK_URL` is set, the pipeline also posts an advisory Teams summary
after local report generation. Teams delivery is best-effort and does not
replace the deterministic markdown as the source of record.

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

## Digest behavior

Thread collection only uses enabled subreddits from `config/subreddits.yaml`.
Primary subreddits are always included, and secondary subreddits only
participate when `INCLUDE_SECONDARY_SUBREDDITS=true`.

The deterministic markdown digest remains the source of record:
- `reports/daily/YYYY-MM-DD.md`
- `reports/latest.md`

When `OPENAI_API_KEY` is available, the pipeline can also write an LLM-enhanced
variant of the same picked topics:
- `reports/daily/YYYY-MM-DD.llm.md`
- `reports/latest.llm.md`

The markdown digest is topic-oriented in both variants:
- `## Executive Summary` describes the day at a high level
- `## Picked Topics` lists the top picked topics for the day
- each topic includes:
  - executive summary
  - relevance for you
  - original post link
  - source subreddit
  - supporting thread count
  - impact score

Topic selection stays deterministic. The LLM-enhanced markdown only rewrites the
top-level executive summary and the prose of already-selected topics into
cleaner wording. It does not choose topics, links, or source subreddits, and
if an advisory rewrite step is unavailable or fails the deterministic markdown
still completes normally.

`Watch Next` is optional. When OpenAI suggestions are unavailable, the pipeline
falls back to up to three insights marked `new`; if neither source is available,
the section is omitted.

If OpenAI quota is exhausted, the pipeline still writes the deterministic
markdown and adds a prominent `## Warnings` section near the top of the report.

## Repository layout

The project uses a `src/` layout and stores:
- raw fetches in `data/raw/`
- normalized artifacts in `data/processed/`
- run state in `data/state/`
- generated reports in `reports/`

Run state now also records OpenAI token usage totals plus Teams publish status
for the completed run.

Before changing pipeline behavior, ranking, or outputs, check the hard behavior
guarantees in [`docs/invariants.md`](docs/invariants.md).
