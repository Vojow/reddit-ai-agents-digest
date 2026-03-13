# Architecture

The project is a file-oriented daily pipeline with deterministic intermediate
artifacts. The runtime flow is:

1. Load YAML config and environment-backed runtime settings.
2. Collect Reddit posts into `data/raw/posts/YYYY-MM-DD.json` and
   `data/processed/posts/YYYY-MM-DD.json` using Reddit public JSON listing endpoints.
3. Collect Reddit comments into `data/raw/comments/YYYY-MM-DD.json` and
   `data/processed/comments/YYYY-MM-DD.json` using Reddit public thread JSON endpoints.
4. Extract normalized insights into `data/processed/insights/YYYY-MM-DD.json`.
5. Compare those insights to the most recent prior run and mark them as `new`
   or `ongoing`.
6. Rank collected threads across enabled subreddits so picked topics stay
   grounded in configured source posts.
7. Derive deterministic picked topics from scored insights and ranked posts.
8. Optionally generate OpenAI-backed `Watch Next` suggestions into
   `data/processed/suggestions/YYYY-MM-DD.json`.
9. Optionally generate OpenAI-backed topic rewrites into
   `data/processed/topic_rewrites/YYYY-MM-DD.json`.
10. Render the deterministic Markdown digest to `reports/daily/YYYY-MM-DD.md`
    and refresh `reports/latest.md`.
11. Optionally render an LLM-enhanced digest for the same selected topics to
    `reports/daily/YYYY-MM-DD.llm.md` and `reports/latest.llm.md`.
12. Optionally export raw posts, insights, and daily digest summaries to Google
    Sheets.
13. Persist run metadata into `data/state/YYYY-MM-DD.json` and `data/state/latest.json`.

Stage ownership and extension points are documented in
[`docs/pipeline-stages.md`](pipeline-stages.md).
Persisted field-level artifact contracts are documented in
[`docs/artifact-schemas.md`](artifact-schemas.md).

## Code layout

```text
src/reddit_digest/
├── cli.py
├── pipeline.py
├── collectors/
│   ├── reddit_posts.py
│   └── reddit_comments.py
├── extractors/
│   ├── approaches.py
│   ├── common.py
│   ├── guides.py
│   ├── openai_suggestions.py
│   ├── service.py
│   ├── testing_insights.py
│   └── tools.py
├── models/
│   ├── base.py
│   ├── comment.py
│   ├── digest.py
│   ├── insight.py
│   ├── post.py
│   └── suggestion.py
├── outputs/
│   ├── google_sheets.py
│   └── markdown.py
├── ranking/
│   ├── impact.py
│   ├── novelty.py
│   └── threads.py
└── utils/
    ├── logging.py
    ├── retries.py
    └── state.py
```

## Key design choices

- Normalized typed models sit between collection and downstream processing.
- Each stage writes its own output instead of relying on in-memory-only flow.
- Thread ranking uses only enabled subreddits and keeps the existing score
  formula for source-post selection.
- Picked topics are rendered from scored insights with source links from the
  ranked enabled-subreddit post set.

The main architectural constraints and tradeoffs now live in the ADR index:
[`docs/adr/README.md`](adr/README.md).

## Current gaps

- There is no long-term trend analysis beyond the most recent prior run.
- The OpenAI suggestion schema is prompt-based JSON rather than strict schema enforcement.
- The GCP-side Workload Identity Federation setup still has to be provisioned
  outside the repository.
