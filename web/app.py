"""Web interface with live preview and SSE pipeline progress.

Run locally with: python web/app.py
Access at: http://localhost:5000
"""

import os
import json
import time
import tempfile
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

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {'txt', 'md', 'pdf', 'docx', 'doc'}
workflow_cache = {}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def sse_event(data, event=None):
    """Format a Server-Sent Event."""
    msg = ''
    if event:
        msg += f'event: {event}\n'
    msg += f'data: {json.dumps(data)}\n\n'
    return msg


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/upload-stream', methods=['POST'])
def upload_stream():
    """SSE-powered file upload with pipeline progress."""
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
            # Stage 1: Parse document
            yield sse_event({'stage': 'parse', 'pct': 10, 'msg': f'Parsing {filename}...'})
            parser = DocumentParser()
            result = parser.parse(filepath)

            if not result['success']:
                yield sse_event({'stage': 'error', 'msg': result.get('error', 'Parse failed')})
                return

            # Stage 2: Detect workflows
            yield sse_event({'stage': 'detect', 'pct': 35, 'msg': 'Detecting workflows...'})
            detector = WorkflowDetector()
            workflows = detector.detect_workflows(result['text'])

            if not workflows:
                yield sse_event({'stage': 'error', 'msg': 'No workflows detected'})
                return

            # Stage 3: Analyze
            yield sse_event({'stage': 'analyze', 'pct': 60, 'msg': f'Analyzing {len(workflows)} workflow(s)...'})
            cache_key = f"{filename}_{os.getpid()}_{int(time.time())}"
            workflow_cache[cache_key] = workflows
            summary = detector.get_workflow_summary(workflows)

            # Stage 4: Build response
            yield sse_event({'stage': 'build', 'pct': 85, 'msg': 'Building workflow data...'})
            workflow_list = []
            for wf in workflows:
                complexity = 'High' if wf.step_count > 20 else ('Medium' if wf.step_count > 10 else 'Low')
                complexity_warning = f'High complexity ({wf.step_count} steps). Consider splitting.' if wf.step_count > 20 else None
                workflow_list.append({
                    'id': wf.id, 'title': wf.title,
                    'step_count': wf.step_count, 'decision_count': wf.decision_count,
                    'confidence': round(wf.confidence, 2), 'complexity': complexity,
                    'complexity_warning': complexity_warning,
                    'preview': wf.content[:200] + ('...' if len(wf.content) > 200 else ''),
                    'has_subsections': len(wf.subsections) > 0
                })

            # Stage 5: Done
            yield sse_event({
                'stage': 'done', 'pct': 100, 'msg': 'Complete!',
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
    """Non-streaming upload (fallback)."""
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

            detector = WorkflowDetector()
            workflows = detector.detect_workflows(result['text'])
            if not workflows:
                return jsonify({'error': 'No workflows detected'}), 400

            cache_key = f"{filename}_{os.getpid()}_{int(time.time())}"
            workflow_cache[cache_key] = workflows
            summary = detector.get_workflow_summary(workflows)

            workflow_list = []
            for wf in workflows:
                complexity = 'High' if wf.step_count > 20 else ('Medium' if wf.step_count > 10 else 'Low')
                workflow_list.append({
                    'id': wf.id, 'title': wf.title,
                    'step_count': wf.step_count, 'decision_count': wf.decision_count,
                    'confidence': round(wf.confidence, 2), 'complexity': complexity,
                    'complexity_warning': f'High complexity ({wf.step_count} steps).' if wf.step_count > 20 else None,
                    'preview': wf.content[:200] + ('...' if len(wf.content) > 200 else ''),
                    'has_subsections': len(wf.subsections) > 0
                })

            return jsonify({'success': True, 'cache_key': cache_key, 'workflows': workflow_list, 'summary': summary, 'metadata': result.get('metadata', {})})
        finally:
            if filepath.exists():
                filepath.unlink()

    except Exception as e:
        logger.error(f"Upload error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/workflow/<cache_key>/<workflow_id>', methods=['GET'])
def get_workflow(cache_key, workflow_id):
    """Get specific workflow content."""
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
    """Generate flowchart — returns Mermaid code as JSON for live preview."""
    try:
        data = request.get_json()
        if not data or 'workflow_text' not in data:
            return jsonify({'error': 'No workflow text provided'}), 400

        workflow_text = data['workflow_text']
        title = data.get('title', 'Workflow')
        theme = data.get('theme', 'default')
        validate_flag = data.get('validate', True)

        # Parse
        parser = NLPParser(use_spacy=True)
        steps = parser.parse(workflow_text)
        if not steps:
            return jsonify({'error': 'No workflow steps detected'}), 400

        # Build
        builder = GraphBuilder()
        flowchart = builder.build(steps, title=title)

        # Validate
        validation_result = {}
        if validate_flag:
            validator = ISO5807Validator()
            is_valid, errors, warnings = validator.validate(flowchart)
            validation_result = {'is_valid': is_valid, 'errors': errors, 'warnings': warnings}

        # Generate Mermaid
        generator = MermaidGenerator()
        mermaid_code = generator.generate_with_theme(flowchart, theme=theme)

        # Node confidence data for frontend
        node_confidence = []
        for node in flowchart.nodes:
            node_data = {'id': node.id, 'label': node.label, 'type': node.node_type, 'confidence': node.confidence}
            if hasattr(node, 'alternatives') and node.alternatives:
                node_data['alternatives'] = node.alternatives
            node_confidence.append(node_data)

        return jsonify({
            'success': True,
            'mermaid_code': mermaid_code,
            'validation': validation_result,
            'node_confidence': node_confidence,
            'stats': {
                'nodes': len(flowchart.nodes),
                'connections': len(flowchart.connections),
                'steps': len(steps)
            }
        })

    except Exception as e:
        logger.error(f"Generation error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/clipboard', methods=['POST'])
def from_clipboard():
    """Extract workflow from text input."""
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({'error': 'No text provided'}), 400

        text = data['text']
        detector = WorkflowDetector()
        workflows = detector.detect_workflows(text)

        if workflows and len(workflows) > 1:
            summary = detector.get_workflow_summary(workflows)
            cache_key = f"text_{os.getpid()}_{int(time.time())}"
            workflow_cache[cache_key] = workflows
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
        cache_key = f"text_{os.getpid()}_{int(time.time())}"
        if workflows:
            workflow_cache[cache_key] = workflows

        return jsonify({'success': True, 'cache_key': cache_key, 'workflow_text': workflow_text, 'summary': summary})

    except Exception as e:
        logger.error(f"Clipboard error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    parser = DocumentParser()
    return jsonify({'status': 'ok', 'supported_formats': parser.get_supported_formats(), 'version': '0.3.0'})


if __name__ == '__main__':
    print("\n" + "="*60)
    print("  \U0001f680 ISO 5807 Flowchart Generator v0.3.0")
    print("  Live Preview + SSE Progress + ISO Mapper")
    print("="*60)
    print("\n  Access at: http://localhost:5000")
    print("  Press Ctrl+C to stop\n")
    app.run(host='127.0.0.1', port=5000, debug=True)
