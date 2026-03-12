# Architecture

The repository currently contains the base scaffold for the Reddit digest
pipeline. The implemented structure is:

```text
reddit-ai-agents-digest/
├── config/
│   ├── scoring.yaml
│   └── subreddits.yaml
├── data/
│   ├── processed/
│   ├── raw/
│   └── state/
├── docs/
│   ├── architecture.md
│   └── digest-format.md
├── reports/
│   └── daily/
├── src/
│   └── reddit_digest/
│       ├── cli.py
│       ├── collectors/
│       ├── extractors/
│       ├── models/
│       ├── outputs/
│       ├── ranking/
│       └── utils/
├── tests/
│   └── test_imports.py
├── .env.example
├── AGENTS.md
├── Makefile
├── README.md
├── pyproject.toml
└── uv.lock
```

Future issues will fill in the runtime modules beneath `src/reddit_digest/`,
expand the tests, and add operations and backlog documentation.
