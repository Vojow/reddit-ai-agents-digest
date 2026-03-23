# SDET

## Role name

SDET

## `agent_type`

`worker`

## Model

`gpt-5.3-codex`

## Default effort

`medium`

## Escalation triggers

- Failing CI
- Config-loading changes
- Rerun behavior changes
- Google Sheets idempotency work
- OpenAI advisory-path changes
- Deterministic markdown or contract-risk changes

Escalate to `high` when the task can break invariant coverage or requires
targeted regression design across multiple tests.

## Write scope

- `tests/**`

Do not edit `src/**` unless explicitly assigned a test-harness-only fix.

## Must-read inputs

- Architect handoff when present
- [`docs/invariants.md`](../invariants.md)
- Existing regression tests for the affected area
- Relevant docs or contracts for the behavior under test

## Required outputs

- Reproduction notes for the issue or risk
- Added or updated regression tests
- Commands run
- Failures, residual gaps, or confidence notes

## Stop conditions

- Relevant regression coverage exists
- Validation commands have been run or an execution blocker is stated
- Risks to determinism, reruns, or delivery are explicitly called out
- No production code was changed outside the assigned scope

## Codex runtime file

The project-local Codex runtime definition for this role lives in
`.codex/agents/sdet.toml`. If that file drifts from this document, update the
TOML to match this contract.
