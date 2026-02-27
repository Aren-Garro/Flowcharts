"""Startup bootstrap checks for web server readiness."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

from src.parser.ollama_extractor import discover_ollama_models

CORE_MODULES = (
    "spacy",
    "pydantic",
    "typer",
    "rich",
    "flask",
    "requests",
    "graphviz",
)


def _env_flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _run_command(cmd: list[str], timeout: int = 1200) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        output = (result.stdout or "") + (result.stderr or "")
        return result.returncode == 0, output.strip()
    except Exception as exc:
        return False, str(exc)


def _check_module(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _empty_startup_report() -> Dict[str, Any]:
    return {
        "enabled": False,
        "strict": False,
        "ready": True,
        "checks": [],
        "warnings": [],
        "errors": [],
        "started_at": None,
        "finished_at": None,
        "duration_seconds": 0.0,
    }


def _record(
    report: Dict[str, Any],
    name: str,
    ok: bool,
    details: str = "",
    error: Optional[str] = None,
) -> None:
    report["checks"].append(
        {
            "name": name,
            "ok": bool(ok),
            "details": details,
            "error": error,
        }
    )


def _ensure_requirements(report: Dict[str, Any], project_root: Path) -> bool:
    if all(_check_module(module) for module in CORE_MODULES):
        _record(report, "requirements", True, details="Core runtime modules already installed.")
        return True

    requirements = project_root / "requirements.txt"
    if not requirements.exists():
        _record(report, "requirements", False, error=f"Missing file: {requirements}")
        return False
    ok, out = _run_command([sys.executable, "-m", "pip", "install", "-r", str(requirements)])
    _record(report, "requirements", ok, details=out[-6000:] if out else "")
    return ok


def _ensure_llm_extras(report: Dict[str, Any], project_root: Path) -> bool:
    if _check_module("llama_cpp") and _check_module("instructor"):
        _record(report, "llm_extras", True, details="llama_cpp + instructor already installed.")
        return True

    pyproject = project_root / "pyproject.toml"
    if not pyproject.exists():
        _record(report, "llm_extras", False, error=f"Missing file: {pyproject}")
        return False

    ok, out = _run_command([sys.executable, "-m", "pip", "install", ".[llm]"], timeout=1800)
    _record(report, "llm_extras", ok, details=out[-6000:] if out else "")
    return ok


def _ensure_spacy_model(report: Dict[str, Any]) -> bool:
    if not _check_module("spacy"):
        _record(report, "spacy_model", False, error="spaCy not installed")
        return False

    try:
        import spacy

        spacy.load("en_core_web_sm")
        _record(report, "spacy_model", True, details="en_core_web_sm already installed.")
        return True
    except Exception:
        pass

    ok, out = _run_command(
        [sys.executable, "-m", "spacy", "download", "en_core_web_sm"],
        timeout=1800,
    )
    _record(report, "spacy_model", ok, details=out[-6000:] if out else "")
    return ok


def _ensure_ollama_model(report: Dict[str, Any], base_url: str, model: str) -> bool:
    info = discover_ollama_models(base_url=base_url)
    if not info.get("reachable"):
        _record(
            report,
            "ollama_model",
            False,
            error=f"Ollama not reachable at {base_url}",
        )
        return False

    model_names = [m.get("name") for m in info.get("models") or [] if m.get("name")]
    if model in model_names:
        _record(report, "ollama_model", True, details=f"Model ready: {model}")
        return True

    ok, out = _run_command(["ollama", "pull", model], timeout=3600)
    if not ok:
        _record(report, "ollama_model", False, details=out[-6000:] if out else "", error=f"Failed to pull {model}")
        return False

    info = discover_ollama_models(base_url=base_url)
    model_names = [m.get("name") for m in info.get("models") or [] if m.get("name")]
    final_ok = model in model_names
    _record(
        report,
        "ollama_model",
        final_ok,
        details=f"Pulled model: {model}" if final_ok else "Pull command completed but model not listed by Ollama.",
        error=None if final_ok else f"Model not visible after pull: {model}",
    )
    return final_ok


def run_startup_preflight(project_root: Path, ollama_base_url: str) -> Dict[str, Any]:
    """Run startup bootstrap sequence and return readiness report."""
    report = _empty_startup_report()
    enabled = _env_flag("FLOWCHART_BOOTSTRAP_ON_START", True)
    strict = _env_flag("FLOWCHART_BOOTSTRAP_STRICT", False)
    report["enabled"] = enabled
    report["strict"] = strict

    started = time.time()
    report["started_at"] = started

    if not enabled:
        report["finished_at"] = time.time()
        report["duration_seconds"] = round(report["finished_at"] - started, 3)
        return report

    checks = [
        ("FLOWCHART_BOOTSTRAP_REQUIREMENTS", _ensure_requirements, {"project_root": project_root}),
        ("FLOWCHART_BOOTSTRAP_LLM", _ensure_llm_extras, {"project_root": project_root}),
        ("FLOWCHART_BOOTSTRAP_SPACY", _ensure_spacy_model, {}),
    ]

    for env_name, fn, kwargs in checks:
        if not _env_flag(env_name, True):
            _record(report, fn.__name__.replace("_ensure_", ""), True, details=f"Skipped by {env_name}=0")
            continue
        ok = fn(report, **kwargs)
        if not ok:
            report["warnings"].append(f"{fn.__name__} failed")
            if strict:
                report["errors"].append(f"{fn.__name__} failed")

    if _env_flag("FLOWCHART_BOOTSTRAP_OLLAMA", True):
        model = os.environ.get("FLOWCHART_OLLAMA_BOOTSTRAP_MODEL", "llama3.2:3b").strip() or "llama3.2:3b"
        ok = _ensure_ollama_model(report, ollama_base_url, model)
        if not ok:
            report["warnings"].append("_ensure_ollama_model failed")
            if strict:
                report["errors"].append("_ensure_ollama_model failed")
    else:
        _record(report, "ollama_model", True, details="Skipped by FLOWCHART_BOOTSTRAP_OLLAMA=0")

    local_llm_ready = _check_module("llama_cpp") and _check_module("instructor")
    _record(report, "local_llm_runtime", local_llm_ready, details="llama_cpp + instructor import check")
    if not local_llm_ready:
        report["warnings"].append("local_llm_runtime missing")
        if strict:
            report["errors"].append("local_llm_runtime missing")

    report["ready"] = len(report["errors"]) == 0 if strict else True
    report["finished_at"] = time.time()
    report["duration_seconds"] = round(report["finished_at"] - started, 3)
    return report
