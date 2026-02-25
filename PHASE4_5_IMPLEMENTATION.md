# Phase 4 & 5 Implementation Notes

## Phase 4: Interface Enhancement

### New CLI Flags

| Flag | Default | Options | Description |
|------|---------|---------|-------------|
| `--quantization` / `-q` | `5bit` | `4bit`, `5bit`, `8bit` | LLM quantization level |
| `--renderer auto` | — | Added to existing | Auto-select best renderer |
| `--extraction auto` | — | Added to existing | Auto-select best extractor |

### WebSocket Real-Time Preview

`web/websocket_handler.py` implements Socket.IO for real-time flowchart generation:

**Client Events:**
- `generate_live` → Send workflow text, receive incremental updates
- `ping_capabilities` → Request system capability snapshot

**Server Events:**
- `progress` → Stage updates with percentage (init → extract → build → validate → generate → done)
- `node` → Individual node data streamed as graph is built
- `validation` → ISO 5807 validation results
- `mermaid_code` → Generated Mermaid.js source
- `result` → Final complete result object
- `error` → Error messages

**Dependencies:** `pip install flask-socketio` (optional — app works without it)

### Async Background Rendering

`web/async_renderer.py` provides non-blocking rendering:

```
POST /api/render/async    → Submit job, get job_id
GET  /api/render/status/X  → Poll job status
GET  /api/render/download/X → Download completed output
```

- Thread-pool with semaphore (max 3 concurrent renders)
- Automatic HTML fallback on renderer failure
- 1-hour TTL with automatic cleanup

### Local Model Discovery

```
GET /api/models → List GGUF files in common directories
```

Searches: `~/.cache/huggingface`, `~/models`, `./models`

### Pure Python Air-Gapped Fallback

The `html` renderer always works — no Docker, no Node.js, no binaries:
- Generates standalone HTML with embedded Mermaid CDN
- Client-side browser rendering only
- Automatic fallback when other renderers fail

## Phase 5: Dynamic Routing Controller

### Capability Detector (`src/capability_detector.py`)

Probes system for:

| Category | Checks |
|----------|--------|
| Hardware | Total/available RAM, CPU count, platform, architecture |
| GPU | CUDA (nvidia-smi), Metal (macOS system_profiler) |
| Python packages | llama-cpp-python, instructor, graphviz, spacy, flask-socketio |
| System binaries | dot, d2, mmdc, node, docker |
| Services | Kroki health check via HTTP |

### Auto-Selection Logic

**Extraction:**
1. If `--extraction auto` and model path provided → check LLM prerequisites → use `local-llm` if available
2. If LLM available AND ≥5GB RAM (or GPU present) → recommend `local-llm`
3. Otherwise → `heuristic` (always available)

**Renderer (priority order):**
1. Graphviz (native, fastest, no browser)
2. D2 (modern aesthetics)
3. Mermaid with mmdc (full image export)
4. Kroki (multi-engine container)
5. HTML (pure Python, zero dependencies)

### Adaptive Fallback Chain

When rendering fails, the pipeline automatically tries:
```
Selected Renderer → Mermaid → Pure Python HTML
```

This ensures output is always generated regardless of environment.

### Config Validation

```python
pipeline = FlowchartPipeline(config)
issues = pipeline.validate_config()  # Returns list of warnings
```

CLI and web API both surface these warnings before execution.

### New API Endpoint

```
GET /api/capabilities → Full system assessment
GET /api/capabilities?refresh=true → Force re-scan
```

### Enhanced `flowchart renderers` Command

Now shows full hardware assessment, all engines, and auto recommendations.

## Files Changed

| File | Phase | Description |
|------|-------|-------------|
| `src/capability_detector.py` | 5 | Hardware/software probing and recommendation engine |
| `src/pipeline.py` | 5 | Adaptive auto-selection + fallback chain |
| `web/websocket_handler.py` | 4 | Socket.IO real-time preview |
| `web/async_renderer.py` | 4 | Background rendering job manager |
| `web/app.py` | 4+5 | Capabilities API, async renders, model discovery, WebSocket |
| `cli/main.py` | 4+5 | Quantization flag, auto mode, config validation |
| `PHASE4_5_IMPLEMENTATION.md` | — | This file |

## Usage Examples

```bash
# Auto-detect everything
flowchart generate workflow.txt --extraction auto --renderer auto

# Full LLM pipeline with quantization
flowchart generate workflow.txt \
  --extraction local-llm \
  --model-path ./models/llama-3-8b.Q4_K_M.gguf \
  --quantization 4bit \
  --renderer graphviz

# Check system capabilities
flowchart renderers

# Air-gapped mode (zero external dependencies)
flowchart generate workflow.txt --renderer html
```
