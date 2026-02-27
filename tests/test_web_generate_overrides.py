"""Tests for web generate endpoint node override behavior."""

import web.app as web_app


app = web_app.app


def _disable_capability_probe():
    # Capability probing imports spaCy and fails on Python 3.14 in this env.
    web_app.cap_detector.validate_config = lambda _config: []


def _post_generate(client, workflow_text, node_overrides=None):
    payload = {
        "workflow_text": workflow_text,
        "title": "Test Workflow",
        "theme": "default",
        "validate": True,
    }
    if node_overrides is not None:
        payload["node_overrides"] = node_overrides
    return client.post("/api/generate", json=payload)


def test_generate_with_node_override_applies_type_and_label():
    _disable_capability_probe()
    with app.test_client() as client:
        workflow_text = "1. Start\n2. Process data\n3. End"
        res = _post_generate(
            client,
            workflow_text,
            node_overrides=[{"id": "STEP_2", "type": "decision", "label": "Review Data"}],
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["applied_overrides"]["requested_count"] == 1
        assert data["applied_overrides"]["applied_count"] == 1
        assert data["applied_overrides"]["ignored"] == []
        step_node = next((n for n in data["node_confidence"] if n["id"] == "STEP_2"), None)
        assert step_node is not None
        assert step_node["type"] == "decision"
        assert step_node["label"] == "Review Data"
        assert "Review Data" in data["mermaid_code"]


def test_generate_with_invalid_overrides_reports_ignored():
    _disable_capability_probe()
    with app.test_client() as client:
        workflow_text = "1. Start\n2. Process data\n3. End"
        res = _post_generate(
            client,
            workflow_text,
            node_overrides=[
                {"id": "MISSING_NODE", "type": "process"},
                {"id": "STEP_2", "type": "not-a-type"},
                {"id": "STEP_2", "label": "   "},
            ],
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["applied_overrides"]["requested_count"] == 3
        assert data["applied_overrides"]["applied_count"] == 0
        reasons = {item["reason"] for item in data["applied_overrides"]["ignored"]}
        assert "node_not_found" in reasons
        assert "invalid_node_type" in reasons
        assert "empty_label" in reasons


def test_generate_protects_last_start_and_end_terminators():
    _disable_capability_probe()
    with app.test_client() as client:
        workflow_text = "1. Start\n2. Process data\n3. End"
        res = _post_generate(
            client,
            workflow_text,
            node_overrides=[
                {"id": "START", "type": "process"},
                {"id": "END", "type": "process"},
            ],
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["applied_overrides"]["applied_count"] == 0
        reasons = {item["reason"] for item in data["applied_overrides"]["ignored"]}
        assert "would_remove_last_start_terminator" in reasons
        assert "would_remove_last_end_terminator" in reasons
        start_node = next((n for n in data["node_confidence"] if n["id"] == "START"), None)
        end_node = next((n for n in data["node_confidence"] if n["id"] == "END"), None)
        assert start_node is not None and start_node["type"] == "terminator"
        assert end_node is not None and end_node["type"] == "terminator"


def test_generate_accepts_missing_node_overrides_field():
    _disable_capability_probe()
    with app.test_client() as client:
        workflow_text = "1. Start\n2. Process data\n3. End"
        res = _post_generate(client, workflow_text)
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["applied_overrides"]["requested_count"] == 0
        assert data["applied_overrides"]["applied_count"] == 0
        assert data["applied_overrides"]["ignored"] == []
