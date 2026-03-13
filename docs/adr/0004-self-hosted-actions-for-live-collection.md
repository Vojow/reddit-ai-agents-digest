# ADR-0004 Self-hosted GitHub Actions is required for live collection

- Status: Accepted

## Context

GitHub-hosted Actions runners were blocked by Reddit when using the public JSON
ingestion path, which prevented reliable scheduled collection.

## Decision

The supported GitHub Actions path for live Reddit collection is a `self-hosted`
runner. GitHub-hosted runners are not a supported live-collection environment
for the current ingestion model.

## Consequences

- The workflow remains markdown-only by default in CI unless explicitly
  reconfigured for other outputs.
- Local runs and self-hosted runs share the same canonical command path.
- Any return to GitHub-hosted live collection would require either a collector
  model change or a new ADR.
