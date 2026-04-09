# ISO 5807 Flowchart Generator

Turn workflow notes, manuals, clipboard text, and imported documents into ISO 5807-aligned flowcharts using local parsing and optional local AI.

[![ISO 5807](https://img.shields.io/badge/ISO-5807-blue)](docs/ISO_5807_SPEC.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.9%2B-green)](pyproject.toml)

Version: `2.1.1`

## What Is New In The Current Build

- Adaptive `--extraction auto` and `--renderer auto` routing based on detected local capabilities.
- Multiple extraction backends: heuristic, local GGUF via `llama-cpp-python`, and Ollama.
- Multiple renderers: Mermaid, Graphviz, D2, Kroki, and pure-HTML fallback.
- Printable PDF export that converts oversized diagrams into readable paginated PDFs.
- Batch document splitting and multi-workflow ZIP export.
- Web Studio with live generation, sample workflows, async render jobs, and capability/health endpoints.
- Capability inspection via `flowchart renderers`.
- Interactive first-run tutorial via `flowchart tutorial`.
- Import flow from files or clipboard with optional preview before generation.

## Core Features

- ISO 5807 symbol mapping for process, decision, I/O, database, document, manual, display, predefined process, and terminator nodes.
- Flow extraction from `txt`, `md`, `pdf`, `docx`, `doc`, and clipboard content.
- Hardware-aware local routing with graceful fallback when a preferred backend is unavailable.
- Validation support through the built-in ISO 5807 validator.
- Command-line, Python API, and browser-based workflows in one repo.

## Install

### Base install

```bash
git clone https://github.com/Aren-Garro/Flowcharts.git
cd Flowcharts
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Then install the project and the default NLP model:

```bash
pip install .
python -m spacy download en_core_web_sm
```

### Optional extras

Install optional components only if you need them:

```bash
pip install .[llm]
pip install .[webfetch]
pip install .[dev]
```

## Optional Local Backends

### Graphviz

Needed for native Graphviz rendering.

- Python package: already included in base dependencies
- System binary: install `graphviz` so `dot` is on your `PATH`

### Mermaid image export

Needed for Mermaid PNG/SVG/PDF rendering.

```bash
npm install -g @mermaid-js/mermaid-cli
```

Without `mmdc`, Mermaid still works for `.mmd` and HTML-based output paths.

### D2

Install the `d2` binary if you want D2 layouts.

### Kroki

Run a local Kroki container if you want unified HTTP rendering:

```bash
docker run -d -p 8000:8000 yuzutech/kroki
```

### Local GGUF models

Needed for `--extraction local-llm`:

```bash
pip install .[llm]
```

Then point to a local `.gguf` file with `--model-path`.

### Ollama

Needed for `--extraction ollama` or auto-selection that prefers Ollama:

```bash
ollama serve
ollama pull llama3.1
```

If Ollama is running on a non-default port, set the web app and API default before launch:

```bash
# Example
export FLOWCHART_OLLAMA_BASE_URL=http://127.0.0.1:11435
python web/app.py
```

On Windows PowerShell:

```powershell
$env:FLOWCHART_OLLAMA_BASE_URL = "http://127.0.0.1:11435"
python web/app.py
```

## Quick Start

### Generate from a text workflow

```bash
flowchart generate examples/user_authentication.txt -o auth.png --renderer auto --extraction auto
```

### Import a PDF or Word document

```bash
flowchart import manual.pdf -o manual_flow.png --renderer auto --extraction auto
```

### Batch export every detected workflow from a document

```bash
flowchart batch handbook.docx --split-mode auto --format png --zip
```

### Inspect what your machine supports

```bash
flowchart renderers
```

### Launch the web app

```bash
python web/app.py
```

Open `http://127.0.0.1:5000`.

## CLI Commands

The package installs both `flowchart` and `flowchart-gen`.

### `flowchart generate`

Generate from a text file.

```bash
flowchart generate workflow.txt -o output.png
flowchart generate workflow.txt --renderer graphviz --gv-engine neato -o output.svg
flowchart generate workflow.txt --renderer d2 --d2-layout elk -o output.png
flowchart generate workflow.txt --renderer auto --extraction auto -o output.pdf
```

Useful options:

- `--renderer mermaid|graphviz|d2|kroki|html|auto`
- `--extraction heuristic|local-llm|ollama|auto`
- `--direction TD|LR|BT|RL`
- `--theme default|forest|dark|neutral`
- `--model-path <path-to-model.gguf>`
- `--gpu-layers <n>`
- `--context-size <tokens>`
- `--gv-engine dot|neato|fdp|circo|twopi`
- `--d2-layout dagre|elk|tala`
- `--kroki-url http://localhost:8000`
- `--validate/--no-validate`

### `flowchart import`

Import a document or clipboard content, detect the best workflow section, and generate a flowchart.

```bash
flowchart import document.docx -o document.png --preview
flowchart import --clipboard --renderer auto --extraction auto -o clipboard_flow.svg
flowchart import SOP.pdf --renderer graphviz --format pdf -o sop.pdf
```

Useful options:

- `--clipboard`
- `--preview`
- `--format png|svg|pdf|html|mmd`
- the same extraction/renderer/model options as `generate`

### `flowchart batch`

Split a larger document into multiple workflows and export them all.

```bash
flowchart batch guide.pdf --split-mode section --format svg -o out_dir
flowchart batch guide.docx --split-mode subsection --zip --format png
flowchart batch runbook.md --split-mode procedure --renderer auto --extraction auto
```

Split modes:

- `auto`
- `section`
- `subsection`
- `procedure`
- `none`

### Other commands

```bash
flowchart validate workflow.txt --verbose
flowchart renderers
flowchart info
flowchart tutorial
flowchart version
```

## How To Choose Extractors

### Heuristic

Use when you want deterministic behavior and minimal setup.

```bash
flowchart generate workflow.txt --extraction heuristic
```

### Local GGUF

Use when you have a local model file and want stronger semantic extraction without a remote API.

```bash
flowchart generate workflow.txt \
  --extraction local-llm \
  --model-path ./models/llama3.gguf \
  --quantization 5bit \
  --gpu-layers -1 \
  --context-size 8192
```

### Ollama

Use when you already run Ollama locally.

```bash
flowchart generate workflow.txt --extraction ollama
```

If auto mode sees Ollama and at least one pulled model, it will typically recommend it first.

## How To Choose Renderers

### Mermaid

Good for Mermaid source output, HTML previews, and environments that already use Mermaid.

```bash
flowchart generate workflow.txt --renderer mermaid -o output.mmd
flowchart generate workflow.txt --renderer mermaid -o output.html
```

### Graphviz

Best default for polished static image output when Graphviz is installed.

```bash
flowchart generate workflow.txt --renderer graphviz -o output.png
```

### D2

Useful if you prefer D2 layout and have the `d2` binary installed.

```bash
flowchart generate workflow.txt --renderer d2 -o output.svg
```

### Kroki

Useful when you want a local HTTP rendering service.

```bash
flowchart generate workflow.txt --renderer kroki --kroki-url http://localhost:8000 -o output.png
```

### HTML fallback

Always available. Use it in air-gapped or low-dependency environments.

```bash
flowchart generate workflow.txt --renderer html -o output.html
```

## Web Studio

Run:

```bash
python web/app.py
```

What the web app includes:

- Sample workflows for quick demos.
- Upload and import flows for text, markdown, PDFs, and Word documents.
- Async render queue with status and download endpoints.
- Capability and health endpoints for local diagnostics.
- Pure-Python HTML fallback when richer renderers are unavailable.
- Batch export endpoint for multi-workflow documents.
- Optional WebSocket support when `flask-socketio` is installed.

Useful environment variables:

- `FLOWCHART_WEB_HOST`
- `FLOWCHART_WEB_PORT`
- `FLOWCHART_WEB_DEBUG`
- `FLOWCHART_TMP_ROOT`
- `FLOWCHART_OLLAMA_BASE_URL`

`FLOWCHART_OLLAMA_BASE_URL` is the default Ollama endpoint for the server and the Web UI. If you run the browser app at `http://localhost:5000` and Ollama is on another local port, set this variable before starting `web/app.py` so the UI initializes against the correct Ollama host and model list automatically.

Selected web endpoints:

- `GET /api/health`
- `GET /api/capabilities`
- `GET /api/renderers`
- `GET /api/models`
- `GET /api/ollama/models`
- `POST /api/generate`
- `POST /api/render`
- `POST /api/render/async`
- `GET /api/render/status/<job_id>`
- `GET /api/render/download/<job_id>`
- `POST /api/upload`
- `POST /api/upload-stream`
- `POST /api/batch-export`
- `GET /api/samples`

## Python API

```python
from src.pipeline import FlowchartPipeline, PipelineConfig

workflow_text = """
1. Start
2. Read input from database
3. Check if record exists
   - If yes: Process record
   - If no: End
4. Save result
5. End
"""

config = PipelineConfig(
    extraction="auto",
    renderer="auto",
    direction="TD",
    theme="default",
)

pipeline = FlowchartPipeline(config)
ok = pipeline.process(workflow_text, "output.png", title="Example Flow", format="png")

print(ok)
print(pipeline.get_last_extraction_metadata())
print(pipeline.get_last_render_metadata())
print(pipeline.get_last_timings())
```

## Supported Input And Output Formats

Inputs:

- `txt`
- `md`
- `pdf`
- `docx`
- `doc`
- clipboard text

Outputs:

- `png`
- `svg`
- `pdf`
- `html`
- `mmd`

## Common How-Tos

### Generate a printable PDF

```bash
flowchart generate workflow.txt --renderer auto -o workflow.pdf
```

The web server also converts large PNG-style renders into paginated printable PDFs automatically.

### Export Mermaid source only

```bash
flowchart generate workflow.txt --renderer mermaid -o workflow.mmd
```

### Validate a workflow before rendering

```bash
flowchart validate workflow.txt --verbose
```

### Review extracted content before generation

```bash
flowchart import process.docx --preview -o process.png
```

### Produce a zero-extra-dependency HTML artifact

```bash
flowchart generate workflow.txt --renderer html -o workflow.html
```

### Create many charts from one manual

```bash
flowchart batch manual.pdf --split-mode auto --zip --format png
```

## Project Layout

- `src/` core pipeline, parsing, model definitions, renderers, validation, and capability detection
- `cli/` Typer-based CLI commands
- `web/` Flask app, async renderer, HTML fallback, and templates
- `examples/` sample workflow inputs
- `docs/` usage notes, implementation reports, and troubleshooting
- `tests/` automated test coverage

## Documentation

- [Quick Start](docs/QUICK_START.md)
- [Usage Guide](docs/USAGE.md)
- [ISO 5807 Spec](docs/ISO_5807_SPEC.md)
- [Import Guide](docs/reports/IMPORT_GUIDE.md)
- [Troubleshooting](docs/reports/TROUBLESHOOTING.md)
- [Changelog](docs/reports/CHANGELOG.md)
- [Project Status](docs/reports/PROJECT_STATUS.md)

## Troubleshooting

### `Graphviz not available`

Install the system `graphviz` binary and make sure `dot` is on your `PATH`.

### `mermaid-cli not found`

Install Mermaid CLI:

```bash
npm install -g @mermaid-js/mermaid-cli
```

Or fall back to:

```bash
flowchart generate workflow.txt --renderer html -o output.html
```

### Ollama is not detected

Make sure the service is running and at least one model has been pulled:

```bash
ollama serve
ollama pull llama3.1
flowchart renderers
```

### Local LLM extraction is unavailable

Install the optional dependencies and provide a valid GGUF path:

```bash
pip install .[llm]
flowchart generate workflow.txt --extraction local-llm --model-path ./model.gguf
```

## Contributing

See [docs/reports/CONTRIBUTING.md](docs/reports/CONTRIBUTING.md).
