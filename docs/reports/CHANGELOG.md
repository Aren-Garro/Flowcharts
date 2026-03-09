# Changelog

## [1.0.0] - 2026-02-23

### Phase 1: Live Preview + SSE Pipeline
- In-browser Mermaid.js rendering via CDN (no download required)
- SSE-powered file processing with real-time stage indicators
- Multi-format export: SVG, PNG, .mmd, copy-to-clipboard
- ISO 5807 verb-to-symbol mapper (`iso_mapper.py`)
- spaCy NLP dependency tree analysis for accurate verb+object extraction
- Confidence scoring per node for uncertain classifications
- Theme switcher with instant re-render
- Direct textarea input for paste-and-generate

### Phase 2: Smart NLP + Confidence System
- Loop-back connection detection ("go back to step N", "repeat from step 2")
- Cross-reference detection maps to Predefined Process nodes
- Decision branch reconnection to main flow (no more dangling branches)
- Per-node confidence propagation from NLP through to rendering
- Low-confidence nodes styled with orange dashed borders
- Click-to-change node type dropdown in confidence panel
- Loop-back edges rendered as dotted arrows
- Loop target nodes highlighted with purple tint
- Enhanced pattern library: 6 loop patterns, 7 crossref patterns, 5 parallel patterns
- Validation warnings panel for structural issues
- Color legend for all node types
- Keyboard shortcuts: Ctrl+Enter generate, Ctrl+S export SVG

### Phase 3: Production Polish
- URL fetch endpoint (`/api/fetch-url`) with requests + BeautifulSoup
- 5 built-in sample workflows (login, e-commerce, bug triage, ETL, onboarding)
- Sample workflow dropdown populated from `/api/samples` on page load
- Generation history drawer (last 10 generations, click to restore)
- Zoom controls (+/-/1:1 reset) on diagram toolbar
- Fullscreen diagram mode (F11 or button, Esc to exit)
- Toast notifications replace static status bar
- Cache auto-cleanup with 30-minute TTL
- DRY helper functions for workflow building and caching
- Health endpoint reports version, cache stats, sample count
- Mobile responsive layout improvements

### Infrastructure
- `VERSION` file for release tracking
- `CHANGELOG.md` for release documentation
- Semantic commit messages throughout
