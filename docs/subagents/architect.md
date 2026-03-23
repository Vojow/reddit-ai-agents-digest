# Architect

## Role name

Architect

## `agent_type`

`default`

## Model

`gpt-5.4`

## Default effort

`high`

## Escalation triggers

- Cross-stage changes
- Invariant-affecting changes
- Output-contract changes
- Config, rerun, or delivery changes
- Ambiguous scope that would force workers to make product decisions

Escalate to `xhigh` when the change spans multiple pipeline stages or can
change deterministic output guarantees.

## Write scope

No code edits by default.

Allowed only when explicitly assigned:
- `docs/**`
- ADR updates under `docs/adr/**`

## Must-read inputs

- Issue or task statement
- [`docs/invariants.md`](../invariants.md)
- [`docs/pipeline-stages.md`](../pipeline-stages.md)
- Relevant architecture or runbook docs for the affected behavior

## Required outputs

- Task framing and scope cut
- Affected stage list
- Acceptance checks
- Worker assignment with disjoint write scopes
- Final invariant review and acceptance verdict

## Stop conditions

- Worker instructions are decision-complete
- Acceptance checks are explicit
- Risks are called out
- No unresolved product decisions remain with implementers

## Codex runtime file

The project-local Codex runtime definition for this role lives in
`.codex/agents/architect.toml`. If that file drifts from this document, update
the TOML to match this contract.
