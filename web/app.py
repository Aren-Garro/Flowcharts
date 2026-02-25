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
import tempfile
import zipfile
from pathlib import Path
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
from web.async_renderer import render_manager

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()

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
        extraction = data.get('extraction', 'heuristic')
        theme = data.get('theme', 'default')

        # If split_mode is not 'none', re-detect workflows with new split strategy
        if split_mode != 'none':
            # Get original text from workflows
            full_text = '\n\n'.join(wf.content for wf in workflows)
            detector = WorkflowDetector(split_mode=split_mode)
            workflows = detector.detect_workflows(full_text)
            if not workflows:
                return jsonify({'error': f'No workflows detected with split mode: {split_mode}'}), 400

        # Create temp directory for batch export
        temp_dir = Path(tempfile.mkdtemp())
        zip_path = temp_dir / 'workflows.zip'

        config = PipelineConfig(
            extraction=extraction,
            renderer=renderer,
            theme=theme,
            validate=data.get('validate', True),
        )
        pipeline = FlowchartPipeline(config)

        success_count = 0
        failed_count = 0
        temp_files = []

        for i, workflow in enumerate(workflows, 1):
            try:
                workflow_name = workflow.title or f"Workflow_{i}"
                # Sanitize filename
                safe_name = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in workflow_name)
                safe_name = safe_name.strip().replace(' ', '_')

                # Extract steps
                steps = pipeline.extract_steps(workflow.content)
                if not steps:
                    logger.warning(f"No steps in workflow: {safe_name}")
                    failed_count += 1
                    continue

                # Build flowchart
                flowchart = pipeline.build_flowchart(steps, title=workflow_name)

                # Render to temp file
                output_file = temp_dir / f"{safe_name}.{format}"
                success = pipeline.render(flowchart, str(output_file), format=format)

                if success and output_file.exists():
                    temp_files.append(output_file)
                    success_count += 1
                else:
                    logger.warning(f"Failed to render: {safe_name}")
                    failed_count += 1

            except Exception as e:
                logger.error(f"Error processing workflow {i}: {e}")
                failed_count += 1

        if success_count == 0:
            return jsonify({'error': 'No workflows successfully rendered'}), 500

        # Create ZIP archive
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file_path in temp_files:
                zf.write(file_path, arcname=file_path.name)

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
        validate_flag = data.get('validate', True)
        extraction_method = data.get('extraction', 'heuristic')
        renderer_type = data.get('renderer', 'mermaid')
        model_path = data.get('model_path', None)
        quantization = data.get('quantization', '5bit')
        graphviz_engine = data.get('graphviz_engine', 'dot')
        d2_layout = data.get('d2_layout', 'elk')
        kroki_url = data.get('kroki_url', 'http://localhost:8000')

        config = PipelineConfig(
            extraction=extraction_method,
            renderer=renderer_type,
            model_path=model_path,
            quantization=quantization,
            theme=theme,
            validate=validate_flag,
            graphviz_engine=graphviz_engine,
            d2_layout=d2_layout,
            kroki_url=kroki_url,
        )

        # Validate config against capabilities
        config_warnings = cap_detector.validate_config(config)

        pipeline = FlowchartPipeline(config)
        steps = pipeline.extract_steps(workflow_text)
        if not steps:
            return jsonify({'error': 'No workflow steps detected'}), 400

        flowchart = pipeline.build_flowchart(steps, title=title)

        validation_result = {}
        if validate_flag:
            validator = ISO5807Validator()
            is_valid, errors, warnings = validator.validate(flowchart)
            validation_result = {'is_valid': is_valid, 'errors': errors, 'warnings': warnings}

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

        response = {
            'success': True,
            'mermaid_code': mermaid_code,
            'validation': validation_result,
            'node_confidence': node_confidence,
            'stats': {
                'nodes': len(flowchart.nodes),
                'connections': len(flowchart.connections),
                'steps': len(steps)
            },
            'pipeline': {
                'extraction': extraction_method,
                'renderer': renderer_type,
            },
        }
        if alt_code:
            response['alt_code'] = alt_code
        if config_warnings:
            response['config_warnings'] = config_warnings

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
            extraction=data.get('extraction', 'heuristic'),
            theme=data.get('theme', 'default'),
            model_path=data.get('model_path'),
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

        with tempfile.NamedTemporaryFile(suffix=f'.{format}', delete=False) as tmp:
            output_path = tmp.name

        success = False
        if renderer_type == 'mermaid' and mermaid_code:
            renderer = ImageRenderer()
            if format == 'html':
                success = renderer.render_html(mermaid_code, output_path, title='Flowchart')
            else:
                success = renderer.render(mermaid_code, output_path, format=format, theme=theme)
        elif workflow_text:
            config = PipelineConfig(
                renderer=renderer_type, theme=theme,
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
