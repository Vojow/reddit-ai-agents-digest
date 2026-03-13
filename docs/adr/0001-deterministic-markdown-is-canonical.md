# ADR-0001 Deterministic markdown is the canonical report

- Status: Accepted

## Context

The pipeline can emit multiple artifacts for the same run date, including an
optional LLM-enhanced markdown variant, Google Sheets rows, and advisory Teams
notifications. Operators still need one authoritative report per run date.

## Decision

The deterministic markdown at `reports/daily/YYYY-MM-DD.md` is the canonical
report for a run. `reports/latest.md` is the latest mirror of that canonical
report.

## Consequences

- Run state points at the deterministic markdown, not the LLM variant.
- Advisory outputs may fail without invalidating the canonical report.
- Review and recovery logic should treat deterministic markdown generation as
  the critical path.
