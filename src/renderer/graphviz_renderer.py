"""Native Graphviz DOT renderer for flowcharts.

Replaces the Node.js/Chromium mermaid-cli dependency with compiled
C-based Graphviz rendering via pydot/graphviz Python bindings.
Uses the Sugiyama hierarchical layout algorithm for optimal flowchart display.

Requires:
    pip install graphviz
    System: graphviz (apt install graphviz / brew install graphviz / choco install graphviz)
"""

import warnings
from pathlib import Path
from typing import Dict, Literal

from src.models import Connection, ConnectionType, Flowchart, FlowchartNode, NodeType

# ISO 5807 → Graphviz DOT shape mapping
NODE_TYPE_TO_DOT_SHAPE: Dict[str, str] = {
    NodeType.TERMINATOR: "oval",
    NodeType.PROCESS: "box",
    NodeType.DECISION: "diamond",
    NodeType.IO: "parallelogram",
    NodeType.DATABASE: "cylinder",
    NodeType.DISPLAY: "hexagon",
    NodeType.DOCUMENT: "note",
    NodeType.PREDEFINED: "doubleoctagon",
    NodeType.MANUAL: "trapezium",
    NodeType.CONNECTOR: "circle",
}

# Color scheme matching existing Mermaid styles
NODE_TYPE_COLORS: Dict[str, dict] = {
    NodeType.TERMINATOR: {"fillcolor": "#90EE90", "fontcolor": "#333333"},  # Green
    NodeType.DECISION: {"fillcolor": "#FFE4B5", "fontcolor": "#333333"},   # Yellow
    NodeType.PREDEFINED: {"fillcolor": "#B0E0E6", "fontcolor": "#333333"},  # Light blue
    NodeType.DATABASE: {"fillcolor": "#E8E8E8", "fontcolor": "#333333"},   # Gray
    NodeType.DOCUMENT: {"fillcolor": "#FAFAD2", "fontcolor": "#333333"},   # Light yellow
    NodeType.IO: {"fillcolor": "#E0E0FF", "fontcolor": "#333333"},         # Light purple
    NodeType.MANUAL: {"fillcolor": "#FFE4E1", "fontcolor": "#333333"},     # Light pink
    NodeType.DISPLAY: {"fillcolor": "#E0FFE0", "fontcolor": "#333333"},    # Light green
}


class GraphvizRenderer:
    """Render flowcharts using native Graphviz DOT engine.

    Eliminates Node.js/Chromium dependency entirely.
    Uses compiled C Graphviz for near-instant rendering.
    """

    def __init__(self, engine: str = "dot", rankdir: str = "TB"):
        """
        Args:
            engine: Graphviz layout engine ('dot', 'neato', 'fdp', 'circo', 'twopi').
            rankdir: Graph direction ('TB'=top-bottom, 'LR'=left-right, 'BT', 'RL').
        """
        self.engine = engine
        self.rankdir = rankdir
        self._available = None

    @property
    def available(self) -> bool:
        """Check if graphviz is installed."""
        if self._available is None:
            try:
                import graphviz

                # Also verify the system binary exists
                graphviz.version()
                self._available = True
            except Exception:
                self._available = False
        return self._available

    def render(
        self,
        flowchart: Flowchart,
        output_path: str,
        format: Literal["png", "svg", "pdf"] = "png",
    ) -> bool:
        """Render flowchart to image file.

        Args:
            flowchart: Validated Flowchart model.
            output_path: Output file path (extension ignored, format param used).
            format: Output format.

        Returns:
            True if successful.
        """
        if not self.available:
            warnings.warn(
                "Graphviz not available. Install:\n"
                "  pip install graphviz\n"
                "  System: apt install graphviz / brew install graphviz"
            )
            return False

        try:
            import graphviz as gv

            dot = gv.Digraph(
                name=flowchart.title or "Flowchart",
                format=format,
                engine=self.engine,
            )

            # Graph-level attributes
            dot.attr(
                rankdir=self.rankdir,
                splines="ortho",
                nodesep="0.8",
                ranksep="1.0",
                fontname="Helvetica",
                fontsize="12",
                bgcolor="white",
            )

            # Default node style
            dot.attr(
                "node",
                style="filled,rounded",
                fontname="Helvetica",
                fontsize="11",
                fillcolor="#FFFFFF",
                color="#333333",
                penwidth="1.5",
            )

            # Default edge style
            dot.attr(
                "edge",
                fontname="Helvetica",
                fontsize="10",
                color="#555555",
                arrowsize="0.8",
            )

            # Add nodes
            for node in flowchart.nodes:
                self._add_node(dot, node)

            # Add edges
            for conn in flowchart.connections:
                self._add_edge(dot, conn)

            # Render to file
            out = Path(output_path)
            dot.render(
                filename=out.stem,
                directory=str(out.parent),
                cleanup=True,
            )

            print(f"✓ Graphviz rendered: {output_path}")
            return True

        except Exception as e:
            warnings.warn(f"Graphviz rendering failed: {e}")
            return False

    def generate_dot(self, flowchart: Flowchart) -> str:
        """Generate DOT source code without rendering.

        Useful for piping to external tools or inspection.
        """
        try:
            import graphviz as gv

            dot = gv.Digraph(
                name=flowchart.title or "Flowchart",
                engine=self.engine,
            )
            dot.attr(rankdir=self.rankdir, splines="ortho")
            dot.attr("node", style="filled,rounded", fontname="Helvetica")

            for node in flowchart.nodes:
                self._add_node(dot, node)
            for conn in flowchart.connections:
                self._add_edge(dot, conn)

            return dot.source

        except ImportError:
            return "// graphviz package not installed"

    def _add_node(self, dot, node: FlowchartNode):
        """Add a flowchart node with ISO 5807 shape mapping."""
        shape = NODE_TYPE_TO_DOT_SHAPE.get(node.node_type, "box")
        colors = NODE_TYPE_COLORS.get(node.node_type, {})

        # Special handling for terminator end nodes
        is_end = node.node_type == NodeType.TERMINATOR and any(
            kw in node.label.lower() for kw in ["end", "stop", "finish"]
        )
        if is_end:
            colors = {"fillcolor": "#FFB6C1", "fontcolor": "#333333"}

        attrs = {
            "shape": shape,
            "label": self._truncate_label(node.label),
            **colors,
        }

        # Low confidence styling
        confidence = getattr(node, "confidence", 1.0)
        if confidence < 0.7:
            attrs["style"] = "filled,dashed"
            attrs["color"] = "#FF9800"
            attrs["penwidth"] = "2.5"

        dot.node(node.id, **attrs)

    def _add_edge(self, dot, conn: Connection):
        """Add an edge with optional label and loop styling."""
        attrs = {}

        if conn.label:
            attrs["label"] = f" {conn.label} "

        if conn.connection_type == ConnectionType.LOOP:
            attrs["style"] = "dashed"
            attrs["color"] = "#9C27B0"

        dot.edge(conn.from_node, conn.to_node, **attrs)

    @staticmethod
    def _truncate_label(label: str, max_len: int = 40) -> str:
        """Truncate long labels with word wrapping via \\n."""
        if len(label) <= max_len:
            return label
        words = label.split()
        lines = []
        current_line = ""
        for word in words:
            if len(current_line) + len(word) + 1 > max_len:
                lines.append(current_line)
                current_line = word
            else:
                current_line = f"{current_line} {word}".strip()
        if current_line:
            lines.append(current_line)
        return "\\n".join(lines[:3])  # Max 3 lines
