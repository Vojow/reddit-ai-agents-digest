# Subagent Operating Model

This repository uses an ad hoc four-role Codex squad for implementation work
that needs delegation. These roles are operating playbooks for Codex sessions,
not production pipeline features.

Use the smallest sufficient squad for the task. Do not spawn all four roles by
default.

## Source of truth

- [`docs/invariants.md`](invariants.md) is the first required read for any
  change that can affect pipeline behavior, outputs, reruns, or delivery.
- This document and the role contracts under `docs/subagents/` are the
  authoritative source of truth for the squad.
- The executable Codex layer lives in project-local subagent files under
  `.codex/agents/`.
- If the docs and `.codex/agents/*.toml` drift, correct the TOML files to
  match the docs.
- The role contracts live in:
  - [`docs/subagents/architect.md`](subagents/architect.md)
  - [`docs/subagents/doc-reader-writer.md`](subagents/doc-reader-writer.md)
  - [`docs/subagents/sdet.md`](subagents/sdet.md)
  - [`docs/subagents/developer.md`](subagents/developer.md)

## Codex runtime layer

Project-local Codex subagents are defined in standalone TOML files:

- `.codex/agents/architect.toml`
- `.codex/agents/doc-reader-writer.toml`
- `.codex/agents/sdet.toml`
- `.codex/agents/developer.toml`

Project-local runtime settings belong in `.codex/config.toml` under `[agents]`.
Do not put these role definitions in `~/.codex/config.toml`.

## Default routing

- Docs-only change: Doc reader/writer only
- Test-only investigation or failing CI: SDET only
- Single-module implementation with no invariant impact: Developer plus SDET
- Cross-stage, config, output-contract, rerun, or delivery change: Architect
  first, then Developer plus SDET, plus Doc reader/writer when behavior or
  operations docs change

## Default role settings

| Role | `agent_type` | Model | Default effort | Escalate to | Write scope | Primary tasks |
|---|---|---|---|---|---|---|
| Architect | `default` | `gpt-5.4` | `high` | `xhigh` for cross-stage or invariant-affecting work | none by default; docs or ADRs only when assigned | task framing, architecture decisions, scope cuts, acceptance criteria, final risk review |
| Doc reader/writer | `worker` | `gpt-5.4-mini` | `medium` | `high` when behavior changes affect multiple docs or ADRs | `docs/**`, `README.md`, `AGENTS.md` | read issues and docs, update docs, runbooks, or ADRs, keep docs and tests aligned |
| SDET | `worker` | `gpt-5.3-codex` | `medium` | `high` for config, reruns, Sheets, OpenAI advisory path, or failing CI | `tests/**` only | reproduce bugs, add or update regression tests, run validation, report failures clearly |
| Developer | `worker` | `gpt-5.3-codex` | `medium` | `high` for `pipeline_stages.py`, `config.py`, `outputs/google_sheets.py`, `outputs/markdown.py`, or `extractors/openai_suggestions.py` | `src/**`, `config/*.yaml` | implement production changes, keep modules typed and scoped, hand off assumptions and risks |

## Working sequence

For medium or large tasks, use this order:

1. Architect reads the issue and [`docs/invariants.md`](invariants.md),
   identifies affected stages, defines acceptance checks, and assigns write
   scopes.
2. Spawn only the needed workers.
3. Developer implements production changes.
4. Doc reader/writer updates docs when behavior, config, outputs, or
   operations changed.
5. SDET adds or updates targeted tests, then runs targeted checks and
   `uv run pytest -q`.
6. Architect reviews the combined result against invariants before final
   handoff.

## Required handoff outputs

- Developer: changed modules, assumptions, risk notes
- Doc reader/writer: changed docs, behavior statements updated, missing-doc
  gaps if any
- SDET: tests added or updated, commands run, failures or residual gaps
- Architect: final acceptance verdict and invariant check

## Role boundaries

- Architect owns task decomposition and acceptance criteria, not routine code
  edits.
- Doc reader/writer updates docs whenever CLI behavior, config, outputs,
  runbooks, or invariants change.
- SDET does not edit `src/**` unless explicitly assigned a test-harness-only
  fix.
- Developer does not edit docs or tests by default; those changes belong to
  Doc reader/writer and SDET so write sets stay disjoint.

## Runtime defaults

The project-local Codex runtime uses:

- `.codex/config.toml`
- `[agents] max_threads = 4`
- `[agents] max_depth = 1`

## Pilot validation

The first validation task for this operating model is the current config drift:

- `config/subreddits.yaml` includes `ClaudeAI`
- tests and docs must align with the authoritative default set
- the existing uncommitted change in `src/reddit_digest/config.py` is treated
  as protected work during that pilot

For this pilot, the config file is authoritative unless a broader product
decision says otherwise.
