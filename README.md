# reddit-ai-agents-digest

Daily Reddit intelligence pipeline for:
- AI agents
- AI-enhanced development
- AI-enhanced testing

## Local setup

Requirements:
- Python 3.12
- `uv`

Install dependencies:

```bash
uv sync --dev
```

Run the package entrypoint:

```bash
uv run reddit-digest --help
```

Run tests:

```bash
uv run pytest
```

Copy `.env.example` to `.env` and populate any secrets required for the commands
you want to run.

Key runtime environment variables:
- `REDDIT_CLIENT_ID`
- `REDDIT_CLIENT_SECRET`
- `REDDIT_USER_AGENT`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `GOOGLE_SERVICE_ACCOUNT_JSON`
- `GOOGLE_SHEETS_SPREADSHEET_ID`

Supported runtime overrides:
- `INCLUDE_SECONDARY_SUBREDDITS`
- `LOOKBACK_HOURS`
- `MIN_POST_SCORE`
- `MIN_COMMENTS`
- `MAX_POSTS_PER_SUBREDDIT`
- `MAX_COMMENTS_PER_POST`

## Repository layout

The project uses a `src/` layout and stores:
- raw fetches in `data/raw/`
- normalized artifacts in `data/processed/`
- run state in `data/state/`
- generated reports in `reports/`
