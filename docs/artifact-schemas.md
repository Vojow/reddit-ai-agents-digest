# Artifact Schema Reference

This page documents the persisted artifact families, their stable fields, and
whether they are source-of-record or derived/advisory outputs.

## Source-of-record summary

- Source-of-record local outputs:
  - `reports/daily/YYYY-MM-DD.md`
  - `data/raw/**/*.json`
  - `data/processed/posts/*.json`
  - `data/processed/comments/*.json`
  - `data/processed/insights/*.json`
  - `data/state/*.json`
- Derived deterministic outputs:
  - Google Sheets rows derived from collected posts, insights, and digest summaries
- Advisory outputs:
  - `reports/daily/YYYY-MM-DD.llm.md`
  - `data/processed/suggestions/*.json`
  - `data/processed/topic_rewrites/*.json`
  - Teams webhook payloads

## Raw artifact families

### `data/raw/posts/YYYY-MM-DD.json`

- Type: object keyed by configured subreddit name
- Per-subreddit fields:
  - `sort_modes`: object keyed by listing mode such as `new` or `top`
  - `selected`: array of shortlisted raw post payloads that passed filtering
- Selected/raw post fields:
  - `id`
  - `subreddit`
  - `title`
  - `author`
  - `score`
  - `num_comments`
  - `created_utc`
  - `url`
  - `permalink`
  - `selftext`
- Ownership: collection stage
- Stability: shape should only change with an intentional collection contract change

### `data/raw/comments/YYYY-MM-DD.json`

- Type: object keyed by `post_id`
- Value: array of raw comment payloads returned for that post before normalization filtering
- Raw comment fields:
  - `id`
  - `post_id`
  - `parent_id`
  - `subreddit`
  - `author`
  - `body`
  - `score`
  - `created_utc`
  - `permalink`
- Ownership: collection stage
- Stability: keyed by shortlisted post IDs for the run date

## Processed deterministic artifact families

### `data/processed/posts/YYYY-MM-DD.json`

- Type: array of normalized `Post` records
- Fields:
  - `id`
  - `subreddit`
  - `title`
  - `author`
  - `score`
  - `num_comments`
  - `created_utc`
  - `url`
  - `permalink`
  - `selftext`
- Semantics: filtered shortlist used by downstream ranking and digest grounding

### `data/processed/comments/YYYY-MM-DD.json`

- Type: array of normalized `Comment` records
- Fields:
  - `id`
  - `post_id`
  - `parent_id`
  - `subreddit`
  - `author`
  - `body`
  - `score`
  - `created_utc`
  - `permalink`
- Semantics: deleted/removed/empty comments are excluded before persistence

### `data/processed/insights/YYYY-MM-DD.json`

- Type: array of normalized `Insight` records
- Fields:
  - `category`
  - `title`
  - `summary`
  - `tags`
  - `evidence`
  - `source_kind`
  - `source_id`
  - `source_permalink`
  - `source_post_id`
  - `subreddit`
  - `novelty`
  - `why_it_matters`
- Semantics:
  - `source_kind` is `post` or `comment`
  - `novelty` is persisted after novelty comparison and is typically `new` or `ongoing`
  - `why_it_matters` is the deterministic relevance text used by the canonical digest

## Advisory processed artifact families

### `data/processed/suggestions/YYYY-MM-DD.json`

- Type: array of advisory `Suggestion` records
- Fields:
  - `category`
  - `title`
  - `rationale`
- Semantics:
  - `category` is `content` or `source`
  - derived only from the day’s collected findings
  - used for `Watch Next` and future monitoring ideas, not same-day topic selection

### `data/processed/topic_rewrites/YYYY-MM-DD.json`

- Type: array of advisory topic rewrite records
- Fields:
  - `topic_key`
  - `executive_summary`
  - `relevance_for_user`
- Semantics:
  - must exactly cover the deterministic topic set for that run
  - may rewrite prose only
  - may not change titles, links, source subreddits, scores, or counts

## Run state

### `data/state/YYYY-MM-DD.json` and `data/state/latest.json`

- Type: single object
- Fields:
  - `run_date`
  - `completed_at`
  - `raw_posts_path`
  - `raw_comments_path`
  - `insights_path`
  - `report_path`
  - `sheets_exported`
  - `teams_published`
  - `teams_error`
  - `openai_usage`
- Nested `openai_usage` fields:
  - `total_calls`
  - `input_tokens`
  - `output_tokens`
  - `total_tokens`
  - `operations`
- Nested `operations` item fields:
  - `operation`
  - `calls`
  - `input_tokens`
  - `output_tokens`
  - `total_tokens`
- Semantics:
  - `report_path` always points to the deterministic markdown
  - `latest.json` mirrors the latest completed run and is replaced on rerun

## Google Sheets tabs

### `Raw_Posts`

- Columns:
  - `run_date`
  - `post_id`
  - `subreddit`
  - `title`
  - `url`
  - `permalink`
  - `score`
  - `num_comments`
  - `created_utc`
  - `impact_score`
- Key semantics: upserted by `run_date` plus `post_id`

### `Insights`

- Columns:
  - `run_date`
  - `category`
  - `title`
  - `subreddit`
  - `source_kind`
  - `source_id`
  - `source_post_id`
  - `source_permalink`
  - `novelty`
  - `tags`
  - `impact_score`
  - `why_it_matters`
- Key semantics: upserted by `run_date` plus `source_id`

### `Daily_Digest`

- Columns:
  - `run_date`
  - `total_posts`
  - `total_insights`
  - `top_thread_title`
  - `top_thread_url`
  - `top_tool`
  - `top_approach`
  - `top_guide`
  - `top_testing_insight`
  - `watch_next`
- Key semantics: one summary row per `run_date`
