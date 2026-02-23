"""Web interface with live preview, SSE, URL fetch, and sample workflows.

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
    """Format a Server-Sent Event."""
    msg = ''
    if event:
        msg += f'event: {event}\n'
    msg += f'data: {json.dumps(data)}\n\n'
    return msg


def cleanup_cache():
    """Remove expired cache entries."""
    now = time.time()
    expired = [k for k, ts in cache_timestamps.items() if now - ts > CACHE_TTL]
    for k in expired:
        workflow_cache.pop(k, None)
        cache_timestamps.pop(k, None)


def cache_workflows(workflows, prefix='file'):
    """Cache workflows and return cache key."""
    cleanup_cache()
    cache_key = f"{prefix}_{os.getpid()}_{int(time.time())}"
    workflow_cache[cache_key] = workflows
    cache_timestamps[cache_key] = time.time()
    return cache_key


def build_workflow_list(workflows):
    """Build JSON-serializable workflow list."""
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


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/samples', methods=['GET'])
def get_samples():
    """Return available sample workflows."""
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
    """Get a specific sample workflow text."""
    if sample_id not in SAMPLE_WORKFLOWS:
        return jsonify({'error': 'Sample not found'}), 404
    sample = SAMPLE_WORKFLOWS[sample_id]
    return jsonify({'success': True, 'text': sample['text'], 'title': sample['title']})


@app.route('/api/fetch-url', methods=['POST'])
def fetch_url():
    """Fetch content from a URL and extract workflows."""
    try:
        data = request.get_json()
        if not data or 'url' not in data:
            return jsonify({'error': 'No URL provided'}), 400

        url = data['url'].strip()
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        try:
            import requests as req
            resp = req.get(url, timeout=15, headers={
                'User-Agent': 'FlowchartGenerator/1.0'
            })
            resp.raise_for_status()
            content_type = resp.headers.get('content-type', '')
        except ImportError:
            return jsonify({'error': 'requests library not installed. Run: pip install requests'}), 500
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

        detector = WorkflowDetector()
        workflows = detector.detect_workflows(text[:50000])

        if not workflows:
            extractor = ContentExtractor()
            workflow_text = extractor.preprocess_for_parser(text[:10000])
            return jsonify({
                'success': True,
                'workflow_text': workflow_text,
                'source': url,
                'char_count': len(text)
            })

        cache_key = cache_workflows(workflows, 'url')
        summary = detector.get_workflow_summary(workflows)

        return jsonify({
            'success': True,
            'cache_key': cache_key,
            'workflows': build_workflow_list(workflows),
            'summary': summary,
            'source': url,
            'char_count': len(text)
        })

    except Exception as e:
        logger.error(f"URL fetch error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


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
            yield sse_event({'stage': 'parse', 'pct': 10, 'msg': f'Parsing {filename}...'})
            parser = DocumentParser()
            result = parser.parse(filepath)

            if not result['success']:
                yield sse_event({'stage': 'error', 'msg': result.get('error', 'Parse failed')})
                return

            yield sse_event({'stage': 'detect', 'pct': 35, 'msg': 'Detecting workflows...'})
            detector = WorkflowDetector()
            workflows = detector.detect_workflows(result['text'])

            if not workflows:
                yield sse_event({'stage': 'error', 'msg': 'No workflows detected'})
                return

            yield sse_event({'stage': 'analyze', 'pct': 60, 'msg': f'Analyzing {len(workflows)} workflow(s)...'})
            cache_key = cache_workflows(workflows, filename)
            summary = detector.get_workflow_summary(workflows)

            yield sse_event({'stage': 'build', 'pct': 85, 'msg': 'Building workflow data...'})
            workflow_list = build_workflow_list(workflows)

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

            cache_key = cache_workflows(workflows, filename)
            summary = detector.get_workflow_summary(workflows)

            return jsonify({
                'success': True, 'cache_key': cache_key,
                'workflows': build_workflow_list(workflows),
                'summary': summary,
                'metadata': result.get('metadata', {})
            })
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
    """Generate flowchart - returns Mermaid code as JSON for live preview."""
    try:
        data = request.get_json()
        if not data or 'workflow_text' not in data:
            return jsonify({'error': 'No workflow text provided'}), 400

        workflow_text = data['workflow_text']
        title = data.get('title', 'Workflow')
        theme = data.get('theme', 'default')
        validate_flag = data.get('validate', True)

        parser = NLPParser(use_spacy=True)
        steps = parser.parse(workflow_text)
        if not steps:
            return jsonify({'error': 'No workflow steps detected'}), 400

        builder = GraphBuilder()
        flowchart = builder.build(steps, title=title)

        validation_result = {}
        if validate_flag:
            validator = ISO5807Validator()
            is_valid, errors, warnings = validator.validate(flowchart)
            validation_result = {'is_valid': is_valid, 'errors': errors, 'warnings': warnings}

        generator = MermaidGenerator()
        mermaid_code = generator.generate_with_theme(flowchart, theme=theme)

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
    return jsonify({
        'status': 'ok',
        'supported_formats': parser.get_supported_formats(),
        'version': '1.0.0',
        'cache_entries': len(workflow_cache),
        'samples_available': len(SAMPLE_WORKFLOWS)
    })


if __name__ == '__main__':
    print("\n" + "="*60)
    print("  \U0001f680 ISO 5807 Flowchart Generator v1.0.0")
    print("  Live Preview + Confidence + Loops + Samples")
    print("="*60)
    print("\n  Access at: http://localhost:5000")
    print(f"  Samples:  {len(SAMPLE_WORKFLOWS)} built-in workflows")
    print("  Press Ctrl+C to stop\n")
    app.run(host='127.0.0.1', port=5000, debug=True)
