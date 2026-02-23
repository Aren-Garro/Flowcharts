# Phase 1 Implementation: Workflow Detection & Selection

## Overview

Phase 1 addresses two critical issues with the flowchart generator:

1. **Multi-Workflow Documents**: Documents containing multiple distinct workflows (e.g., setup procedures for different systems) are no longer compressed into a single overly complex flowchart
2. **ISO 5807 Compliance**: Complex workflows are detected and flagged with warnings to maintain readability standards

## Features Implemented

### 1. Workflow Boundary Detection

**File**: `src/importers/workflow_detector.py`

- **Section Detection**: Automatically identifies document sections using multiple patterns:
  - Markdown headers (`# Header`, `## Subheader`)
  - Numbered sections (`1.`, `1.1`, `2.3.1`)
  - ALL CAPS headers
  - Underlined headers

- **Hierarchy Building**: Constructs hierarchical section structure with parent-child relationships

- **Workflow Filtering**: Excludes non-workflow sections (Table of Contents, Glossary, References)

- **Content Analysis**: Each section is analyzed for:
  - Step count (numbered items, bullet points)
  - Decision points (if/then, yes/no)
  - Workflow keywords
  - Confidence score (0.0-1.0)

### 2. Complexity Analysis

**Automatic Complexity Assessment**:
- **Low**: ≤10 steps
- **Medium**: 11-20 steps  
- **High**: >20 steps (triggers warning)

**ISO 5807 Compliance Warnings**:
- High complexity workflows display warning messages
- Recommends splitting into sub-workflows
- Node count tracked and reported

### 3. Web Interface Enhancements

**File**: `web/app.py`, `web/templates/index.html`

#### Upload Endpoint
- `/api/upload` now returns multiple detected workflows
- Each workflow includes metadata:
  - ID, title, step count, decision count
  - Complexity level and warnings
  - Confidence score
  - Preview text

#### Workflow Selection
- **Visual Cards**: Each workflow displayed as a selectable card
- **Complexity Badges**: Color-coded (green/yellow/red)
- **Statistics**: Step count, decision count, confidence percentage
- **Warnings**: ISO 5807 compliance alerts for complex workflows
- **Multi-Select**: Generate one or multiple workflows

#### New Endpoint
- `/api/workflow/<cache_key>/<workflow_id>`: Fetch specific workflow content

## Usage

### For Your Document Example

Your AdmarNeuro setup manual contains **4 distinct workflows**:

1. **Section 4: Sierra Wedge Setup** (4.1-4.4)
2. **Section 5: Sierra Wave Setup** (5.1-5.4)  
3. **Section 6: Natus Systems Setup** (6.1-6.6)
4. **Section 7: Network Configuration** (7.1-7.2)

**Before Phase 1**:
- All 4 workflows compressed into single flowchart
- 50+ nodes, impossible to follow
- Violated ISO 5807 readability

**After Phase 1**:
- Upload document → See 4 separate workflows
- Select Sierra Wedge only → Generate clean 7-step flowchart
- Select multiple → Generate separate flowcharts for each
- Complexity warnings for Section 5 (high step count)

### Testing Phase 1

1. **Start the web server**:
   ```bash
   python web/app.py
   ```

2. **Upload your multi-workflow document**:
   - Navigate to http://localhost:5000
   - Drag & drop your DOCX/PDF

3. **View detected workflows**:
   - See list of workflows with metadata
   - Note complexity badges and warnings

4. **Select workflow(s)**:
   - Click workflow cards to select (highlights in blue)
   - Select one or multiple

5. **Generate**:
   - Choose output format (PNG, SVG, PDF, HTML)
   - Click "Generate Flowchart"
   - Downloads separate file for each selected workflow

## API Changes

### Upload Response (New Format)

```json
{
  "success": true,
  "cache_key": "filename_12345",
  "workflows": [
    {
      "id": "section_3",
      "title": "Sierra Wedge Setup",
      "step_count": 7,
      "decision_count": 2,
      "confidence": 0.85,
      "complexity": "Low",
      "complexity_warning": null,
      "preview": "USB Method — Requires Windows 10 32-bit...",
      "has_subsections": true
    },
    {
      "id": "section_4",
      "title": "Sierra Wave Setup",
      "step_count": 23,
      "decision_count": 5,
      "confidence": 0.92,
      "complexity": "High",
      "complexity_warning": "⚠ High complexity (23 steps). Consider splitting into sub-workflows.",
      "preview": "USB Method — Requires Windows 11 Pro 64-bit...",
      "has_subsections": true
    }
  ],
  "summary": {
    "total_workflows": 4,
    "total_steps": 45,
    "total_decisions": 12,
    "avg_confidence": 0.87
  }
}
```

## Known Limitations

1. **Session Management**: Workflow cache is in-memory (resets on server restart)
   - **Future**: Use Redis or database for persistence

2. **Clipboard Multi-Workflow**: Partially implemented
   - **Future**: Full clipboard workflow detection

3. **Sub-workflow Extraction**: Detected but not yet auto-split
   - **Phase 2**: Hierarchical flowchart generation

## Next Steps: Phase 2

1. **Complexity Analyzer**: Automatic step grouping for complex workflows
2. **Sub-process Extraction**: Break workflows into main + detail flowcharts
3. **Hierarchical Generation**: Drill-down capability
4. **Auto-simplification**: Collapse sequential steps

## Files Modified/Added

### New Files
- `src/importers/workflow_detector.py` - Core workflow detection logic
- `PHASE1_IMPLEMENTATION.md` - This document

### Modified Files  
- `web/app.py` - Added workflow detection endpoints
- `web/templates/index.html` - Enhanced UI with workflow selection
- `src/generator/mermaid_generator.py` - Fixed character encoding (previous commit)

## Testing Checklist

- [x] Single workflow document processing
- [x] Multi-workflow document detection
- [x] Section hierarchy parsing
- [x] Complexity analysis and warnings
- [x] Workflow selection UI
- [x] Single workflow generation
- [x] Multiple workflow batch generation
- [ ] Clipboard multi-workflow (partial)
- [ ] Session persistence

## Version

**Current**: v0.2.0
**Previous**: v0.1.0
