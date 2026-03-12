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
6. Rank collected threads across enabled subreddits, producing a diversified
   global top 5 and per-subreddit top 3 lists.
7. Optionally generate OpenAI-backed `Watch Next` suggestions into
   `data/processed/suggestions/YYYY-MM-DD.json`.
8. Render the Markdown digest to `reports/daily/YYYY-MM-DD.md` and refresh
   `reports/latest.md`.
9. Optionally export raw posts, insights, and daily digest summaries to Google
   Sheets.
10. Persist run metadata into `data/state/YYYY-MM-DD.json` and `data/state/latest.json`.

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
- The OpenAI step is advisory only. It can influence `Watch Next`, but it does
  not create same-day Reddit findings.
- MVP ingestion uses public Reddit JSON endpoints and only requires a user agent.
- Thread ranking uses only enabled subreddits and keeps the existing score
  formula for both global and per-subreddit ordering.
- The global `Notable Threads` list applies a minimal diversity rule so it
  includes at least 2 enabled subreddits when eligible candidates exist.
- GitHub Actions authenticates to Google Sheets via GitHub OIDC and Workload
  Identity Federation; local runs can still use ADC or a local JSON fallback.
- The current GitHub Actions workflow is markdown-only on a `self-hosted`
  runner; GitHub-hosted runners are unsupported for live Reddit collection.
- Google Sheets export is idempotent by `run_date`.
- Re-running the same date overwrites file outputs and state rather than
  creating duplicates.

## Current gaps

- There is no long-term trend analysis beyond the most recent prior run.
- The OpenAI suggestion schema is prompt-based JSON rather than strict schema enforcement.
- The GCP-side Workload Identity Federation setup still has to be provisioned
  outside the repository.
