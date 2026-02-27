"""WebSocket handler for real-time flowchart generation preview.

Phase 4: Implements WebSocket streaming so the frontend can receive
JSON parse progress, node-by-node construction, and live Mermaid
code updates without polling.

Requires: pip install flask-socketio
"""

import json
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Guard import — WebSocket is optional
try:
    from flask_socketio import SocketIO, emit
    HAS_SOCKETIO = True
except ImportError:
    HAS_SOCKETIO = False
    SocketIO = None  # type: ignore


def create_socketio(app=None, **kwargs):
    """Create SocketIO instance if flask-socketio is installed."""
    if not HAS_SOCKETIO:
        logger.info("flask-socketio not installed. WebSocket features disabled.")
        logger.info("Install with: pip install flask-socketio")
        return None

    sio = SocketIO(
        app,
        cors_allowed_origins="*",
        async_mode='threading',
        **kwargs,
    )
    _register_handlers(sio)
    return sio


def _register_handlers(sio):
    """Register WebSocket event handlers."""

    @sio.on('connect')
    def handle_connect():
        logger.info("WebSocket client connected")
        emit('status', {'connected': True, 'features': ['live_preview', 'progress', 'node_stream']})

    @sio.on('disconnect')
    def handle_disconnect():
        logger.info("WebSocket client disconnected")

    @sio.on('generate_live')
    def handle_generate_live(data):
        """Real-time flowchart generation with incremental updates."""
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).parent.parent))

        workflow_text = data.get('workflow_text', '')
        title = data.get('title', 'Workflow')
        theme = data.get('theme', 'default')
        extraction = data.get('extraction', 'auto')
        renderer = data.get('renderer', 'mermaid')
        model_path = data.get('model_path')
        ollama_base_url = data.get('ollama_base_url', 'http://localhost:11434')
        ollama_model = data.get('ollama_model')

        if not workflow_text.strip():
            emit('error', {'message': 'No workflow text provided'})
            return

        try:
            from src.pipeline import FlowchartPipeline, PipelineConfig

            # Step 1: Initializing
            emit('progress', {'stage': 'init', 'pct': 5, 'msg': 'Initializing pipeline...'})

            config = PipelineConfig(
                extraction=extraction,
                renderer=renderer,
                model_path=model_path,
                ollama_base_url=ollama_base_url,
                ollama_model=ollama_model,
                theme=theme,
            )
            pipeline = FlowchartPipeline(config)

            # Step 2: Extracting steps
            emit('progress', {'stage': 'extract', 'pct': 20, 'msg': f'Extracting steps via {extraction}...'})
            steps = pipeline.extract_steps(workflow_text)
            extraction_meta = pipeline.get_last_extraction_metadata()

            if not steps:
                emit('error', {'message': 'No workflow steps detected'})
                return

            emit('progress', {'stage': 'extract_done', 'pct': 40,
                              'msg': f'Extracted {len(steps)} steps',
                              'step_count': len(steps)})

            # Step 3: Stream nodes as they're built
            emit('progress', {'stage': 'build', 'pct': 50, 'msg': 'Building flowchart graph...'})

            from src.builder.graph_builder import GraphBuilder
            builder = GraphBuilder()
            flowchart = builder.build(steps, title=title)

            # Stream individual nodes for live preview
            for i, node in enumerate(flowchart.nodes):
                node_data = {
                    'id': node.id,
                    'label': node.label,
                    'type': node.node_type,
                    'confidence': node.confidence,
                }
                if hasattr(node, 'alternatives') and node.alternatives:
                    node_data['alternatives'] = node.alternatives

                emit('node', node_data)

            emit('progress', {'stage': 'build_done', 'pct': 65,
                              'msg': f'{len(flowchart.nodes)} nodes, {len(flowchart.connections)} connections',
                              'node_count': len(flowchart.nodes),
                              'connection_count': len(flowchart.connections)})

            # Step 4: Validate
            emit('progress', {'stage': 'validate', 'pct': 75, 'msg': 'Validating ISO 5807...'})

            from src.builder.validator import ISO5807Validator
            validator = ISO5807Validator()
            is_valid, errors, warnings_list = validator.validate(flowchart)

            emit('validation', {
                'is_valid': is_valid,
                'errors': errors,
                'warnings': warnings_list,
            })

            # Step 5: Generate Mermaid code
            emit('progress', {'stage': 'generate', 'pct': 85, 'msg': 'Generating diagram code...'})

            from src.generator.mermaid_generator import MermaidGenerator
            generator = MermaidGenerator()
            mermaid_code = generator.generate_with_theme(flowchart, theme=theme)

            emit('mermaid_code', {'code': mermaid_code})

            # Step 6: Generate alternative renderer code if applicable
            alt_code = None
            if renderer == 'graphviz':
                try:
                    from src.renderer.graphviz_renderer import GraphvizRenderer
                    gv = GraphvizRenderer()
                    alt_code = {'type': 'dot', 'source': gv.generate_dot(flowchart)}
                except Exception:
                    pass
            elif renderer == 'd2':
                try:
                    from src.renderer.d2_renderer import D2Renderer
                    d2 = D2Renderer()
                    alt_code = {'type': 'd2', 'source': d2.generate_d2(flowchart)}
                except Exception:
                    pass

            # Final result
            emit('progress', {'stage': 'done', 'pct': 100, 'msg': 'Complete!'})

            result = {
                'success': True,
                'mermaid_code': mermaid_code,
                'stats': {
                    'nodes': len(flowchart.nodes),
                    'connections': len(flowchart.connections),
                    'steps': len(steps),
                },
                'validation': {
                    'is_valid': is_valid,
                    'errors': errors,
                    'warnings': warnings_list,
                },
                'pipeline': {
                    'extraction': extraction,
                    'requested_extraction': extraction_meta.get('requested_extraction', extraction),
                    'resolved_extraction': extraction_meta.get('resolved_extraction', extraction),
                    'final_extraction': extraction_meta.get('final_extraction', extraction),
                    'fallback_used': extraction_meta.get('fallback_used', False),
                    'fallback_reason': extraction_meta.get('fallback_reason'),
                    'renderer': renderer,
                },
            }
            if alt_code:
                result['alt_code'] = alt_code

            emit('result', result)

        except Exception as e:
            logger.error(f"WebSocket generation error: {e}", exc_info=True)
            emit('error', {'message': str(e)})

    @sio.on('ping_capabilities')
    def handle_ping_capabilities():
        """Return system capabilities over WebSocket."""
        try:
            from src.capability_detector import CapabilityDetector
            detector = CapabilityDetector()
            emit('capabilities', detector.get_summary())
        except Exception as e:
            emit('error', {'message': f'Capability detection failed: {e}'})
