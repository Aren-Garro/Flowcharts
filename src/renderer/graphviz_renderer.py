"""Native Graphviz DOT renderer for flowcharts.

Replaces the Node.js/Chromium mermaid-cli dependency with compiled
C-based Graphviz rendering via pydot/graphviz Python bindings.
Uses the Sugiyama hierarchical layout algorithm for optimal flowchart display.

Requires:
    pip install graphviz
    System: graphviz (apt install graphviz / brew install graphviz / choco install graphviz)
"""

import textwrap
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Literal, Tuple

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


@dataclass(frozen=True)
class LayoutProfile:
    """Layout defaults tuned for export readability."""

    graph_attrs: Dict[str, str]
    node_attrs: Dict[str, str]
    edge_attrs: Dict[str, str]


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
            dot = self._build_digraph(flowchart, format=format)

            # Render to file
            out = Path(output_path)
            dot.render(
                filename=out.stem,
                directory=str(out.parent),
                cleanup=True,
            )

            print(f"Graphviz rendered: {output_path}")
            return True

        except Exception as e:
            warnings.warn(f"Graphviz rendering failed: {e}")
            return False

    def generate_dot(self, flowchart: Flowchart) -> str:
        """Generate DOT source code without rendering.

        Useful for piping to external tools or inspection.
        """
        try:
            return self._build_digraph(flowchart).source

        except ImportError:
            return "// graphviz package not installed"

    def _build_digraph(
        self,
        flowchart: Flowchart,
        format: Literal["png", "svg", "pdf"] | None = None,
    ):
        import graphviz as gv

        dot = gv.Digraph(
            name=flowchart.title or "Flowchart",
            format=format,
            engine=self.engine,
        )
        layout = self._layout_profile(flowchart)
        dot.attr(**layout.graph_attrs)
        dot.attr("node", **layout.node_attrs)
        dot.attr("edge", **layout.edge_attrs)

        grouped_nodes = {}
        for node in flowchart.nodes:
            group_name = getattr(node, "group", None)
            if group_name not in grouped_nodes:
                grouped_nodes[group_name] = []
            grouped_nodes[group_name].append(node)

        for group_name, nodes in grouped_nodes.items():
            if group_name:
                with dot.subgraph(name=f"cluster_{hash(group_name)}") as s:
                    s.attr(
                        label=group_name,
                        color="#94A3B8",
                        pencolor="#94A3B8",
                        style="rounded,filled",
                        fillcolor="#F8FAFC",
                        fontname="Arial Bold",
                        fontsize="13",
                        margin="22",
                    )
                    for node in nodes:
                        self._add_node(s, node)
            else:
                for node in nodes:
                    self._add_node(dot, node)

        for conn in flowchart.connections:
            self._add_edge(dot, conn)

        return dot

    def _layout_profile(self, flowchart: Flowchart) -> LayoutProfile:
        node_count = len(flowchart.nodes)
        edge_count = len(flowchart.connections)
        decision_count = sum(1 for node in flowchart.nodes if node.node_type == NodeType.DECISION)
        longest_label = max((len((node.label or "").strip()) for node in flowchart.nodes), default=0)
        phase_count = len({str(getattr(node, "group", "") or "") for node in flowchart.nodes if getattr(node, "group", None)})

        complex_diagram = (
            node_count >= 12
            or edge_count >= 14
            or decision_count >= 3
            or longest_label >= 32
        )
        very_complex_diagram = node_count >= 20 or edge_count >= 24 or decision_count >= 5 or phase_count >= 5
        phased_diagram = phase_count >= 4

        graph_attrs = {
            "rankdir": self.rankdir,
            "splines": "ortho",
            "fontname": "Arial",
            "fontsize": "12",
            "bgcolor": "white",
            "pad": "0.35",
            "nodesep": "0.85",
            "ranksep": "1.0",
            "newrank": "true",
            "compound": "true",
            "overlap": "false",
            "outputorder": "edgesfirst",
        }
        node_attrs = {
            "style": "filled,rounded",
            "fontname": "Arial",
            "fontsize": "11",
            "fillcolor": "#FFFFFF",
            "color": "#333333",
            "penwidth": "1.5",
            "margin": "0.18,0.12",
        }
        edge_attrs = {
            "fontname": "Arial",
            "fontsize": "10",
            "fontcolor": "#4B5563",
            "color": "#59636E",
            "arrowsize": "0.8",
            "penwidth": "1.2",
        }

        if complex_diagram:
            graph_attrs.update({
                "nodesep": "1.0",
                "ranksep": "1.2",
                "pad": "0.45",
            })
            node_attrs.update({
                "fontsize": "12",
                "margin": "0.22,0.15",
            })
            edge_attrs.update({
                "fontsize": "11",
                "penwidth": "1.3",
            })

        if very_complex_diagram:
            graph_attrs.update({
                "nodesep": "1.1",
                "ranksep": "1.35",
                "pad": "0.6",
            })
            node_attrs.update({
                "fontsize": "12",
                "margin": "0.24,0.16",
            })
            edge_attrs.update({
                "fontsize": "11",
                "penwidth": "1.4",
            })

        if phased_diagram:
            graph_attrs.update({
                "nodesep": "1.25",
                "ranksep": "1.7",
                "pad": "0.95",
            })
            node_attrs.update({
                "margin": "0.32,0.2",
            })
            edge_attrs.update({
                "fontsize": "11",
                "penwidth": "1.45",
            })

        return LayoutProfile(
            graph_attrs=graph_attrs,
            node_attrs=node_attrs,
            edge_attrs=edge_attrs,
        )

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
            "label": self._truncate_label(node.label, node.node_type),
            **colors,
        }

        if node.node_type == NodeType.DECISION:
            attrs.update({"width": "3.1", "height": "1.7"})
        elif node.node_type in {NodeType.TERMINATOR, NodeType.IO, NodeType.DOCUMENT, NodeType.DISPLAY}:
            attrs.update({"width": "2.7", "height": "1.0"})
        elif node.node_type == NodeType.CONNECTOR:
            attrs.update({"width": "0.7", "height": "0.7"})
        else:
            attrs.update({"width": "2.8", "height": "1.0"})

        # Low confidence styling
        confidence = getattr(node, "confidence", 1.0)
        if confidence < 0.7:
            attrs["style"] = "filled,rounded,dashed"
            attrs["color"] = "#C58A2B"
            attrs["penwidth"] = "2.0"

        dot.node(node.id, **attrs)

    def _add_edge(self, dot, conn: Connection):
        """Add an edge with optional label, loop styling, and port snapping."""
        attrs = {}
        label = (conn.label or "").strip()
        connection_type = str(conn.connection_type)

        if label:
            # Graphviz warns that ortho edges don't handle edge labels well.
            # Use xlabels so labeled edges still render without warnings.
            attrs["xlabel"] = f" {label} "

        if connection_type == ConnectionType.LOOP:
            attrs["style"] = "dashed"
            attrs["color"] = "#7C3AED"
            # Loop backs usually look better without strict port snapping 
            # as they often need to come out the side
            dot.edge(conn.from_node, conn.to_node, **attrs)
            return

        branch_ports = self._branch_ports(connection_type)
        if branch_ports:
            attrs["minlen"] = "3"
            attrs["weight"] = "1"
            tail_port, head_port = branch_ports
            dot.edge(f"{conn.from_node}:{tail_port}", f"{conn.to_node}:{head_port}", **attrs)
            return

        tail_port, head_port = self._main_flow_ports()
        attrs["weight"] = "3"
        dot.edge(f"{conn.from_node}:{tail_port}", f"{conn.to_node}:{head_port}", **attrs)

    def _main_flow_ports(self) -> Tuple[str, str]:
        if self.rankdir in {"LR", "RL"}:
            return ("e", "w") if self.rankdir == "LR" else ("w", "e")
        return ("s", "n") if self.rankdir == "TB" else ("n", "s")

    def _branch_ports(self, connection_type: str) -> Tuple[str, str] | None:
        is_positive = connection_type in {ConnectionType.YES, ConnectionType.TRUE, "yes", "true"}
        is_negative = connection_type in {ConnectionType.NO, ConnectionType.FALSE, "no", "false"}
        if not (is_positive or is_negative):
            return None

        if self.rankdir in {"LR", "RL"}:
            if is_positive:
                return ("s", "n")
            return ("n", "s")

        if is_positive:
            return ("e", "w")
        return ("w", "e")

    @staticmethod
    def _truncate_label(label: str, node_type: str, max_lines: int = 4) -> str:
        """Truncate long labels with word wrapping via \\n."""
        clean = " ".join((label or "").split())
        if not clean:
            return ""

        wrap_width = {
            NodeType.DECISION: 20,
            NodeType.TERMINATOR: 22,
            NodeType.IO: 24,
            NodeType.DOCUMENT: 24,
            NodeType.DISPLAY: 24,
            NodeType.CONNECTOR: 10,
        }.get(node_type, 28)

        lines = textwrap.wrap(
            clean,
            width=wrap_width,
            break_long_words=True,
            break_on_hyphens=True,
        )
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            lines[-1] = lines[-1].rstrip(". ") + "..."
        return "\\n".join(lines)

