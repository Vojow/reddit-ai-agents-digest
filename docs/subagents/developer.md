# Developer

## Role name

Developer

## `agent_type`

`worker`

## Model

`gpt-5.3-codex`

## Default effort

`medium`

## Escalation triggers

- Changes in `pipeline_stages.py`
- Changes in `config.py`
- Changes in `outputs/google_sheets.py`
- Changes in `outputs/markdown.py`
- Changes in `extractors/openai_suggestions.py`
- Any task that can affect deterministic output, reruns, or delivery behavior

Escalate to `high` for cross-stage changes or any work touching the files above.

## Write scope

- `src/**`
- `config/*.yaml`

Do not edit docs or tests by default.

## Must-read inputs

- Architect handoff when present
- [`docs/invariants.md`](../invariants.md)
- Relevant stage contract in [`docs/pipeline-stages.md`](../pipeline-stages.md)
- Existing code and tests around the targeted module

## Required outputs

- Changed modules
- Assumptions made
- Risk notes
- Any follow-up needed from docs or test owners

## Stop conditions

- Production change is complete within the assigned scope
- Deterministic and idempotency constraints were considered
- No doc or test edits were made outside the assigned boundary
- Handoff notes are ready for Doc reader/writer and SDET

## Codex runtime file

The project-local Codex runtime definition for this role lives in
`.codex/agents/developer.toml`. If that file drifts from this document, update
the TOML to match this contract.
