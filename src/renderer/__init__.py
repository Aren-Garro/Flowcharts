"""Renderer package - Multi-engine flowchart rendering.

Supports:
- Mermaid.js (via mermaid-cli or HTML fallback)
- Graphviz (native DOT engine, no Node.js required)
- D2 (modern declarative diagramming with TALA/ELK layout)
- Kroki (unified multi-engine rendering via Docker)
"""

from src.renderer.image_renderer import ImageRenderer

__all__ = ["ImageRenderer"]

# Lazy imports for optional renderers
def get_graphviz_renderer(**kwargs):
    from src.renderer.graphviz_renderer import GraphvizRenderer
    return GraphvizRenderer(**kwargs)

def get_d2_renderer(**kwargs):
    from src.renderer.d2_renderer import D2Renderer
    return D2Renderer(**kwargs)

def get_kroki_renderer(**kwargs):
    from src.renderer.kroki_renderer import KrokiRenderer
    return KrokiRenderer(**kwargs)
