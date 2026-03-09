# Phase 2 & 3 Implementation Notes

## Phase 2: CLI Enhancement

### New CLI Flags

All generation commands now accept:

| Flag | Default | Options | Description |
|------|---------|---------|-------------|
| `--extraction` / `-e` | `heuristic` | `heuristic`, `local-llm`, `auto` | Workflow extraction method |
| `--renderer` / `-r` | `mermaid` | `mermaid`, `graphviz`, `d2`, `kroki`, `html` | Rendering engine |
| `--model-path` | None | Path to `.gguf` file | Local LLM model for extraction |
| `--gpu-layers` | -1 | Integer | GPU layers for LLM (-1 = all) |
| `--context-size` | 8192 | Integer | LLM context window tokens |
| `--gv-engine` | `dot` | `dot`, `neato`, `fdp`, `circo`, `twopi` | Graphviz layout engine |
| `--d2-layout` | `elk` | `dagre`, `elk`, `tala` | D2 layout engine |
| `--kroki-url` | `http://localhost:8000` | URL | Local Kroki container |

### New CLI Command: `renderers`

```bash
flowchart renderers
```

Shows status of all rendering and extraction engines.

### Usage Examples

```bash
# Classic Mermaid (unchanged behavior)
flowchart generate workflow.txt -o output.png

# Graphviz rendering (no Node.js needed)
flowchart generate workflow.txt -o output.png --renderer graphviz

# D2 with TALA layout
flowchart generate workflow.txt -o output.svg --renderer d2 --d2-layout tala

# Local LLM extraction + Graphviz rendering
flowchart generate workflow.txt -o output.png \
  --extraction local-llm \
  --model-path ./models/llama-3-8b-instruct.Q5_K_M.gguf \
  --renderer graphviz

# Import with full pipeline config
flowchart import document.pdf --renderer d2 --extraction auto
```

### Automatic Fallback

If a selected renderer fails (e.g., D2 binary not installed), the system
automatically falls back to HTML output with embedded Mermaid CDN.

## Phase 3: Web Interface Enhancement

### New API Endpoints

#### `GET /api/renderers`
Returns availability status of all rendering and extraction engines.

```json
{
  "renderers": {
    "mermaid": {"available": true, "image_export": false, "note": "HTML output only"},
    "graphviz": {"available": true, "note": "Native DOT engine"},
    "d2": {"available": false, "note": "Install from d2lang.com"},
    "kroki": {"available": false, "note": "Start: docker run -d -p 8000:8000 yuzutech/kroki"}
  },
  "extractors": {
    "heuristic": {"available": true, "note": "spaCy + EntityRuler"},
    "local-llm": {"available": false, "note": "Install: pip install llama-cpp-python instructor"}
  }
}
```

#### `POST /api/generate` (Enhanced)
Now accepts additional fields:
- `extraction`: Extraction method selection
- `renderer`: Renderer selection 
- `model_path`: GGUF model path for LLM extraction
- `graphviz_engine`: Graphviz layout engine
- `d2_layout`: D2 layout engine
- `kroki_url`: Kroki container URL

Response now includes:
- `alt_code`: Alternative renderer source code (DOT/D2) when applicable
- `pipeline`: Active extraction/renderer info

#### `POST /api/render` (New)
Server-side rendering to downloadable file via any configured renderer.

#### `GET /api/health` (Enhanced)
Now includes renderer and extractor status.

### Architecture

All web API generation now routes through `FlowchartPipeline` with
`PipelineConfig`, ensuring consistent behavior between CLI and web.

## Files Changed

- `cli/main.py` - Complete rewrite with pipeline integration
- `cli/import_command.py` - Added pipeline_config parameter
- `web/app.py` - Added renderer/extractor APIs, pipeline integration
- `PHASE2_3_IMPLEMENTATION.md` - This file
