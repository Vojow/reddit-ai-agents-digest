# ADR-0003 Public Reddit JSON endpoints are the MVP ingestion path

- Status: Accepted

## Context

Reddit app credentials were not reliably available for MVP development, but the
project still needed live subreddit ingestion.

## Decision

MVP ingestion uses Reddit’s public JSON endpoints with a configurable
`REDDIT_USER_AGENT`, while preserving the ability to support authenticated
collectors later.

## Consequences

- Local and self-hosted runs can collect live Reddit data without app keys.
- GitHub-hosted runners are susceptible to source blocking by Reddit.
- Collection artifacts preserve enough raw payload detail to support later
  collector changes without changing downstream deterministic contracts.
