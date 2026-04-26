"""Mermaid.js code generator for flowcharts.

Phase 2: Confidence-based node styling, loop-back edge styling,
tooltip labels for uncertain nodes.

Enhancement 5: Warning/critical annotation styling with colors.
"""

import re
import unicodedata
import html
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

    # Soft-wrap thresholds — tuned so node labels stay readable in printed exports
    # without expanding the diagram canvas excessively.
    LABEL_WRAP_WIDTH = 32
    LABEL_MAX_LINES = 4

    # Refined neutral palette + single signal accent reserved for decisions and
    # the primary START terminator. Consciously generic — designed to read on
    # white paper, projector slides, and dark-mode screens without theming per
    # document.
    THEME_TOKENS = {
        'background': '#FFFFFF',
        'paper': '#F5F2ED',
        'ink': '#1B1B1A',
        'ink_soft': '#5C5B58',
        'edge': '#1B1B1A',
        'edge_label': '#3D3D3B',
        'accent': '#D2502B',          # decision + primary terminator
        'accent_soft': '#FCE9DF',     # decision fill
        'subtle': '#E8E2D5',          # low-confidence dashed border
        'success': '#3F6B4A',         # success / Yes branch
        'caution': '#A05C12',         # warning band
        'critical': '#9B2226',        # critical band
    }

    def __init__(self):
        self.direction = "TD"

    def _soft_wrap(self, text: str, width: int = None, max_lines: int = None) -> str:
        """Word-wrap a label so nodes stay compact in printed/exported diagrams.

        Returns text with newline separators (which `_sanitize_text` later
        converts to `<br/>`). Truncates with an ellipsis on the final line when
        content exceeds max_lines instead of letting Mermaid blow up the canvas.
        """
        if not text:
            return text
        width = width or self.LABEL_WRAP_WIDTH
        max_lines = max_lines or self.LABEL_MAX_LINES

        wrapped: List[str] = []
        for paragraph in text.splitlines():
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            words = paragraph.split()
            line = ''
            for word in words:
                if not line:
                    line = word
                    continue
                if len(line) + 1 + len(word) <= width:
                    line = f'{line} {word}'
                else:
                    wrapped.append(line)
                    if len(wrapped) >= max_lines:
                        break
                    line = word
            if line and len(wrapped) < max_lines:
                wrapped.append(line)
            if len(wrapped) >= max_lines:
                break

        if not wrapped:
            return ''
        if len(wrapped) >= max_lines:
            last = wrapped[-1]
            if len(last) > width - 1:
                last = last[:width - 1].rstrip()
            if not last.endswith('…'):
                wrapped[-1] = last + '…'
        return '\n'.join(wrapped)

    def generate(self, flowchart: Flowchart, direction: str = "TD") -> str:
        """Generate Mermaid.js flowchart code."""
        self.direction = direction
        lines = []

        lines.append(f"flowchart {self.direction}")

        if flowchart.title:
            lines.append(f"    %% {self._sanitize_text(flowchart.title)}")

        # Node definitions
        grouped_nodes = {}
        for node in flowchart.nodes:
            group_name = getattr(node, "group", None)
            if group_name not in grouped_nodes:
                grouped_nodes[group_name] = []
            grouped_nodes[group_name].append(node)

        for group_name, nodes in grouped_nodes.items():
            if group_name:
                # Create a stable, unique subgraph ID from the group name
                safe_group_id = re.sub(r'[^a-zA-Z0-9]', '_', group_name)
                lines.append(f"    subgraph {safe_group_id} [\"{self._sanitize_text(group_name)}\"]")
                for node in nodes:
                    node_def = self._generate_node(node)
                    lines.append(f"        {node_def}")
                lines.append("    end")
            else:
                for node in nodes:
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

        # Normalize any HTML entities from imported/extracted text.
        text = html.unescape(text)
        
        # Protect our intentional line breaks by converting them to Mermaid HTML tags
        text = text.replace('\n', '<br/>')

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

        # ALLOW < and > so our <br/> tags survive sanitization
        text = re.sub(r'[^a-zA-Z0-9\s.,;:!?\'\"\-_/\\=+<>]', ' ', text)
        
        # Don't flatten all whitespace (which destroys spacing around tags)
        text = re.sub(r'[ \t\r]+', ' ', text)
        return text.strip()

    _DECISION_MARKER_RE = re.compile(r'^\s*(\d+\.\s*)?\?\s+', re.UNICODE)

    def _strip_decision_marker(self, label: str) -> str:
        """Remove the parser's leading `?` decision-question marker from a label.

        The marker is meaningful upstream (it forces the line through the
        action-line filter) but is noise inside a rendered diamond, which
        already reads as a question via its shape.
        """
        if not label:
            return label
        return self._DECISION_MARKER_RE.sub(lambda m: m.group(1) or '', label)

    def _generate_node(self, node: FlowchartNode) -> str:
        """Generate Mermaid node definition with soft-wrapped, escaped label."""
        shape_template, _ = self.NODE_TYPE_TO_SHAPE.get(
            node.node_type,
            ("[{}]", "rect")
        )

        raw_label = self._strip_decision_marker(node.label or '')
        # Soft-wrap before sanitize so newlines become <br/> via _sanitize_text.
        label = self._soft_wrap(raw_label)
        label = self._sanitize_text(label)
        label = self._escape_label(label)

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
        # Keep rendered labels human-readable in exported artifacts.
        # Avoid HTML entities so text like apostrophes does not become '&#39;'.
        text = text.replace('|', '/')
        # Mermaid flowchart labels are not JSON strings; backslash-quote can break parsing.
        # Normalize double-quotes to apostrophes for parser-safe labels.
        text = text.replace('"', "'")
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
        """Apply the refined neutral palette to special and low-confidence nodes.

        The palette stays generic on purpose: ink-on-paper bodies, a single
        accent (orange) reserved for decisions and the START terminator, and
        muted bands for warnings/criticals so the eye lands on the workflow
        shape first, the annotations second.
        """
        styles: List[str] = []
        t = self.THEME_TOKENS
        buckets = self._classify_style_buckets(flowchart)
        loop_target_ids = self._collect_loop_targets(flowchart)

        # Start = filled with accent so the eye finds the entry point instantly.
        self._append_style_group(
            styles, buckets["start_nodes"],
            f"fill:{t['accent']},stroke:{t['ink']},stroke-width:1.6px,color:#FFFFFF",
        )
        # End = ink-filled charcoal.
        self._append_style_group(
            styles, buckets["end_nodes"],
            f"fill:{t['ink']},stroke:{t['ink']},stroke-width:1.6px,color:#FFFFFF",
        )
        # Decision diamonds = paper fill with accent border so YES/NO branches
        # read as the moment the workflow forks.
        self._append_style_group(
            styles, buckets["decision_nodes"],
            f"fill:{t['accent_soft']},stroke:{t['accent']},stroke-width:1.8px,color:{t['ink']}",
        )
        # Predefined / subroutine = paper fill with ink-soft border.
        self._append_style_group(
            styles, buckets["predefined_nodes"],
            f"fill:{t['paper']},stroke:{t['ink_soft']},stroke-width:1.4px,color:{t['ink']}",
        )
        # Low-confidence = dashed warm-gray border, no fill change.
        self._append_style_group(
            styles, buckets["low_confidence_nodes"],
            f"stroke:{t['ink_soft']},stroke-width:1.4px,stroke-dasharray: 4 4",
        )

        for node_id in loop_target_ids:
            if node_id not in buckets["start_nodes"] and node_id not in buckets["end_nodes"]:
                styles.append(
                    f"    style {node_id} fill:{t['paper']},stroke:{t['ink_soft']},stroke-width:1.4px,stroke-dasharray: 2 4"
                )

        self._append_style_group(
            styles, buckets["critical_nodes"],
            f"stroke:{t['critical']},stroke-width:2px,fill:#FBEAEC,color:{t['ink']}",
        )
        self._append_style_group(
            styles, buckets["warning_nodes"],
            f"stroke:{t['caution']},stroke-width:1.8px,fill:#FBEFD9,color:{t['ink']}",
        )
        self._append_style_group(
            styles, buckets["note_nodes"],
            f"stroke:{t['ink_soft']},stroke-width:1.4px,fill:#EFEDE5,color:{t['ink']}",
        )

        # Distinguish edges that leave decision nodes — branch labels should
        # carry weight so the reader follows the fork. Mermaid's linkStyle uses
        # connection index from declaration order.
        decision_ids = set(buckets["decision_nodes"])
        if decision_ids:
            for idx, conn in enumerate(flowchart.connections):
                if conn.from_node in decision_ids:
                    styles.append(
                        f"    linkStyle {idx} stroke:{t['edge']},stroke-width:1.6px,color:{t['edge_label']},font-style:italic,font-weight:600"
                    )

        return styles

    def _build_theme_init(self, theme: str = 'default') -> str:
        """Return the Mermaid `%%{init: ...}%%` directive carrying our theme.

        Mermaid accepts a JSON object literal inside the init directive; using
        json.dumps avoids quoting collisions in values like fontFamily that
        contain commas and family names.
        """
        import json
        t = self.THEME_TOKENS
        # Use 'base' theme so themeVariables actually take effect; callers
        # asking for 'dark' / 'forest' / 'neutral' get Mermaid's stock theme.
        resolved_theme = theme if theme in {'dark', 'forest', 'neutral'} else 'base'
        config = {
            'theme': resolved_theme,
            'themeVariables': {
                'background': t['background'],
                'primaryColor': t['paper'],
                'primaryTextColor': t['ink'],
                'primaryBorderColor': t['ink'],
                'secondaryColor': t['accent_soft'],
                'tertiaryColor': t['paper'],
                'lineColor': t['edge'],
                'textColor': t['ink'],
                'titleColor': t['ink'],
                'edgeLabelBackground': t['background'],
                'fontFamily': 'Fraunces, Iowan Old Style, Georgia, serif',
                'fontSize': '15px',
            },
            'flowchart': {
                'curve': 'basis',
                'htmlLabels': True,
                'nodeSpacing': 32,
                'rankSpacing': 56,
                'padding': 14,
            },
        }
        return f"%%{{init: {json.dumps(config)}}}%%"

    def generate_with_theme(
        self,
        flowchart: Flowchart,
        theme: str = "default",
        direction: str = "TD",
    ) -> str:
        """Generate Mermaid code with the project's refined default theme."""
        code = self.generate(flowchart, direction=direction)
        return f"{self._build_theme_init(theme)}\n{code}"
