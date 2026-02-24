"""Semantic analysis of parsed workflow steps.

Phase 2: Loop detection, cross-reference handling, confidence propagation,
and decision branch reconnection.
"""

import re
from typing import List, Dict, Tuple, Optional, Set
from src.models import WorkflowStep, FlowchartNode, Connection, NodeType, ConnectionType


class WorkflowAnalyzer:
    """Analyze workflow steps and build flowchart structure."""

    LOOP_BACK_PATTERNS = [
        re.compile(r'(?:return|go back|repeat from)\s+(?:to\s+)?step\s+(\d+)', re.IGNORECASE),
        re.compile(r'(?:loop|repeat)\s+(?:back\s+)?(?:to\s+)?step\s+(\d+)', re.IGNORECASE),
        re.compile(r'(?:restart|resume)\s+(?:at|from)\s+step\s+(\d+)', re.IGNORECASE),
    ]

    CROSSREF_PATTERNS = [
        re.compile(r'(?:see|refer to|per|follow|as described in)\s+(?:section|procedure|process)\s+[\w.]+', re.IGNORECASE),
        re.compile(r'(?:using|per|follow)\s+(?:method|protocol|guideline)\s+[\w.]+', re.IGNORECASE),
    ]

    def __init__(self):
        self.node_counter = 0

    def analyze(self, steps: List[WorkflowStep]) -> Tuple[List[FlowchartNode], List[Connection]]:
        """
        Analyze workflow steps and create flowchart nodes and connections.

        Returns:
            Tuple of (nodes, connections)
        """
        nodes = []
        connections = []
        step_id_map: Dict[int, str] = {}  # step_number -> node_id
        decision_stack: List[str] = []     # track open decisions for reconnection
        branch_endpoints: List[str] = []   # endpoints of decision branches

        # Ensure start node
        if not steps or steps[0].node_type != NodeType.TERMINATOR:
            start_node = FlowchartNode(
                id="START",
                node_type=NodeType.TERMINATOR,
                label="Start",
                original_text="Start",
                confidence=1.0
            )
            nodes.append(start_node)
            prev_node_id = "START"
        else:
            prev_node_id = None

        for i, step in enumerate(steps):
            node_id = self._generate_node_id(step, i)

            # Check for cross-references -> override to PREDEFINED
            effective_type = step.node_type or NodeType.PROCESS
            confidence = step.confidence if hasattr(step, 'confidence') else 1.0
            alternatives = step.alternatives if hasattr(step, 'alternatives') else []

            if self._is_crossref(step.text):
                effective_type = NodeType.PREDEFINED
                confidence = max(confidence, 0.85)
                if NodeType.PROCESS not in alternatives:
                    alternatives = [NodeType.PROCESS] + list(alternatives)

            # Check for loop-back reference
            loop_target = self._detect_loop_target(step.text)

            # Create node
            node = FlowchartNode(
                id=node_id,
                node_type=effective_type,
                label=self._create_node_label(step),
                original_text=step.text,
                confidence=confidence,
                alternatives=alternatives
            )
            nodes.append(node)

            # Track step number -> node ID for loop-back
            if step.step_number:
                step_id_map[step.step_number] = node_id

            # Reconnect from dangling branch endpoints
            if branch_endpoints and prev_node_id is None:
                for ep in branch_endpoints:
                    connections.append(Connection(
                        from_node=ep,
                        to_node=node_id,
                        connection_type=ConnectionType.NORMAL
                    ))
                branch_endpoints = []
                prev_node_id = None  # Already connected via branch endpoints
            elif prev_node_id:
                connections.append(Connection(
                    from_node=prev_node_id,
                    to_node=node_id,
                    connection_type=ConnectionType.NORMAL
                ))

            # Handle loop-back: create connection back to target step
            if loop_target and loop_target in step_id_map:
                target_id = step_id_map[loop_target]
                connections.append(Connection(
                    from_node=node_id,
                    to_node=target_id,
                    label="Loop back",
                    connection_type=ConnectionType.LOOP
                ))
                # After a loop-back, flow may continue or may not
                # Don't set prev_node_id so next step connects fresh
                prev_node_id = node_id

            # Handle decision branches
            elif step.is_decision and step.branches:
                decision_stack.append(node_id)
                local_endpoints = []

                for j, branch_text in enumerate(step.branches):
                    branch_id = f"{node_id}_BRANCH_{j}"
                    branch_label = self._extract_branch_label(branch_text)

                    branch_node_type = NodeType.PROCESS
                    if "end" in branch_text.lower() or "stop" in branch_text.lower():
                        branch_node_type = NodeType.TERMINATOR

                    branch_node = FlowchartNode(
                        id=branch_id,
                        node_type=branch_node_type,
                        label=branch_label,
                        original_text=branch_text,
                        confidence=confidence * 0.9,
                        alternatives=[]
                    )
                    nodes.append(branch_node)

                    conn_label = "Yes" if j == 0 else "No"
                    conn_type = ConnectionType.YES if j == 0 else ConnectionType.NO
                    connections.append(Connection(
                        from_node=node_id,
                        to_node=branch_id,
                        label=conn_label,
                        connection_type=conn_type
                    ))

                    # Check if branch loops back
                    branch_loop = self._detect_loop_target(branch_text)
                    if branch_loop and branch_loop in step_id_map:
                        connections.append(Connection(
                            from_node=branch_id,
                            to_node=step_id_map[branch_loop],
                            label="Loop back",
                            connection_type=ConnectionType.LOOP
                        ))
                    elif branch_node_type != NodeType.TERMINATOR:
                        local_endpoints.append(branch_id)

                # Store branch endpoints for reconnection
                branch_endpoints = local_endpoints
                prev_node_id = None  # Branches handle connections
            else:
                prev_node_id = node_id

        # End node
        last_node = nodes[-1] if nodes else None
        if not last_node or last_node.node_type != NodeType.TERMINATOR:
            end_node = FlowchartNode(
                id="END",
                node_type=NodeType.TERMINATOR,
                label="End",
                original_text="End",
                confidence=1.0
            )
            nodes.append(end_node)

            # Connect remaining endpoints
            if branch_endpoints:
                for ep in branch_endpoints:
                    connections.append(Connection(
                        from_node=ep,
                        to_node="END",
                        connection_type=ConnectionType.NORMAL
                    ))
            elif prev_node_id:
                connections.append(Connection(
                    from_node=prev_node_id,
                    to_node="END",
                    connection_type=ConnectionType.NORMAL
                ))

        return nodes, connections

    def _detect_loop_target(self, text: str) -> Optional[int]:
        """Detect if text contains a loop-back reference to a step number."""
        for pattern in self.LOOP_BACK_PATTERNS:
            match = pattern.search(text)
            if match:
                try:
                    return int(match.group(1))
                except (ValueError, IndexError):
                    pass
        # Check for generic loop indicators (no specific step)
        if re.search(r'\b(?:repeat|loop)\s+(?:the\s+)?(?:above|previous|process)\b', text, re.IGNORECASE):
            return None  # Generic loop, handled by is_loop flag
        return None

    def _is_crossref(self, text: str) -> bool:
        """Check if text contains a cross-reference to another procedure."""
        for pattern in self.CROSSREF_PATTERNS:
            if pattern.search(text):
                return True
        return False

    def _generate_node_id(self, step: WorkflowStep, index: int) -> str:
        """Generate unique node ID."""
        if step.node_type == NodeType.TERMINATOR:
            if "start" in step.text.lower():
                return "START"
            elif "end" in step.text.lower():
                return "END"
        if step.step_number:
            return f"STEP_{step.step_number}"
        else:
            return f"NODE_{index}"

    def _create_node_label(self, step: WorkflowStep) -> str:
        """Create concise node label from step text with step number."""
        # Handle terminator nodes (Start/End)
        if step.node_type == NodeType.TERMINATOR:
            if "start" in step.text.lower():
                return "Start"
            elif "end" in step.text.lower():
                return "End"
        
        # For decision nodes, add question mark if needed
        if step.is_decision:
            text = step.text
            if not text.endswith('?'):
                text += '?'
            # Prepend step number if available
            if step.step_number:
                return f"{step.step_number}. {text}"
            return text
        
        # For all other nodes, prepend step number if available
        if step.step_number:
            return f"{step.step_number}. {step.text}"
        
        return step.text

    def _extract_branch_label(self, branch_text: str) -> str:
        """Extract clean label from branch text."""
        text = branch_text.lower()
        for prefix in ['if yes:', 'if no:', 'yes:', 'no:', 'then:', 'else:', 'otherwise:']:
            text = text.replace(prefix, '')
        text = text.strip()
        if text:
            text = text[0].upper() + text[1:]
        return text
