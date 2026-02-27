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
import time
import zipfile
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from flask import Flask, render_template, request, jsonify, send_file, Response
from werkzeug.utils import secure_filename
import logging

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.importers.document_parser import DocumentParser
from src.importers.content_extractor import ContentExtractor
from src.importers.workflow_detector import WorkflowDetector
from src.parser.nlp_parser import NLPParser
from src.builder.graph_builder import GraphBuilder
from src.builder.validator import ISO5807Validator
from src.generator.mermaid_generator import MermaidGenerator
from src.renderer.image_renderer import ImageRenderer
from src.pipeline import FlowchartPipeline, PipelineConfig
from src.capability_detector import CapabilityDetector
from src.parser.ollama_extractor import discover_ollama_models
from src.quality_assurance import evaluate_quality, build_source_snapshot, QualityThresholds
from src.models import NodeType
from web.async_renderer import render_manager

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
TMP_ROOT = Path.cwd() / '.tmp' / 'web'
UPLOAD_ROOT = TMP_ROOT / 'uploads'
JOB_ROOT = TMP_ROOT / 'jobs'
RENDER_ROOT = TMP_ROOT / 'renders'
for p in (UPLOAD_ROOT, JOB_ROOT, RENDER_ROOT):
    p.mkdir(parents=True, exist_ok=True)
app.config['UPLOAD_FOLDER'] = str(UPLOAD_ROOT)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# WebSocket support (optional)
try:
    from web.websocket_handler import create_socketio
    socketio = create_socketio(app)
except Exception:
    socketio = None
    logger.info("WebSocket disabled (install flask-socketio for real-time preview)")

# Capability detector (singleton)
cap_detector = CapabilityDetector()

ALLOWED_EXTENSIONS = {'txt', 'md', 'pdf', 'docx', 'doc'}
workflow_cache = {}
cache_timestamps = {}
CACHE_TTL = 1800  # 30 minutes


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


def _user_quality_presentation(quality: Dict[str, Any], validation: Dict[str, Any]) -> Dict[str, Any]:
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

    if blockers or validation_errors:
        actions = [
            'Review highlighted issues and edit unclear steps.',
            'Regenerate after applying changes.',
        ]
        if any('detection_confidence' in str(b) for b in blockers):
            actions.append('Add more explicit process steps in the source text.')
        return {
            'status': 'issues',
            'summary': 'Issues found. Output generated, but review is required before final use.',
            'recommended_actions': actions,
        }

    if warnings or validation_warnings or not quality.get('certified', False):
        return {
            'status': 'review',
            'summary': 'Flowchart generated successfully. A quick review is recommended.',
            'recommended_actions': [
                'Check decision branches and end states.',
                'Use inline step edits for wording and node type fixes.',
            ],
        }

    return {
        'status': 'ready',
        'summary': 'Ready for use. Quality and ISO checks look good.',
        'recommended_actions': ['Export as SVG or PDF for professional sharing.'],
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
    base_url = request.args.get('base_url', 'http://localhost:11434')
    info = discover_ollama_models(base_url=base_url)
    return jsonify({'success': True, **info})


# ── Enhancement 1: Batch Export ──

@app.route('/api/batch-export', methods=['POST'])
def batch_export():
    """Export multiple workflows from cached document as ZIP."""
    try:
        data = request.get_json()
        if not data or 'cache_key' not in data:
            return jsonify({'error': 'No cache key provided'}), 400

        cache_key = data['cache_key']
        if cache_key not in workflow_cache:
            return jsonify({'error': 'Cache expired. Re-upload document.'}), 404

        workflows = workflow_cache[cache_key]
        split_mode = data.get('split_mode', 'none')  # If 'none', use existing workflows
        format = data.get('format', 'png')
        renderer = data.get('renderer', 'mermaid')
        extraction = data.get('extraction', 'auto')
        theme = data.get('theme', 'default')
        direction = data.get('direction', 'TD')
        quality_mode = data.get('quality_mode', 'draft_allowed')
        min_detection_confidence_certified = _safe_float(
            data.get('min_detection_confidence_certified', 0.65), 0.65
        )
        model_path = data.get('model_path')
        ollama_base_url = data.get('ollama_base_url', 'http://localhost:11434')
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
                # Re-evaluate quality with render integrity included.
                workflow_result['quality'] = evaluate_quality(
                    detection_confidence=getattr(workflow, 'confidence', None),
                    flowchart=flowchart,
                    validation_errors=errors,
                    validation_warnings=warnings_list,
                    extraction_meta=extraction_meta,
                    render_success=success,
                    output_path=str(output_file),
                    thresholds=QualityThresholds(
                        min_detection_confidence_certified=min_detection_confidence_certified
                    ),
                )

                if success and output_file.exists():
                    temp_files.append(output_file)
                    success_count += 1
                    workflow_result['rendered'] = True
                else:
                    logger.warning(f"Failed to render: {safe_name}")
                    failed_count += 1
                    workflow_result['error'] = f'Failed to render via {renderer}'
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
    return render_template('index.html')


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
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({'error': 'No URL provided'}), 400

        url = data['url'].strip()
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        try:
            import requests as req
            resp = req.get(url, timeout=15, headers={'User-Agent': 'FlowchartGenerator/2.0'})
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


@app.route('/api/generate', methods=['POST'])
def generate_flowchart():
    """Generate flowchart with multi-renderer and extraction method support."""
    try:
        data = request.get_json()
        if not data or 'workflow_text' not in data:
            return jsonify({'error': 'No workflow text provided'}), 400

        workflow_text = data['workflow_text']
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
        extraction_method = data.get('extraction', 'auto')
        renderer_type = data.get('renderer', 'mermaid')
        model_path = data.get('model_path', None)
        ollama_base_url = data.get('ollama_base_url', 'http://localhost:11434')
        ollama_model = data.get('ollama_model')
        quantization = data.get('quantization', '5bit')
        direction = data.get('direction', 'TD')
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
        # Validate config against capabilities (uses request-specific provider settings)
        config_warnings = pipeline.validate_config()
        steps = pipeline.extract_steps(workflow_text)
        if not steps:
            return jsonify({'error': 'No workflow steps detected'}), 400
        extraction_meta = pipeline.get_last_extraction_metadata()
        if extraction_meta.get('fallback_used') and extraction_meta.get('fallback_reason'):
            config_warnings.append(extraction_meta['fallback_reason'])

        flowchart = pipeline.build_flowchart(steps, title=title)
        override_meta = _apply_node_overrides(flowchart, node_overrides)

        validation_result = {}
        if validate_flag:
            validator = ISO5807Validator()
            is_valid, errors, warnings = validator.validate(flowchart)
            validation_result = {'is_valid': is_valid, 'errors': errors, 'warnings': warnings}
        else:
            validator = ISO5807Validator()
            is_valid, errors, warnings = validator.validate(flowchart)

        generator = MermaidGenerator()
        mermaid_code = generator.generate_with_theme(flowchart, theme=theme)

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

        node_confidence = []
        for node in flowchart.nodes:
            node_data = {'id': node.id, 'label': node.label, 'type': node.node_type, 'confidence': node.confidence}
            if hasattr(node, 'alternatives') and node.alternatives:
                node_data['alternatives'] = node.alternatives
            node_confidence.append(node_data)

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

        if quality_mode == 'certified_only' and not quality['certified']:
            user_quality = _user_quality_presentation(quality, validation_result)
            return jsonify({
                'success': False,
                'error': 'Workflow does not meet certified quality gates',
                'quality': quality,
                'validation': validation_result,
                'applied_overrides': override_meta,
                'ux_mode': ux_mode,
                'user_quality_status': user_quality['status'],
                'user_quality_summary': user_quality['summary'],
                'user_recommended_actions': user_quality['recommended_actions'],
                'pipeline': {
                    'extraction': extraction_method,
                    'requested_extraction': extraction_meta.get('requested_extraction', extraction_method),
                    'resolved_extraction': extraction_meta.get('resolved_extraction', extraction_method),
                    'final_extraction': extraction_meta.get('final_extraction', extraction_method),
                    'fallback_used': extraction_meta.get('fallback_used', False),
                    'fallback_reason': extraction_meta.get('fallback_reason'),
                    'renderer': renderer_type,
                },
            }), 422

        user_quality = _user_quality_presentation(quality, validation_result)
        response = {
            'success': True,
            'mermaid_code': mermaid_code,
            'validation': validation_result,
            'applied_overrides': override_meta,
            'node_confidence': node_confidence,
            'stats': {
                'nodes': len(flowchart.nodes),
                'connections': len(flowchart.connections),
                'steps': len(steps)
            },
            'ux_mode': ux_mode,
            'user_quality_status': user_quality['status'],
            'user_quality_summary': user_quality['summary'],
            'user_recommended_actions': user_quality['recommended_actions'],
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
        }
        if alt_code:
            response['alt_code'] = alt_code
        if config_warnings:
            response['config_warnings'] = config_warnings
        if source_snapshot is not None:
            response['source_snapshot'] = source_snapshot

        return jsonify(response)

    except Exception as e:
        logger.error(f"Generation error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


# ── Phase 4: Async Rendering ──

@app.route('/api/render/async', methods=['POST'])
def render_async():
    """Submit a background rendering job."""
    try:
        data = request.get_json()
        if not data or 'workflow_text' not in data:
            return jsonify({'error': 'No workflow text provided'}), 400

        job_id = render_manager.submit(
            workflow_text=data['workflow_text'],
            title=data.get('title', 'Workflow'),
            renderer=data.get('renderer', 'mermaid'),
            format=data.get('format', 'png'),
            extraction=data.get('extraction', 'auto'),
            theme=data.get('theme', 'default'),
            model_path=data.get('model_path'),
            ollama_base_url=data.get('ollama_base_url', 'http://localhost:11434'),
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
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        renderer_type = data.get('renderer', 'mermaid')
        format = data.get('format', 'png')
        theme = data.get('theme', 'default')

        workflow_text = data.get('workflow_text')
        mermaid_code = data.get('mermaid_code')

        if not workflow_text and not mermaid_code:
            return jsonify({'error': 'Provide workflow_text or mermaid_code'}), 400

        output_path = str(RENDER_ROOT / f"flowchart_{int(time.time())}_{uuid.uuid4().hex[:8]}.{format}")

        success = False
        if renderer_type == 'mermaid' and mermaid_code:
            renderer = ImageRenderer()
            if format == 'html':
                success = renderer.render_html(mermaid_code, output_path, title='Flowchart')
            else:
                success = renderer.render(mermaid_code, output_path, format=format, theme=theme)
        elif workflow_text:
            config = PipelineConfig(
                extraction=data.get('extraction', 'auto'),
                renderer=renderer_type, theme=theme,
                direction=data.get('direction', 'TD'),
                model_path=data.get('model_path'),
                ollama_base_url=data.get('ollama_base_url', 'http://localhost:11434'),
                ollama_model=data.get('ollama_model'),
                graphviz_engine=data.get('graphviz_engine', 'dot'),
                d2_layout=data.get('d2_layout', 'elk'),
                kroki_url=data.get('kroki_url', 'http://localhost:8000'),
            )
            pipeline = FlowchartPipeline(config)
            success = pipeline.process(workflow_text, output_path, format=format)

        if success and Path(output_path).exists():
            return send_file(
                output_path, as_attachment=True,
                download_name=f'flowchart.{format}',
                mimetype=f'image/{format}' if format in ('png', 'svg') else 'application/octet-stream'
            )
        else:
            return jsonify({'error': f'{renderer_type} rendering failed'}), 500
    except Exception as e:
        logger.error(f"Render error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/clipboard', methods=['POST'])
def from_clipboard():
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({'error': 'No text provided'}), 400

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
        workflow_text = extractor.extract_best_workflow(text)
        if not workflow_text:
            workflow_text = extractor.preprocess_for_parser(text)

        summary = extractor.get_workflow_summary(workflow_text)
        cache_key = cache_workflows(workflows or [], 'text')
        return jsonify({'success': True, 'cache_key': cache_key, 'workflow_text': workflow_text, 'summary': summary})
    except Exception as e:
        logger.error(f"Clipboard error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    parser = DocumentParser()
    caps = cap_detector.get_summary()
    return jsonify({
        'status': 'ok',
        'supported_formats': parser.get_supported_formats(),
        'version': '2.1.0',
        'cache_entries': len(workflow_cache),
        'samples_available': len(SAMPLE_WORKFLOWS),
        'websocket_enabled': socketio is not None,
        'async_render_jobs': len(render_manager._jobs),
        'batch_export': True,  # Enhancement 1
        'capabilities': caps,
    })


if __name__ == '__main__':
    print("\n" + "="*60)
    print("  \U0001f680 ISO 5807 Flowchart Generator v2.1.0")
    print("  Phase 4+5: WebSocket + Async + Adaptive Routing")
    print("  Enhancement 1: Batch Export with ZIP download")
    print("="*60)
    print(f"\n  Access at: http://localhost:5000")
    print(f"  Samples:  {len(SAMPLE_WORKFLOWS)} built-in workflows")
    print(f"  WebSocket: {'\u2713 Enabled' if socketio else '\u274c Disabled (pip install flask-socketio)'}")
    print(f"  Batch Export: \u2713 Enabled")

    # Show capabilities at startup
    caps = cap_detector.detect()
    print(f"\n  Hardware:  {caps.total_ram_gb}GB RAM | {caps.cpu_count} CPUs | GPU: {caps.gpu_backend}")
    print(f"  Extract:  {', '.join(caps.available_extractors)} (recommended: {caps.recommended_extraction})")
    print(f"  Render:   {', '.join(caps.available_renderers)} (recommended: {caps.recommended_renderer})")
    if caps.warnings:
        print(f"  Warnings: {len(caps.warnings)}")
        for w in caps.warnings[:3]:
            print(f"    \u26a0 {w}")

    print("\n  Press Ctrl+C to stop\n")

    if socketio:
        socketio.run(app, host='127.0.0.1', port=5000, debug=True)
    else:
        app.run(host='127.0.0.1', port=5000, debug=True)
