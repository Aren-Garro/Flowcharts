"""Enterprise quality gates for workflow detection, flowchart integrity, and exports."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.models import Flowchart


@dataclass(frozen=True)
class QualityThresholds:
    """Thresholds used to classify draft vs certified outputs."""

    min_detection_confidence_certified: float = 0.65
    min_detection_confidence_draft: float = 0.25


def evaluate_quality(
    *,
    detection_confidence: Optional[float],
    flowchart: Flowchart,
    validation_errors: List[str],
    validation_warnings: List[str],
    extraction_meta: Optional[Dict[str, Any]] = None,
    render_success: Optional[bool] = None,
    output_path: Optional[str] = None,
    thresholds: Optional[QualityThresholds] = None,
) -> Dict[str, Any]:
    """Compute quality tier and enterprise blockers for one workflow artifact."""
    cfg = thresholds or QualityThresholds()

    score = float(detection_confidence if detection_confidence is not None else 0.5)
    score = max(0.0, min(1.0, score))
    blockers: List[str] = []
    warnings: List[str] = []
    detection_flags: List[str] = []

    if score < cfg.min_detection_confidence_draft:
        blockers.append(
            f"detection_confidence_below_draft_threshold ({score:.2f} < {cfg.min_detection_confidence_draft:.2f})"
        )
    elif score < cfg.min_detection_confidence_certified:
        warnings.append(
            f"detection_confidence_below_certified_threshold ({score:.2f} < {cfg.min_detection_confidence_certified:.2f})"
        )
        detection_flags.append("low_detection_confidence")

    # Graph integrity and core ISO checks
    structure_valid, structure_errors = flowchart.validate_structure()
    if not structure_valid:
        blockers.extend([f"graph_integrity:{err}" for err in structure_errors])

    if validation_errors:
        blockers.extend([f"iso_critical:{err}" for err in validation_errors])
    if validation_warnings:
        warnings.extend([f"iso_warning:{w}" for w in validation_warnings])

    # Certified output should not rely on degraded extraction fallback.
    if extraction_meta and extraction_meta.get("fallback_used"):
        warnings.append("extraction_fallback_used")

    if render_success is False:
        blockers.append("render_failed")
    if output_path:
        p = Path(output_path)
        if not p.exists():
            blockers.append("render_artifact_missing")
        elif p.stat().st_size <= 0:
            blockers.append("render_artifact_empty")

    certified = len(blockers) == 0 and score >= cfg.min_detection_confidence_certified and not (
        extraction_meta and extraction_meta.get("fallback_used")
    )
    tier = "certified" if certified else "draft"

    return {
        "tier": tier,
        "certified": certified,
        "detection_score": round(score, 3),
        "detection_flags": detection_flags,
        "blockers": blockers,
        "warnings": warnings,
        "iso_critical_passed": len(validation_errors) == 0,
        "graph_integrity_passed": structure_valid,
        "quality_mode_supported": ["draft_allowed", "certified_only"],
    }


def build_source_snapshot(
    *,
    workflow_text: str,
    steps: List[Any],
    flowchart: Flowchart,
    pipeline_config: Dict[str, Any],
) -> Dict[str, Any]:
    """Build auditable source snapshot for enterprise export bundles."""
    return {
        "workflow_text": workflow_text,
        "steps": [
            {
                "step_number": getattr(step, "step_number", None),
                "text": getattr(step, "text", ""),
                "node_type": str(getattr(step, "node_type", "")) if getattr(step, "node_type", None) is not None else None,
                "confidence": getattr(step, "confidence", None),
                "is_decision": getattr(step, "is_decision", False),
                "branches": getattr(step, "branches", None),
            }
            for step in steps
        ],
        "graph": {
            "title": flowchart.title,
            "nodes": [
                {
                    "id": n.id,
                    "type": str(n.node_type),
                    "label": n.label,
                    "confidence": n.confidence,
                    "warning_level": getattr(n, "warning_level", ""),
                }
                for n in flowchart.nodes
            ],
            "connections": [
                {
                    "from": c.from_node,
                    "to": c.to_node,
                    "label": c.label,
                    "connection_type": str(c.connection_type),
                }
                for c in flowchart.connections
            ],
        },
        "pipeline_config": pipeline_config,
    }
