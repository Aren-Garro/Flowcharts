# ISO 5807 Flowchart Generator

Production-ready | 100+ tests | ISO 5807 compliant | Local LLM extraction | Multi-renderer | Web interface | Batch export

**NLP-driven workflow visualization conforming to ISO 5807 standards with local AI extraction, multi-engine rendering, batch export, and zero API costs.**

Transform natural language workflow descriptions into professional, printable flowcharts using heuristic NLP or local generative AI. Render via Graphviz, D2, Kroki, or Mermaid - all running 100% locally with no cloud dependencies. Process multi-section documents and export all workflows as ZIP archives.

> **Version 2.1.0** - Multi-engine architecture with local LLM support and batch export. See [PROJECT_STATUS.md](PROJECT_STATUS.md) for detailed metrics.

---

## What's New in v2.1.0

### Batch Export (New!)
- **Multi-workflow processing** from single documents
- **Split mode detection**: auto, section, subsection, procedure
- **ZIP archive generation** with all workflows
- **CLI and Web UI support**
- Process manuals, guides, and multi-procedure documents

### Local LLM Extraction (Phase 2)
- **Zero-shot workflow extraction** using quantized open-weight models (Llama-3, Mistral)
- Runs via `llama-cpp-python` with GGUF quantization - **5-6GB RAM** on consumer hardware
- CUDA/Metal GPU acceleration with automatic CPU fallback
- **Pydantic + Instructor** schema validation with self-correction loop
- Sliding window chunking for large documents (8,192 token context)

### Multi-Engine Rendering (Phase 3)
- **Graphviz**: Native C-compiled DOT layout via Sugiyama framework - near-instant rendering
- **D2**: Modern declarative diagrams with ELK/TALA/dagre layout engines
- **Kroki**: Unified Docker container supporting Mermaid, Graphviz, D2, PlantUML, and more
- **HTML fallback**: Standalone HTML with embedded Mermaid.js CDN - zero backend deps
- Mermaid.js remains supported (Node.js no longer required for basic operation)

### Enhanced Parsing (Phase 1)
- Custom **EntityRuler** with domain-specific regex for ISO 5807 symbol classification
- 8 entity types: `CONDITIONAL_FORK`, `DATABASE_OP`, `MANUAL_INTERVENTION`, `DOCUMENT_GEN`, `SUB_ROUTINE`, `IO_OPERATION`, `DISPLAY_OP`, `TERMINATOR`
- SVO triple extraction for concise node labels
- Deterministic fallback for constrained environments

###  Dynamic Pipeline (Phase 5)
- Auto-detection of available hardware and engines
- `--extraction` flag: `heuristic`, `local-llm`, `auto`
- `--renderer` flag: `mermaid`, `graphviz`, `d2`, `kroki`, `html`
- Graceful degradation  LLM failures fall back to enhanced heuristic

---

## Quick Start

See **[QUICKSTART.md](QUICKSTART.md)** for the full installation and usage guide.

```bash
# Clone
git clone https://github.com/Aren-Garro/Flowcharts.git
cd Flowcharts

# Create and activate virtual environment (recommended)
python -m venv .venv
# PowerShell
.\.venv\Scripts\Activate.ps1

# Install runtime dependencies
pip install .
python -m spacy download en_core_web_sm

# Check available engines on this machine
python -m cli.main renderers

# Generate polished output (recommended)
python -m cli.main generate examples/user_authentication.txt -o output.png --renderer graphviz

# Start web interface
python web/app.py
# Open http://127.0.0.1:5000
```

### End-to-End Flow

```bash
# 1) Preview or share as HTML
python -m cli.main generate examples/simple_workflow.txt -o preview.html --renderer html

# 2) Generate print-ready PDF/PNG/SVG
python -m cli.main generate examples/simple_workflow.txt -o final.pdf --renderer graphviz

# 3) Batch export a multi-workflow document
python -m cli.main batch manual.docx --split-mode auto --format png --renderer graphviz --zip
```

---

## Features

### Extraction Engines

| Engine | Flag | Dependencies | Best For |
|--------|------|-------------|----------|
| **Heuristic** | `--extraction heuristic` | spaCy + EntityRuler (built-in) | Fast, low resource, deterministic |
| **Local LLM** | `--extraction local-llm` | `llama-cpp-python`, `instructor` | Complex workflows, semantic understanding |
| **Auto** | `--extraction auto` | Detects available engines | Automatic best-effort |

### Rendering Engines

| Engine | Flag | Dependencies | Best For |
|--------|------|-------------|----------|
| **Graphviz** | `--renderer graphviz` | `graphviz` Python pkg + system binary | Fast rendering, CI/CD pipelines |
| **D2** | `--renderer d2` | D2 Go binary | Modern aesthetics, complex layouts |
| **Kroki** | `--renderer kroki` | Docker (`yuzutech/kroki`) | Multi-engine, unified API |
| **Mermaid** | `--renderer mermaid` | Node.js + mermaid-cli (optional) | GitHub/GitLab previews |
| **HTML** | `--renderer html` | None (pure Python) | Zero-dependency fallback |

### Core Capabilities

-  **Dual extraction**: Heuristic NLP or local generative AI
-  **ISO 5807 compliant**: All 10 standard symbol types
-  **Import documents**: PDF, DOCX, TXT, MD, or clipboard
-  **Batch export**: Process multi-section documents as ZIP
-  **Web interface**: Drag-and-drop browser UI with multi-renderer support
-  **4 rendering engines**: Graphviz, D2, Kroki, Mermaid/HTML
-  **Automatic validation**: ISO 5807 structural checks
-  **100% local**: Zero API costs, zero cloud dependencies, full data privacy
-  **Decision support**: Automatic True/False branch detection
-  **Loop handling**: Recognizes iterative workflows
-  **Comprehensive testing**: 100+ tests with ~85% code coverage
-  **Cross-platform**: Windows, macOS, Linux
-  **Rich CLI**: Progress indicators, colored output, status tables

---

## CLI Reference

### Commands

```bash
# Import any document and auto-generate flowchart
python -m cli.main import document.pdf
python -m cli.main import workflow.docx --renderer graphviz
python -m cli.main import --clipboard --extraction local-llm --model-path ./model.gguf

# Generate from workflow text file
python -m cli.main generate input.txt -o output.png --renderer graphviz
python -m cli.main generate input.txt -o output.svg --renderer d2 --d2-layout elk
python -m cli.main generate input.txt --extraction local-llm --model-path ./model.gguf

# Batch export all workflows from a document
python -m cli.main batch manual.docx --split-mode section -o ./outputs --format png
python -m cli.main batch procedures.pdf --split-mode auto --zip
python -m cli.main batch guide.txt --split-mode subsection --format svg --renderer graphviz

# Check available engines
python -m cli.main renderers

# Validate ISO 5807 compliance
python -m cli.main validate input.txt

# Show ISO 5807 symbol reference
python -m cli.main info

# Version
python -m cli.main version
```

### Pipeline Flags

| Flag | Values | Default | Description |
|------|--------|---------|-------------|
| `--extraction` / `-e` | `heuristic`, `local-llm`, `auto` | `heuristic` | Workflow extraction method |
| `--renderer` / `-r` | `mermaid`, `graphviz`, `d2`, `kroki`, `html` | `mermaid` | Rendering engine |
| `--model-path` | File path | None | Path to GGUF model file |
| `--gpu-layers` | Integer | `-1` (all) | GPU layers for LLM inference |
| `--context-size` | Integer | `8192` | LLM context window (tokens) |
| `--gv-engine` | `dot`, `neato`, `fdp`, `circo`, `twopi` | `dot` | Graphviz layout algorithm |
| `--d2-layout` | `dagre`, `elk`, `tala` | `elk` | D2 layout engine |
| `--kroki-url` | URL | `http://localhost:8000` | Local Kroki container URL |
| `-o` / `--output` | File path | `output.png` | Output file path |
| `-f` / `--format` | `png`, `svg`, `pdf`, `html`, `mmd` | Auto-detect | Output format |
| `-t` / `--theme` | `default`, `forest`, `dark`, `neutral` | `default` | Visual theme |
| `-d` / `--direction` | `TD`, `LR`, `BT`, `RL` | `TD` | Flow direction |

### Batch Export Flags

| Flag | Values | Default | Description |
|------|--------|---------|-------------|
| `--split-mode` | `auto`, `section`, `subsection`, `procedure`, `none` | `auto` | Document splitting strategy |
| `--zip` | Flag | False | Create ZIP archive instead of folder |
| `-o` / `--output` | Directory path | `./flowcharts` | Output directory for batch files |
| `-f` / `--format` | `png`, `svg`, `pdf`, `html` | `png` | Output format for all workflows |
| `--renderer` | Same as above | `graphviz` | Rendering engine for batch |

---

## Web Interface

```bash
python web/app.py
# Visit http://localhost:5000
```

Optional runtime temp override:

```bash
# PowerShell
$env:FLOWCHART_TMP_ROOT="C:\temp\flowcharts-web"
python web/app.py

# bash/zsh
FLOWCHART_TMP_ROOT=/tmp/flowcharts-web python web/app.py
```

Web server runtime options:

```bash
# PowerShell
$env:FLOWCHART_WEB_HOST="0.0.0.0"
$env:FLOWCHART_WEB_PORT="5000"
$env:FLOWCHART_WEB_DEBUG="0"
python web/app.py
```

Startup bootstrap (runs before the web server starts):

```bash
# Enabled by default when running web/app.py
$env:FLOWCHART_BOOTSTRAP_ON_START="1"
$env:FLOWCHART_BOOTSTRAP_REQUIREMENTS="1"
$env:FLOWCHART_BOOTSTRAP_LLM="1"
$env:FLOWCHART_BOOTSTRAP_SPACY="1"
$env:FLOWCHART_BOOTSTRAP_OLLAMA="1"
$env:FLOWCHART_OLLAMA_BOOTSTRAP_MODEL="llama3.2:3b"

# Optional strict mode: fail readiness when bootstrap checks fail
$env:FLOWCHART_BOOTSTRAP_STRICT="1"
```

### Features

- **Drag & drop document upload** (PDF, DOCX, TXT, MD)
- **Multi-workflow detection** from single documents
- **Batch export button** (appears when 2+ workflows detected)
- **Split mode selector**: auto, section, subsection, procedure
- **Format selector**: PNG, SVG, PDF, HTML
- **ZIP download** of all workflows
- Select extraction method and rendering engine
- Real-time workflow preview
- Multi-format download (PNG, SVG, PDF, HTML)
- SSE streaming for upload progress
- API endpoints: `/api/generate`, `/api/render`, `/api/batch-export`, `/api/renderers`

### Polished Export Defaults

- `POST /api/render` now accepts export controls:
  - `profile`: `polished` (default) or `fast_preview`
  - `quality_mode`: `draft_allowed` (default) or `certified_only`
  - `preferred_renderer`: `graphviz`, `d2`, `mermaid`, `kroki`, `html`
  - `strict_artifact_checks`: boolean
- Polished exports prioritize deterministic print quality (`graphviz -> d2 -> mermaid -> html`).
- Artifact checks validate file integrity for `png`, `svg`, and `pdf` before download.
- Response headers include selected renderer metadata:
  - `X-Flowchart-Profile`
  - `X-Flowchart-Requested-Renderer`
  - `X-Flowchart-Resolved-Renderer`
  - `X-Flowchart-Fallback-Chain`
  - `X-Flowchart-Artifact-Bytes`

### Batch Export UI

1. Upload a multi-section document (for example, training manual or SOP guide)
2. Let the system auto-detect workflows
3. Click **Batch Export All**
4. Choose split mode and output format
5. Click **Download ZIP**
6. Save the generated workflow package

---

## Batch Export Examples

### Processing a Multi-Section Manual

```bash
# Auto-detect workflow boundaries
python -m cli.main batch UserManual.docx --split-mode auto --format png

# Split by section headers (e.g., "Section 1", "Section 2")
python -m cli.main batch TrainingGuide.pdf --split-mode section --format svg --zip

# Split by subsections (e.g., "2.1", "2.2", "2.3")
python -m cli.main batch Procedures.docx --split-mode subsection --renderer graphviz

# Split by procedure headers (e.g., "Procedure:", "Process:")
python -m cli.main batch SOPs.txt --split-mode procedure --format pdf
```

### Output Structure

**Without --zip flag:**
```
flowcharts/
 Section_1_Setup.png
 Section_2_Configuration.png
 Section_3_Troubleshooting.png
 Section_4_Maintenance.png
```

**With --zip flag:**
```
flowcharts_1740512345.zip
   Section_1_Setup.png
   Section_2_Configuration.png
   Section_3_Troubleshooting.png
   Section_4_Maintenance.png
```

---

## ISO 5807 Symbol Support

| Symbol | Shape | Use Case | Example Keywords |
|--------|-------|----------|------------------|
| **Terminator** | Oval | Start/End points | "Start", "End", "Begin", "Finish" |
| **Process** | Rectangle | Processing steps | "Validate", "Calculate", "Process" |
| **Decision** | Diamond | Conditional branching | "If", "Check", "Whether" |
| **Input/Output** | Parallelogram | Data I/O | "Read file", "Send data", "Upload" |
| **Database** | Cylinder | Database operations | "Query", "Insert", "Commit" |
| **Display** | Hexagon | Screen output | "Show message", "Alert user" |
| **Document** | Wavy Rectangle | Document generation | "Generate report", "Export PDF" |
| **Predefined** | Double Rectangle | Sub-routines | "Call API", "Invoke function" |
| **Manual** | Trapezoid | Manual operations | "Wait for approval", "Review" |
| **Connector** | Circle | Flow connectors | Internal routing |

---

## Project Structure

```
Flowcharts/
 src/
    __init__.py
    models.py                  # Pydantic data models (Node, Connection, Flowchart, ISO 5807 enums)
    pipeline.py                # Dynamic routing controller (Phase 5)
    parser/
       nlp_parser.py          # NLP parser with spaCy + SVO extraction
       workflow_analyzer.py   # Semantic workflow analysis
       entity_ruler.py        # Domain-specific EntityRuler (Phase 1)
       llm_extractor.py       # Local LLM extraction via llama-cpp-python (Phase 2)
       iso_mapper.py          # ISO 5807 symbol mapper
       patterns.py            # Pattern definitions
    builder/
       graph_builder.py       # Directed graph construction
       validator.py           # ISO 5807 structural validation
    generator/
       mermaid_generator.py   # Mermaid.js code generation
    renderer/
       image_renderer.py      # Mermaid rendering + HTML fallback
       graphviz_renderer.py   # Graphviz/DOT rendering (Phase 3)
       d2_renderer.py         # D2 declarative rendering (Phase 3)
       kroki_renderer.py      # Kroki unified rendering (Phase 3)
    importers/
        document_parser.py     # Multi-format document ingestion
        content_extractor.py   # Smart workflow detection
        workflow_detector.py   # Multi-workflow detection + split modes
 cli/
    main.py                    # CLI with all pipeline flags (Phase 4)
    import_command.py          # Document import command
    batch_command.py           # Batch export command
 web/
    app.py                     # Flask web interface with batch export API
    templates/
        index.html             # Web UI with batch export button
 tests/                         # 100+ tests
 examples/                      # Example workflows
 docs/                          # Documentation
 requirements.txt               # Runtime dependency mirror for convenience installs
 QUICKSTART.md                  # Installation & usage guide
 IMPORT_GUIDE.md                # Document import guide
```

---

## Development Status

**Version 2.1.0 - Multi-Engine Architecture + Batch Export**

### Implemented

- Core Pydantic data models with ISO 5807 enums  
- Pattern recognition system  
- NLP parser (spaCy + EntityRuler integration)  
- **Custom EntityRuler with 8 domain-specific entity types**  
- Workflow analyzer with SVO triple extraction  
- Graph builder with structural validation  
- Mermaid.js generator  
- **Local LLM extractor (llama-cpp-python + Instructor)**  
- **Pydantic schema validation with self-correction loop**  
- **Sliding window document chunking**  
- **Graphviz native renderer (DOT/Sugiyama)**  
- **D2 declarative renderer (ELK/TALA/dagre)**  
- **Kroki unified container renderer**  
- **HTML fallback (embedded Mermaid.js CDN)**  
- **Dynamic pipeline with auto-detection and fallback**  
- **CLI with --extraction, --renderer, --model-path flags**  
- **Web interface with multi-renderer API**  
- **Batch export CLI command with --split-mode and --zip** (NEW)  
- **Batch export Web UI with split mode selector** (NEW)  
- **Multi-workflow detection from single documents** (NEW)  
- **ZIP archive generation for workflow batches** (NEW)  
- Document parser (PDF, DOCX, TXT, MD)  
- Smart content extraction  
- Import command with auto-detection  
- ISO 5807 validation system  
- Comprehensive test suite (100+ tests)  
- CI/CD pipeline (GitHub Actions)  
- Cross-platform support (Windows, macOS, Linux)  

### Test Coverage

- **Unit Tests**: 82+ tests covering all core components
- **E2E Tests**: 25+ integration tests
- **Edge Cases**: 10+ tests for special scenarios
- **Code Coverage**: ~85%
- **Python Versions**: 3.9, 3.10, 3.11, 3.12

### Performance

| Operation | Heuristic | Local LLM |
|-----------|-----------|----------|
| Workflow extraction (5 steps) | <100ms | 2-5s |
| Workflow extraction (20 steps) | <500ms | 5-15s |
| Batch export (5 workflows) | <2s | 10-30s |
| Graphviz render | <50ms | <50ms |
| D2 render | <100ms | <100ms |
| Mermaid HTML render | <10ms | <10ms |
| Mermaid-cli render (legacy) | 2-5s | 2-5s |

---

## Examples

The repository includes 6 validated example workflows:

```bash
# Quick test with Graphviz (no Node.js needed)
python -m cli.main generate examples/simple_workflow.txt -o test.png --renderer graphviz

# HTML output (zero dependencies)
python -m cli.main generate examples/user_authentication.txt -o test.html --renderer html

# D2 with modern aesthetics
python -m cli.main generate examples/database_operations.txt -o test.svg --renderer d2

# Batch export example
python -m cli.main batch examples/multi_workflow_guide.txt --split-mode auto --zip

# Check all engines
python -m cli.main renderers
```

---

## Workflow Syntax

### Simple Linear Flow

```
1. Start
2. Read user input
3. Process data
4. Save results
5. End
```

### With Decision Points

```
1. Start application
2. Check if user is logged in
   - If yes: Show dashboard
   - If no: Redirect to login
3. End
```

### With Loops

```
1. Start
2. Initialize counter
3. Read next record
4. Process record
5. Check if more records exist
   - If yes: Return to step 3
   - If no: Continue
6. Generate summary
7. End
```

### Complex Example

```
1. User submits order
2. Validate order details
3. Check if items are in stock
   - If yes: Continue to step 4
   - If no: Display out-of-stock message and end
4. Calculate total price from database
5. Process payment
6. Check if payment successful
   - If yes: Generate invoice document
   - If no: Display payment error
7. Send confirmation email
8. End
```

---

## Known Limitations

1. **Mermaid PNG/SVG export requires mermaid-cli**  Use `--renderer graphviz`, `--renderer d2`, or `--renderer html` as alternatives (no Node.js needed)
2. **Local LLM requires GGUF model download**  Models are 4-8GB; see [QUICKSTART.md](QUICKSTART.md) for download links
3. **D2 requires system binary**  Install from [d2lang.com](https://d2lang.com/tour/install)
4. **Kroki requires Docker**  Run `docker run -d -p 8000:8000 yuzutech/kroki`
5. **PDF must be text-based**  Scanned PDFs without OCR layer won't work
6. **spaCy model optional**  Graceful fallback to pattern-based parsing
7. **Batch export split detection**  Complex document structures may require manual split mode selection

---

## Testing

```bash
# Install test tooling
pip install -e ".[dev]"

# Run all tests
python run_all_tests.py

# Run specific test suites
pytest tests/test_e2e.py -v
pytest tests/ -v --tb=short
pytest tests/test_web_generate_overrides.py tests/test_web_batch_export_quality.py -v --tb=short

# Validate code
python validate_code.py
```

---

## Documentation

- **[QUICKSTART.md](QUICKSTART.md)**  Installation tiers & usage guide
- **[IMPORT_GUIDE.md](IMPORT_GUIDE.md)**  Document import & web interface
- [Backend Hygiene](docs/BACKEND_HYGIENE.md)
- [Quick Start Guide](docs/QUICK_START.md)
- [API Reference](docs/API_REFERENCE.md)
- [Tutorial](docs/TUTORIAL.md)
- [Project Status](PROJECT_STATUS.md)
- [Windows Setup](WINDOWS_QUICK_START.md)

---

## Contributing

Contributions welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

```bash
git clone https://github.com/Aren-Garro/Flowcharts.git
cd Flowcharts
./setup_dev.sh  # or setup_dev.bat on Windows
python run_all_tests.py
```

---

## License

MIT License  See [LICENSE](LICENSE) file for details.

## Author

**Aren Garro**  [GitHub](https://github.com/Aren-Garro)

## Acknowledgments

- **ISO 5807:1985** Standard for flowchart symbols
- [spaCy](https://spacy.io/)  NLP & EntityRuler
- [llama-cpp-python](https://github.com/abetlen/llama-cpp-python)  Local LLM inference
- [Instructor](https://github.com/jxnl/instructor)  Structured LLM output validation
- [Graphviz](https://graphviz.org/)  Graph layout & rendering
- [D2](https://d2lang.com/)  Modern declarative diagrams
- [Kroki](https://kroki.io/)  Unified diagram rendering
- [Mermaid.js](https://mermaid.js.org/)  Diagram syntax
- [Pydantic](https://docs.pydantic.dev/)  Data validation
- [PyPDF2](https://pypdf2.readthedocs.io/) & [pdfplumber](https://github.com/jsvine/pdfplumber)  PDF parsing
- [python-docx](https://python-docx.readthedocs.io/)  Word document parsing

---

**Repository:** https://github.com/Aren-Garro/Flowcharts  
**Issues:** https://github.com/Aren-Garro/Flowcharts/issues  
**Last Updated:** February 27, 2026 - v2.1.0 with backend hygiene updates


