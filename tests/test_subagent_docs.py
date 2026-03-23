from __future__ import annotations

from pathlib import Path
import tomllib


def test_subagent_docs_are_linked_and_structured() -> None:
    agents = (Path.cwd() / "AGENTS.md").read_text()
    index = (Path.cwd() / "docs" / "subagents.md").read_text()
    config = (Path.cwd() / ".codex" / "config.toml").read_text()
    architect = (Path.cwd() / "docs" / "subagents" / "architect.md").read_text()
    worker = (Path.cwd() / "docs" / "subagents" / "worker.md").read_text()
    explorer_reviewer = (Path.cwd() / "docs" / "subagents" / "explorer-reviewer.md").read_text()
    doc_reader_writer = (Path.cwd() / "docs" / "subagents" / "doc-reader-writer.md").read_text()
    sdet = (Path.cwd() / "docs" / "subagents" / "sdet.md").read_text()
    architect_toml = (Path.cwd() / ".codex" / "agents" / "architect.toml").read_text()
    worker_toml = (Path.cwd() / ".codex" / "agents" / "worker.toml").read_text()
    explorer_reviewer_toml = (Path.cwd() / ".codex" / "agents" / "explorer-reviewer.toml").read_text()
    doc_reader_writer_toml = (Path.cwd() / ".codex" / "agents" / "doc-reader-writer.toml").read_text()
    sdet_toml = (Path.cwd() / ".codex" / "agents" / "sdet.toml").read_text()

    assert "docs/subagents.md" in agents
    assert ".codex/agents/" in agents
    assert "delegation is mandatory" in agents
    assert "must not keep production implementation local" in agents
    assert "Explorer reviewer findings-first review" in agents
    assert "main/parent Codex chat is treated as the Architect" in agents
    assert "delegates implementation to Worker and review to Explorer reviewer" in agents
    assert "five-role Codex squad" in index
    assert ".codex/agents/" in index
    assert ".codex/config.toml" in index
    assert "Architect" in index
    assert "Worker" in index
    assert "Explorer reviewer" in index
    assert "Doc reader/writer" in index
    assert "SDET" in index
    assert "mandatory delegation" in index
    assert "must not keep production implementation local" in index
    assert "main/parent Codex chat is treated as Architect" in index
    assert "frames scope and acceptance criteria" in index
    assert "uses `Context7` by default for external library/framework/API docs" in index
    assert "uses `Context7` by default for upstream product/library docs" in index
    assert "use `jCodeMunch` by default" in index
    assert "Explorer reviewer should use `jCodeMunch` by default" in index
    assert "SDET should use `jCodeMunch` by default" in index
    assert "Parent/main Codex chat is treated as Architect by default" in architect
    assert "Mandatory delegation is enforced for non-trivial `src/**` changes" in architect
    assert "`Context7` by default when planning depends on external" in architect
    assert "`Context7` was used by default for external-doc tasks" in architect
    assert "parent/main Codex chat is treated as Architect" in architect_toml
    assert "task affects src/** beyond a trivial one-file fix" in architect_toml
    assert "Use Context7 by default when planning depends on external" in architect_toml
    assert "Assume the CLI is available as `context7` on PATH." in architect_toml
    assert "Do not treat Context7 as the default for repo-local codebase inspection." in architect_toml
    assert "Context7" in doc_reader_writer
    assert "`Context7` by default when docs updates depend on upstream product/library" in doc_reader_writer
    assert "`Context7` was used by default for external-doc tasks" in doc_reader_writer
    assert "Use Context7 by default when doc updates depend on external product/library" in doc_reader_writer_toml
    assert "Assume the CLI is available as `context7` on PATH." in doc_reader_writer_toml
    assert "Do not treat Context7 as the default for repo-local codebase inspection." in doc_reader_writer_toml
    assert "Context7" not in worker
    assert "Context7" not in worker_toml
    assert "Context7" not in explorer_reviewer
    assert "Context7" not in explorer_reviewer_toml
    assert "Context7" not in sdet
    assert "Context7" not in sdet_toml
    assert "jCodeMunch" in explorer_reviewer
    assert "jCodeMunch" in sdet
    assert "`jCodeMunch` context and graph tools by default" in explorer_reviewer
    assert "symbol/reference discovery, blast-radius review, and code-context gathering" in explorer_reviewer
    assert "`jCodeMunch` context and graph tools by default" in sdet
    assert "test-impact and affected-file discovery" in sdet
    assert "Use jCodeMunch by default" in explorer_reviewer_toml
    assert "symbol and reference discovery, blast-radius" in explorer_reviewer_toml
    assert "Use jCodeMunch by default" in sdet_toml
    assert "test-impact discovery, reference search," in sdet_toml
    assert "affected-file discovery, and code/test context gathering before writing tests." in sdet_toml
    assert "Do not put these role definitions in `~/.codex/config.toml`." in index
    assert "[agents] max_threads = 4" in index
    assert "[agents] max_depth = 1" in index
    assert "[agents]" in config

    stale_terms = ("Developer", "developer.toml", "developer.md")
    contract_surface = "\n".join(
        (
            agents,
            index,
            architect,
            worker,
            explorer_reviewer,
            doc_reader_writer,
            sdet,
            architect_toml,
            worker_toml,
            explorer_reviewer_toml,
            doc_reader_writer_toml,
            sdet_toml,
        )
    )
    for stale in stale_terms:
        assert stale not in contract_surface

    required_headings = (
        "## Role name",
        "## `agent_type`",
        "## Model",
        "## Default effort",
        "## Escalation triggers",
        "## Write scope",
        "## Must-read inputs",
        "## Required outputs",
        "## Stop conditions",
        "## Codex runtime file",
    )
    role_docs = (
        Path.cwd() / "docs" / "subagents" / "architect.md",
        Path.cwd() / "docs" / "subagents" / "worker.md",
        Path.cwd() / "docs" / "subagents" / "explorer-reviewer.md",
        Path.cwd() / "docs" / "subagents" / "doc-reader-writer.md",
        Path.cwd() / "docs" / "subagents" / "sdet.md",
    )

    for path in role_docs:
        content = path.read_text()
        for heading in required_headings:
            assert heading in content


def test_project_local_subagent_toml_files_exist_and_have_required_fields() -> None:
    config_path = Path.cwd() / ".codex" / "config.toml"
    config = tomllib.loads(config_path.read_text())

    assert config["agents"]["max_threads"] == 4
    assert config["agents"]["max_depth"] == 1

    expected_agents = (
        ("architect.toml", "architect", "gpt-5.4", "high", "read-only"),
        ("worker.toml", "worker", "gpt-5.3-codex", "medium", "workspace-write"),
        ("explorer-reviewer.toml", "explorer_reviewer", "gpt-5.4-mini", "medium", "read-only"),
        ("doc-reader-writer.toml", "doc_reader_writer", "gpt-5.4-mini", "medium", "workspace-write"),
        ("sdet.toml", "sdet", "gpt-5.3-codex", "medium", "workspace-write"),
    )

    for filename, name, model, effort, sandbox in expected_agents:
        path = Path.cwd() / ".codex" / "agents" / filename
        payload = tomllib.loads(path.read_text())

        assert payload["name"] == name
        assert payload["description"]
        assert payload["developer_instructions"]
        assert payload["model"] == model
        assert payload["model_reasoning_effort"] == effort
        assert payload["sandbox_mode"] == sandbox
