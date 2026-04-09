"""Graph builder for flowchart construction."""

from typing import Dict, List, Optional

from src.models import Flowchart, WorkflowStep
from src.parser.workflow_analyzer import WorkflowAnalyzer


class GraphBuilder:
    """Build flowchart graph from parsed workflow steps."""

    def __init__(self):
        self.analyzer = WorkflowAnalyzer()

    def build(self, steps: List[WorkflowStep], title: Optional[str] = None) -> Flowchart:
        """
        Build complete flowchart from workflow steps.

        Args:
            steps: List of parsed workflow steps
            title: Optional flowchart title

        Returns:
            Complete Flowchart object
        """
        # Analyze steps to create nodes and connections
        nodes, connections = self.analyzer.analyze(steps)

        # Create flowchart
        flowchart = Flowchart(
            nodes=nodes,
            connections=connections,
            title=title
        )

        # Optimize layout
        self._optimize_layout(flowchart)

        return flowchart

    def _optimize_layout(self, flowchart: Flowchart) -> None:
        """
        Calculate optimal node positions for layout.

        Args:
            flowchart: Flowchart to optimize
        """
        grouped_nodes = [
            node for node in flowchart.nodes
            if getattr(node, "group", None) and node.id not in {"START", "END"}
        ]
        if len({str(node.group) for node in grouped_nodes}) >= 2:
            self._optimize_grouped_layout(flowchart)
            return

        # Simple hierarchical layout
        # Group nodes by level (distance from start)
        levels = self._calculate_levels(flowchart)

        # Assign positions based on levels
        x_spacing = 200
        y_spacing = 100

        level_counts: Dict[int, int] = {}

        for node in flowchart.nodes:
            level = levels.get(node.id, 0)

            # Count nodes at this level
            if level not in level_counts:
                level_counts[level] = 0

            x = level_counts[level] * x_spacing
            y = level * y_spacing

            node.position = (x, y)
            level_counts[level] += 1

    def _optimize_grouped_layout(self, flowchart: Flowchart) -> None:
        group_order: List[str] = []
        group_nodes: Dict[str, List] = {}
        ungrouped: List = []

        for node in flowchart.nodes:
            group_name = getattr(node, "group", None)
            if group_name and node.id not in {"START", "END"}:
                group_key = str(group_name)
                if group_key not in group_nodes:
                    group_nodes[group_key] = []
                    group_order.append(group_key)
                group_nodes[group_key].append(node)
            else:
                ungrouped.append(node)

        row_spacing = 240
        col_spacing = 250
        intra_row_spacing = 110

        for row_index, group_name in enumerate(group_order):
            y = row_index * row_spacing
            x = 0
            for index, node in enumerate(group_nodes[group_name]):
                if index > 0:
                    x += intra_row_spacing
                node.position = (y, x)
                x += col_spacing

        if group_order:
            first_group_y = 0
            last_group_y = (len(group_order) - 1) * row_spacing
        else:
            first_group_y = 0
            last_group_y = 0

        for node in ungrouped:
            if node.id == "START":
                node.position = (first_group_y - 120, 0)
            elif node.id == "END":
                node.position = (last_group_y + 120, col_spacing * 2)
            elif node.position is None:
                node.position = (last_group_y + 120, col_spacing)

    def _calculate_levels(self, flowchart: Flowchart) -> Dict[str, int]:
        """
        Calculate hierarchical level for each node.

        Args:
            flowchart: Flowchart to analyze

        Returns:
            Dictionary mapping node ID to level
        """
        levels = {}

        # Find start node
        start_nodes = [n for n in flowchart.nodes if "START" in n.id or "start" in n.label.lower()]
        if not start_nodes:
            # No explicit start, use first node
            if flowchart.nodes:
                start_nodes = [flowchart.nodes[0]]

        if not start_nodes:
            return levels

        # BFS to assign levels
        queue = [(start_nodes[0].id, 0)]
        visited = set()

        while queue:
            node_id, level = queue.pop(0)

            if node_id in visited:
                continue

            visited.add(node_id)
            levels[node_id] = level

            # Find outgoing connections
            for conn in flowchart.connections:
                if conn.from_node == node_id and conn.to_node not in visited:
                    queue.append((conn.to_node, level + 1))

        return levels
