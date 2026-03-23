# Operations

## Local setup

```bash
uv sync --dev
```

The CLI auto-loads `.env` from the repository root when config is read.
Exported environment variables still override values from `.env`.
In linked git worktrees, if the current worktree does not have a `.env`, the
CLI falls back to the primary worktree's `.env`.

Required environment variables for local markdown-only runs:
- `REDDIT_USER_AGENT`

Additional environment variables for the full local pipeline:
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
- `TEAMS_WEBHOOK_URL`
- `INCLUDE_SECONDARY_SUBREDDITS`
- `LOOKBACK_HOURS`
- `MIN_POST_SCORE`
- `MIN_COMMENTS`
- `MAX_POSTS_PER_SUBREDDIT`
- `MAX_COMMENTS_PER_POST`

`OPENAI_MODEL` defaults to `gpt-5-mini` when it is unset.

## CLI reference

The CLI entrypoint is `reddit-digest` and currently exposes one subcommand:

```bash
uv run reddit-digest run-daily --date 2026-03-12
```

Supported flags:
- `--date YYYY-MM-DD` selects the run date and defaults to the current day.
- `--skip-sheets` skips Google Sheets export and only writes local artifacts.
- `--markdown-only` skips OpenAI suggestions and LLM rewrite outputs.
- `--base-path PATH` runs the pipeline against a different repository root.

## Run locally

Run the markdown-only pipeline:

```bash
make run-markdown
```

`make run-markdown` routes through `scripts/run_markdown_with_env.sh`, which is
the preferred entrypoint for automations and fresh linked worktrees. The helper
looks up `uv` from common install locations when the automation shell has a
thin `PATH` and reuses the primary worktree `.env` when the current worktree
does not have one yet.

Run the full pipeline including advisory OpenAI stages and Sheets export:

```bash
uv run reddit-digest run-daily --date 2026-03-12
```

## Output locations

Schema details for these artifact families live in
[`docs/artifact-schemas.md`](artifact-schemas.md).

- Raw posts: `data/raw/posts/YYYY-MM-DD.json`
- Raw comments: `data/raw/comments/YYYY-MM-DD.json`
- Processed posts: `data/processed/posts/YYYY-MM-DD.json`
- Processed comments: `data/processed/comments/YYYY-MM-DD.json`
- Processed insights: `data/processed/insights/YYYY-MM-DD.json`
- OpenAI suggestions: `data/processed/suggestions/YYYY-MM-DD.json`
- OpenAI topic rewrites: `data/processed/topic_rewrites/YYYY-MM-DD.json`
- OpenAI executive summary rewrites: `data/processed/executive_summary_rewrites/YYYY-MM-DD.json`
- Deterministic daily digest: `reports/daily/YYYY-MM-DD.md`
- Deterministic latest digest: `reports/latest.md`
- LLM daily digest: `reports/daily/YYYY-MM-DD.llm.md`
- LLM latest digest: `reports/latest.llm.md`
- Run state: `data/state/YYYY-MM-DD.json`
- Latest run state mirror: `data/state/latest.json`

When `TEAMS_WEBHOOK_URL` is configured, the pipeline also sends a best-effort
Teams summary that includes:
- the selected report variant
- the LLM executive summary when an LLM variant is present
- top picked topics
- emerging theme labels
- watch-next items
- OpenAI token usage totals for the run

## Google Sheets tabs

When Sheets export is enabled, the exporter rewrites these tabs idempotently by
`run_date`:
- `Raw_Posts` stores one scored row per collected post.
- `Insights` stores one scored row per extracted insight.
- `Daily_Digest` stores one summary row per daily report.

## Ranking behavior

- Only enabled subreddits contribute to thread ranking and topic source
  grounding.
- `INCLUDE_SECONDARY_SUBREDDITS=false` means secondary subreddits do not
  contribute threads or source posts.
- Topic selection is deterministic and derived from scored insights.
- The deterministic markdown and the LLM markdown use the same selected topics.
- The LLM variant may rewrite the top-level `Executive Summary` and `Picked
  Topics` prose. It does not change topic titles, links, subreddit attribution,
  scores, or counts.

## Failure handling

Scenario-based rerun and recovery steps are documented in
[`docs/rerun-runbook.md`](rerun-runbook.md).

- Networked stages retry up to three times.
- Same-day reruns overwrite file outputs deterministically.
- The deterministic markdown remains the source-of-record output for each run.
- The LLM markdown variant is best-effort; if advisory rewriting fails, the
  deterministic markdown and run state still complete.
- If OpenAI quota is exhausted, the deterministic markdown still completes and
  includes a prominent `## Warnings` section explaining that advisory OpenAI
  outputs were skipped.
- When OpenAI suggestions are unavailable, `Watch Next` falls back to up to
  three insights marked `new`.
- Sheets export replaces existing rows for the same `run_date`.
- Teams delivery is advisory-only. A webhook failure is recorded in run state
  and logged as a warning, but it does not fail the deterministic pipeline.
- The latest completed state is mirrored into `data/state/latest.json`.

## GitHub Actions

The scheduled workflow lives at `.github/workflows/daily-digest.yml`.

It supports:
- daily scheduled runs at `07:00 UTC`
- manual dispatch from the GitHub Actions UI
- markdown generation without Google Sheets export
- execution on a `self-hosted` runner only

Repository variables required for the current workflow:
- `REDDIT_USER_AGENT`

Optional repository variables:
- `OPENAI_MODEL`

GitHub-hosted runners are not supported for live Reddit collection because
Reddit blocks the public JSON requests from those runner networks. The workflow
therefore runs only on a `self-hosted` runner and uses the same canonical local
command as manual execution: `make run-markdown`.

Optional secrets:
- `OPENAI_API_KEY`

The workflow currently runs markdown-only, so Google auth is not required in CI
for the current markdown-only workflow. It emits only the deterministic
markdown, even if `OPENAI_API_KEY` is present. If you later want Sheets export
in self-hosted CI, use the runbook in
[`docs/gcp-wif-setup.md`](gcp-wif-setup.md) and reintroduce the OIDC auth step.

On workflow failure, the action uploads `reports/`, `data/processed/`, and
`data/state/` as an artifact for debugging.
