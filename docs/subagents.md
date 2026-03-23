# Subagent Operating Model

This repository uses a five-role Codex squad for delegated implementation work.
These roles are operating playbooks for Codex sessions, not production pipeline
features.

Use the smallest sufficient squad for the task. Do not spawn every role by
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
  - [`docs/subagents/worker.md`](subagents/worker.md)
  - [`docs/subagents/explorer-reviewer.md`](subagents/explorer-reviewer.md)
  - [`docs/subagents/doc-reader-writer.md`](subagents/doc-reader-writer.md)
  - [`docs/subagents/sdet.md`](subagents/sdet.md)

## Codex runtime layer

Project-local Codex subagents are defined in standalone TOML files:

- `.codex/agents/architect.toml`
- `.codex/agents/worker.toml`
- `.codex/agents/explorer-reviewer.toml`
- `.codex/agents/doc-reader-writer.toml`
- `.codex/agents/sdet.toml`

Project-local runtime settings belong in `.codex/config.toml` under `[agents]`.
Do not put these role definitions in `~/.codex/config.toml`.

## Default routing

- Parent-chat default for non-trivial production changes in `src/**`:
  the main/parent Codex chat is treated as Architect.
- Docs-only change: Doc reader/writer only
- Test-only investigation or failing CI: SDET only
- Non-trivial production code changes in `src/**`: mandatory delegation
  using Architect, Worker, and Explorer reviewer at minimum
- Cross-stage, config, output-contract, rerun, or delivery changes:
  Architect first, then Worker, then Explorer reviewer, plus Doc
  reader/writer and SDET when docs/tests are in scope

Mandatory delegation rule:
- The parent agent must not keep production implementation local when the task
  affects `src/**` beyond a trivial one-file fix.
- That parent Architect chat frames scope and acceptance criteria, delegates
  implementation to Worker, and delegates review to Explorer reviewer.

## Default role settings

| Role | `agent_type` | Model | Default effort | Escalate to | Write scope | Primary tasks |
|---|---|---|---|---|---|---|
| Architect | `default` | `gpt-5.4` | `high` | `xhigh` for cross-stage or invariant-affecting work | none by default; docs or ADRs only when assigned | task framing, architecture decisions, scope cuts, acceptance criteria, final risk review; uses `Context7` by default for external library/framework/API docs |
| Worker | `worker` | `gpt-5.3-codex` | `medium` | `high` for `pipeline_stages.py`, `config.py`, `outputs/google_sheets.py`, `outputs/markdown.py`, or `extractors/openai_suggestions.py` | `src/**`, `config/*.yaml` when assigned | implement production changes with narrow scope and explicit assumptions |
| Explorer reviewer | `explorer` | `gpt-5.4-mini` | `medium` | `high` when deterministic output, reruns, delivery, or contracts may regress | read-only | findings-first review for regressions, invariant risk, and missing tests; uses `jCodeMunch` by default for codebase inspection |
| Doc reader/writer | `worker` | `gpt-5.4-mini` | `medium` | `high` when behavior changes affect multiple docs or ADRs | `docs/**`, `README.md`, `AGENTS.md` | read issues and docs, update docs, runbooks, or ADRs, keep docs and tests aligned; uses `Context7` by default for upstream product/library docs |
| SDET | `worker` | `gpt-5.3-codex` | `medium` | `high` for config, reruns, Sheets, OpenAI advisory path, or failing CI | `tests/**` only | reproduce bugs, add or update regression tests, run validation, report failures clearly; uses `jCodeMunch` by default for impact discovery |

## Working sequence

For non-trivial production changes, use this order:

1. Architect reads the issue and [`docs/invariants.md`](invariants.md),
   identifies affected stages, defines acceptance checks, and assigns write
   scopes.
2. Worker implements production changes within assigned write scope.
3. Explorer reviewer runs a read-only, findings-first review for regression and
   invariant risk.
4. Doc reader/writer updates docs when behavior, config, outputs, or
   operations changed.
5. SDET adds or updates targeted tests, then runs targeted checks and
   `uv run pytest -q`.
6. Architect reviews the combined result against invariants before final
   handoff.

## Required handoff outputs

- Worker: changed modules, assumptions, risk notes
- Explorer reviewer: findings-first review, missing-test gaps, residual risks
- Doc reader/writer: changed docs, behavior statements updated, missing-doc
  gaps if any
- SDET: tests added or updated, commands run, failures or residual gaps
- Architect: final acceptance verdict and invariant check

## Role boundaries

- Architect owns task decomposition and acceptance criteria, not routine code
  edits.
- Architect should use `Context7` by default when planning depends on external
  library/framework/API docs; repo-local codebase inspection should use local
  repo context and assigned analysis tools.
- Worker owns production edits, not docs/tests by default.
- Explorer reviewer is read-only and does not implement fixes.
- Explorer reviewer should use `jCodeMunch` by default for symbol and reference discovery, blast-radius review, and code-context gathering.
- Doc reader/writer updates docs whenever CLI behavior, config, outputs,
  runbooks, or invariants change.
- Doc reader/writer should use `Context7` by default when README/runbook/doc
  updates depend on upstream product/library docs; repo-local inspection
  remains local-context first.
- SDET does not edit `src/**` unless explicitly assigned a test-harness-only
  fix.
- SDET should use `jCodeMunch` by default for test-impact discovery, reference search, affected-file discovery, and code/test context gathering before writing tests.
- Parent agent must enforce mandatory delegation for non-trivial `src/**` work
  and should not implement those changes locally.

## Runtime defaults

The project-local Codex runtime uses:

- `.codex/config.toml`
- `[agents] max_threads = 4`
- `[agents] max_depth = 1`
