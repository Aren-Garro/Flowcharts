"""Local web interface for flowchart generation.

Run locally with: python web/app.py
Access at: http://localhost:5000
"""

import os
import tempfile
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
import logging

# Add parent directory to path for imports
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
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = tempfile.gettempdir()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Allowed file extensions
ALLOWED_EXTENSIONS = {'txt', 'md', 'pdf', 'docx', 'doc'}

# Store workflows temporarily (in production, use session or database)
workflow_cache = {}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/')
def index():
    """Render main page."""
    return render_template('index.html')


@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Handle file upload and workflow detection."""
    try:
        # Check if file was uploaded
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': f'Unsupported file type. Allowed: {", ".join(ALLOWED_EXTENSIONS)}'}), 400
        
        # Save uploaded file temporarily
        filename = secure_filename(file.filename)
        filepath = Path(app.config['UPLOAD_FOLDER']) / filename
        file.save(filepath)
        
        try:
            # Parse document
            parser = DocumentParser()
            result = parser.parse(filepath)
            
            if not result['success']:
                return jsonify({'error': result.get('error', 'Failed to parse document')}), 400
            
            # Detect workflows
            detector = WorkflowDetector()
            workflows = detector.detect_workflows(result['text'])
            
            if not workflows:
                return jsonify({'error': 'No workflows detected in document'}), 400
            
            # Generate unique cache key
            cache_key = f"{filename}_{os.getpid()}"
            workflow_cache[cache_key] = workflows
            
            # Get summary
            summary = detector.get_workflow_summary(workflows)
            
            # Prepare workflow list for frontend
            workflow_list = []
            for wf in workflows:
                # Assess complexity
                complexity = 'Low'
                complexity_warning = None
                
                if wf.step_count > 20:
                    complexity = 'High'
                    complexity_warning = f'⚠ High complexity ({wf.step_count} steps). Consider splitting into sub-workflows.'
                elif wf.step_count > 10:
                    complexity = 'Medium'
                
                workflow_list.append({
                    'id': wf.id,
                    'title': wf.title,
                    'step_count': wf.step_count,
                    'decision_count': wf.decision_count,
                    'confidence': round(wf.confidence, 2),
                    'complexity': complexity,
                    'complexity_warning': complexity_warning,
                    'preview': wf.content[:200] + '...' if len(wf.content) > 200 else wf.content,
                    'has_subsections': len(wf.subsections) > 0
                })
            
            return jsonify({
                'success': True,
                'cache_key': cache_key,
                'workflows': workflow_list,
                'summary': summary,
                'metadata': result.get('metadata', {})
            })
        
        finally:
            # Clean up uploaded file
            if filepath.exists():
                filepath.unlink()
    
    except Exception as e:
        logger.error(f"Upload error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/workflow/<cache_key>/<workflow_id>', methods=['GET'])
def get_workflow(cache_key, workflow_id):
    """Get specific workflow content by ID."""
    try:
        if cache_key not in workflow_cache:
            return jsonify({'error': 'Workflow cache expired. Please re-upload document.'}), 404
        
        workflows = workflow_cache[cache_key]
        
        # Find workflow by ID
        workflow = next((wf for wf in workflows if wf.id == workflow_id), None)
        
        if not workflow:
            return jsonify({'error': f'Workflow {workflow_id} not found'}), 404
        
        # Prepare workflow for parser
        extractor = ContentExtractor()
        workflow_text = extractor.preprocess_for_parser(workflow.content)
        
        return jsonify({
            'success': True,
            'workflow_text': workflow_text,
            'title': workflow.title,
            'step_count': workflow.step_count,
            'decision_count': workflow.decision_count,
            'confidence': workflow.confidence
        })
    
    except Exception as e:
        logger.error(f"Get workflow error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/generate', methods=['POST'])
def generate_flowchart():
    """Generate flowchart from workflow text."""
    try:
        data = request.get_json()
        
        if not data or 'workflow_text' not in data:
            return jsonify({'error': 'No workflow text provided'}), 400
        
        workflow_text = data['workflow_text']
        title = data.get('title', 'Workflow')
        theme = data.get('theme', 'default')
        direction = data.get('direction', 'TD')
        format = data.get('format', 'png')
        validate_flag = data.get('validate', True)
        
        # Parse workflow
        parser = NLPParser(use_spacy=True)
        steps = parser.parse(workflow_text)
        
        if not steps:
            return jsonify({'error': 'No workflow steps detected'}), 400
        
        # Check complexity
        if len(steps) > 20:
            logger.warning(f"High complexity workflow: {len(steps)} steps")
        
        # Build flowchart
        builder = GraphBuilder()
        flowchart = builder.build(steps, title=title)
        
        # Validate if requested
        validation_result = {}
        if validate_flag:
            validator = ISO5807Validator()
            is_valid, errors, warnings = validator.validate(flowchart)
            validation_result = {
                'is_valid': is_valid,
                'errors': errors,
                'warnings': warnings
            }
            
            # Add complexity warning
            if len(flowchart.nodes) > 20:
                if 'warnings' not in validation_result:
                    validation_result['warnings'] = []
                validation_result['warnings'].append(
                    f"High node count ({len(flowchart.nodes)}). Consider splitting into multiple flowcharts for better readability (ISO 5807 compliance)."
                )
        
        # Generate Mermaid code
        generator = MermaidGenerator()
        mermaid_code = generator.generate_with_theme(flowchart, theme=theme)
        
        # For HTML format, return Mermaid code directly
        if format == 'mmd' or format == 'html':
            return jsonify({
                'success': True,
                'mermaid_code': mermaid_code,
                'validation': validation_result,
                'stats': {
                    'nodes': len(flowchart.nodes),
                    'connections': len(flowchart.connections),
                    'steps': len(steps)
                }
            })
        
        # Render to image format
        renderer = ImageRenderer()
        
        # Create temporary output file
        output_path = Path(tempfile.gettempdir()) / f"flowchart_{os.getpid()}.{format}"
        
        success = renderer.render(
            mermaid_code,
            str(output_path),
            format=format,
            width=3000,
            height=2000,
            theme=theme
        )
        
        if not success:
            return jsonify({'error': 'Failed to render flowchart'}), 500
        
        # Return file
        return send_file(
            output_path,
            as_attachment=True,
            download_name=f"{title.replace(' ', '_')}.{format}",
            mimetype=f'image/{format}'
        )
    
    except Exception as e:
        logger.error(f"Generation error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/clipboard', methods=['POST'])
def from_clipboard():
    """Extract workflow from clipboard text."""
    try:
        data = request.get_json()
        
        if not data or 'text' not in data:
            return jsonify({'error': 'No text provided'}), 400
        
        text = data['text']
        
        # Detect workflows
        detector = WorkflowDetector()
        workflows = detector.detect_workflows(text)
        
        if workflows and len(workflows) > 1:
            # Multiple workflows detected
            summary = detector.get_workflow_summary(workflows)
            return jsonify({
                'success': True,
                'multiple_workflows': True,
                'workflows': [w.to_dict() for w in workflows],
                'summary': summary
            })
        
        # Single workflow or fallback
        extractor = ContentExtractor()
        workflow_text = extractor.extract_best_workflow(text)
        
        if not workflow_text:
            workflow_text = extractor.preprocess_for_parser(text)
        
        # Get summary
        summary = extractor.get_workflow_summary(workflow_text)
        
        return jsonify({
            'success': True,
            'workflow_text': workflow_text,
            'summary': summary
        })
    
    except Exception as e:
        logger.error(f"Clipboard error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    parser = DocumentParser()
    return jsonify({
        'status': 'ok',
        'supported_formats': parser.get_supported_formats(),
        'version': '0.2.0'
    })


if __name__ == '__main__':
    print("\n" + "="*60)
    print("  🚀 ISO 5807 Flowchart Generator - Web Interface")
    print("="*60)
    print("\n  Access at: http://localhost:5000")
    print("  Press Ctrl+C to stop\n")
    
    app.run(host='127.0.0.1', port=5000, debug=True)
