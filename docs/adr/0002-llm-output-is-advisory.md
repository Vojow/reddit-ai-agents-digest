# ADR-0002 LLM output is advisory only

- Status: Accepted

## Context

OpenAI is useful for suggestions and clearer prose, but topic selection and
source attribution need to remain inspectable and deterministic.

## Decision

OpenAI output is advisory only. It may generate `Watch Next` suggestions and
rewrite topic prose, but it must not choose same-day topics or alter
deterministic topic titles, links, subreddit attribution, counts, or scores.

## Consequences

- The LLM markdown variant uses the same picked topics as the deterministic digest.
- Quota and rate-limit issues degrade to deterministic-only output where documented.
- Future LLM features should attach to advisory stages unless the design is
  intentionally changed with a new ADR.
