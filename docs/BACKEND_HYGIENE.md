# Backend Hygiene Guidelines

This document defines backend cleanup standards to keep the repository maintainable.

## Dependency Source of Truth

- Primary source: `pyproject.toml` (`[project.dependencies]` and `[project.optional-dependencies]`).
- `requirements.txt` mirrors runtime dependencies for convenience installs.
- `setup.py` is a setuptools shim only; do not duplicate metadata there.

## Runtime Temp Files

- Default runtime temp root: OS temp directory at `flowcharts/web`.
- Override with:

```bash
FLOWCHART_TMP_ROOT=/path/to/runtime/tmp
```

- Runtime artifacts should not be written under repo root by default.

## Parser Modules

- Keep a single workflow detector implementation in active use.
- Use `src/importers/workflow_detector.py` for document splitting logic.
- Do not reintroduce imports of `src.parser.workflow_detector`.

## Test Guardrails

- Keep regression tests for:
  - temp root resolution and env override behavior
  - absence of legacy import paths in runtime modules
- Run targeted checks:

```bash
.venv\\Scripts\\python.exe -m pytest tests/test_backend_hygiene.py tests/test_web_generate_overrides.py
```
