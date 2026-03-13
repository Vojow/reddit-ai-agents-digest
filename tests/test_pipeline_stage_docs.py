from __future__ import annotations

from pathlib import Path


def test_pipeline_stage_contracts_are_documented_and_linked() -> None:
    readme = (Path.cwd() / "README.md").read_text()
    architecture = (Path.cwd() / "docs" / "architecture.md").read_text()
    document = (Path.cwd() / "docs" / "pipeline-stages.md").read_text()

    assert "docs/pipeline-stages.md" in readme
    assert "docs/pipeline-stages.md" in architecture
    assert "CollectionStage" in document
    assert "AnalysisStage" in document
    assert "OpenAIStage" in document
    assert "RenderStage" in document
    assert "DeliveryStage" in document
    assert "StateStage" in document
    assert "deterministic" in document
    assert "advisory" in document
