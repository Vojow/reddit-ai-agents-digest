# Pipeline Stage Contracts

This is the contract reference for where behavior belongs in the pipeline.

## 1. Config and composition

- Responsibility: load runtime config and compose concrete stage dependencies.
- Entry point: `src/reddit_digest/pipeline.py`
- Inputs: repo root, environment variables, YAML config, CLI flags
- Outputs: a `PipelineRunContext` plus concrete stage objects
- Status: deterministic
- Failure behavior: missing required config fails the run before collection starts
- Extension guidance: add new runtime dependencies at the composition boundary instead of constructing them inside downstream stage logic

## 2. Collection stage

- Responsibility: collect raw Reddit posts and comments for enabled subreddits
- Entry point: `CollectionStage` in `src/reddit_digest/pipeline_stages.py`
- Inputs: `PipelineRunContext`
- Outputs: raw post/comment paths plus collected posts/comments
- Status: deterministic for a fixed upstream Reddit response set
- Failure behavior: network failures retry; exhausted retries fail the run
- Extension guidance: add new collection sources under `src/reddit_digest/collectors/` and wire them through the collection stage rather than changing render/export logic

## 3. Analysis stage

- Responsibility: extract insights, apply novelty classification, rank threads, and select picked topics
- Entry point: `AnalysisStage` in `src/reddit_digest/pipeline_stages.py`
- Inputs: collected posts/comments plus scoring and subreddit config
- Outputs: processed insights path, novelty-tagged insights, ranked thread selection, picked topics
- Status: deterministic
- Failure behavior: analysis errors fail the run because downstream stages require these artifacts
- Extension guidance:
  - add new extraction rules under `src/reddit_digest/extractors/`
  - change thread ranking under `src/reddit_digest/ranking/threads.py`
  - keep topic selection grounded in ranked enabled-subreddit source posts

## 4. OpenAI advisory stage

- Responsibility: generate `Watch Next` suggestions plus optional executive-summary and topic-prose rewrites
- Entry point: `OpenAIStage` in `src/reddit_digest/pipeline_stages.py`
- Inputs: collected posts, analyzed insights, picked topics, OpenAI runtime config
- Outputs: advisory watch-next strings, optional topic rewrites, optional executive summary rewrite, warning text, OpenAI usage summary
- Status: advisory
- Failure behavior:
  - quota/rate-limit errors degrade gracefully and preserve deterministic output
  - non-quota OpenAI failures still fail the run to surface malformed or unexpected behavior
- Extension guidance: add advisory-only enrichments here; do not move deterministic topic selection or source attribution into the LLM path

## 5. Render stage

- Responsibility: build the structured digest artifact and write markdown outputs
- Entry point: `RenderStage` in `src/reddit_digest/pipeline_stages.py`
- Inputs: analyzed insights, picked topics, advisory warnings, advisory rewrites
- Outputs:
  - structured digest artifact
  - deterministic markdown
  - optional LLM markdown variant
- Status: deterministic for the canonical markdown, advisory for the `.llm.md` variant
- Failure behavior: deterministic markdown must still be written when advisory rewrite data is unavailable
- Extension guidance: add new local file outputs here when they derive from the digest artifact; keep the deterministic markdown as the source of record

## 6. Delivery stage

- Responsibility: publish optional downstream outputs that depend on completed local artifacts
- Entry point: `DeliveryStage` in `src/reddit_digest/pipeline_stages.py`
- Inputs: collected posts, analyzed insights, structured digest, runtime delivery config, markdown output paths
- Outputs:
  - Google Sheets upserts
  - advisory Teams notifications
  - delivery status flags
- Status:
  - Sheets export is deterministic and idempotent by `run_date`
  - Teams delivery is advisory
- Failure behavior:
  - Sheets failures fail the full pipeline when Sheets export is enabled
  - Teams failures log a warning, populate run state, and do not fail the deterministic pipeline
- Extension guidance: new external sinks belong here when they consume completed local artifacts rather than participating in topic selection

## 7. State stage

- Responsibility: persist the completed run state
- Entry point: `StateStage` in `src/reddit_digest/pipeline_stages.py`
- Inputs: artifact paths plus delivery/advisory status from earlier stages
- Outputs: `data/state/YYYY-MM-DD.json` and `data/state/latest.json`
- Status: deterministic
- Failure behavior: state persistence failures fail the run because they break rerun and operational visibility
- Extension guidance: add new run metadata here only if it describes completed pipeline state, not speculative future work

## Downstream assumptions

- Collection must finish before analysis begins.
- Analysis artifacts are the only allowed source for picked topics and emerging themes.
- The render stage consumes advisory rewrites but owns the canonical markdown output.
- Delivery must not mutate deterministic local artifacts.
- State is written after all enabled stages complete so it reflects final outcomes, including advisory failures.
