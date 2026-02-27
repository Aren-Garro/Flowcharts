"""ISO 5807 compliance validator."""

from typing import Dict, List, Tuple

from src.models import ConnectionType, Flowchart, NodeType


class ISO5807Validator:
    """Validate flowcharts against ISO 5807 standards."""

    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def validate(self, flowchart: Flowchart) -> Tuple[bool, List[str], List[str]]:
        """
        Validate flowchart against ISO 5807 standards.

        Args:
            flowchart: Flowchart to validate

        Returns:
            Tuple of (is_valid, errors, warnings)
        """
        self.errors = []
        self.warnings = []

        # Run validation checks
        self._validate_structure(flowchart)
        self._validate_symbols(flowchart)
        self._validate_connections(flowchart)
        self._validate_decisions(flowchart)
        self._validate_terminators(flowchart)
        self._validate_labels(flowchart)

        is_valid = len(self.errors) == 0
        return is_valid, self.errors, self.warnings

    def _validate_structure(self, flowchart: Flowchart) -> None:
        """Validate basic flowchart structure."""
        # Check minimum requirements
        if not flowchart.nodes:
            self.errors.append("Flowchart has no nodes")
            return

        if len(flowchart.nodes) < 2:
            self.warnings.append("Flowchart has fewer than 2 nodes (start + end minimum)")

        # Use built-in validation
        is_valid, validation_errors = flowchart.validate_structure()
        if not is_valid:
            self.errors.extend(validation_errors)

    def _validate_symbols(self, flowchart: Flowchart) -> None:
        """Validate ISO 5807 symbol usage."""
        # Check that only valid node types are used
        valid_types = set(NodeType.__members__.values())

        for node in flowchart.nodes:
            if node.node_type not in valid_types:
                self.errors.append(f"Invalid node type '{node.node_type}' for node '{node.id}'")

    def _validate_connections(self, flowchart: Flowchart) -> None:
        """Validate connections between nodes."""
        node_ids = {n.id for n in flowchart.nodes}

        for conn in flowchart.connections:
            # Check that referenced nodes exist
            if conn.from_node not in node_ids:
                self.errors.append(f"Connection references non-existent source node: {conn.from_node}")

            if conn.to_node not in node_ids:
                self.errors.append(f"Connection references non-existent target node: {conn.to_node}")

        # Check for cycles (except intentional loops)
        if self._has_invalid_cycles(flowchart):
            self.warnings.append("Flowchart contains cycles - verify loops are intentional")

    def _collect_yes_no_targets(
        self,
        outgoing: List,
    ) -> Tuple[set, set]:
        yes_targets = {
            c.to_node
            for c in outgoing
            if c.connection_type == ConnectionType.YES
            or (c.label and "yes" in c.label.lower())
        }
        no_targets = {
            c.to_node
            for c in outgoing
            if c.connection_type == ConnectionType.NO
            or (c.label and "no" in c.label.lower())
        }
        return yes_targets, no_targets

    def _validate_decision_target_convergence(
        self,
        node_id: str,
        common_targets: set,
        node_map: Dict[str, object],
    ) -> None:
        if not common_targets:
            return

        non_terminator_common = []
        for target_id in common_targets:
            target_node = node_map.get(target_id)
            if target_node and target_node.node_type != NodeType.TERMINATOR:
                non_terminator_common.append(target_id)

        if non_terminator_common:
            self.errors.append(
                f"Decision node '{node_id}': Yes/No branches both lead "
                f"to same node(s): {', '.join(non_terminator_common)}. "
                "Decision branches must lead to different nodes."
            )
            return

        self.warnings.append(
            f"Decision node '{node_id}': Both branches lead to END. "
            "Verify this is intentional (e.g., final validation step)."
        )

    def _validate_single_decision_node(
        self,
        node,
        flowchart: Flowchart,
        node_map: Dict[str, object],
    ) -> None:
        outgoing = [c for c in flowchart.connections if c.from_node == node.id]

        if len(outgoing) < 2:
            self.errors.append(
                f"Decision node '{node.id}' has {len(outgoing)} branch(es), expected at least 2"
            )
        elif len(outgoing) > 3:
            self.warnings.append(
                f"Decision node '{node.id}' has {len(outgoing)} branches - consider simplifying"
            )

        unlabeled = [c for c in outgoing if not c.label]
        if unlabeled:
            self.warnings.append(
                f"Decision node '{node.id}' has {len(unlabeled)} unlabeled branch(es)"
            )

        yes_targets, no_targets = self._collect_yes_no_targets(outgoing)
        if yes_targets and no_targets:
            self._validate_decision_target_convergence(
                node.id,
                yes_targets & no_targets,
                node_map,
            )

    def _validate_decisions(self, flowchart: Flowchart) -> None:
        """Validate decision nodes have proper branches."""
        node_map = {n.id: n for n in flowchart.nodes}

        for node in flowchart.nodes:
            if node.node_type != NodeType.DECISION:
                continue
            self._validate_single_decision_node(node, flowchart, node_map)

    def _validate_terminators(self, flowchart: Flowchart) -> None:
        """Validate terminator (start/end) nodes."""
        terminators = [n for n in flowchart.nodes if n.node_type == NodeType.TERMINATOR]

        if not terminators:
            self.errors.append("Flowchart has no terminator nodes (start/end)")
            return

        # Check for start node
        start_nodes = [n for n in terminators if "start" in n.label.lower() or "begin" in n.label.lower()]
        if not start_nodes:
            self.warnings.append("No explicit START terminator found")
        elif len(start_nodes) > 1:
            self.errors.append(f"Multiple START nodes found: {len(start_nodes)}")

        # Check for end node
        end_nodes = [
            n
            for n in terminators
            if "end" in n.label.lower()
            or "finish" in n.label.lower()
            or "stop" in n.label.lower()
        ]
        if not end_nodes:
            self.warnings.append("No explicit END terminator found")

        # Start node should have no incoming connections (except from itself in edge cases)
        if start_nodes:
            start_id = start_nodes[0].id
            incoming = [c for c in flowchart.connections if c.to_node == start_id and c.from_node != start_id]
            if incoming:
                self.errors.append(
                    f"START node '{start_id}' has {len(incoming)} incoming connection(s) - "
                    "START nodes should only have outgoing connections"
                )

        # End nodes should have no outgoing connections
        for end_node in end_nodes:
            outgoing = [c for c in flowchart.connections if c.from_node == end_node.id]
            if outgoing:
                self.errors.append(f"END node '{end_node.id}' has {len(outgoing)} outgoing connection(s)")

    def _validate_labels(self, flowchart: Flowchart) -> None:
        """Validate node labels are clear and concise."""
        max_label_length = 100

        for node in flowchart.nodes:
            if not node.label:
                self.errors.append(f"Node '{node.id}' has no label")
            elif len(node.label) > max_label_length:
                self.warnings.append(
                    f"Node '{node.id}' label is very long ({len(node.label)} chars) - consider shortening"
                )

    def _build_graph(self, flowchart: Flowchart) -> Dict[str, List[str]]:
        graph: Dict[str, List[str]] = {node.id: [] for node in flowchart.nodes}
        for conn in flowchart.connections:
            if conn.from_node in graph:
                graph[conn.from_node].append(conn.to_node)
        return graph

    def _dfs_has_cycle(
        self,
        node_id: str,
        graph: Dict[str, List[str]],
        visited: set,
        rec_stack: set,
    ) -> bool:
        visited.add(node_id)
        rec_stack.add(node_id)

        for neighbor in graph.get(node_id, []):
            if neighbor not in visited:
                if self._dfs_has_cycle(neighbor, graph, visited, rec_stack):
                    return True
            elif neighbor in rec_stack:
                return True

        rec_stack.remove(node_id)
        return False

    def _has_invalid_cycles(self, flowchart: Flowchart) -> bool:
        """Check for cycles in the flowchart graph."""
        graph = self._build_graph(flowchart)
        visited = set()
        rec_stack = set()

        for node_id in graph:
            if node_id not in visited:
                if self._dfs_has_cycle(node_id, graph, visited, rec_stack):
                    return True

        return False
