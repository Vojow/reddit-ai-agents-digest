# Folder structure
```
reddit-ai-dev-testing-digest/
├── .github/
│   ├── workflows/
│   │   ├── daily-digest.yml
│   │   └── codex-issue-implement.yml
│   ├── ISSUE_TEMPLATE/
│   │   ├── feature.md
│   │   ├── bug.md
│   │   └── task.md
│   └── pull_request_template.md
├── config/
│   ├── subreddits.yaml
│   ├── scoring.yaml
│   └── prompts.yaml
├── data/
│   ├── raw/
│   ├── processed/
│   └── state/
├── docs/
│   ├── architecture.md
│   ├── backlog.md
│   ├── operations.md
│   └── decisions/
├── reports/
│   ├── daily/
│   └── latest.md
├── src/
│   └── reddit_digest/
│       ├── __init__.py
│       ├── main.py
│       ├── config.py
│       ├── collectors/
│       │   ├── reddit_posts.py
│       │   └── reddit_comments.py
│       ├── extractors/
│       │   ├── tools.py
│       │   ├── approaches.py
│       │   ├── guides.py
│       │   └── testing_insights.py
│       ├── ranking/
│       │   ├── impact.py
│       │   └── dedupe.py
│       ├── outputs/
│       │   ├── markdown.py
│       │   ├── google_sheets.py
│       │   └── json_store.py
│       ├── models/
│       │   ├── post.py
│       │   ├── comment.py
│       │   └── digest.py
│       └── utils/
│           ├── logging.py
│           ├── dates.py
│           └── text.py
├── tests/
│   ├── test_scoring.py
│   ├── test_extractors.py
│   ├── test_markdown_output.py
│   └── test_config.py
├── .env.example
├── AGENTS.md
├── README.md
├── pyproject.toml
└── Makefile
```
