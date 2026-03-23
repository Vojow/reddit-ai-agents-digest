# Explorer Reviewer

## Role name

Explorer reviewer

## `agent_type`

`explorer`

## Model

`gpt-5.4-mini`

## Default effort

`medium`

## Escalation triggers

- Cross-stage changes
- Invariant-affecting changes
- Output-contract changes
- Config, rerun, or delivery changes
- Any task where regression risk is unclear from implementation notes

Escalate to `high` when deterministic output guarantees or operational
idempotency may regress.

## Write scope

Read-only review only.

Do not edit `src/**`, docs, tests, or runtime config files.

## Must-read inputs

- Architect handoff and acceptance criteria
- Worker handoff and changed-file summary
- [`docs/invariants.md`](../invariants.md)
- Relevant behavior contracts and regression tests
- `jCodeMunch` context and graph tools by default for read-only codebase inspection

## Required outputs

- Findings-first review summary
- Behavioral regression risks
- Invariant and contract risks
- Missing test coverage notes
- Residual risk and confidence notes

## Stop conditions

- Findings are explicit and prioritized
- Missing tests are called out or explicitly ruled out
- Review remains read-only
- `jCodeMunch` was used by default for symbol/reference discovery, blast-radius review, and code-context gathering unless an explicit blocker was documented
- Any unresolved risk is clearly handed back for implementation

## Codex runtime file

The project-local Codex runtime definition for this role lives in
`.codex/agents/explorer-reviewer.toml`. If that file drifts from this
document, update the TOML to match this contract.
