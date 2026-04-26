"""Web interface with live preview, SSE, URL fetch, sample workflows,
multi-renderer, LLM extraction, WebSocket streaming, async rendering,
hardware-aware capability detection, and batch export.

Phase 4+5: WebSocket for real-time preview, async background renders,
capability detection endpoint, pure-Python air-gapped fallback.

Enhancement 1: Batch export multi-workflow processing with ZIP output.

Run locally with: python web/app.py
Access at: http://localhost:5000
"""

import os
import json
import re
import time
import zipfile
import uuid
import base64
import tempfile
import threading
import xml.etree.ElementTree as ET
from io import BytesIO
from datetime import datetime, timezone
from queue import Queue, Empty
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from flask import Flask, render_template, request, jsonify, send_file, Response
from werkzeug.utils import secure_filename
import logging
from PIL import Image

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.importers.document_parser import DocumentParser
from src.importers.content_extractor import ContentExtractor
from src.importers.workflow_detector import WorkflowDetector
from src.parser.nlp_parser import NLPParser
from src.builder.graph_builder import GraphBuilder
from src.builder.validator import ISO5807Validator


def _fit_png_to_pdf_page(
    png_bytes: bytes,
    page_size: Optional[Tuple[int, int]] = None,
    margin: int = 36,
    min_readable_scale: float = 0.3,
    overlap: int = 24,
) -> bytes:
    """Place a PNG on printable PDF page(s) with margins.

    Large/tall exports are tiled onto multiple standard pages so the output
    stays printable and readable instead of inheriting the raw graph canvas size.
    """
    with Image.open(BytesIO(png_bytes)) as image:
        if image.mode in ('RGBA', 'LA'):
            flattened = Image.new('RGB', image.size, 'white')
            flattened.paste(image, mask=image.split()[-1])
            rgb_image = flattened
        else:
            rgb_image = image.convert('RGB')

        if page_size is None:
            page_size = (792, 612) if rgb_image.width >= rgb_image.height else (612, 792)
        page_width, page_height = page_size
        max_width = max(1, page_width - (margin * 2))
        max_height = max(1, page_height - (margin * 2))
        single_page_scale = min(max_width / rgb_image.width, max_height / rgb_image.height, 1.0)
        target_scale = single_page_scale if single_page_scale >= min_readable_scale else min(1.0, min_readable_scale)

        target_width = max(1, int(round(rgb_image.width * target_scale)))
        target_height = max(1, int(round(rgb_image.height * target_scale)))
        resized = rgb_image.resize((target_width, target_height), Image.LANCZOS)

        if single_page_scale >= min_readable_scale:
            page = Image.new('RGB', (page_width, page_height), 'white')
            offset_x = (page_width - target_width) // 2
            offset_y = (page_height - target_height) // 2
            page.paste(resized, (offset_x, offset_y))
            pages = [page]
        else:
            usable_step_x = max(1, max_width - overlap)
            usable_step_y = max(1, max_height - overlap)

            x_starts = list(range(0, max(1, target_width - max_width + 1), usable_step_x))
            y_starts = list(range(0, max(1, target_height - max_height + 1), usable_step_y))
            last_x = max(0, target_width - max_width)
            last_y = max(0, target_height - max_height)
            if not x_starts or x_starts[-1] != last_x:
                x_starts.append(last_x)
            if not y_starts or y_starts[-1] != last_y:
                y_starts.append(last_y)

            pages = []
            for y_start in y_starts:
                for x_start in x_starts:
                    crop = resized.crop((
                        x_start,
                        y_start,
                        min(x_start + max_width, target_width),
                        min(y_start + max_height, target_height),
                    ))
                    page = Image.new('RGB', (page_width, page_height), 'white')
                    page.paste(crop, (margin, margin))
                    pages.append(page)

        pdf_bytes = BytesIO()
        first_page, *rest = pages
        first_page.save(pdf_bytes, format='PDF', save_all=bool(rest), append_images=rest)
        return pdf_bytes.getvalue()
from src.generator.mermaid_generator import MermaidGenerator
from src.renderer.image_renderer import ImageRenderer
from src.pipeline import FlowchartPipeline, PipelineConfig
from src.capability_detector import CapabilityDetector
from src.parser.ollama_extractor import discover_ollama_models
from src.quality_assurance import evaluate_quality, build_source_snapshot, QualityThresholds
from src.models import NodeType
from src import __version__
from web.async_renderer import render_manager
from web.startup import run_startup_preflight
from web.html_fallback import HTMLFallbackRenderer

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
DEFAULT_OLLAMA_BASE_URL = os.environ.get('FLOWCHART_OLLAMA_BASE_URL', 'http://localhost:11434').strip() or 'http://localhost:11434'


def _resolve_tmp_root() -> Path:
    """Resolve runtime temp directory root.

    Priority:
    1. FLOWCHART_TMP_ROOT env var (absolute or relative path)
    2. OS temp dir under flowcharts/web
    """
    override = os.environ.get('FLOWCHART_TMP_ROOT', '').strip()
    if override:
        return Path(override).expanduser().resolve()
    return (Path(tempfile.gettempdir()) / 'flowcharts' / 'web').resolve()


TMP_ROOT = _resolve_tmp_root()
UPLOAD_ROOT = TMP_ROOT / 'uploads'
JOB_ROOT = TMP_ROOT / 'jobs'
RENDER_ROOT = TMP_ROOT / 'renders'
for p in (UPLOAD_ROOT, JOB_ROOT, RENDER_ROOT):
    p.mkdir(parents=True, exist_ok=True)
app.config['UPLOAD_FOLDER'] = str(UPLOAD_ROOT)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


EXPORT_PROFILE_DEFAULTS: Dict[str, Dict[str, Any]] = {
    'polished': {
        'png_width': 4200,
        'png_height': 2800,
        'background': 'white',
        'pdf_margin': 42,
        'pdf_min_readable_scale': 0.42,
        'pdf_overlap': 36,
    },
    'fast_preview': {
        'png_width': 2200,
        'png_height': 1600,
        'background': 'white',
        'pdf_margin': 36,
        'pdf_min_readable_scale': 0.3,
        'pdf_overlap': 24,
    },
}


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {'1', 'true', 'yes', 'on'}


def _resolve_server_runtime_config() -> Dict[str, Any]:
    host = os.environ.get('FLOWCHART_WEB_HOST', '127.0.0.1').strip() or '127.0.0.1'
    port_raw = os.environ.get('FLOWCHART_WEB_PORT', '5000').strip() or '5000'
    try:
        port = int(port_raw)
    except ValueError:
        port = 5000
    debug = _env_bool('FLOWCHART_WEB_DEBUG', False)
    return {'host': host, 'port': port, 'debug': debug}


def _utc_iso(ts: Optional[float]) -> Optional[str]:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _json_payload(required_keys: Optional[List[str]] = None) -> Tuple[Optional[Dict[str, Any]], Optional[Any]]:
    """Return validated JSON dict payload or a Flask JSON error response."""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return None, (jsonify({'error': 'Invalid JSON payload'}), 400)

    if required_keys:
        for key in required_keys:
            if key not in payload:
                message = {
                    'cache_key': 'No cache key provided',
                    'url': 'No URL provided',
                    'workflow_text': 'No workflow text provided',
                    'text': 'No text provided',
                }.get(key, f'Missing required field: {key}')
                return None, (jsonify({'error': message}), 400)

    return payload, None


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}


def _normalize_export_profile(raw: Any) -> str:
    profile = str(raw or 'polished').strip().lower()
    return profile if profile in {'polished', 'fast_preview'} else 'polished'


def _export_profile_settings(profile: str) -> Dict[str, Any]:
    return dict(EXPORT_PROFILE_DEFAULTS.get(profile, EXPORT_PROFILE_DEFAULTS['polished']))


def _normalize_renderer(raw: Any) -> str:
    renderer = str(raw or 'mermaid').strip().lower()
    allowed = {'mermaid', 'graphviz', 'd2', 'kroki', 'html'}
    return renderer if renderer in allowed else 'mermaid'


def _export_renderer_candidates(
    *,
    profile: str,
    requested_renderer: str,
    preferred_renderer: Optional[str],
    has_workflow_text: bool,
) -> List[str]:
    if not has_workflow_text:
        return ['mermaid', 'html']

    base = (
        [requested_renderer, 'mermaid', 'html']
        if profile == 'fast_preview'
        else ['graphviz', 'd2', 'mermaid', 'html']
    )
    if preferred_renderer:
        base.insert(0, preferred_renderer)
    if requested_renderer:
        base.insert(0, requested_renderer)

    deduped: List[str] = []
    for item in base:
        normalized = _normalize_renderer(item)
        if normalized not in deduped:
            deduped.append(normalized)
    return deduped


def _validate_export_artifact(path: Path, format_name: str) -> Tuple[bool, List[str], int]:
    issues: List[str] = []
    if not path.exists():
        return False, ['render_artifact_missing'], 0

    size = path.stat().st_size
    if size <= 0:
        issues.append('render_artifact_empty')
        return False, issues, size

    fmt = format_name.lower()
    try:
        if fmt == 'pdf':
            with path.open('rb') as f:
                header = f.read(4)
            if header != b'%PDF':
                issues.append('invalid_pdf_header')
        elif fmt == 'png':
            with path.open('rb') as f:
                header = f.read(8)
            if header != b'\x89PNG\r\n\x1a\n':
                issues.append('invalid_png_header')
        elif fmt == 'svg':
            ET.fromstring(path.read_text(encoding='utf-8', errors='replace'))
    except Exception:
        issues.append(f'invalid_{fmt}_artifact')

    return len(issues) == 0, issues, size


def _export_strategy_name(
    *,
    profile: str,
    final_renderer: str,
    client_layout: bool = False,
) -> str:
    normalized_profile = _normalize_export_profile(profile)
    if client_layout:
        return f'client-layout-{normalized_profile}'
    return f'{str(final_renderer or "unknown").strip().lower()}-{normalized_profile}'

# WebSocket support (optional)
try:
    from web.websocket_handler import create_socketio
    socketio = create_socketio(app)
except Exception:
    socketio = None
    logger.info("WebSocket disabled (install flask-socketio for real-time preview)")

# Capability detector (singleton)
cap_detector = CapabilityDetector(ollama_base_url=DEFAULT_OLLAMA_BASE_URL)

ALLOWED_EXTENSIONS = {'txt', 'md', 'pdf', 'docx', 'doc'}
workflow_cache = {}
cache_timestamps = {}
CACHE_TTL = 1800  # 30 minutes
upgrade_jobs: Dict[str, Dict[str, Any]] = {}
UPGRADE_JOB_TTL = 3600  # 1 hour
upgrade_lock = threading.Lock()
startup_report: Dict[str, Any] = {
    'enabled': False,
    'strict': False,
    'ready': True,
    'checks': [],
    'warnings': [],
    'errors': [],
    'started_at': None,
    'finished_at': None,
    'duration_seconds': 0.0,
}


TERMINATOR_START_KEYWORDS = ('start', 'begin')
TERMINATOR_END_KEYWORDS = ('end', 'finish', 'stop')


def _node_type_value(node_type: Any) -> str:
    """Return normalized node type string."""
    if isinstance(node_type, NodeType):
        return node_type.value
    return str(node_type)


def _is_start_terminator(node: Any) -> bool:
    """Return True if node is a start-like terminator."""
    node_type = _node_type_value(getattr(node, 'node_type', ''))
    if node_type != NodeType.TERMINATOR.value:
        return False
    label = str(getattr(node, 'label', '')).lower()
    return any(k in label for k in TERMINATOR_START_KEYWORDS)


def _is_end_terminator(node: Any) -> bool:
    """Return True if node is an end-like terminator."""
    node_type = _node_type_value(getattr(node, 'node_type', ''))
    if node_type != NodeType.TERMINATOR.value:
        return False
    label = str(getattr(node, 'label', '')).lower()
    return any(k in label for k in TERMINATOR_END_KEYWORDS)


def _count_start_end_terminators(nodes: List[Any]) -> Tuple[int, int]:
    """Count current start-like and end-like terminators."""
    start_count = 0
    end_count = 0
    for node in nodes:
        if _is_start_terminator(node):
            start_count += 1
        if _is_end_terminator(node):
            end_count += 1
    return start_count, end_count


def _parse_node_type(raw_type: Any) -> Optional[NodeType]:
    """Parse node type override value safely."""
    if not isinstance(raw_type, str):
        return None
    raw_type = raw_type.strip().lower()
    if not raw_type:
        return None
    try:
        return NodeType(raw_type)
    except ValueError:
        return None


def _apply_node_overrides(flowchart: Any, raw_overrides: Any) -> Dict[str, Any]:
    """Apply optional node overrides to a flowchart and return audit metadata."""
    outcome: Dict[str, Any] = {
        'requested_count': 0,
        'applied_count': 0,
        'ignored': [],
    }
    if raw_overrides is None:
        return outcome

    if not isinstance(raw_overrides, list):
        outcome['ignored'].append({'id': '*', 'reason': 'invalid_overrides_payload'})
        return outcome

    outcome['requested_count'] = len(raw_overrides)
    if not raw_overrides:
        return outcome

    node_map = {node.id: node for node in flowchart.nodes}
    for override in raw_overrides:
        if not isinstance(override, dict):
            outcome['ignored'].append({'id': '*', 'reason': 'invalid_override_format'})
            continue

        node_id = override.get('id')
        if not isinstance(node_id, str) or not node_id.strip():
            outcome['ignored'].append({'id': '*', 'reason': 'missing_node_id'})
            continue

        node_id = node_id.strip()
        node = node_map.get(node_id)
        if node is None:
            outcome['ignored'].append({'id': node_id, 'reason': 'node_not_found'})
            continue

        applied_any = False

        parsed_type = _parse_node_type(override.get('type'))
        if override.get('type') is not None:
            if parsed_type is None:
                outcome['ignored'].append({'id': node_id, 'reason': 'invalid_node_type'})
            else:
                start_count, end_count = _count_start_end_terminators(flowchart.nodes)
                if parsed_type != NodeType.TERMINATOR:
                    if _is_start_terminator(node) and start_count <= 1:
                        outcome['ignored'].append({'id': node_id, 'reason': 'would_remove_last_start_terminator'})
                        parsed_type = None
                    if _is_end_terminator(node) and end_count <= 1:
                        outcome['ignored'].append({'id': node_id, 'reason': 'would_remove_last_end_terminator'})
                        parsed_type = None
                if parsed_type is not None:
                    node.node_type = parsed_type.value
                    applied_any = True

        if 'label' in override:
            label = override.get('label')
            if isinstance(label, str):
                label = label.strip()
                if label:
                    node.label = label
                    applied_any = True
                else:
                    outcome['ignored'].append({'id': node_id, 'reason': 'empty_label'})
            else:
                outcome['ignored'].append({'id': node_id, 'reason': 'invalid_label'})

        if applied_any:
            confidence = override.get('confidence', 1.0)
            if isinstance(confidence, (int, float)):
                confidence = max(0.0, min(1.0, float(confidence)))
            else:
                confidence = 1.0
            node.confidence = confidence
            outcome['applied_count'] += 1
        else:
            has_type = override.get('type') is not None
            has_label = 'label' in override
            if not has_type and not has_label:
                outcome['ignored'].append({'id': node_id, 'reason': 'no_supported_fields'})

    return outcome

SAMPLE_WORKFLOWS = {
    'user-login': {
        'title': 'User Login Flow',
        'description': 'Authentication with 2FA and lockout',
        'text': """1. User opens login page
2. Enter username and password
3. Check if credentials are valid
  - Yes: Check if 2FA is enabled
  - No: Increment failed attempts
4. If failed attempts >= 3, lock account
5. If 2FA enabled, send verification code
6. User enters verification code
7. Verify code is correct
  - Yes: Create session and redirect to dashboard
  - No: Display error message
8. Log authentication event to database
9. End"""
    },
    'order-processing': {
        'title': 'E-Commerce Order Processing',
        'description': 'From cart to delivery with payment and inventory',
        'text': """1. Customer submits order
2. Validate cart items and quantities
3. Check inventory availability
  - Yes: Reserve inventory
  - No: Display out-of-stock message
4. Calculate total with tax and shipping
5. Process payment through gateway
6. Check if payment successful
  - Yes: Generate order confirmation
  - No: Display payment error, return to step 4
7. Send confirmation email to customer
8. Save order to database
9. Notify warehouse for fulfillment
10. Update inventory records
11. End"""
    },
    'bug-triage': {
        'title': 'Bug Report Triage',
        'description': 'Issue classification and assignment workflow',
        'text': """1. Bug report received
2. Verify report has required fields
3. Check if duplicate exists in database
  - Yes: Link to existing issue and close
  - No: Continue triage
4. Determine severity level
5. If critical, alert on-call engineer
6. Assign to appropriate team
7. Estimate effort and set priority
8. Add to sprint backlog
9. Notify reporter of status
10. End"""
    },
    'data-pipeline': {
        'title': 'ETL Data Pipeline',
        'description': 'Extract, transform, load with validation',
        'text': """1. Schedule triggers pipeline run
2. Connect to source database
3. Extract raw data from tables
4. Validate data schema and types
5. Check if validation passes
  - Yes: Apply transformation rules
  - No: Log errors and send alert
6. Transform data per business rules
7. Check for duplicate records
8. Load data into warehouse
9. Verify row counts match
  - Yes: Update pipeline status to success
  - No: Rollback and retry from step 3
10. Generate pipeline report
11. Store report to document archive
12. End"""
    },
    'employee-onboarding': {
        'title': 'Employee Onboarding',
        'description': 'HR process from offer to first day',
        'text': """1. HR receives signed offer letter
2. Create employee record in database
3. Send welcome email to new hire
4. Provision IT equipment
5. Create accounts per IT procedure
6. If remote employee, ship equipment
7. Schedule orientation sessions
8. Assign onboarding buddy
9. Manager prepares first-week plan
10. Employee completes tax forms
11. Verify all documents received
  - Yes: Activate employee status
  - No: Send reminder and repeat from step 10
12. First day orientation
13. End"""
    }
}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _safe_float(value, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _check_decision_integrity(flowchart: Any) -> Dict[str, Any]:
    """Check that every decision node has at least two labeled outgoing branches.

    A flowchart whose diamonds dead-end into a single edge isn't really a
    flowchart — it's a chain. This is the cheapest sanity guard against parser
    glitches that lose YES/NO branches, and we surface it in the user-facing
    quality summary so business users get an actionable hint instead of a
    silently-degraded export.
    """
    nodes = list(getattr(flowchart, 'nodes', []) or [])
    connections = list(getattr(flowchart, 'connections', []) or [])

    decision_nodes = [
        node for node in nodes
        if _node_type_value(getattr(node, 'node_type', '')) == NodeType.DECISION.value
    ]
    incomplete: List[Dict[str, Any]] = []

    for node in decision_nodes:
        node_id = getattr(node, 'id', '')
        outgoing = [c for c in connections if getattr(c, 'from_node', '') == node_id]
        labeled = [c for c in outgoing if str(getattr(c, 'label', '') or '').strip()]
        labels_lower = {str(getattr(c, 'label', '') or '').strip().lower() for c in labeled}
        has_yes = any(label in {'yes', 'true', 'approved', 'pass', 'valid', 'ok'} for label in labels_lower)
        has_no = any(label in {'no', 'false', 'rejected', 'fail', 'invalid'} for label in labels_lower)

        if len(outgoing) < 2 or len(labeled) < 2:
            incomplete.append({
                'id': node_id,
                'label': str(getattr(node, 'label', '') or '')[:80],
                'branch_count': len(outgoing),
                'labeled_branches': len(labeled),
                'has_yes': has_yes,
                'has_no': has_no,
            })

    return {
        'total_decisions': len(decision_nodes),
        'decisions_with_branches': len(decision_nodes) - len(incomplete),
        'incomplete_decisions': incomplete,
    }


def _user_quality_presentation(
    quality: Dict[str, Any],
    validation: Dict[str, Any],
    decision_integrity: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Map technical quality data to plain-language UX messaging."""
    if not quality:
        return {
            'status': 'review',
            'summary': 'Quality results are not available yet.',
            'recommended_actions': ['Generate again and review validation results.'],
        }

    blockers = quality.get('blockers') or []
    warnings = quality.get('warnings') or []
    validation_errors = (validation or {}).get('errors') or []
    validation_warnings = (validation or {}).get('warnings') or []
    incomplete_decisions = (decision_integrity or {}).get('incomplete_decisions') or []
    decision_action = None
    if incomplete_decisions:
        count = len(incomplete_decisions)
        suffix = 's' if count != 1 else ''
        decision_action = (
            f"{count} decision{suffix} missing a branch — review the source "
            f"for a missing Yes/No outcome."
        )

    if blockers or validation_errors:
        actions = [
            'Review highlighted issues and edit unclear steps.',
            'Regenerate after applying changes.',
        ]
        if any('detection_confidence' in str(b) for b in blockers):
            actions.append('Add more explicit process steps in the source text.')
        if decision_action:
            actions.insert(0, decision_action)
        return {
            'status': 'issues',
            'summary': 'Issues found. Output generated, but review is required before final use.',
            'recommended_actions': actions,
        }

    if warnings or validation_warnings or incomplete_decisions or not quality.get('certified', False):
        actions = [
            'Check decision branches and end states.',
            'Use inline step edits for wording and node type fixes.',
        ]
        if decision_action:
            actions.insert(0, decision_action)
        return {
            'status': 'review',
            'summary': 'Flowchart generated successfully. A quick review is recommended.',
            'recommended_actions': actions,
        }

    return {
        'status': 'ready',
        'summary': 'Ready for use. Quality and ISO checks look good.',
        'recommended_actions': ['Export as SVG or PDF for professional sharing.'],
    }


def _normalize_workflow_input(raw_text: str) -> Dict[str, Any]:
    """Normalize workflow input and produce lightweight preflight guidance."""
    extractor = ContentExtractor()
    normalized_text = extractor.preprocess_for_parser(raw_text or "")
    workflow_summary = extractor.get_workflow_summary(normalized_text)

    detector = WorkflowDetector(split_mode='auto')
    detected_sections = detector.detect_workflows(raw_text or "")
    detector_summary = detector.get_workflow_summary(detected_sections)

    warnings_list: List[str] = []
    if detector_summary.get('total_workflows', 0) > 1:
        warnings_list.append('This input may contain multiple workflows. Review the selected flow before sharing.')
    if workflow_summary.get('decision_steps', 0) == 0 and re.search(r'\b(if|whether|otherwise|yes|no)\b', raw_text or '', re.IGNORECASE):
        warnings_list.append('Branch wording was detected, but no clear decision steps were reconstructed.')
    if workflow_summary.get('numbered_steps', 0) < 2 and workflow_summary.get('bullet_points', 0) > 2:
        warnings_list.append('This input is mostly bullets. Converting bullets to numbered steps will usually improve accuracy.')
    if workflow_summary.get('confidence', 0) < 0.45:
        warnings_list.append('Input structure is weak. Review flagged items before exporting.')

    inferred_title = 'Workflow'
    workflows = detector_summary.get('workflows') or []
    if workflows:
        inferred_title = workflows[0].get('title') or inferred_title
    elif normalized_text.strip():
        first_line = normalized_text.splitlines()[0].strip()
        inferred_title = first_line[:80] if first_line else inferred_title

    return {
        'normalized_text': normalized_text,
        'summary': {
            'title': inferred_title,
            'estimated_steps': workflow_summary.get('numbered_steps', 0) or workflow_summary.get('total_lines', 0),
            'decision_count': workflow_summary.get('decision_steps', 0),
            'workflow_candidates': detector_summary.get('total_workflows', 0),
            'input_confidence': round(float(workflow_summary.get('confidence', 0.0)), 2),
        },
        'warnings': warnings_list,
        'multiple_workflows_detected': detector_summary.get('total_workflows', 0) > 1,
        'input_confidence': round(float(workflow_summary.get('confidence', 0.0)), 2),
    }


def _review_reason(text: str) -> str:
    return text.strip().rstrip('.')


def _build_review_guidance(
    flowchart: Any,
    validation_result: Dict[str, Any],
    preflight: Dict[str, Any],
) -> Dict[str, Any]:
    """Build actionable review guidance for the highest-risk nodes."""
    validation_errors = validation_result.get('errors') or []
    validation_warnings = validation_result.get('warnings') or []
    node_reviews: List[Dict[str, Any]] = []

    for node in getattr(flowchart, 'nodes', []):
        node_id = str(getattr(node, 'id', ''))
        label = str(getattr(node, 'label', '') or '')
        node_type = _node_type_value(getattr(node, 'node_type', 'process'))
        if node_id in {'START', 'END'}:
            continue

        reasons: List[str] = []
        suggested_fixes: List[str] = []
        confidence = float(getattr(node, 'confidence', 0.0) or 0.0)
        original_text = str(getattr(node, 'original_text', '') or '')
        label_word_count = len(label.split())

        if confidence < 0.65:
            reasons.append(_review_reason('Low model confidence.'))
            suggested_fixes.append('Shorten label')
        if label_word_count > 7 or len(label) > 38:
            reasons.append(_review_reason('Label is long and may be hard to read in exports.'))
            suggested_fixes.append('Shorten label')
        if node_type == NodeType.DECISION.value and not label.endswith('?'):
            reasons.append(_review_reason('This looks like a decision but is not phrased as a question.'))
            suggested_fixes.append('Mark as decision')
        if node_type != NodeType.DECISION.value and re.search(r'\b(if|whether|approved|valid|ready|available|exists)\b', label, re.IGNORECASE):
            reasons.append(_review_reason('This step likely represents a decision.'))
            suggested_fixes.append('Mark as decision')
        if node_type == NodeType.PROCESS.value and label.lower().startswith('move to:'):
            reasons.append(_review_reason('This step looks like a phase transition.'))
            suggested_fixes.append('Treat as phase transition')
        if original_text and (',' in original_text or ';' in original_text or ' and ' in original_text.lower()) and len(original_text) > 48:
            reasons.append(_review_reason('This step may combine multiple actions.'))
            suggested_fixes.append('Split into 2 steps')

        node_validation_warnings = [
            item for item in validation_warnings
            if node_id.lower() in str(item).lower() or label.lower()[:18] in str(item).lower()
        ]
        for warning in node_validation_warnings[:2]:
            reasons.append(_review_reason(str(warning)))

        if not reasons:
            continue

        deduped_fixes: List[str] = []
        for fix in suggested_fixes:
            if fix not in deduped_fixes:
                deduped_fixes.append(fix)

        risk_score = len(reasons) + (1 if confidence < 0.65 else 0) + (1 if node_validation_warnings else 0)
        node_reviews.append({
            'id': node_id,
            'label': label,
            'type': node_type,
            'confidence': round(confidence, 3),
            'reasons': reasons[:3],
            'suggested_fixes': deduped_fixes[:4],
            'risk_score': risk_score,
        })

    node_reviews.sort(key=lambda item: (-item['risk_score'], item['confidence'], item['label']))
    top_review_nodes = node_reviews[:5]

    preflight_warnings = preflight.get('warnings') or []
    export_deferred = bool(
        preflight.get('input_confidence', 0.0) < 0.45
        or preflight.get('multiple_workflows_detected')
        or validation_errors
        or top_review_nodes
    )

    recommended_actions: List[str] = []
    if preflight_warnings:
        recommended_actions.append(preflight_warnings[0])
    if top_review_nodes:
        recommended_actions.append('Review the flagged nodes before sharing the diagram.')
    if validation_errors:
        recommended_actions.append('Resolve validation issues before exporting.')
    if not recommended_actions:
        recommended_actions.append('Export the shareable PDF when ready.')

    return {
        'top_review_nodes': top_review_nodes,
        'export_deferred': export_deferred,
        'recommended_actions': recommended_actions[:4],
    }


def _readiness_presentation(
    quality: Dict[str, Any],
    validation_result: Dict[str, Any],
    preflight: Dict[str, Any],
    review_guidance: Dict[str, Any],
) -> Dict[str, str]:
    """Map backend quality signals into business-facing readiness labels."""
    if review_guidance.get('export_deferred') and (
        validation_result.get('errors')
        or preflight.get('input_confidence', 0.0) < 0.45
    ):
        return {
            'status': 'likely_inaccurate',
            'label': 'Likely inaccurate',
            'summary': 'The input or structure is too ambiguous to recommend sharing yet.',
        }

    if review_guidance.get('top_review_nodes') or not quality.get('certified', False):
        return {
            'status': 'needs_review',
            'label': 'Needs review',
            'summary': 'A quick guided review is recommended before sharing this output.',
        }

    return {
        'status': 'ready',
        'label': 'Ready to share',
        'summary': 'This output looks ready to share as a polished artifact.',
    }


def sse_event(data, event=None):
    msg = ''
    if event:
        msg += f'event: {event}\n'
    msg += f'data: {json.dumps(data)}\n\n'
    return msg


def cleanup_cache():
    now = time.time()
    expired = [k for k, ts in cache_timestamps.items() if now - ts > CACHE_TTL]
    for k in expired:
        workflow_cache.pop(k, None)
        cache_timestamps.pop(k, None)


def cache_workflows(workflows, prefix='file'):
    cleanup_cache()
    cache_key = f"{prefix}_{os.getpid()}_{int(time.time())}"
    workflow_cache[cache_key] = workflows
    cache_timestamps[cache_key] = time.time()
    return cache_key


def build_workflow_list(workflows):
    result = []
    for wf in workflows:
        complexity = 'High' if wf.step_count > 20 else ('Medium' if wf.step_count > 10 else 'Low')
        result.append({
            'id': wf.id, 'title': wf.title,
            'step_count': wf.step_count, 'decision_count': wf.decision_count,
            'confidence': round(wf.confidence, 2), 'complexity': complexity,
            'complexity_warning': f'High complexity ({wf.step_count} steps). Consider splitting.' if wf.step_count > 20 else None,
            'preview': wf.content[:200] + ('...' if len(wf.content) > 200 else ''),
            'has_subsections': len(wf.subsections) > 0
        })
    return result


def _single_workflow_summary(workflow_text: str, workflow: Optional[Any] = None) -> Dict[str, Any]:
    extractor = ContentExtractor()
    summary = extractor.get_workflow_summary(workflow_text)
    if workflow is not None:
        summary['workflow_title'] = workflow.title
        summary['detector_step_count'] = workflow.step_count
        summary['detector_decision_count'] = workflow.decision_count
        summary['detector_confidence'] = round(workflow.confidence, 2)
    summary['step_count'] = int(summary.get('numbered_steps') or summary.get('step_count') or 0)
    summary['decision_count'] = int(summary.get('decision_steps') or summary.get('decision_count') or 0)
    summary['avg_confidence'] = float(summary.get('confidence') or 0)
    return summary


# ── Phase 5: Capability Detection ──

@app.route('/api/capabilities', methods=['GET'])
def get_capabilities():
    """Return full hardware + software capability assessment."""
    force = request.args.get('refresh', 'false').lower() == 'true'
    if force:
        cap_detector._cache = None
    return jsonify({'success': True, **cap_detector.get_summary()})


@app.route('/api/renderers', methods=['GET'])
def get_renderers():
    """Return available rendering engines and their status."""
    summary = cap_detector.get_summary()
    return jsonify({
        'success': True,
        'renderers': summary['renderers']['details'],
        'extractors': summary['extractors']['details'],
        'recommended': {
            'extraction': summary['extractors']['recommended'],
            'renderer': summary['renderers']['recommended'],
        },
    })


@app.route('/api/models', methods=['GET'])
def get_local_models():
    """List available GGUF model files in common directories."""
    models = []
    search_dirs = [
        Path.home() / '.cache' / 'huggingface',
        Path.home() / 'models',
        Path.home() / '.local' / 'share' / 'models',
        Path.cwd() / 'models',
    ]
    for d in search_dirs:
        if d.exists():
            for f in d.rglob('*.gguf'):
                size_gb = round(f.stat().st_size / (1024**3), 2)
                models.append({
                    'path': str(f),
                    'name': f.name,
                    'size_gb': size_gb,
                    'directory': str(f.parent),
                })
    models.sort(key=lambda m: m['name'])
    return jsonify({'success': True, 'models': models})


@app.route('/api/ollama/models', methods=['GET'])
def get_ollama_models():
    """List available Ollama models for a given base URL."""
    base_url = request.args.get('base_url', DEFAULT_OLLAMA_BASE_URL)
    info = discover_ollama_models(base_url=base_url)
    return jsonify({'success': True, **info})


# ── Enhancement 1: Batch Export ──

@app.route('/api/batch-export', methods=['POST'])
def batch_export():
    """Export multiple workflows from cached document as ZIP."""
    try:
        data, error_response = _json_payload(required_keys=['cache_key'])
        if error_response is not None:
            return error_response

        cache_key = data['cache_key']
        if cache_key not in workflow_cache:
            return jsonify({'error': 'Cache expired. Re-upload document.'}), 404

        workflows = workflow_cache[cache_key]
        split_mode = data.get('split_mode', 'none')  # If 'none', use existing workflows
        format = data.get('format', 'png')
        renderer = data.get('renderer', 'mermaid')
        extraction = _normalize_extraction_method(data.get('extraction', 'heuristic'))
        theme = data.get('theme', 'default')
        direction = data.get('direction', 'LR')
        quality_mode = data.get('quality_mode', 'draft_allowed')
        min_detection_confidence_certified = _safe_float(
            data.get('min_detection_confidence_certified', 0.65), 0.65
        )
        model_path = data.get('model_path')
        ollama_base_url = data.get('ollama_base_url', DEFAULT_OLLAMA_BASE_URL)
        ollama_model = data.get('ollama_model')
        validate_iso = data.get('validate', True)
        include_validation_report = data.get('include_validation_report', True)
        include_qa_manifest = data.get('include_qa_manifest', True)
        include_source_snapshot = data.get('include_source_snapshot', True)

        # If split_mode is not 'none', re-detect workflows with new split strategy
        if split_mode != 'none':
            # Get original text from workflows
            full_text = '\n\n'.join(wf.content for wf in workflows)
            detector = WorkflowDetector(split_mode=split_mode)
            workflows = detector.detect_workflows(full_text)
            if not workflows:
                return jsonify({'error': f'No workflows detected with split mode: {split_mode}'}), 400

        # Create temp directory for batch export
        temp_dir = JOB_ROOT / f"job_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        temp_dir.mkdir(parents=True, exist_ok=True)
        zip_path = temp_dir / 'workflows.zip'

        config = PipelineConfig(
            extraction=extraction,
            renderer=renderer,
            model_path=model_path,
            ollama_base_url=ollama_base_url,
            ollama_model=ollama_model,
            direction=direction,
            theme=theme,
            validate=validate_iso,
        )
        pipeline = FlowchartPipeline(config)

        success_count = 0
        failed_count = 0
        temp_files = []
        validation_entries = []
        source_snapshots = []

        for i, workflow in enumerate(workflows, 1):
            try:
                workflow_name = workflow.title or f"Workflow_{i}"
                # Sanitize filename
                safe_name = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in workflow_name)
                safe_name = safe_name.strip().replace(' ', '_')
                workflow_result = {
                    'workflow': workflow_name,
                    'output_file': f"{safe_name}.{format}",
                    'rendered': False,
                    'iso_5807': {'is_valid': None, 'errors': [], 'warnings': []},
                }

                # Extract steps
                steps = pipeline.extract_steps(workflow.content)
                if not steps:
                    logger.warning(f"No steps in workflow: {safe_name}")
                    failed_count += 1
                    workflow_result['error'] = 'No workflow steps detected'
                    validation_entries.append(workflow_result)
                    continue

                # Build flowchart
                flowchart = pipeline.build_flowchart(steps, title=workflow_name)
                extraction_meta = pipeline.get_last_extraction_metadata()
                workflow_result['pipeline'] = extraction_meta

                validator = ISO5807Validator()
                is_valid, errors, warnings_list = validator.validate(flowchart)
                if validate_iso:
                    workflow_result['iso_5807'] = {
                        'is_valid': bool(is_valid),
                        'errors': errors,
                        'warnings': warnings_list,
                    }
                quality = evaluate_quality(
                    detection_confidence=getattr(workflow, 'confidence', None),
                    flowchart=flowchart,
                    validation_errors=errors,
                    validation_warnings=warnings_list,
                    extraction_meta=extraction_meta,
                    thresholds=QualityThresholds(
                        min_detection_confidence_certified=min_detection_confidence_certified
                    ),
                )
                workflow_result['quality'] = quality

                if include_source_snapshot:
                    source_snapshots.append({
                        'workflow': workflow_name,
                        'snapshot': build_source_snapshot(
                            workflow_text=workflow.content,
                            steps=steps,
                            flowchart=flowchart,
                            pipeline_config={
                                'extraction': extraction,
                                'renderer': renderer,
                                'direction': direction,
                                'theme': theme,
                                'quality_mode': quality_mode,
                                'min_detection_confidence_certified': min_detection_confidence_certified,
                            },
                        ),
                    })

                if quality_mode == 'certified_only' and not quality['certified']:
                    failed_count += 1
                    workflow_result['error'] = 'Blocked by certified quality gates'
                    validation_entries.append(workflow_result)
                    continue

                # Render to temp file
                output_file = temp_dir / f"{safe_name}.{format}"
                success = pipeline.render(flowchart, str(output_file), format=format)
                render_meta = pipeline.get_last_render_metadata()
                workflow_result['render'] = render_meta
                rendered_path = Path(render_meta.get('output_path') or output_file)
                resolved_format = rendered_path.suffix.lstrip('.').lower() if rendered_path.suffix else format
                artifact_ok, artifact_issues, artifact_bytes = _validate_export_artifact(rendered_path, resolved_format)
                workflow_result['artifact_format'] = resolved_format
                workflow_result['artifact_bytes'] = artifact_bytes
                workflow_result['resolved_renderer'] = render_meta.get('final_renderer', renderer)
                workflow_result['fallback_chain'] = render_meta.get('fallback_chain', [])
                # Re-evaluate quality with render integrity included.
                workflow_result['quality'] = evaluate_quality(
                    detection_confidence=getattr(workflow, 'confidence', None),
                    flowchart=flowchart,
                    validation_errors=errors,
                    validation_warnings=warnings_list,
                    extraction_meta=extraction_meta,
                    render_success=success,
                    output_path=str(rendered_path),
                    thresholds=QualityThresholds(
                        min_detection_confidence_certified=min_detection_confidence_certified
                    ),
                )

                if success and resolved_format != format:
                    success = False
                    workflow_result['error'] = (
                        f"Requested {format.upper()} export but renderer produced {resolved_format.upper()}"
                    )
                elif success and not artifact_ok:
                    success = False
                    workflow_result['error'] = f'Artifact validation failed: {", ".join(artifact_issues)}'

                if success and rendered_path.exists():
                    temp_files.append(rendered_path)
                    success_count += 1
                    workflow_result['rendered'] = True
                else:
                    logger.warning(f"Failed to render: {safe_name}")
                    failed_count += 1
                    workflow_result['error'] = workflow_result.get('error') or f'Failed to render via {renderer}'
                validation_entries.append(workflow_result)

            except Exception as e:
                logger.error(f"Error processing workflow {i}: {e}")
                failed_count += 1
                validation_entries.append({
                    'workflow': workflow.title or f"Workflow_{i}",
                    'output_file': None,
                    'rendered': False,
                    'iso_5807': {'is_valid': None, 'errors': [], 'warnings': []},
                    'error': str(e),
                })

        if success_count == 0:
            status = 422 if quality_mode == 'certified_only' else 500
            return jsonify({
                'error': 'No workflows met export quality gates' if quality_mode == 'certified_only'
                else 'No workflows successfully rendered',
                'quality_mode': quality_mode,
                'results': validation_entries,
            }), status

        # Create ZIP archive
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file_path in temp_files:
                zf.write(file_path, arcname=file_path.name)
            if include_qa_manifest:
                qa_manifest = {
                    'generated_at': int(time.time()),
                    'quality_mode': quality_mode,
                    'min_detection_confidence_certified': min_detection_confidence_certified,
                    'workflows_total': len(workflows),
                    'workflows_rendered': success_count,
                    'workflows_failed': failed_count,
                    'results': validation_entries,
                }
                zf.writestr('qa_manifest.json', json.dumps(qa_manifest, indent=2))
            if include_source_snapshot:
                zf.writestr('source_snapshot.json', json.dumps(source_snapshots, indent=2))
            if include_validation_report:
                report = {
                    'generated_at': int(time.time()),
                    'renderer': renderer,
                    'format': format,
                    'extraction': extraction,
                    'direction': direction,
                    'quality_mode': quality_mode,
                    'min_detection_confidence_certified': min_detection_confidence_certified,
                    'workflows_total': len(workflows),
                    'workflows_rendered': success_count,
                    'workflows_failed': failed_count,
                    'results': validation_entries,
                }
                zf.writestr('iso5807_validation_report.json', json.dumps(report, indent=2))

        # Send ZIP file
        response = send_file(
            zip_path,
            as_attachment=True,
            download_name=f'flowcharts_{int(time.time())}.zip',
            mimetype='application/zip'
        )

        # Cleanup will happen after response is sent
        # (Flask handles temp file cleanup automatically)

        logger.info(f"Batch export: {success_count} succeeded, {failed_count} failed")
        return response

    except Exception as e:
        logger.error(f"Batch export error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


# ── Core Endpoints ──

@app.route('/')
def index():
    return render_template('index.html', default_ollama_base_url=DEFAULT_OLLAMA_BASE_URL)


@app.route('/api/samples', methods=['GET'])
def get_samples():
    samples = []
    for key, sample in SAMPLE_WORKFLOWS.items():
        samples.append({
            'id': key,
            'title': sample['title'],
            'description': sample['description'],
            'step_count': len([l for l in sample['text'].split('\n') if l.strip() and l.strip()[0].isdigit()])
        })
    return jsonify({'success': True, 'samples': samples})


@app.route('/api/samples/<sample_id>', methods=['GET'])
def get_sample(sample_id):
    if sample_id not in SAMPLE_WORKFLOWS:
        return jsonify({'error': 'Sample not found'}), 404
    sample = SAMPLE_WORKFLOWS[sample_id]
    return jsonify({'success': True, 'text': sample['text'], 'title': sample['title']})


@app.route('/api/fetch-url', methods=['POST'])
def fetch_url():
    try:
        data, error_response = _json_payload(required_keys=['url'])
        if error_response is not None:
            return error_response

        url = data['url'].strip()
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        try:
            import requests as req
            resp = req.get(url, timeout=15, headers={'User-Agent': 'FlowchartGenerator/2.1.1'})
            resp.raise_for_status()
            content_type = resp.headers.get('content-type', '')
        except ImportError:
            return jsonify({'error': 'requests library not installed'}), 500
        except Exception as e:
            return jsonify({'error': f'Failed to fetch URL: {str(e)}'}), 400

        text = ''
        if 'html' in content_type:
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(resp.text, 'html.parser')
                for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
                    tag.decompose()
                text = soup.get_text(separator='\n', strip=True)
            except ImportError:
                import re
                text = re.sub(r'<[^>]+>', '\n', resp.text)
                text = re.sub(r'\n\s*\n', '\n', text)
        else:
            text = resp.text

        if not text.strip():
            return jsonify({'error': 'No text content found at URL'}), 400

        # Use WorkflowDetector with auto split mode
        detector = WorkflowDetector(split_mode='auto')
        workflows = detector.detect_workflows(text[:50000])

        if not workflows:
            extractor = ContentExtractor()
            workflow_text = extractor.preprocess_for_parser(text[:10000])
            return jsonify({'success': True, 'workflow_text': workflow_text, 'source': url, 'char_count': len(text)})

        cache_key = cache_workflows(workflows, 'url')
        summary = detector.get_workflow_summary(workflows)
        return jsonify({
            'success': True, 'cache_key': cache_key,
            'workflows': build_workflow_list(workflows),
            'summary': summary, 'source': url, 'char_count': len(text)
        })
    except Exception as e:
        logger.error(f"URL fetch error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/upload-stream', methods=['POST'])
def upload_stream():
    """Upload document with SSE progress and multi-workflow detection."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    if not allowed_file(file.filename):
        return jsonify({'error': f'Unsupported type. Allowed: {", ".join(ALLOWED_EXTENSIONS)}'}), 400

    filename = secure_filename(file.filename)
    filepath = Path(app.config['UPLOAD_FOLDER']) / filename
    file.save(filepath)

    def generate():
        try:
            yield sse_event({'stage': 'parse', 'pct': 10, 'msg': f'Parsing {filename}...'})
            parser = DocumentParser()
            result = parser.parse(filepath)
            if not result['success']:
                yield sse_event({'stage': 'error', 'msg': result.get('error', 'Parse failed')})
                return
            if not str(result.get('text') or '').strip():
                yield sse_event({'stage': 'error', 'msg': 'No extractable text found in uploaded document.'})
                return

            yield sse_event({'stage': 'detect', 'pct': 35, 'msg': 'Detecting workflows...'})
            # Use WorkflowDetector with auto split mode for multi-workflow detection
            detector = WorkflowDetector(split_mode='auto')
            workflows = detector.detect_workflows(result['text'])
            
            if not workflows:
                yield sse_event({'stage': 'error', 'msg': 'No workflows detected'})
                return

            workflow_count = len(workflows)
            yield sse_event({'stage': 'analyze', 'pct': 60, 'msg': f'Analyzing {workflow_count} workflow(s)...'})
            cache_key = cache_workflows(workflows, filename)
            summary = detector.get_workflow_summary(workflows)

            yield sse_event({'stage': 'build', 'pct': 85, 'msg': 'Building workflow data...'})
            workflow_list = build_workflow_list(workflows)

            yield sse_event({
                'stage': 'done', 'pct': 100, 
                'msg': f'Complete! Detected {workflow_count} workflow(s)',
                'data': {
                    'success': True, 'cache_key': cache_key,
                    'workflows': workflow_list, 'summary': summary,
                    'metadata': result.get('metadata', {})
                }
            })
        except Exception as e:
            logger.error(f"Stream error: {e}", exc_info=True)
            yield sse_event({'stage': 'error', 'msg': str(e)})
        finally:
            try:
                if filepath.exists():
                    filepath.unlink()
            except Exception:
                pass

    return Response(generate(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Standard upload endpoint (non-streaming) with multi-workflow detection."""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        if not allowed_file(file.filename):
            return jsonify({'error': f'Unsupported type. Allowed: {", ".join(ALLOWED_EXTENSIONS)}'}), 400

        filename = secure_filename(file.filename)
        filepath = Path(app.config['UPLOAD_FOLDER']) / filename
        file.save(filepath)

        try:
            parser = DocumentParser()
            result = parser.parse(filepath)
            if not result['success']:
                return jsonify({'error': result.get('error', 'Failed to parse')}), 400
            if not str(result.get('text') or '').strip():
                return jsonify({'error': 'No extractable text found in uploaded document.'}), 400

            # Use WorkflowDetector with auto split mode
            detector = WorkflowDetector(split_mode='auto')
            workflows = detector.detect_workflows(result['text'])
            if not workflows:
                return jsonify({'error': 'No workflows detected'}), 400

            cache_key = cache_workflows(workflows, filename)
            summary = detector.get_workflow_summary(workflows)
            return jsonify({
                'success': True, 'cache_key': cache_key,
                'workflows': build_workflow_list(workflows),
                'summary': summary, 'metadata': result.get('metadata', {})
            })
        finally:
            if filepath.exists():
                filepath.unlink()
    except Exception as e:
        logger.error(f"Upload error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/workflow/<cache_key>/<workflow_id>', methods=['GET'])
def get_workflow(cache_key, workflow_id):
    try:
        if cache_key not in workflow_cache:
            return jsonify({'error': 'Cache expired. Re-upload document.'}), 404
        workflows = workflow_cache[cache_key]
        workflow = next((wf for wf in workflows if wf.id == workflow_id), None)
        if not workflow:
            return jsonify({'error': f'Workflow {workflow_id} not found'}), 404

        extractor = ContentExtractor()
        workflow_text = extractor.preprocess_for_parser(workflow.content)
        return jsonify({'success': True, 'workflow_text': workflow_text, 'title': workflow.title,
                        'step_count': workflow.step_count, 'decision_count': workflow.decision_count,
                        'confidence': workflow.confidence})
    except Exception as e:
        logger.error(f"Get workflow error: {e}")
        return jsonify({'error': str(e)}), 500


def _normalize_extraction_method(raw_value: Any) -> str:
    raw = str(raw_value or 'auto').strip().lower()
    mapping = {
        'rules': 'heuristic',
        'spacy': 'heuristic',
        'llm': 'local-llm',
        'standard': 'heuristic',
        'enhanced_local_ai': 'auto',
    }
    return mapping.get(raw, raw)


def _extract_with_timeout(
    pipeline: FlowchartPipeline,
    workflow_text: str,
    timeout_ms: int,
) -> Tuple[List[Any], Dict[str, Any], bool, Optional[str]]:
    """Extract with timeout; fallback to heuristic when provider is slow."""
    extraction = _normalize_extraction_method(pipeline.config.extraction)
    if extraction == 'heuristic' or timeout_ms <= 0:
        steps = pipeline.extract_steps(workflow_text)
        return steps, pipeline.get_last_extraction_metadata(), False, None

    q: Queue = Queue(maxsize=1)

    def _worker():
        try:
            steps = pipeline.extract_steps(workflow_text)
            q.put(('ok', steps, pipeline.get_last_extraction_metadata(), None))
        except Exception as exc:
            q.put(('err', [], {}, exc))

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    thread.join(timeout=max(0.001, timeout_ms / 1000.0))
    if thread.is_alive():
        fallback_reason = f"{extraction} extraction timed out after {timeout_ms}ms"
        warnings_payload = {
            'requested_extraction': extraction,
            'resolved_extraction': extraction,
            'final_extraction': 'heuristic',
            'fallback_used': True,
            'fallback_reason': fallback_reason,
        }
        fallback_config = PipelineConfig(
            extraction='heuristic',
            renderer=pipeline.config.renderer,
            model_path=pipeline.config.model_path,
            ollama_base_url=pipeline.config.ollama_base_url,
            ollama_model=pipeline.config.ollama_model,
            quantization=pipeline.config.quantization,
            direction=pipeline.config.direction,
            theme=pipeline.config.theme,
            validate=pipeline.config.validate,
            graphviz_engine=pipeline.config.graphviz_engine,
            d2_layout=pipeline.config.d2_layout,
            kroki_url=pipeline.config.kroki_url,
        )
        fallback_pipeline = FlowchartPipeline(fallback_config)
        fallback_steps = fallback_pipeline.extract_steps(workflow_text)
        return fallback_steps, warnings_payload, True, fallback_reason

    try:
        status, steps, extraction_meta, exc = q.get_nowait()
    except Empty:
        status, steps, extraction_meta, exc = 'err', [], {}, RuntimeError('Extraction worker failed')

    if status == 'err':
        raise exc

    return steps, extraction_meta, False, None


def _build_generate_response(
    data: Dict[str, Any],
    *,
    force_extraction: Optional[str] = None,
    request_timeout_ms: int = 12000,
    allow_timeout_fallback: bool = True,
) -> Tuple[Dict[str, Any], int]:
    """Shared generate execution path for single-pass and upgrade jobs."""
    request_started = time.perf_counter()
    raw_workflow_text = data['workflow_text']
    title = data.get('title', 'Workflow')
    theme = data.get('theme', 'default')
    ux_mode = data.get('ux_mode', 'simple')
    validate_flag = data.get('validate', True)
    quality_mode = data.get('quality_mode', 'draft_allowed')
    include_source_snapshot = data.get('include_source_snapshot', False)
    node_overrides = data.get('node_overrides')
    min_detection_confidence_certified = _safe_float(
        data.get('min_detection_confidence_certified', 0.65), 0.65
    )
    extraction_method = _normalize_extraction_method(force_extraction or data.get('extraction', 'heuristic'))
    renderer_type = data.get('renderer', 'mermaid')
    model_path = data.get('model_path', None)
    ollama_base_url = data.get('ollama_base_url', DEFAULT_OLLAMA_BASE_URL)
    ollama_model = data.get('ollama_model')
    quantization = data.get('quantization', '5bit')
    direction = data.get('direction', 'LR')
    graphviz_engine = data.get('graphviz_engine', 'dot')
    d2_layout = data.get('d2_layout', 'elk')
    kroki_url = data.get('kroki_url', 'http://localhost:8000')

    config = PipelineConfig(
        extraction=extraction_method,
        renderer=renderer_type,
        model_path=model_path,
        ollama_base_url=ollama_base_url,
        ollama_model=ollama_model,
        quantization=quantization,
        direction=direction,
        theme=theme,
        validate=validate_flag,
        graphviz_engine=graphviz_engine,
        d2_layout=d2_layout,
        kroki_url=kroki_url,
    )

    pipeline = FlowchartPipeline(config)
    config_warnings = pipeline.validate_config()
    extraction_timed_out = False
    timeout_fallback_reason = None
    preflight = _normalize_workflow_input(raw_workflow_text)
    workflow_text = preflight['normalized_text'] or raw_workflow_text
    if title == 'Workflow' and preflight.get('summary', {}).get('title'):
        title = preflight['summary']['title']

    if allow_timeout_fallback:
        steps, extraction_meta, extraction_timed_out, timeout_fallback_reason = _extract_with_timeout(
            pipeline,
            workflow_text,
            request_timeout_ms,
        )
    else:
        steps = pipeline.extract_steps(workflow_text)
        extraction_meta = pipeline.get_last_extraction_metadata()

    if not steps:
        return {'error': 'No workflow steps detected'}, 400

    if extraction_meta.get('fallback_used') and extraction_meta.get('fallback_reason'):
        config_warnings.append(extraction_meta['fallback_reason'])
    if extraction_timed_out and timeout_fallback_reason:
        config_warnings.append(timeout_fallback_reason)

    build_started = time.perf_counter()
    flowchart = pipeline.build_flowchart(steps, title=title)
    build_ms = round((time.perf_counter() - build_started) * 1000, 2)
    override_meta = _apply_node_overrides(flowchart, node_overrides)

    validation_started = time.perf_counter()
    validation_result = {}
    if validate_flag:
        validator = ISO5807Validator()
        is_valid, errors, warnings = validator.validate(flowchart)
        validation_result = {'is_valid': is_valid, 'errors': errors, 'warnings': warnings}
    else:
        validator = ISO5807Validator()
        is_valid, errors, warnings = validator.validate(flowchart)
    validation_ms = round((time.perf_counter() - validation_started) * 1000, 2)

    generator = MermaidGenerator()
    mermaid_code = generator.generate_with_theme(flowchart, theme=theme, direction=direction)

    alt_code = None
    if renderer_type == 'graphviz':
        try:
            from src.renderer.graphviz_renderer import GraphvizRenderer
            gv = GraphvizRenderer(engine=graphviz_engine)
            alt_code = {'type': 'dot', 'source': gv.generate_dot(flowchart)}
        except Exception as e:
            logger.warning(f"Graphviz code gen failed: {e}")
    elif renderer_type == 'd2':
        try:
            from src.renderer.d2_renderer import D2Renderer
            d2 = D2Renderer(layout=d2_layout)
            alt_code = {'type': 'd2', 'source': d2.generate_d2(flowchart)}
        except Exception as e:
            logger.warning(f"D2 code gen failed: {e}")

    review_lookup = {item['id']: item for item in review_guidance['top_review_nodes']} if 'review_guidance' in locals() else {}
    node_confidence = []
    for node in flowchart.nodes:
        node_data = {'id': node.id, 'label': node.label, 'type': node.node_type, 'confidence': node.confidence}
        if hasattr(node, 'alternatives') and node.alternatives:
            node_data['alternatives'] = node.alternatives
        if node.id in review_lookup:
            node_data['review_reasons'] = review_lookup[node.id]['reasons']
            node_data['suggested_fixes'] = review_lookup[node.id]['suggested_fixes']
        node_confidence.append(node_data)

    quality_started = time.perf_counter()
    quality = evaluate_quality(
        detection_confidence=data.get('detection_confidence'),
        flowchart=flowchart,
        validation_errors=errors if 'errors' in locals() else [],
        validation_warnings=warnings if 'warnings' in locals() else [],
        extraction_meta=extraction_meta,
        thresholds=QualityThresholds(
            min_detection_confidence_certified=min_detection_confidence_certified
        ),
    )
    quality_ms = round((time.perf_counter() - quality_started) * 1000, 2)
    review_guidance = _build_review_guidance(flowchart, validation_result, preflight)
    review_lookup = {item['id']: item for item in review_guidance['top_review_nodes']}
    for node_data in node_confidence:
        review_item = review_lookup.get(node_data['id'])
        if review_item:
            node_data['review_reasons'] = review_item['reasons']
            node_data['suggested_fixes'] = review_item['suggested_fixes']
    readiness = _readiness_presentation(quality, validation_result, preflight, review_guidance)

    source_snapshot = None
    if include_source_snapshot:
        source_snapshot = build_source_snapshot(
            workflow_text=workflow_text,
            steps=steps,
            flowchart=flowchart,
            pipeline_config={
                'extraction': extraction_method,
                'renderer': renderer_type,
                'direction': direction,
                'theme': theme,
                'quality_mode': quality_mode,
                'min_detection_confidence_certified': min_detection_confidence_certified,
            },
        )

    timings = pipeline.get_last_timings()
    if extraction_timed_out:
        timings['extract_ms'] = float(request_timeout_ms)
    timings.setdefault('build_ms', build_ms)
    timings['validate_ms'] = validation_ms
    timings['quality_ms'] = quality_ms
    timings['total_ms'] = round((time.perf_counter() - request_started) * 1000, 2)

    if timings['total_ms'] > 3000:
        logger.info(
            "Slow generation detected: total_ms=%s extraction=%s final=%s fallback=%s renderer=%s",
            timings['total_ms'],
            extraction_meta.get('requested_extraction', extraction_method),
            extraction_meta.get('final_extraction', extraction_method),
            extraction_meta.get('fallback_reason'),
            renderer_type,
        )

    decision_integrity = _check_decision_integrity(flowchart)

    if quality_mode == 'certified_only' and not quality['certified']:
        user_quality = _user_quality_presentation(quality, validation_result, decision_integrity)
        return {
            'success': False,
            'error': 'Workflow does not meet certified quality gates',
            'quality': quality,
            'validation': validation_result,
            'applied_overrides': override_meta,
            'ux_mode': ux_mode,
            'user_quality_status': user_quality['status'],
            'user_quality_summary': user_quality['summary'],
            'user_recommended_actions': user_quality['recommended_actions'],
            'readiness_status': readiness['status'],
            'readiness_label': readiness['label'],
            'readiness_summary': readiness['summary'],
            'preflight': preflight,
            'review_guidance': review_guidance,
            'decision_integrity': decision_integrity,
            'timings': timings,
            'pipeline': {
                'extraction': extraction_method,
                'requested_extraction': extraction_meta.get('requested_extraction', extraction_method),
                'resolved_extraction': extraction_meta.get('resolved_extraction', extraction_method),
                'final_extraction': extraction_meta.get('final_extraction', extraction_method),
                'fallback_used': extraction_meta.get('fallback_used', False),
                'fallback_reason': extraction_meta.get('fallback_reason'),
                'renderer': renderer_type,
            },
        }, 422

    user_quality = _user_quality_presentation(quality, validation_result, decision_integrity)
    response = {
        'success': True,
        'mermaid_code': mermaid_code,
        'flowchart_data': _serialize_flowchart(flowchart, direction),
        'validation': validation_result,
        'applied_overrides': override_meta,
        'node_confidence': node_confidence,
        'stats': {
            'nodes': len(flowchart.nodes),
            'connections': len(flowchart.connections),
            'steps': len(steps),
            'decisions': decision_integrity.get('total_decisions', 0),
            'incomplete_decisions': len(decision_integrity.get('incomplete_decisions', [])),
        },
        'ux_mode': ux_mode,
        'user_quality_status': user_quality['status'],
        'user_quality_summary': user_quality['summary'],
        'user_recommended_actions': review_guidance['recommended_actions'] or user_quality['recommended_actions'],
        'readiness_status': readiness['status'],
        'readiness_label': readiness['label'],
        'readiness_summary': readiness['summary'],
        'preflight': preflight,
        'review_guidance': review_guidance,
        'decision_integrity': decision_integrity,
        'pipeline': {
            'extraction': extraction_method,
            'requested_extraction': extraction_meta.get('requested_extraction', extraction_method),
            'resolved_extraction': extraction_meta.get('resolved_extraction', extraction_method),
            'final_extraction': extraction_meta.get('final_extraction', extraction_method),
            'fallback_used': extraction_meta.get('fallback_used', False),
            'fallback_reason': extraction_meta.get('fallback_reason'),
            'renderer': renderer_type,
        },
        'quality': quality,
        'timings': timings,
    }
    if alt_code:
        response['alt_code'] = alt_code
    if config_warnings:
        response['config_warnings'] = config_warnings
    if source_snapshot is not None:
        response['source_snapshot'] = source_snapshot
    return response, 200


def _cleanup_upgrade_jobs():
    now = time.time()
    with upgrade_lock:
        expired = [
            job_id for job_id, job in upgrade_jobs.items()
            if now - float(job.get('created_at', now)) > UPGRADE_JOB_TTL
        ]
        for job_id in expired:
            upgrade_jobs.pop(job_id, None)


def _serialize_flowchart(flowchart, direction: str) -> Dict[str, Any]:
    nodes = []
    for node in flowchart.nodes:
        position = None
        if getattr(node, "position", None):
            position = [int(node.position[0]), int(node.position[1])]
        nodes.append({
            'id': node.id,
            'label': node.label,
            'type': node.node_type,
            'group': getattr(node, 'group', None),
            'position': position,
        })

    connections = [
        {
            'from': conn.from_node,
            'to': conn.to_node,
            'label': conn.label,
            'type': conn.connection_type,
        }
        for conn in flowchart.connections
    ]

    return {
        'direction': direction,
        'nodes': nodes,
        'connections': connections,
    }


def _decode_data_url(data_url: str) -> Tuple[bytes, str]:
    if not data_url or ',' not in data_url:
        raise ValueError('Invalid data URL payload')
    header, encoded = data_url.split(',', 1)
    mime = 'application/octet-stream'
    if ';base64' not in header:
        raise ValueError('Expected base64 data URL payload')
    if ':' in header:
        mime = header.split(':', 1)[1].split(';', 1)[0] or mime
    return base64.b64decode(encoded), mime


def _run_upgrade_job(job_id: str, payload: Dict[str, Any]):
    with upgrade_lock:
        job = upgrade_jobs.get(job_id)
        if not job:
            return
        job['status'] = 'running'
        job['started_at'] = time.time()
    try:
        # 1. Look for a timeout passed from the UI payload
        ui_timeout = int(_safe_float(payload.get('request_timeout_ms'), 0))
        
        # 2. Look for the env variable, but increase the default to 60 seconds (60000ms)
        env_timeout = int(_safe_float(os.environ.get('FLOWCHART_UPGRADE_TIMEOUT_MS', 60000), 60000))
        
        # 3. Use whichever timeout is larger
        upgrade_timeout_ms = max(ui_timeout, env_timeout)

        response, status = _build_generate_response(
            payload,
            request_timeout_ms=upgrade_timeout_ms,
            allow_timeout_fallback=True,
        )
        with upgrade_lock:
            job = upgrade_jobs.get(job_id)
            if not job:
                return
            if status == 200 and response.get('success'):
                job['status'] = 'completed'
                job['result'] = response
            else:
                job['status'] = 'failed'
                job['error'] = response.get('error', f'Upgrade failed with status {status}')
                job['result'] = response
            job['completed_at'] = time.time()
    except Exception as exc:
        with upgrade_lock:
            job = upgrade_jobs.get(job_id)
            if not job:
                return
            job['status'] = 'failed'
            job['error'] = str(exc)
            job['completed_at'] = time.time()


def _submit_upgrade_job(payload: Dict[str, Any]) -> str:
    _cleanup_upgrade_jobs()
    job_id = str(uuid.uuid4())[:12]
    with upgrade_lock:
        upgrade_jobs[job_id] = {
            'id': job_id,
            'status': 'pending',
            'created_at': time.time(),
            'started_at': None,
            'completed_at': None,
            'result': None,
            'error': None,
        }
    thread = threading.Thread(target=_run_upgrade_job, args=(job_id, payload), daemon=True)
    thread.start()
    return job_id


@app.route('/api/generate', methods=['POST'])
def generate_flowchart():
    """Generate flowchart with optional two-pass quality upgrade mode."""
    try:
        data, error_response = _json_payload(required_keys=['workflow_text'])
        if error_response is not None:
            return error_response

        response_mode = str(data.get('response_mode', 'single')).strip().lower()
        request_timeout_ms = int(_safe_float(data.get('request_timeout_ms', 12000), 12000))
        normalized_extraction = _normalize_extraction_method(data.get('extraction', 'auto'))

        if response_mode == 'two_pass' and normalized_extraction != 'heuristic':
            provisional_payload = dict(data)
            provisional_payload['extraction'] = 'heuristic'
            provisional_response, provisional_status = _build_generate_response(
                provisional_payload,
                force_extraction='heuristic',
                request_timeout_ms=request_timeout_ms,
                allow_timeout_fallback=False,
            )
            if provisional_status != 200:
                return jsonify(provisional_response), provisional_status

            upgrade_payload = dict(data)
            upgrade_payload['extraction'] = normalized_extraction
            upgrade_job_id = _submit_upgrade_job(upgrade_payload)
            provisional_response['provisional'] = True
            provisional_response['upgrade_job_id'] = upgrade_job_id
            return jsonify(provisional_response), 200

        response, status = _build_generate_response(
            data,
            request_timeout_ms=request_timeout_ms,
            allow_timeout_fallback=True,
        )
        response['provisional'] = False
        return jsonify(response), status

    except Exception as e:
        logger.error(f"Generation error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


# ── Phase 4: Async Rendering ──

@app.route('/api/generate/upgrade-status/<job_id>', methods=['GET'])
def generate_upgrade_status(job_id):
    """Poll two-pass generation upgrade job status."""
    _cleanup_upgrade_jobs()
    with upgrade_lock:
        job = upgrade_jobs.get(job_id)
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        payload = {
            'success': True,
            'job_id': job_id,
            'status': job.get('status', 'pending'),
            'created_at': job.get('created_at'),
            'started_at': job.get('started_at'),
            'completed_at': job.get('completed_at'),
            'error': job.get('error'),
        }
        if job.get('status') == 'completed' and isinstance(job.get('result'), dict):
            payload['result'] = job['result']
        return jsonify(payload)


@app.route('/api/render/async', methods=['POST'])
def render_async():
    """Submit a background rendering job."""
    try:
        data, error_response = _json_payload(required_keys=['workflow_text'])
        if error_response is not None:
            return error_response

        job_id = render_manager.submit(
            workflow_text=data['workflow_text'],
            title=data.get('title', 'Workflow'),
            renderer=data.get('renderer', 'mermaid'),
            format=data.get('format', 'png'),
            extraction=data.get('extraction', 'auto'),
            theme=data.get('theme', 'default'),
            model_path=data.get('model_path'),
            ollama_base_url=data.get('ollama_base_url', DEFAULT_OLLAMA_BASE_URL),
            ollama_model=data.get('ollama_model'),
            graphviz_engine=data.get('graphviz_engine', 'dot'),
            d2_layout=data.get('d2_layout', 'elk'),
            kroki_url=data.get('kroki_url', 'http://localhost:8000'),
        )

        return jsonify({'success': True, 'job_id': job_id})
    except Exception as e:
        logger.error(f"Async render submit error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/render/status/<job_id>', methods=['GET'])
def render_status(job_id):
    """Poll async rendering job status."""
    status = render_manager.get_status(job_id)
    if not status:
        return jsonify({'error': 'Job not found'}), 404
    return jsonify({'success': True, **status})


@app.route('/api/render/download/<job_id>', methods=['GET'])
def render_download(job_id):
    """Download completed async render output."""
    output_path = render_manager.get_output_path(job_id)
    if not output_path:
        return jsonify({'error': 'Output not available'}), 404

    p = Path(output_path)
    mime_map = {
        '.png': 'image/png',
        '.svg': 'image/svg+xml',
        '.pdf': 'application/pdf',
        '.html': 'text/html',
    }
    mimetype = mime_map.get(p.suffix, 'application/octet-stream')
    return send_file(output_path, as_attachment=True,
                     download_name=f'flowchart{p.suffix}', mimetype=mimetype)


@app.route('/api/render', methods=['POST'])
def render_to_file():
    """Synchronous server-side rendering (kept for backwards compat)."""
    try:
        data, error_response = _json_payload()
        if error_response is not None:
            return error_response

        renderer_type = _normalize_renderer(data.get('renderer', 'mermaid'))
        format = str(data.get('format', 'png')).strip().lower()
        theme = data.get('theme', 'default')
        profile = _normalize_export_profile(data.get('profile', 'polished'))
        profile_settings = _export_profile_settings(profile)
        quality_mode = str(data.get('quality_mode', 'draft_allowed')).strip().lower()
        preferred_renderer_raw = data.get('preferred_renderer')
        preferred_renderer = _normalize_renderer(preferred_renderer_raw) if preferred_renderer_raw else None
        strict_artifact_checks = _as_bool(
            data.get('strict_artifact_checks'),
            default=(profile == 'polished' or quality_mode == 'certified_only'),
        )

        workflow_text = data.get('workflow_text')
        mermaid_code = data.get('mermaid_code')
        png_data_url = data.get('png_data_url')

        if not workflow_text and not mermaid_code and not png_data_url:
            return jsonify({'error': 'Provide workflow_text, mermaid_code, or png_data_url'}), 400

        if png_data_url:
            if format not in {'png', 'pdf'}:
                return jsonify({'error': 'png_data_url export only supports PNG or PDF'}), 400
            png_bytes, mime = _decode_data_url(str(png_data_url))
            if mime != 'image/png':
                return jsonify({'error': 'png_data_url must be a PNG data URL'}), 400
            if format == 'png':
                response = send_file(
                    BytesIO(png_bytes),
                    as_attachment=True,
                    download_name='flowchart.png',
                    mimetype='image/png',
                )
            else:
                pdf_bytes = BytesIO(_fit_png_to_pdf_page(
                    png_bytes,
                    margin=int(profile_settings['pdf_margin']),
                    min_readable_scale=float(profile_settings['pdf_min_readable_scale']),
                    overlap=int(profile_settings['pdf_overlap']),
                ))
                pdf_bytes.seek(0)
                response = send_file(
                    pdf_bytes,
                    as_attachment=True,
                    download_name='flowchart.pdf',
                    mimetype='application/pdf',
                )
            response.headers['X-Flowchart-Profile'] = profile
            response.headers['X-Flowchart-Requested-Renderer'] = renderer_type
            response.headers['X-Flowchart-Resolved-Renderer'] = 'client-layout'
            response.headers['X-Flowchart-Export-Strategy'] = _export_strategy_name(
                profile=profile,
                final_renderer='client-layout',
                client_layout=True,
            )
            response.headers['X-Flowchart-Fallback-Chain'] = json.dumps([])
            response.headers['X-Flowchart-Artifact-Bytes'] = str(len(png_bytes))
            if profile == 'polished':
                response.headers['X-Flowchart-Export-Notice'] = (
                    'Current-view export preserves manual layout for print-ready output.'
                )
            return response

        attempts: List[Dict[str, Any]] = []
        last_error = f'{renderer_type} rendering failed'
        candidates = _export_renderer_candidates(
            profile=profile,
            requested_renderer=renderer_type,
            preferred_renderer=preferred_renderer,
            has_workflow_text=bool(workflow_text),
        )

        for candidate in candidates:
            output_path = RENDER_ROOT / f"flowchart_{candidate}_{int(time.time())}_{uuid.uuid4().hex[:8]}.{format}"
            success = False
            render_meta: Dict[str, Any] = {
                'requested_renderer': candidate,
                'resolved_renderer': candidate,
                'final_renderer': candidate,
                'fallback_chain': [],
                'success': False,
                'output_path': str(output_path),
                'format': format,
            }
            printable_pdf_from_png = False
            intermediate_png_path: Optional[Path] = None

            if mermaid_code and not workflow_text:
                if candidate not in {'mermaid', 'html'}:
                    continue
                if format == 'html' or candidate == 'html':
                    renderer = HTMLFallbackRenderer()
                    html_path = output_path.with_suffix('.html')
                    success = renderer.render(mermaid_code, str(html_path), title='Flowchart')
                    render_meta['final_renderer'] = 'html'
                    render_meta['output_path'] = str(html_path)
                else:
                    renderer = ImageRenderer()
                    success = renderer.render(
                        mermaid_code,
                        str(output_path),
                        format=format,
                        width=int(profile_settings['png_width']),
                        height=int(profile_settings['png_height']),
                        background=str(profile_settings['background']),
                        theme=theme,
                    )
            elif workflow_text:
                config = PipelineConfig(
                    extraction=data.get('extraction', 'auto'),
                    renderer=candidate,
                    theme=theme,
                    direction=data.get('direction', 'LR'),
                    model_path=data.get('model_path'),
                    ollama_base_url=data.get('ollama_base_url', DEFAULT_OLLAMA_BASE_URL),
                    ollama_model=data.get('ollama_model'),
                    graphviz_engine=data.get('graphviz_engine', 'dot'),
                    d2_layout=data.get('d2_layout', 'elk'),
                    kroki_url=data.get('kroki_url', 'http://localhost:8000'),
                )
                pipeline = FlowchartPipeline(config)
                render_format = format
                pipeline_output_path = output_path
                if format == 'pdf' and candidate != 'html':
                    render_format = 'png'
                    pipeline_output_path = output_path.with_suffix('.png')
                    printable_pdf_from_png = True
                    intermediate_png_path = pipeline_output_path
                success = pipeline.process(workflow_text, str(pipeline_output_path), format=render_format)
                render_meta = pipeline.get_last_render_metadata() or render_meta
                if success and printable_pdf_from_png:
                    png_path = Path(render_meta.get('output_path') or pipeline_output_path)
                    if png_path.exists():
                        output_path.write_bytes(_fit_png_to_pdf_page(
                            png_path.read_bytes(),
                            margin=int(profile_settings['pdf_margin']),
                            min_readable_scale=float(profile_settings['pdf_min_readable_scale']),
                            overlap=int(profile_settings['pdf_overlap']),
                        ))
                        render_meta['output_path'] = str(output_path)
                        render_meta['artifact_format'] = 'pdf'
                    else:
                        success = False
                        last_error = 'Printable PDF conversion failed: missing PNG artifact'
            else:
                continue

            rendered_path = Path(render_meta.get('output_path') or output_path)
            resolved_format = rendered_path.suffix.lstrip('.').lower() if rendered_path.suffix else format
            fallback_chain = render_meta.get('fallback_chain', [])
            artifact_ok, artifact_issues, artifact_bytes = _validate_export_artifact(rendered_path, resolved_format)

            if success and resolved_format != format:
                success = False
                last_error = (
                    f"Requested {format.upper()} export but renderer produced {resolved_format.upper()}"
                )
            elif success and strict_artifact_checks and not artifact_ok:
                success = False
                last_error = f'Artifact validation failed: {", ".join(artifact_issues)}'
            elif not success and artifact_issues:
                last_error = f'Artifact validation failed: {", ".join(artifact_issues)}'

            attempts.append(
                {
                    'requested_renderer': candidate,
                    'resolved_renderer': render_meta.get('resolved_renderer', candidate),
                    'final_renderer': render_meta.get('final_renderer', candidate),
                    'fallback_chain': fallback_chain,
                    'artifact_format': resolved_format,
                    'artifact_bytes': artifact_bytes,
                    'success': bool(success),
                }
            )

            if success and rendered_path.exists():
                mime_map = {
                    'png': 'image/png',
                    'svg': 'image/svg+xml',
                    'pdf': 'application/pdf',
                    'html': 'text/html',
                }
                response = send_file(
                    rendered_path,
                    as_attachment=True,
                    download_name=f'flowchart.{resolved_format}',
                    mimetype=mime_map.get(resolved_format, 'application/octet-stream'),
                )
                response.headers['X-Flowchart-Profile'] = profile
                response.headers['X-Flowchart-Requested-Renderer'] = renderer_type
                response.headers['X-Flowchart-Resolved-Renderer'] = str(
                    render_meta.get('final_renderer', candidate)
                )
                response.headers['X-Flowchart-Export-Strategy'] = _export_strategy_name(
                    profile=profile,
                    final_renderer=str(render_meta.get('final_renderer', candidate)),
                    client_layout=False,
                )
                response.headers['X-Flowchart-Fallback-Chain'] = json.dumps(fallback_chain)
                response.headers['X-Flowchart-Artifact-Bytes'] = str(artifact_bytes)
                if printable_pdf_from_png:
                    response.headers['X-Flowchart-PDF-Layout'] = 'printable-pages'
                if profile == 'polished':
                    response.headers['X-Flowchart-Export-Notice'] = (
                        'Polished exports optimize for print-ready PDF and PNG readability.'
                    )
                if intermediate_png_path and intermediate_png_path.exists():
                    try:
                        intermediate_png_path.unlink()
                    except OSError:
                        pass
                return response

            if intermediate_png_path and intermediate_png_path.exists():
                try:
                    intermediate_png_path.unlink()
                except OSError:
                    pass

        return jsonify({
            'error': last_error,
            'profile': profile,
            'requested_renderer': renderer_type,
            'attempts': attempts,
        }), 500
    except Exception as e:
        logger.error(f"Render error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/clipboard', methods=['POST'])
def from_clipboard():
    try:
        data, error_response = _json_payload(required_keys=['text'])
        if error_response is not None:
            return error_response

        text = data['text']
        # Use WorkflowDetector with auto split mode
        detector = WorkflowDetector(split_mode='auto')
        workflows = detector.detect_workflows(text)

        if workflows and len(workflows) > 1:
            summary = detector.get_workflow_summary(workflows)
            cache_key = cache_workflows(workflows, 'text')
            workflow_list = []
            for wf in workflows:
                complexity = 'High' if wf.step_count > 20 else ('Medium' if wf.step_count > 10 else 'Low')
                workflow_list.append({
                    'id': wf.id, 'title': wf.title,
                    'step_count': wf.step_count, 'decision_count': wf.decision_count,
                    'confidence': round(wf.confidence, 2), 'complexity': complexity,
                    'preview': wf.content[:200] + ('...' if len(wf.content) > 200 else ''),
                })
            return jsonify({'success': True, 'cache_key': cache_key, 'multiple_workflows': True,
                            'workflows': workflow_list, 'summary': summary})

        extractor = ContentExtractor()
        single_workflow = workflows[0] if workflows else None
        workflow_text = (
            extractor.preprocess_for_parser(single_workflow.content)
            if single_workflow is not None
            else None
        )
        if not workflow_text:
            workflow_text = extractor.extract_best_workflow(text)
        if not workflow_text:
            workflow_text = extractor.preprocess_for_parser(text)

        summary = _single_workflow_summary(workflow_text, single_workflow)
        cache_key = cache_workflows(workflows or [], 'text')
        return jsonify({'success': True, 'cache_key': cache_key, 'workflow_text': workflow_text, 'summary': summary})
    except Exception as e:
        logger.error(f"Clipboard error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    parser = DocumentParser()
    caps = cap_detector.get_summary()
    ready = bool(startup_report.get('ready', True))
    return jsonify({
        'status': 'ok' if ready else 'degraded',
        'startup_ready': ready,
        'startup': {
            'enabled': startup_report.get('enabled', False),
            'strict': startup_report.get('strict', False),
            'ready': startup_report.get('ready', True),
            'duration_seconds': startup_report.get('duration_seconds', 0.0),
            'started_at': _utc_iso(startup_report.get('started_at')),
            'finished_at': _utc_iso(startup_report.get('finished_at')),
            'warnings': startup_report.get('warnings', []),
            'errors': startup_report.get('errors', []),
            'checks': startup_report.get('checks', []),
        },
        'supported_formats': parser.get_supported_formats(),
        'version': __version__,
        'cache_entries': len(workflow_cache),
        'samples_available': len(SAMPLE_WORKFLOWS),
        'websocket_enabled': socketio is not None,
        'async_render_jobs': len(render_manager._jobs),
        'batch_export': True,  # Enhancement 1
        'capabilities': caps,
    })


if __name__ == '__main__':
    runtime_config = _resolve_server_runtime_config()
    startup_report = run_startup_preflight(
        project_root=Path(__file__).resolve().parent.parent,
        ollama_base_url=DEFAULT_OLLAMA_BASE_URL,
    )

    print("\n" + "="*60)
    print(f"  ISO 5807 Flowchart Generator v{__version__}")
    print("  Phase 4+5: WebSocket + Async + Adaptive Routing")
    print("  Enhancement 1: Batch Export with ZIP download")
    print("="*60)
    print(f"\n  Access at: http://{runtime_config['host']}:{runtime_config['port']}")
    print(f"  Samples:  {len(SAMPLE_WORKFLOWS)} built-in workflows")
    print(f"  WebSocket: {'Enabled' if socketio else 'Disabled (pip install flask-socketio)'}")
    print("  Batch Export: Enabled")
    print(
        "  Startup Bootstrap: "
        f"{'Ready' if startup_report.get('ready', False) else 'Needs attention'}"
    )

    # Show capabilities at startup
    caps = cap_detector.detect()
    print(f"\n  Hardware:  {caps.total_ram_gb}GB RAM | {caps.cpu_count} CPUs | GPU: {caps.gpu_backend}")
    print(f"  Extract:  {', '.join(caps.available_extractors)} (recommended: {caps.recommended_extraction})")
    print(f"  Render:   {', '.join(caps.available_renderers)} (recommended: {caps.recommended_renderer})")
    if caps.warnings:
        print(f"  Warnings: {len(caps.warnings)}")
        for w in caps.warnings[:3]:
            print(f"    WARNING: {w}")

    print("\n  Press Ctrl+C to stop\n")

    if socketio:
        socketio.run(
            app,
            host=runtime_config['host'],
            port=runtime_config['port'],
            debug=runtime_config['debug'],
        )
    else:
        app.run(
            host=runtime_config['host'],
            port=runtime_config['port'],
            debug=runtime_config['debug'],
        )
