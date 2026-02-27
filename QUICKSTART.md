# Quick Start Guide

Use this guide for an end-to-end setup and first successful polished export.

---

## 1) Install

```bash
git clone https://github.com/Aren-Garro/Flowcharts.git
cd Flowcharts
python -m venv .venv
```

Activate the environment:

```bash
# PowerShell
.\.venv\Scripts\Activate.ps1

# bash/zsh
source .venv/bin/activate
```

Install dependencies:

```bash
pip install .
python -m spacy download en_core_web_sm
```

Optional extras:

```bash
# Better web URL extraction
pip install ".[webfetch]"

# Local LLM extraction
pip install ".[llm]"
```

---

## 2) Verify Runtime

```bash
python -m cli.main renderers
```

Recommended baseline for polished exports:
- Extraction: `heuristic` or `auto`
- Renderer: `graphviz`

If Graphviz is not ready:
- macOS: `brew install graphviz`
- Ubuntu/Debian: `sudo apt-get install graphviz`
- Windows: `choco install graphviz` or `winget install graphviz`

---

## 3) First End-to-End Run (CLI)

### A. Preview output quickly

```bash
python -m cli.main generate examples/simple_workflow.txt -o preview.html --renderer html
```

### B. Generate polished export

```bash
python -m cli.main generate examples/simple_workflow.txt -o final.png --renderer graphviz
python -m cli.main generate examples/simple_workflow.txt -o final.pdf --renderer graphviz
```

### C. Batch export a multi-workflow document

```bash
python -m cli.main batch manual.docx --split-mode auto --format png --renderer graphviz --zip
```

---

## 4) Web App End-to-End Run

Start the server:

```bash
python web/app.py
```

Open:
- `http://127.0.0.1:5000`

Web flow:
1. Upload a workflow file or paste text.
2. Generate a flowchart.
3. In export controls, use `Polished Export`.
4. Export `PNG` / `PDF` / `SVG`.
5. For multi-workflow sources, use `Batch Export All` -> `Download ZIP`.

---

## 5) Production Export Behavior

`POST /api/render` supports:
- `profile`: `polished` (default) or `fast_preview`
- `quality_mode`: `draft_allowed` (default) or `certified_only`
- `preferred_renderer`: `graphviz`, `d2`, `mermaid`, `kroki`, `html`
- `strict_artifact_checks`: boolean

Polished profile behavior:
- Renderer order prefers stable print output.
- Artifacts are validated for format integrity.
- Response headers expose renderer/fallback metadata:
  - `X-Flowchart-Profile`
  - `X-Flowchart-Requested-Renderer`
  - `X-Flowchart-Resolved-Renderer`
  - `X-Flowchart-Fallback-Chain`
  - `X-Flowchart-Artifact-Bytes`

---

## 6) Optional Startup Bootstrap (Web)

The web app can auto-prepare requirements/models at startup.

```bash
# PowerShell
$env:FLOWCHART_BOOTSTRAP_ON_START="1"
$env:FLOWCHART_BOOTSTRAP_REQUIREMENTS="1"
$env:FLOWCHART_BOOTSTRAP_LLM="1"
$env:FLOWCHART_BOOTSTRAP_SPACY="1"
$env:FLOWCHART_BOOTSTRAP_OLLAMA="1"
$env:FLOWCHART_OLLAMA_BOOTSTRAP_MODEL="llama3.2:3b"
```

Optional strict mode:

```bash
$env:FLOWCHART_BOOTSTRAP_STRICT="1"
```

---

## 7) Common Issues

### `can't open file '...\\web\\app.py'`
- Run from repo root:
  - `cd C:\dev\Flowcharts`
  - `.\.venv\Scripts\python.exe .\web\app.py`

### Slow two-pass upgrade with Ollama
- Set a tighter timeout:
  - `$env:FLOWCHART_UPGRADE_TIMEOUT_MS="12000"`

### Graphviz edge label warnings
- Fixed in current version by using xlabels for orthogonal edges.

### `&#39;` appears in labels
- Fixed in current version by decoding HTML entities in Mermaid label generation.

---

## 8) Validation

```bash
python validate_code.py
python -m pytest -q
```

You are ready for production-style generation and polished export workflows.
