# ADR-0005 Same-day reruns use overwrite and upsert semantics

- Status: Accepted

## Context

Daily pipelines need safe reruns after partial failures without multiplying
dated files or downstream sheet rows for the same run date.

## Decision

Same-day reruns overwrite local dated artifacts for that `run_date`, refresh the
latest mirrors, and upsert Google Sheets rows by `run_date`-scoped keys instead
of appending duplicates.

## Consequences

- Operators can rerun a date without manual cleanup.
- The pipeline must continue to treat idempotency as a non-negotiable behavior.
- Any future sink added to the delivery stage should define comparable rerun
  semantics before it is treated as production-ready.
