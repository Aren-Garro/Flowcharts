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
        re.compile(r'retry\s+(?:from\s+)?step\s+(\d+)', re.IGNORECASE),
        re.compile(r'redo\s+(?:from\s+)?step\s+(\d+)', re.IGNORECASE),
    ]
    
    SKIP_PATTERNS = [
        re.compile(r'(?:skip|jump|go)\s+(?:to\s+)?step\s+(\d+)', re.IGNORECASE),
        re.compile(r'continue\s+to\s+step\s+(\d+)', re.IGNORECASE),
        re.compile(r'proceed\s+(?:to\s+)?step\s+(\d+)', re.IGNORECASE),
    ]

    CROSSREF_PATTERNS = [
        re.compile(r'(?:see|refer to|per|follow|as described in)\s+(?:section|procedure|process)\s+[\w.]+', re.IGNORECASE),
        re.compile(r'(?:using|per|follow)\s+(?:method|protocol|guideline)\s+[\w.]+', re.IGNORECASE),
    ]

    def __init__(self):
        self.node_counter = 0

    def _is_terminator_text(self, text: str) -> bool:
        """Check if text is a pure start/end terminator."""
        t = text.strip().lower()
        return t in ('start', 'begin', 'end', 'finish', 'stop', 'done', 'terminate', 'complete')

    def analyze(self, steps: List[WorkflowStep]) -> Tuple[List[FlowchartNode], List[Connection]]:
        """
        Analyze workflow steps and create flowchart nodes and connections.

        Returns:
            Tuple of (nodes, connections)
        """
        nodes = []
        connections = []
        step_id_map: Dict[int, str] = {}  # step_number -> node_id
        branch_endpoints: List[str] = []   # endpoints of decision branches

        # Check if first step is a Start terminator
        has_start_step = (steps and self._is_terminator_text(steps[0].text))
        # Check if last step is an End terminator
        has_end_step = (steps and self._is_terminator_text(steps[-1].text))

        # Create auto Start node ONLY if first step isn't already Start
        if has_start_step:
            # Use the first step as the start node directly
            start_node = FlowchartNode(
                id="START",
                node_type=NodeType.TERMINATOR,
                label="Start",
                original_text="Start",
                confidence=1.0
            )
            nodes.append(start_node)
            if steps[0].step_number:
                step_id_map[steps[0].step_number] = "START"
            prev_node_id = "START"
            # Skip the first step since we consumed it
            steps = steps[1:]
        else:
            # No start step found, auto-create one
            start_node = FlowchartNode(
                id="START",
                node_type=NodeType.TERMINATOR,
                label="Start",
                original_text="Start",
                confidence=1.0
            )
            nodes.append(start_node)
            prev_node_id = "START"

        # If last step is End, we'll handle it specially
        if has_end_step:
            # Remove last step from processing, we'll add End node at the end
            end_step = steps[-1]
            steps = steps[:-1]

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

            # Check for loop-back reference in main step text
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

            # Track step number -> node ID for loop-back and skip references
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
                prev_node_id = node_id

            # Handle decision branches
            elif step.is_decision and step.branches:
                local_endpoints = []

                for j, branch_text in enumerate(step.branches):
                    conn_label = "Yes" if j == 0 else "No"
                    conn_type = ConnectionType.YES if j == 0 else ConnectionType.NO
                    
                    # Check if branch contains a skip/goto instruction
                    skip_target = self._detect_skip_target(branch_text)
                    # Check if branch contains a loop-back/retry instruction
                    loop_back_target = self._detect_loop_target(branch_text)
                    # Check if branch is just "Continue"
                    is_continue = self._is_continue_branch(branch_text)
                    
                    if skip_target:
                        # Direct forward jump to target step - NO intermediate node
                        target_node_id = step_id_map.get(skip_target, f"STEP_{skip_target}")
                        connections.append(Connection(
                            from_node=node_id,
                            to_node=target_node_id,
                            label=conn_label,
                            connection_type=conn_type
                        ))
                    elif loop_back_target:
                        # Loop back to earlier step (retry pattern) - NO intermediate node
                        target_node_id = step_id_map.get(loop_back_target, f"STEP_{loop_back_target}")
                        connections.append(Connection(
                            from_node=node_id,
                            to_node=target_node_id,
                            label=conn_label,
                            connection_type=ConnectionType.LOOP
                        ))
                    elif is_continue:
                        # "Continue" means flow continues to next step - NO intermediate node
                        # Add decision node itself to endpoints for reconnection to next step
                        local_endpoints.append(node_id)
                    else:
                        # Branch has actual action text - create intermediate node
                        branch_label = self._extract_branch_label(branch_text)
                        
                        # Skip creating node if label is empty or just punctuation
                        if not branch_label or branch_label in ('Continue', 'Yes', 'No'):
                            local_endpoints.append(node_id)
                            continue
                        
                        branch_id = f"{node_id}_BRANCH_{j}"
                        branch_node_type = NodeType.PROCESS
                        if "end" in branch_text.lower() or "stop" in branch_text.lower():
                            branch_node_type = NodeType.TERMINATOR
                        elif "setup complete" in branch_text.lower():
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

                        connections.append(Connection(
                            from_node=node_id,
                            to_node=branch_id,
                            label=conn_label,
                            connection_type=conn_type
                        ))

                        if branch_node_type != NodeType.TERMINATOR:
                            local_endpoints.append(branch_id)

                # Store branch endpoints for reconnection
                branch_endpoints = local_endpoints
                prev_node_id = None  # Branches handle connections
            else:
                prev_node_id = node_id

        # End node
        end_node = FlowchartNode(
            id="END",
            node_type=NodeType.TERMINATOR,
            label="End",
            original_text="End",
            confidence=1.0
        )
        nodes.append(end_node)
        
        # Track end step number if it had one
        if has_end_step and end_step.step_number:
            step_id_map[end_step.step_number] = "END"

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
        """Detect if text contains a loop-back/retry reference to a step number."""
        for pattern in self.LOOP_BACK_PATTERNS:
            match = pattern.search(text)
            if match:
                try:
                    return int(match.group(1))
                except (ValueError, IndexError):
                    pass
        return None
    
    def _detect_skip_target(self, text: str) -> Optional[int]:
        """Detect if text contains a skip/goto instruction to a step number."""
        # Don't match if it's a retry/loop-back
        if self._detect_loop_target(text):
            return None
        for pattern in self.SKIP_PATTERNS:
            match = pattern.search(text)
            if match:
                try:
                    return int(match.group(1))
                except (ValueError, IndexError):
                    pass
        return None
    
    def _is_continue_branch(self, text: str) -> bool:
        """Check if branch text is just 'Continue' (flow to next step)."""
        text_lower = text.strip().lower()
        
        # Remove branch prefixes
        for prefix in ['if yes:', 'if no:', 'yes:', 'no:', 'then:', 'else:', 'otherwise:']:
            text_lower = text_lower.replace(prefix, '').strip()
        
        # Check if remaining text is a continue keyword
        return text_lower in ('continue', 'proceed', 'next', 'go on', '')

    def _is_crossref(self, text: str) -> bool:
        """Check if text contains a cross-reference to another procedure."""
        for pattern in self.CROSSREF_PATTERNS:
            if pattern.search(text):
                return True
        return False

    def _generate_node_id(self, step: WorkflowStep, index: int) -> str:
        """Generate unique node ID."""
        if step.step_number:
            return f"STEP_{step.step_number}"
        else:
            return f"NODE_{index}"

    def _create_node_label(self, step: WorkflowStep) -> str:
        """Create concise node label from step text with step number."""
        # For decision nodes, add question mark if needed
        if step.is_decision:
            text = step.text
            if not text.endswith('?'):
                text += '?'
            if step.step_number:
                return f"{step.step_number}. {text}"
            return text
        
        # For all other nodes, prepend step number if available
        if step.step_number:
            return f"{step.step_number}. {step.text}"
        
        return step.text

    def _extract_branch_label(self, branch_text: str) -> str:
        """Extract clean label from branch text, removing skip/goto/retry/continue instructions."""
        text = branch_text
        text_lower = text.lower()
        
        # Remove branch prefixes first
        for prefix in ['if yes:', 'if no:', 'yes:', 'no:', 'then:', 'else:', 'otherwise:']:
            if text_lower.startswith(prefix):
                text = text[len(prefix):]
                text_lower = text.lower()
        
        # Remove skip/goto instructions
        text = re.sub(r'(?:skip|jump|go)\s+(?:to\s+)?step\s+\d+', '', text, flags=re.IGNORECASE)
        # Remove continue to step instructions
        text = re.sub(r'continue\s+to\s+step\s+\d+', '', text, flags=re.IGNORECASE)
        # Remove retry/redo instructions
        text = re.sub(r'(?:verify\s+[^\s]+\s+and\s+)?(?:retry|redo)\s+(?:from\s+)?step\s+\d+', '', text, flags=re.IGNORECASE)
        # Remove standalone 'continue' or 'proceed'
        if text.strip().lower() in ('continue', 'proceed', 'next', 'go on'):
            return ''
        
        text = text.strip()
        # Clean up leading 'and' or commas
        text = re.sub(r'^[,\s]+', '', text)
        text = re.sub(r'^and\s+', '', text, flags=re.IGNORECASE)
        
        if text:
            text = text[0].upper() + text[1:]
        return text
