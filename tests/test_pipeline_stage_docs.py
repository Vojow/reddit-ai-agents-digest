from __future__ import annotations

from pathlib import Path


def test_pipeline_stage_contracts_are_documented_and_linked() -> None:
    readme = (Path.cwd() / "README.md").read_text()
    architecture = (Path.cwd() / "docs" / "architecture.md").read_text()
    document = (Path.cwd() / "docs" / "pipeline-stages.md").read_text()

    assert "docs/pipeline-stages.md" in readme
    assert "docs/pipeline-stages.md" in architecture
    assert "PipelineServices" in document
    assert "run_collection_stage()" in document
    assert "run_analysis_stage()" in document
    assert "run_openai_stage()" in document
    assert "run_render_stage()" in document
    assert "run_delivery_stage()" in document
    assert "run_state_stage()" in document
    assert "deterministic" in document
    assert "advisory" in document
