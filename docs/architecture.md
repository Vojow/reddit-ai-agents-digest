# Architecture

The project is a file-oriented daily pipeline with deterministic intermediate
artifacts. The runtime flow is:

1. Load YAML config and environment-backed runtime settings.
2. Collect Reddit posts into `data/raw/posts/YYYY-MM-DD.json` and
   `data/processed/posts/YYYY-MM-DD.json`.
3. Collect Reddit comments into `data/raw/comments/YYYY-MM-DD.json` and
   `data/processed/comments/YYYY-MM-DD.json`.
4. Extract normalized insights into `data/processed/insights/YYYY-MM-DD.json`.
5. Compare those insights to the most recent prior run and mark them as `new`
   or `ongoing`.
6. Optionally generate OpenAI-backed `Watch Next` suggestions into
   `data/processed/suggestions/YYYY-MM-DD.json`.
7. Render the Markdown digest to `reports/daily/YYYY-MM-DD.md` and refresh
   `reports/latest.md`.
8. Optionally export raw posts, insights, and daily digest summaries to Google
   Sheets.
9. Persist run metadata into `data/state/YYYY-MM-DD.json` and `data/state/latest.json`.

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
│   └── novelty.py
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
- Google Sheets export is idempotent by `run_date`.
- Re-running the same date overwrites file outputs and state rather than
  creating duplicates.

## Current gaps

- GitHub Actions automation is not yet added.
- There is no long-term trend analysis beyond the most recent prior run.
- The OpenAI suggestion schema is prompt-based JSON rather than strict schema enforcement.
