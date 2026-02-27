"""Startup bootstrap and JSON guard regression tests."""

import sys
from pathlib import Path

import web.app as web_app
import web.startup as startup


app = web_app.app


def test_requirements_bootstrap_skips_pip_when_modules_exist(monkeypatch):
    report = startup._empty_startup_report()
    monkeypatch.setattr(startup, "_check_module", lambda module_name: True)
    monkeypatch.setattr(startup, "_run_command", lambda cmd, timeout=1200: (_ for _ in ()).throw(RuntimeError("no pip")))
    ok = startup._ensure_requirements(report, Path.cwd())
    assert ok is True
    assert report["checks"][-1]["name"] == "requirements"
    assert report["checks"][-1]["ok"] is True


def test_spacy_model_bootstrap_skips_download_when_model_exists(monkeypatch):
    report = startup._empty_startup_report()

    class _FakeSpacy:
        @staticmethod
        def load(_name):
            return object()

    monkeypatch.setattr(startup, "_check_module", lambda module_name: module_name == "spacy")
    monkeypatch.setattr(startup, "_run_command", lambda cmd, timeout=1200: (_ for _ in ()).throw(RuntimeError("no download")))
    monkeypatch.setitem(sys.modules, "spacy", _FakeSpacy)

    ok = startup._ensure_spacy_model(report)
    assert ok is True
    assert report["checks"][-1]["name"] == "spacy_model"
    assert report["checks"][-1]["ok"] is True


def test_startup_preflight_can_be_disabled(monkeypatch):
    monkeypatch.setenv("FLOWCHART_BOOTSTRAP_ON_START", "0")
    report = startup.run_startup_preflight(Path.cwd(), "http://localhost:11434")
    assert report["enabled"] is False
    assert report["ready"] is True
    assert report["checks"] == []


def test_startup_preflight_strict_mode_reports_errors(monkeypatch):
    monkeypatch.setenv("FLOWCHART_BOOTSTRAP_ON_START", "1")
    monkeypatch.setenv("FLOWCHART_BOOTSTRAP_STRICT", "1")
    monkeypatch.setenv("FLOWCHART_BOOTSTRAP_REQUIREMENTS", "1")
    monkeypatch.setenv("FLOWCHART_BOOTSTRAP_LLM", "0")
    monkeypatch.setenv("FLOWCHART_BOOTSTRAP_SPACY", "0")
    monkeypatch.setenv("FLOWCHART_BOOTSTRAP_OLLAMA", "0")
    monkeypatch.setattr(startup, "_ensure_requirements", lambda report, project_root: False)
    monkeypatch.setattr(startup, "_check_module", lambda module_name: True)

    report = startup.run_startup_preflight(Path.cwd(), "http://localhost:11434")
    assert report["strict"] is True
    assert report["ready"] is False
    assert report["errors"]


def test_generate_rejects_invalid_json_payload(monkeypatch):
    monkeypatch.setattr(web_app.cap_detector, "validate_config", lambda _config: [])
    with app.test_client() as client:
        response = client.post("/api/generate", data="not-json", content_type="text/plain")
        assert response.status_code == 400
        assert response.get_json()["error"] == "Invalid JSON payload"


def test_health_includes_startup_status(monkeypatch):
    monkeypatch.setattr(web_app.cap_detector, "get_summary", lambda: {"extractors": {}, "renderers": {}})
    web_app.startup_report = {
        "enabled": True,
        "strict": False,
        "ready": True,
        "checks": [{"name": "requirements", "ok": True, "details": "", "error": None}],
        "warnings": [],
        "errors": [],
        "started_at": None,
        "finished_at": None,
        "duration_seconds": 0.1,
    }
    with app.test_client() as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        body = response.get_json()
        assert body["startup_ready"] is True
        assert body["startup"]["enabled"] is True
        assert isinstance(body["startup"]["checks"], list)
