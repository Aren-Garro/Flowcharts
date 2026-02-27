"""Tests for enterprise quality gate evaluation."""

from src.models import Flowchart, FlowchartNode, Connection, NodeType
from src.quality_assurance import evaluate_quality, QualityThresholds


def _simple_flowchart() -> Flowchart:
    return Flowchart(
        title="T",
        nodes=[
            FlowchartNode(id="START", node_type=NodeType.TERMINATOR, label="Start"),
            FlowchartNode(id="P1", node_type=NodeType.PROCESS, label="Process"),
            FlowchartNode(id="END", node_type=NodeType.TERMINATOR, label="End"),
        ],
        connections=[
            Connection(from_node="START", to_node="P1"),
            Connection(from_node="P1", to_node="END"),
        ],
    )


def test_quality_certified_when_all_gates_pass():
    q = evaluate_quality(
        detection_confidence=0.9,
        flowchart=_simple_flowchart(),
        validation_errors=[],
        validation_warnings=[],
        extraction_meta={"fallback_used": False},
    )
    assert q["certified"] is True
    assert q["tier"] == "certified"
    assert q["blockers"] == []


def test_quality_draft_when_detection_below_certified_threshold():
    q = evaluate_quality(
        detection_confidence=0.5,
        flowchart=_simple_flowchart(),
        validation_errors=[],
        validation_warnings=[],
        extraction_meta={"fallback_used": False},
        thresholds=QualityThresholds(min_detection_confidence_certified=0.65),
    )
    assert q["certified"] is False
    assert q["tier"] == "draft"
    assert any("detection_confidence_below_certified_threshold" in w for w in q["warnings"])


def test_quality_blocker_for_missing_render_artifact():
    q = evaluate_quality(
        detection_confidence=0.95,
        flowchart=_simple_flowchart(),
        validation_errors=[],
        validation_warnings=[],
        extraction_meta={"fallback_used": False},
        render_success=False,
        output_path="C:/does/not/exist.svg",
    )
    assert q["certified"] is False
    assert "render_failed" in q["blockers"]
