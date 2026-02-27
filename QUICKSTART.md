# Quick Start Guide

Get up and running with the ISO 5807 Flowchart Generator in minutes.

---

## Installation

### Tier 1: Minimal (Zero External Dependencies)

Generates flowcharts using heuristic extraction and HTML output. No Node.js, no system binaries, no Docker.

```bash
git clone https://github.com/Aren-Garro/Flowcharts.git
cd Flowcharts
pip install .
# Optional extras:
# Better URL HTML extraction in web fetch mode
pip install ".[webfetch]"
# Alternative install path if you prefer requirements file:
# pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

**Test it:**

```bash
python -m cli.main generate examples/simple_workflow.txt -o test.html --renderer html
# Open test.html in your browser
```

### Tier 2: Standard (Recommended)

Adds Graphviz for fast, native PNG/SVG rendering without Node.js.

```bash
# Everything from Tier 1, plus:

# macOS
brew install graphviz

# Ubuntu/Debian
sudo apt-get install graphviz

# Windows (via Chocolatey)
choco install graphviz

# Windows (via Winget)
winget install graphviz
```

**Test it:**

```bash
python -m cli.main generate examples/user_authentication.txt -o test.png --renderer graphviz
python -m cli.main renderers  # Should show graphviz as ✓ Ready
```

### Tier 3: Full (All Engines)

Adds local LLM extraction, D2 rendering, and Kroki multi-engine support.

```bash
# Everything from Tier 2, plus:

# Local LLM extraction
pip install ".[llm]"

# Download a GGUF model (pick one):
# Llama-3-8B-Instruct (recommended): https://huggingface.co/bartowski/Meta-Llama-3-8B-Instruct-GGUF
# Mistral-7B-Instruct: https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF
# Place the .gguf file in a models/ directory

# D2 declarative renderer
# macOS
brew install d2
# Linux
curl -fsSL https://d2lang.com/install.sh | sh -s --
# Windows: Download from https://github.com/terrastruct/d2/releases

# Kroki unified renderer (requires Docker)
docker run -d -p 8000:8000 yuzutech/kroki
```

**Test it:**

```bash
python -m cli.main renderers  # All engines should show ✓ Ready

# D2 rendering
python -m cli.main generate examples/database_operations.txt -o test.svg --renderer d2

# Local LLM extraction + Graphviz rendering
python -m cli.main generate examples/complex_decision.txt -o test.png \
    --extraction local-llm \
    --model-path ./models/Meta-Llama-3-8B-Instruct.Q4_K_M.gguf \
    --renderer graphviz

# Kroki multi-engine
python -m cli.main generate examples/simple_workflow.txt -o test.svg --renderer kroki
```

---

## GPU Acceleration (Optional)

For faster LLM inference, install `llama-cpp-python` with GPU support:

```bash
# NVIDIA CUDA
CMAKE_ARGS="-DGGML_CUDA=on" pip install llama-cpp-python --force-reinstall --no-cache-dir

# Apple Metal (M1/M2/M3)
CMAKE_ARGS="-DGGML_METAL=on" pip install llama-cpp-python --force-reinstall --no-cache-dir

# CPU-only (default, no action needed)
pip install llama-cpp-python
```

---

## Usage Examples

### 1. Import Any Document (Easiest)

```bash
# PDF
python -m cli.main import document.pdf

# Word document
python -m cli.main import workflow.docx --renderer graphviz

# From clipboard
python -m cli.main import --clipboard

# With LLM extraction for complex documents
python -m cli.main import complex_process.pdf \
    --extraction local-llm \
    --model-path ./models/model.gguf \
    --renderer d2 \
    --d2-layout elk
```

### 2. Generate from Workflow File

Create a file `workflow.txt`:

```
1. User submits order
2. Validate order details
3. Check if items are in stock
   - If yes: Continue to step 4
   - If no: Display out-of-stock message and end
4. Query total price from database
5. Process payment
6. Check if payment successful
   - If yes: Generate invoice document
   - If no: Display payment error
7. Send confirmation email
8. End
```

Then generate:

```bash
# Fast heuristic + Graphviz (recommended for most use cases)
python -m cli.main generate workflow.txt -o flowchart.png --renderer graphviz

# LLM extraction for deeper semantic understanding
python -m cli.main generate workflow.txt -o flowchart.svg \
    --extraction local-llm \
    --model-path ./models/model.gguf \
    --renderer graphviz

# Modern D2 aesthetics with TALA layout
python -m cli.main generate workflow.txt -o flowchart.svg --renderer d2 --d2-layout tala

# Zero-dependency HTML output
python -m cli.main generate workflow.txt -o flowchart.html --renderer html
```

### 3. Web Interface

```bash
python web/app.py
# Open http://localhost:5000
```

Optional runtime temp override:

```bash
# PowerShell
$env:FLOWCHART_TMP_ROOT="C:\temp\flowcharts-web"
python web/app.py

# bash/zsh
FLOWCHART_TMP_ROOT=/tmp/flowcharts-web python web/app.py
```

1. Drag & drop your document (PDF, DOCX, TXT, MD)
2. Select extraction method (Heuristic or Local LLM)
3. Choose rendering engine (Graphviz, D2, Kroki, Mermaid)
4. Click **Generate Flowchart**
5. Download in your preferred format

### 4. Check Engine Status

```bash
python -m cli.main renderers
```

Outputs a status table showing which extraction and rendering engines are installed and ready.

### 5. Validate Without Generating

```bash
python -m cli.main validate workflow.txt
python -m cli.main validate workflow.txt --verbose
```

---

## Choosing an Extraction Method

| Scenario | Recommended | Why |
|----------|-------------|-----|
| Simple numbered workflows | `--extraction heuristic` | Fast, deterministic, zero overhead |
| Complex SOPs with nested logic | `--extraction local-llm` | Semantic reasoning handles ambiguity |
| CI/CD pipelines | `--extraction heuristic` | No model download needed |
| Proprietary sensitive documents | `--extraction local-llm` | 100% local, no data leaves your machine |
| Low-resource hardware (<4GB RAM) | `--extraction heuristic` | No model loading required |
| Don't know / first time | `--extraction auto` | Picks the best available method |

## Choosing a Renderer

| Scenario | Recommended | Why |
|----------|-------------|-----|
| General use, fast output | `--renderer graphviz` | Near-instant, clean hierarchical layout |
| Modern visual aesthetics | `--renderer d2` | ELK/TALA engines, polished output |
| Multiple diagram formats needed | `--renderer kroki` | Unified API, swap engines at will |
| Zero dependency environments | `--renderer html` | Pure Python, renders in any browser |
| GitHub/GitLab README embedding | `--renderer mermaid` | Native Mermaid syntax support |
| CI/CD without system binaries | `--renderer html` | No Graphviz/D2/Docker needed |

---

## Troubleshooting

### "LLM extraction unavailable"

```bash
pip install ".[llm]"
```

Then download a GGUF model and pass it via `--model-path`.

### "Graphviz not found"

Install the system binary:
- macOS: `brew install graphviz`
- Ubuntu: `sudo apt-get install graphviz`
- Windows: `choco install graphviz`

### "D2 binary not found"

Install D2: https://d2lang.com/tour/install

### "Kroki connection refused"

```bash
docker run -d -p 8000:8000 yuzutech/kroki
```

### "spaCy model not found"

```bash
python -m spacy download en_core_web_sm
```

### Renderer failed, want fallback

The CLI automatically falls back to HTML output if the selected renderer fails. You can also explicitly use:

```bash
python -m cli.main generate workflow.txt -o output.html --renderer html
```

---

## Next Steps

- Read the **[IMPORT_GUIDE.md](IMPORT_GUIDE.md)** for document import details
- Check **[docs/API_REFERENCE.md](docs/API_REFERENCE.md)** for programmatic usage
- Run `python -m cli.main info` for ISO 5807 symbol reference
- Try the example workflows in `examples/`
