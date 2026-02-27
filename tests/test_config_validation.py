"""Tests for shared pipeline option validation and normalization."""

from src.config_validation import normalize_pipeline_options
from src.pipeline import FlowchartPipeline, PipelineConfig
from src.models import Flowchart


def test_normalize_options_accepts_valid_values():
    result = normalize_pipeline_options(
        {
            "extraction": "auto",
            "renderer": "graphviz",
            "quantization": "5bit",
            "direction": "LR",
            "format": "SVG",
            "split_mode": "Section",
        }
    )
    assert result["errors"] == []
    assert result["normalized"]["format"] == "svg"
    assert result["normalized"]["split_mode"] == "section"


def test_normalize_options_accepts_ollama_extraction():
    result = normalize_pipeline_options({"extraction": "ollama", "renderer": "mermaid"})
    assert result["errors"] == []
    assert result["normalized"]["extraction"] == "ollama"


def test_normalize_options_supports_deprecated_aliases():
    result = normalize_pipeline_options({"extraction": "llm", "renderer": "dot"})
    assert result["errors"] == []
    assert result["normalized"]["extraction"] == "local-llm"
    assert result["normalized"]["renderer"] == "graphviz"
    assert len(result["warnings"]) == 2


def test_normalize_options_rejects_invalid_values():
    result = normalize_pipeline_options(
        {
            "extraction": "remote",
            "renderer": "plantuml",
            "quantization": "16bit",
            "direction": "UP",
            "format": "jpg",
            "split_mode": "chapter",
        }
    )
    assert len(result["errors"]) == 6


def test_pipeline_records_render_fallback_metadata(monkeypatch):
    pipeline = FlowchartPipeline(PipelineConfig(renderer="graphviz"))
    flowchart = Flowchart(nodes=[], connections=[], title="Test")

    monkeypatch.setattr(pipeline, "_dispatch_render", lambda *args, **kwargs: False)
    monkeypatch.setattr(pipeline, "_render_html", lambda *args, **kwargs: True)

    success = pipeline.render(flowchart, "output.png", format="png")
    metadata = pipeline.get_last_render_metadata()

    assert success is True
    assert metadata["requested_renderer"] == "graphviz"
    assert metadata["resolved_renderer"] == "graphviz"
    assert metadata["fallback_chain"] == ["mermaid", "html"]
    assert metadata["final_renderer"] == "html"
    assert metadata["success"] is True
