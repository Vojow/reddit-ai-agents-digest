# Rerun And Failure-Recovery Runbook

Use this runbook when a daily run fails partway through or when you need to
rerun a date safely.

## Authoritative outputs

- The deterministic markdown at `reports/daily/YYYY-MM-DD.md` remains the
  authoritative report for a run date.
- `reports/latest.md` mirrors the latest completed deterministic report.
- LLM markdown, Teams delivery, and OpenAI suggestion artifacts are advisory.
- `data/state/YYYY-MM-DD.json` is the authoritative completion record for that
  run date.

## Safe rerun commands

Markdown-only rerun:

```bash
uv run reddit-digest run-daily --date YYYY-MM-DD --skip-sheets
```

Full rerun with Sheets enabled:

```bash
uv run reddit-digest run-daily --date YYYY-MM-DD
```

Canonical local shortcut for the current markdown-only workflow:

```bash
make run-markdown
```

## Scenario: collection succeeded, later deterministic stage failed

Symptoms:
- `data/raw/` files exist for the date
- deterministic markdown or run state is missing

Recovery:
1. Re-run the same `run_date` with the normal command.
2. Do not delete existing raw or processed files first.

Verify afterward:
- `reports/daily/YYYY-MM-DD.md` exists
- `data/state/YYYY-MM-DD.json` exists
- `data/state/latest.json` matches the rerun if it is the latest completed run

## Scenario: deterministic markdown succeeded, LLM rewrite failed

Symptoms:
- `reports/daily/YYYY-MM-DD.md` exists
- `reports/daily/YYYY-MM-DD.llm.md` is missing
- the deterministic report may contain an OpenAI warning section

Recovery:
1. Treat the deterministic report as complete and authoritative.
2. Re-run the same date only if you want to retry the advisory LLM variant.

Verify afterward:
- `reports/daily/YYYY-MM-DD.md` still exists
- if OpenAI succeeds on rerun, `reports/daily/YYYY-MM-DD.llm.md` may appear
- `data/state/YYYY-MM-DD.json` still points `report_path` at the deterministic markdown

## Scenario: Sheets export failed after local artifacts were written

Symptoms:
- deterministic markdown exists
- `data/state/YYYY-MM-DD.json` may be missing because the pipeline did not finish
- the failing run used Sheets export

Recovery:
1. Fix the Google credential or spreadsheet access problem first.
2. Re-run the same `run_date` without changing local artifacts.

Verify afterward:
- `data/state/YYYY-MM-DD.json` exists
- `sheets_exported` is `true`
- `Raw_Posts`, `Insights`, and `Daily_Digest` contain updated rows for that `run_date` without duplicates

## Scenario: Teams delivery failed

Symptoms:
- deterministic markdown exists
- run state exists
- `teams_published` is `false`
- `teams_error` is populated

Recovery:
1. Decide whether the Teams notification matters for this run.
2. If yes, fix the webhook and rerun the same date.
3. If no, keep the deterministic report and state as-is.

Verify afterward:
- local artifacts remain unchanged except for overwrite-on-rerun behavior
- `teams_published` reflects the rerun outcome

## Scenario: rerun a past date safely

Recovery:
1. Use the exact `--date YYYY-MM-DD` you want to regenerate.
2. Run the pipeline again with the same mode as the original run.
3. Expect overwrite semantics for local files and upsert semantics for Sheets.

Verify afterward:
- the dated report and run-state files for that date were replaced, not duplicated
- `reports/latest.md` only changes if the rerun date is also the latest completed run you just executed
- no extra dated files were created for the same run date

## Quick verification checklist

- `reports/daily/YYYY-MM-DD.md` exists
- `data/state/YYYY-MM-DD.json` exists
- `data/state/latest.json` is current when expected
- no duplicate Google Sheets rows exist for the same `run_date`
- any advisory artifacts that are present match the same deterministic topic set
