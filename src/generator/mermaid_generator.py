"""Mermaid.js code generator for flowcharts.

Phase 2: Confidence-based node styling, loop-back edge styling,
tooltip labels for uncertain nodes.

Enhancement 5: Warning/critical annotation styling with colors.
"""

import re
import unicodedata
from typing import Dict, List

from src.models import Connection, ConnectionType, Flowchart, FlowchartNode, NodeType

LOW_CONFIDENCE_THRESHOLD = 0.7


class MermaidGenerator:
    """Generate Mermaid.js flowchart syntax from Flowchart model."""

    NODE_TYPE_TO_SHAPE: Dict[NodeType, tuple[str, str]] = {
        NodeType.TERMINATOR: ("([{}])", "stadium"),
        NodeType.PROCESS: ("[{}]", "rect"),
        NodeType.DECISION: ("{{{}}}", "diamond"),
        NodeType.IO: ("[/{}/]", "lean-r"),
        NodeType.DATABASE: ("[({})]", "cyl"),
        NodeType.DISPLAY: ("{{{{{}}}}}", "hex"),
        NodeType.DOCUMENT: ("[[{}]]", "doc"),
        NodeType.PREDEFINED: ("[[{}]]", "subroutine"),
        NodeType.MANUAL: ("[/{}\\]", "trap-b"),
        NodeType.CONNECTOR: ("(({}))", "circle"),
    }

    # Human-readable type names for tooltips
    NODE_TYPE_LABELS = {
        NodeType.TERMINATOR: "Terminator",
        NodeType.PROCESS: "Process",
        NodeType.DECISION: "Decision",
        NodeType.IO: "I/O",
        NodeType.DATABASE: "Database",
        NodeType.DISPLAY: "Display",
        NodeType.DOCUMENT: "Document",
        NodeType.PREDEFINED: "Predefined Process",
        NodeType.MANUAL: "Manual Input",
        NodeType.CONNECTOR: "Connector",
    }

    def __init__(self):
        self.direction = "TD"

    def generate(self, flowchart: Flowchart, direction: str = "TD") -> str:
        """Generate Mermaid.js flowchart code."""
        self.direction = direction
        lines = []

        lines.append(f"flowchart {self.direction}")

        if flowchart.title:
            lines.append(f"    %% {self._sanitize_text(flowchart.title)}")

        # Node definitions
        for node in flowchart.nodes:
            node_def = self._generate_node(node)
            lines.append(f"    {node_def}")

        lines.append("")

        # Connections
        for connection in flowchart.connections:
            conn_def = self._generate_connection(connection)
            lines.append(f"    {conn_def}")

        # Styling
        lines.append("")
        lines.extend(self._generate_styles(flowchart))

        return "\n".join(lines)

    def _sanitize_text(self, text: str) -> str:
        """Sanitize text for safe Mermaid parsing."""
        if not text:
            return text

        try:
            text = unicodedata.normalize('NFKD', text)
            text = text.encode('ascii', 'ignore').decode('ascii')
        except Exception:
            text = ''.join(char for char in text if ord(char) < 128)

        arrow_replacements = {
            '\u2192': '->', '\u2190': '<-', '\u2191': '^', '\u2193': 'v',
            '\u21d2': '=>', '\u21d0': '<=', '\u2794': '->', '\u279e': '->',
            '\u279c': '->', '\u25b6': '->', '\u25c0': '<-',
        }
        for uc, asc in arrow_replacements.items():
            text = text.replace(uc, asc)

        text = re.sub(r'[^a-zA-Z0-9\s.,;:!?\'\"\-_/\\=+]', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def _generate_node(self, node: FlowchartNode) -> str:
        """Generate Mermaid node definition."""
        shape_template, _ = self.NODE_TYPE_TO_SHAPE.get(
            node.node_type,
            ("[{}]", "rect")
        )

        label = self._sanitize_text(node.label)
        label = self._escape_label(label)

        # Don't add confidence annotations to labels - causes Mermaid parse errors
        # Low confidence is already indicated by visual styling (dashed borders)

        if len(label) > 120:
            label = label[:117] + "..."

        node_def = f"{node.id}{shape_template.format(label)}"
        return node_def

    def _generate_connection(self, connection: Connection) -> str:
        """Generate Mermaid connection definition with loop styling."""
        # Loop-back edges use dotted lines
        if connection.connection_type == ConnectionType.LOOP:
            arrow = "-.->"
        else:
            arrow = "-->"

        if connection.label:
            label = self._sanitize_text(connection.label)
            label = self._escape_label(label)
            if len(label) > 50:
                label = label[:47] + "..."
            return f"{connection.from_node} {arrow}|{label}| {connection.to_node}"
        else:
            return f"{connection.from_node} {arrow} {connection.to_node}"

    def _escape_label(self, text: str) -> str:
        """Escape special characters in labels for Mermaid."""
        text = text.replace('"', '&quot;')
        text = text.replace("'", '&#39;')
        text = text.replace('#', '&num;')
        text = text.replace('(', '&#40;')
        text = text.replace(')', '&#41;')
        text = text.replace('[', '&#91;')
        text = text.replace(']', '&#93;')
        text = text.replace('{', '&#123;')
        text = text.replace('}', '&#125;')
        text = text.replace('|', '&#124;')
        return text

    def _bucket_warning_level(self, buckets: Dict[str, List[str]], node: FlowchartNode) -> None:
        warning_level = getattr(node, 'warning_level', '')
        if warning_level == 'critical':
            buckets["critical_nodes"].append(node.id)
        elif warning_level == 'warning':
            buckets["warning_nodes"].append(node.id)
        elif warning_level == 'note':
            buckets["note_nodes"].append(node.id)

    def _bucket_node_type(self, buckets: Dict[str, List[str]], node: FlowchartNode) -> None:
        if node.node_type == NodeType.TERMINATOR:
            label = node.label.lower()
            if "start" in label or "begin" in label:
                buckets["start_nodes"].append(node.id)
            elif "end" in label or "finish" in label:
                buckets["end_nodes"].append(node.id)
        elif node.node_type == NodeType.DECISION:
            buckets["decision_nodes"].append(node.id)
        elif node.node_type == NodeType.PREDEFINED:
            buckets["predefined_nodes"].append(node.id)

    def _classify_style_buckets(self, flowchart: Flowchart) -> Dict[str, List[str]]:
        buckets = {
            "start_nodes": [],
            "end_nodes": [],
            "decision_nodes": [],
            "low_confidence_nodes": [],
            "predefined_nodes": [],
            "critical_nodes": [],
            "warning_nodes": [],
            "note_nodes": [],
        }

        for node in flowchart.nodes:
            confidence = getattr(node, 'confidence', 1.0)
            self._bucket_warning_level(buckets, node)
            self._bucket_node_type(buckets, node)

            if confidence < LOW_CONFIDENCE_THRESHOLD:
                buckets["low_confidence_nodes"].append(node.id)

        return buckets

    def _collect_loop_targets(self, flowchart: Flowchart) -> set[str]:
        loop_target_ids = set()
        for conn in flowchart.connections:
            if conn.connection_type == ConnectionType.LOOP:
                loop_target_ids.add(conn.to_node)
        return loop_target_ids

    def _append_style_group(self, styles: List[str], node_ids: List[str], style_suffix: str) -> None:
        for node_id in node_ids:
            styles.append(f"    style {node_id} {style_suffix}")

    def _generate_styles(self, flowchart: Flowchart) -> List[str]:
        """Generate CSS styling for special and low-confidence nodes.

        Enhancement 5: Added warning-level styling (critical=red, warning=orange, note=blue).
        """
        styles = []
        buckets = self._classify_style_buckets(flowchart)
        loop_target_ids = self._collect_loop_targets(flowchart)

        self._append_style_group(styles, buckets["start_nodes"], "fill:#90EE90,stroke:#333,stroke-width:2px")
        self._append_style_group(styles, buckets["end_nodes"], "fill:#FFB6C1,stroke:#333,stroke-width:2px")
        self._append_style_group(styles, buckets["decision_nodes"], "fill:#FFE4B5,stroke:#333,stroke-width:2px")
        self._append_style_group(styles, buckets["predefined_nodes"], "fill:#B0E0E6,stroke:#2196F3,stroke-width:2px")
        self._append_style_group(
            styles,
            buckets["low_confidence_nodes"],
            "stroke:#FF9800,stroke-width:3px,stroke-dasharray: 5 5"
        )

        for node_id in loop_target_ids:
            if node_id not in buckets["start_nodes"] and node_id not in buckets["end_nodes"]:
                styles.append(f"    style {node_id} fill:#E8D5F5,stroke:#9C27B0,stroke-width:2px")

        self._append_style_group(styles, buckets["critical_nodes"], "stroke:#D32F2F,stroke-width:4px,fill:#FFCDD2")
        self._append_style_group(styles, buckets["warning_nodes"], "stroke:#F57C00,stroke-width:3px,fill:#FFE0B2")
        self._append_style_group(styles, buckets["note_nodes"], "stroke:#1976D2,stroke-width:2px,fill:#BBDEFB")

        return styles

    def generate_with_theme(self, flowchart: Flowchart, theme: str = "default") -> str:
        """Generate Mermaid code with specific theme."""
        code = self.generate(flowchart)
        theme_line = f"%%{{init: {{'theme':'{theme}'}}}}%%"
        return f"{theme_line}\n{code}"
