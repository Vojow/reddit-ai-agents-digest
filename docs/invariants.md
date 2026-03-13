# Repo Invariants

Use this as the pre-change checklist for any pipeline, output, or docs change.

## Source of record

- `reports/daily/YYYY-MM-DD.md` is the canonical report for a run.
- `reports/latest.md` is only the latest mirror of that deterministic report.
- `reports/daily/YYYY-MM-DD.llm.md` and `reports/latest.llm.md` are advisory variants, not the source of record.

## Deterministic behavior

- The same input artifacts for the same run date must produce the same deterministic markdown.
- Topic selection is deterministic and must stay grounded in collected Reddit posts and extracted insights.
- Enabled subreddit filtering must remain correct; disabled subreddits must not influence ranked threads or picked topics.
- Markdown structure must continue to follow the documented digest contract.

## LLM constraints

- OpenAI output is advisory only.
- LLM rewrites may only rewrite prose for already selected topics.
- LLM output must not change topic titles, source links, source subreddit attribution, support counts, or scores.
- If OpenAI steps fail or quota is exhausted, the deterministic markdown still completes successfully.

## Idempotency and reruns

- Same-day reruns overwrite file outputs for that `run_date`; they do not create parallel copies.
- `data/state/latest.json` mirrors the latest completed run state and should be replaced on rerun.
- Google Sheets export must upsert by `run_date` and must not create duplicate rows for the same date.

## Artifact ownership

- Raw API payloads belong in `data/raw/`.
- Normalized and derived JSON artifacts belong in `data/processed/`.
- Run metadata belongs in `data/state/`.
- Advisory delivery channels such as Teams must not replace local file artifacts as the authoritative output.

## Failure behavior

- Exceptions should not be silently swallowed.
- Deterministic local artifacts should survive advisory-stage failures where documented.
- Teams delivery remains best-effort and must not fail the deterministic pipeline.
