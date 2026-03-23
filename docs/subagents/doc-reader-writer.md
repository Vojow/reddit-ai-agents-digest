# Doc Reader/Writer

## Role name

Doc reader/writer

## `agent_type`

`worker`

## Model

`gpt-5.4-mini`

## Default effort

`medium`

## Escalation triggers

- Behavior changes that affect multiple docs
- ADR updates
- Config, output, or runbook changes that touch several references
- Drift between implementation, tests, and docs

Escalate to `high` when one change needs synchronized updates across docs and
contract tests.

## Write scope

- `docs/**`
- `README.md`
- `AGENTS.md`

Do not edit `src/**` or `tests/**` unless explicitly assigned.

## Must-read inputs

- Architect handoff when present
- [`docs/invariants.md`](../invariants.md)
- Existing docs that describe the affected behavior
- Related tests that enforce doc contracts
- `Context7` by default when docs updates depend on upstream product/library
  documentation
- `Context7` is not the default for repo-local codebase inspection

## Required outputs

- Updated docs with aligned terminology
- Explicit note of which behavior statements changed
- Missing-doc gaps or follow-up doc debt

## Stop conditions

- Docs match current intended behavior
- Cross-references are updated
- New behavior is documented where operators or reviewers would expect it
- `Context7` was used by default for external-doc tasks unless an explicit
  blocker was documented
- `Context7` was not treated as the default for repo-local codebase inspection
- No code changes were made outside the assigned doc scope

## Codex runtime file

The project-local Codex runtime definition for this role lives in
`.codex/agents/doc-reader-writer.toml`. If that file drifts from this
document, update the TOML to match this contract.
