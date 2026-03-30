from __future__ import annotations

from pathlib import Path


def test_docs_describe_dual_markdown_outputs() -> None:
    readme = (Path.cwd() / "README.md").read_text()
    operations = (Path.cwd() / "docs" / "operations.md").read_text()
    architecture = (Path.cwd() / "docs" / "architecture.md").read_text()
    digest_format = (Path.cwd() / "docs" / "digest-format.md").read_text()
    agents = (Path.cwd() / "AGENTS.md").read_text()

    assert "reports/daily/YYYY-MM-DD.llm.md" in readme
    assert "source of record" in readme
    assert "make run-ai" in readme
    assert "AI-enhanced digest locally (no Sheets export)" in readme
    assert "Additional required environment variable for local AI-enhanced runs" in readme
    assert "OPENAI_API_KEY" in readme
    assert ".codex/environments/environment.toml" in readme
    assert "scripts/configure_codex_worktree_env.sh" in readme
    assert "reports/latest.llm.md" in operations
    assert "make run-ai" in operations
    assert "ops/launchd/com.vojow.reddit-ai-agents-digest.daily.plist" in operations
    assert "launchctl bootstrap gui/$(id -u)" in operations
    assert "launchctl bootout gui/$(id -u)" in operations
    assert "launchctl kickstart -k gui/$(id -u)/com.vojow.reddit-ai-agents-digest.daily" in operations
    assert "mkdir -p ~/Library/Logs/reddit-ai-agents-digest" in operations
    assert "/Users/wojciechwieczorek/Library/Logs/reddit-ai-agents-digest/daily.out.log" in operations
    assert "/Users/wojciechwieczorek/Library/Logs/reddit-ai-agents-digest/daily.err.log" in operations
    assert "OPENAI_API_KEY" in operations
    assert ".codex/environments/environment.toml" in operations
    assert "scripts/configure_codex_worktree_env.sh" in operations
    assert "data/processed/topic_rewrites/YYYY-MM-DD.json" in operations
    assert "data/processed/executive_summary_rewrites/YYYY-MM-DD.json" in operations
    assert "same selected topics" in operations
    assert "reports/latest.llm.md" in architecture
    assert "does not create same-day Reddit findings or choose topics" in architecture
    assert "executive summary rewrite" in architecture
    assert "## Picked Topics" in digest_format
    assert "## Emerging Themes" in digest_format
    assert "## Watch Next" in digest_format
    assert "Top Tools Mentioned" not in digest_format
    assert "Optional LLM-enhanced digest" in agents
    assert "it may only rewrite the top-level executive summary and topic prose" in agents
