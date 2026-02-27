"""Regression tests for web batch-export quality gating and artifacts."""

import io
import json
import zipfile
from pathlib import Path

import web.app as web_app
from src.importers.workflow_detector import WorkflowSection
from src.models import Connection, Flowchart, FlowchartNode, NodeType, WorkflowStep

app = web_app.app


def _disable_capability_probe():
    web_app.cap_detector.validate_config = lambda _config: []


def _simple_flowchart(title: str) -> Flowchart:
    return Flowchart(
        title=title,
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


def _mock_pipeline(monkeypatch):
    def extract_steps(_self, text: str):
        if "NO_STEPS" in text:
            return []
        return [
            WorkflowStep(step_number=1, text="Start", action="start", node_type=NodeType.TERMINATOR, confidence=1.0),
            WorkflowStep(step_number=2, text="Process", action="process", node_type=NodeType.PROCESS, confidence=1.0),
            WorkflowStep(step_number=3, text="End", action="end", node_type=NodeType.TERMINATOR, confidence=1.0),
        ]

    def build_flowchart(_self, steps, title: str = "Workflow"):
        assert steps
        return _simple_flowchart(title)

    def render(self, flowchart, output_path: str, format: str = "png"):
        fail_render = "RENDER_FAIL" in (flowchart.title or "")
        self._test_render_meta = {
            "requested_renderer": self.config.renderer,
            "resolved_renderer": self.config.renderer,
            "final_renderer": self.config.renderer,
            "fallback_chain": [],
            "success": not fail_render,
            "output_path": output_path,
            "format": format,
        }
        if fail_render:
            return False
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("ok", encoding="utf-8")
        return True

    def get_last_extraction_metadata(_self):
        return {
            "requested_extraction": "heuristic",
            "resolved_extraction": "heuristic",
            "final_extraction": "heuristic",
            "fallback_used": False,
            "fallback_reason": None,
        }

    def get_last_render_metadata(self):
        return getattr(self, "_test_render_meta", {})

    monkeypatch.setattr(web_app.FlowchartPipeline, "extract_steps", extract_steps)
    monkeypatch.setattr(web_app.FlowchartPipeline, "build_flowchart", build_flowchart)
    monkeypatch.setattr(web_app.FlowchartPipeline, "render", render)
    monkeypatch.setattr(web_app.FlowchartPipeline, "get_last_extraction_metadata", get_last_extraction_metadata)
    monkeypatch.setattr(web_app.FlowchartPipeline, "get_last_render_metadata", get_last_render_metadata)


def _workflow(i: int, title: str, content: str, confidence: float = 0.9) -> WorkflowSection:
    return WorkflowSection(
        id=f"s{i}",
        title=title,
        content=content,
        level=1,
        start_line=0,
        end_line=3,
        confidence=confidence,
    )


def _cache_key_with_workflows(workflows):
    key = "batch_test_key"
    web_app.workflow_cache[key] = workflows
    web_app.cache_timestamps[key] = 0
    return key


def _zip_member_names(response):
    with zipfile.ZipFile(io.BytesIO(response.data), "r") as zf:
        return zf.namelist()


def _zip_json(response, name: str):
    with zipfile.ZipFile(io.BytesIO(response.data), "r") as zf:
        return json.loads(zf.read(name).decode("utf-8"))


def test_batch_export_requires_cache_key(monkeypatch):
    _disable_capability_probe()
    _mock_pipeline(monkeypatch)
    with app.test_client() as client:
        res = client.post("/api/batch-export", json={})
        assert res.status_code == 400
        assert res.get_json()["error"] == "No cache key provided"


def test_batch_export_missing_cache_key_returns_404(monkeypatch):
    _disable_capability_probe()
    _mock_pipeline(monkeypatch)
    with app.test_client() as client:
        res = client.post("/api/batch-export", json={"cache_key": "missing"})
        assert res.status_code == 404
        assert "Cache expired" in res.get_json()["error"]


def test_batch_export_certified_only_blocks_non_certified(monkeypatch):
    _disable_capability_probe()
    _mock_pipeline(monkeypatch)
    cache_key = _cache_key_with_workflows(
        [_workflow(1, "Low Confidence", "1. Start\n2. Process\n3. End", confidence=0.5)]
    )

    with app.test_client() as client:
        res = client.post(
            "/api/batch-export",
            json={"cache_key": cache_key, "quality_mode": "certified_only", "renderer": "graphviz"},
        )
        assert res.status_code == 422
        data = res.get_json()
        assert data["error"] == "No workflows met export quality gates"
        assert data["quality_mode"] == "certified_only"
        assert len(data["results"]) == 1
        assert data["results"][0]["quality"]["certified"] is False


def test_batch_export_draft_allowed_returns_zip_with_manifests_and_partial_failures(monkeypatch):
    _disable_capability_probe()
    _mock_pipeline(monkeypatch)
    cache_key = _cache_key_with_workflows(
        [
            _workflow(1, "Good Workflow", "1. Start\n2. Process\n3. End", confidence=0.9),
            _workflow(2, "RENDER_FAIL Workflow", "1. Start\n2. Process\n3. End", confidence=0.9),
        ]
    )

    with app.test_client() as client:
        res = client.post(
            "/api/batch-export",
            json={
                "cache_key": cache_key,
                "quality_mode": "draft_allowed",
                "renderer": "graphviz",
                "include_validation_report": True,
                "include_qa_manifest": True,
                "include_source_snapshot": True,
            },
        )
        assert res.status_code == 200

        names = _zip_member_names(res)
        assert "Good_Workflow.png" in names
        assert "qa_manifest.json" in names
        assert "iso5807_validation_report.json" in names
        assert "source_snapshot.json" in names

        qa_manifest = _zip_json(res, "qa_manifest.json")
        assert qa_manifest["quality_mode"] == "draft_allowed"
        assert qa_manifest["workflows_total"] == 2
        assert qa_manifest["workflows_rendered"] == 1
        assert qa_manifest["workflows_failed"] == 1

        failed = [r for r in qa_manifest["results"] if r.get("rendered") is False]
        assert len(failed) == 1
        assert "Failed to render via" in failed[0]["error"]


def test_batch_export_respects_optional_manifest_flags(monkeypatch):
    _disable_capability_probe()
    _mock_pipeline(monkeypatch)
    cache_key = _cache_key_with_workflows(
        [_workflow(1, "Only Diagram", "1. Start\n2. Process\n3. End", confidence=0.9)]
    )

    with app.test_client() as client:
        res = client.post(
            "/api/batch-export",
            json={
                "cache_key": cache_key,
                "include_validation_report": False,
                "include_qa_manifest": False,
                "include_source_snapshot": False,
            },
        )
        assert res.status_code == 200
        names = _zip_member_names(res)
        assert "Only_Diagram.png" in names
        assert "qa_manifest.json" not in names
        assert "iso5807_validation_report.json" not in names
        assert "source_snapshot.json" not in names


def test_batch_export_split_mode_redetect_failure_returns_400(monkeypatch):
    _disable_capability_probe()
    _mock_pipeline(monkeypatch)
    cache_key = _cache_key_with_workflows(
        [_workflow(1, "Original", "1. Start\n2. Process\n3. End", confidence=0.9)]
    )
    monkeypatch.setattr(web_app.WorkflowDetector, "detect_workflows", lambda _self, _text: [])

    with app.test_client() as client:
        res = client.post(
            "/api/batch-export",
            json={"cache_key": cache_key, "split_mode": "section"},
        )
        assert res.status_code == 400
        assert "No workflows detected with split mode" in res.get_json()["error"]


def test_batch_export_threshold_override_written_to_manifest(monkeypatch):
    _disable_capability_probe()
    _mock_pipeline(monkeypatch)
    cache_key = _cache_key_with_workflows(
        [_workflow(1, "Threshold Workflow", "1. Start\n2. Process\n3. End", confidence=0.9)]
    )

    with app.test_client() as client:
        res = client.post(
            "/api/batch-export",
            json={
                "cache_key": cache_key,
                "include_qa_manifest": True,
                "min_detection_confidence_certified": 0.77,
            },
        )
        assert res.status_code == 200
        qa_manifest = _zip_json(res, "qa_manifest.json")
        assert qa_manifest["min_detection_confidence_certified"] == 0.77
