"""D2 declarative diagramming renderer for modern flowchart aesthetics.

Uses the D2 language (Terrastruct) with TALA/ELK layout engines
for superior edge routing and professional visual output.

Requires:
    pip install py-d2
    System: d2 binary (https://d2lang.com/tour/install)
"""

import subprocess
import shutil
import warnings
from pathlib import Path
from typing import Optional, Literal, Dict, List

from src.models import Flowchart, FlowchartNode, NodeType, ConnectionType


# ISO 5807 → D2 shape mapping
NODE_TYPE_TO_D2_SHAPE: Dict[str, str] = {
    NodeType.TERMINATOR: "oval",
    NodeType.PROCESS: "rectangle",
    NodeType.DECISION: "diamond",
    NodeType.IO: "parallelogram",
    NodeType.DATABASE: "cylinder",
    NodeType.DISPLAY: "hexagon",
    NodeType.DOCUMENT: "page",
    NodeType.PREDEFINED: "double",
    NodeType.MANUAL: "queue",       # Closest D2 approximation to trapezoid
    NodeType.CONNECTOR: "circle",
}


class D2Renderer:
    """Render flowcharts using the D2 declarative language.

    Produces modern, aesthetically superior diagrams compared
    to Mermaid/Graphviz with advanced layout via TALA/ELK.
    """

    def __init__(self, layout: str = "elk", theme: int = 0):
        """
        Args:
            layout: Layout engine ('dagre', 'elk', 'tala').
            theme: D2 theme ID (0=default, 1=dark, 100+=special).
        """
        self.layout = layout
        self.theme = theme
        self._available = None

    @property
    def available(self) -> bool:
        """Check if D2 binary is installed."""
        if self._available is None:
            self._available = shutil.which("d2") is not None
        return self._available

    def render(
        self,
        flowchart: Flowchart,
        output_path: str,
        format: Literal["png", "svg", "pdf"] = "svg",
    ) -> bool:
        """Render flowchart to image using D2 binary.

        Args:
            flowchart: Validated Flowchart model.
            output_path: Output file path.
            format: Output format (svg is native, png/pdf via conversion).

        Returns:
            True if successful.
        """
        if not self.available:
            warnings.warn(
                "D2 not available. Install from: https://d2lang.com/tour/install"
            )
            return False

        try:
            d2_source = self.generate_d2(flowchart)

            # Write D2 source to temp file
            out = Path(output_path)
            temp_d2 = out.with_suffix(".d2")

            out.parent.mkdir(parents=True, exist_ok=True)
            temp_d2.write_text(d2_source, encoding="utf-8")

            # Build D2 command
            cmd = [
                "d2",
                f"--layout={self.layout}",
                f"--theme={self.theme}",
                str(temp_d2),
                str(out),
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )

            # Cleanup temp file
            try:
                temp_d2.unlink()
            except Exception:
                pass

            if result.returncode != 0:
                warnings.warn(f"D2 rendering failed: {result.stderr}")
                return False

            print(f"✓ D2 rendered: {output_path}")
            return True

        except subprocess.TimeoutExpired:
            warnings.warn("D2 rendering timeout (30s)")
            return False
        except Exception as e:
            warnings.warn(f"D2 rendering error: {e}")
            return False

    def generate_d2(self, flowchart: Flowchart) -> str:
        """Generate D2 declarative source code.

        The D2 syntax is simpler than DOT:
            node_id: "Label" { shape: diamond }
            node_a -> node_b: "edge label"
        """
        lines: List[str] = []

        # Title
        if flowchart.title:
            lines.append(f"# {flowchart.title}")
            lines.append("")

        # Direction
        lines.append("direction: down")
        lines.append("")

        # Node definitions
        for node in flowchart.nodes:
            shape = NODE_TYPE_TO_D2_SHAPE.get(node.node_type, "rectangle")
            label = self._escape_d2(node.label)

            # Build style
            style_parts = []
            style_parts.append(f'shape: {shape}')

            # Color by type
            fill = self._get_fill_color(node)
            if fill:
                style_parts.append(f'style.fill: "{fill}"')
                style_parts.append('style.font-color: "#333333"')

            # Low confidence
            confidence = getattr(node, "confidence", 1.0)
            if confidence < 0.7:
                style_parts.append('style.stroke-dash: 5')
                style_parts.append('style.stroke: "#FF9800"')

            lines.append(f'{node.id}: "{label}" {{')
            for sp in style_parts:
                lines.append(f'  {sp}')
            lines.append('}')
            lines.append('')

        # Connections
        for conn in flowchart.connections:
            edge_str = f"{conn.from_node} -> {conn.to_node}"
            if conn.label:
                edge_str += f": {self._escape_d2(conn.label)}"

            if conn.connection_type == ConnectionType.LOOP:
                lines.append(f"{edge_str} {{")
                lines.append('  style.stroke-dash: 5')
                lines.append('  style.stroke: "#9C27B0"')
                lines.append('}')
            else:
                lines.append(edge_str)

        return "\n".join(lines)

    def _get_fill_color(self, node: FlowchartNode) -> Optional[str]:
        """Get fill color based on node type."""
        colors = {
            NodeType.TERMINATOR: "#90EE90",
            NodeType.DECISION: "#FFE4B5",
            NodeType.PREDEFINED: "#B0E0E6",
            NodeType.DATABASE: "#E8E8E8",
            NodeType.DOCUMENT: "#FAFAD2",
        }
        # End terminators get pink
        if node.node_type == NodeType.TERMINATOR and any(
            kw in node.label.lower() for kw in ["end", "stop", "finish"]
        ):
            return "#FFB6C1"
        return colors.get(node.node_type)

    @staticmethod
    def _escape_d2(text: str) -> str:
        """Escape special characters for D2 syntax."""
        return text.replace('"', '\\"').replace("\n", " ")
