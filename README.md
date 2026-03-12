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
uv sync
```

Run the package entrypoint:

```bash
uv run reddit-digest --help
```

Run tests:

```bash
uv run pytest
```

## Repository layout

The project uses a `src/` layout and stores:
- raw fetches in `data/raw/`
- normalized artifacts in `data/processed/`
- run state in `data/state/`
- generated reports in `reports/`
