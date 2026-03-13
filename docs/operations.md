# Operations

## Local setup

```bash
uv sync --dev
```

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
- `INCLUDE_SECONDARY_SUBREDDITS`
- `LOOKBACK_HOURS`
- `MIN_POST_SCORE`
- `MIN_COMMENTS`
- `MAX_POSTS_PER_SUBREDDIT`
- `MAX_COMMENTS_PER_POST`

## Run locally

Run the markdown-only pipeline:

```bash
make run-markdown
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
- OpenAI topic rewrites: `data/processed/topic_rewrites/YYYY-MM-DD.json`
- Deterministic daily digest: `reports/daily/YYYY-MM-DD.md`
- Deterministic latest digest: `reports/latest.md`
- LLM daily digest: `reports/daily/YYYY-MM-DD.llm.md`
- LLM latest digest: `reports/latest.llm.md`
- Run state: `data/state/YYYY-MM-DD.json`

## Ranking behavior

- Only enabled subreddits contribute to thread ranking and topic source
  grounding.
- `INCLUDE_SECONDARY_SUBREDDITS=false` means secondary subreddits do not
  contribute threads or source posts.
- Topic selection is deterministic and derived from scored insights.
- The deterministic markdown and the LLM markdown use the same selected topics.
- The LLM variant only rewrites `Picked Topics` prose. It does not change topic
  titles, links, subreddit attribution, scores, or counts.

## Failure handling

- Networked stages retry up to three times.
- Same-day reruns overwrite file outputs deterministically.
- The deterministic markdown remains the source-of-record output for each run.
- The LLM markdown variant is best-effort; if topic rewriting fails, the
  deterministic markdown and run state still complete.
- Sheets export replaces existing rows for the same `run_date`.
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
for the current markdown-only workflow. If `OPENAI_API_KEY` is present, the
workflow can emit both markdown variants; otherwise it emits only the
deterministic markdown. If you later want Sheets export in self-hosted CI, use
the runbook in
[`docs/gcp-wif-setup.md`](gcp-wif-setup.md) and reintroduce the OIDC auth step.

On workflow failure, the action uploads `reports/`, `data/processed/`, and
`data/state/` as an artifact for debugging.
