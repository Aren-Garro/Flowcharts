"""Backend hygiene regression checks."""

import tempfile
from pathlib import Path

import web.app as web_app


def test_resolve_tmp_root_defaults_to_system_temp(monkeypatch):
    monkeypatch.delenv("FLOWCHART_TMP_ROOT", raising=False)
    expected = (Path(tempfile.gettempdir()) / "flowcharts" / "web").resolve()
    assert web_app._resolve_tmp_root() == expected


def test_resolve_tmp_root_honors_env_override(monkeypatch):
    override = (Path.cwd() / ".tmp" / "test-runtime-root").resolve()
    monkeypatch.setenv("FLOWCHART_TMP_ROOT", str(override))
    assert web_app._resolve_tmp_root() == override


def test_no_runtime_imports_use_legacy_workflow_detector():
    project_root = Path(__file__).resolve().parents[1]
    offenders = []

    for directory in ("src", "web", "cli"):
        for path in (project_root / directory).rglob("*.py"):
            contents = path.read_text(encoding="utf-8")
            if "src.parser.workflow_detector" in contents and path.name != "test_backend_hygiene.py":
                offenders.append(str(path))

    assert offenders == []
