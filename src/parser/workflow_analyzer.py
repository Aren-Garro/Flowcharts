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
    
    TERMINATOR_PHRASES = [
        'setup complete', 'process complete', 'complete', 'done',
        'finished', 'end', 'stop', 'terminate', 'exit'
    ]

    def __init__(self):
        self.node_counter = 0

    def _is_terminator_text(self, text: str) -> bool:
        """Check if text is a pure start/end terminator."""
        t = text.strip().lower()
        return t in ('start', 'begin', 'end', 'finish', 'stop', 'done',
                      'terminate', 'complete', 'setup complete')

    def _classify_branch(self, branch_text: str) -> dict:
        """
        Classify a single branch into its type and extract metadata.
        
        Returns dict with:
            label: 'Yes' or 'No' (detected from text prefix)
            type: 'skip' | 'retry' | 'continue' | 'terminator' | 'action'
            target: step number (for skip/retry) or None
            action_text: cleaned action text (for action/terminator branches)
        """
        text = branch_text.strip()
        text_lower = text.lower()
        
        # Detect Yes/No from the branch prefix
        label = None
        if re.match(r'^if\s+yes\b', text_lower):
            label = 'Yes'
        elif re.match(r'^if\s+no\b', text_lower):
            label = 'No'
        elif re.match(r'^yes\b', text_lower):
            label = 'Yes'
        elif re.match(r'^no\b', text_lower):
            label = 'No'
        
        # Strip prefix to get the action part
        action_part = re.sub(r'^(?:if\s+)?(?:yes|no)\s*[:\-]?\s*', '', text, flags=re.IGNORECASE).strip()
        
        # Check for skip/goto
        skip_target = self._detect_skip_target(action_part)
        if skip_target:
            return {'label': label, 'type': 'skip', 'target': skip_target, 'action_text': action_part}
        
        # Check for retry/loop-back
        loop_target = self._detect_loop_target(action_part)
        if loop_target:
            return {'label': label, 'type': 'retry', 'target': loop_target, 'action_text': action_part}
        
        # Check for continue
        if action_part.lower() in ('continue', 'proceed', 'next', 'go on', ''):
            return {'label': label, 'type': 'continue', 'target': None, 'action_text': ''}
        
        # Check for terminator
        if any(phrase in action_part.lower() for phrase in self.TERMINATOR_PHRASES):
            return {'label': label, 'type': 'terminator', 'target': None, 'action_text': action_part}
        
        # Regular action
        return {'label': label, 'type': 'action', 'target': None, 'action_text': action_part}

    def analyze(self, steps: List[WorkflowStep]) -> Tuple[List[FlowchartNode], List[Connection]]:
        """
        Analyze workflow steps and create flowchart nodes and connections.
        
        ISO 5807 principles:
        - Decisions have exactly 2 exits: Yes and No
        - Skip/Continue = direct arrow to target step (no intermediate node)
        - Retry = loop-back arrow to target step (no intermediate node)
        - Terminators connect to END
        - All decision arrows are labeled Yes or No
        """
        nodes = []
        connections = []
        step_id_map: Dict[int, str] = {}  # step_number -> node_id
        branch_endpoints: List[Tuple[str, str]] = []  # (node_id, label) for reconnection

        # Detect start/end terminators in source steps
        has_start_step = (steps and self._is_terminator_text(steps[0].text))
        has_end_step = (steps and self._is_terminator_text(steps[-1].text))

        # START node
        start_node = FlowchartNode(
            id="START",
            node_type=NodeType.TERMINATOR,
            label="Start",
            original_text="Start",
            confidence=1.0
        )
        nodes.append(start_node)
        if has_start_step and steps[0].step_number:
            step_id_map[steps[0].step_number] = "START"
        prev_node_id = "START"
        
        # Remove start/end from processing
        if has_start_step:
            steps = steps[1:]
        if has_end_step:
            end_step = steps[-1]
            steps = steps[:-1]

        for i, step in enumerate(steps):
            node_id = self._generate_node_id(step, i)

            # Determine node type
            effective_type = step.node_type or NodeType.PROCESS
            confidence = step.confidence if hasattr(step, 'confidence') else 1.0
            alternatives = step.alternatives if hasattr(step, 'alternatives') else []

            if self._is_crossref(step.text):
                effective_type = NodeType.PREDEFINED
                confidence = max(confidence, 0.85)

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

            if step.step_number:
                step_id_map[step.step_number] = node_id

            # Connect from previous node or branch endpoints
            if branch_endpoints and prev_node_id is None:
                for ep_id, ep_label in branch_endpoints:
                    conn = Connection(
                        from_node=ep_id,
                        to_node=node_id,
                        connection_type=ConnectionType.NORMAL
                    )
                    if ep_label:
                        conn.label = ep_label
                    connections.append(conn)
                branch_endpoints = []
            elif prev_node_id:
                connections.append(Connection(
                    from_node=prev_node_id,
                    to_node=node_id,
                    connection_type=ConnectionType.NORMAL
                ))

            # === DECISION HANDLING ===
            if step.is_decision and step.branches:
                local_endpoints = []
                
                for j, branch_text in enumerate(step.branches):
                    info = self._classify_branch(branch_text)
                    
                    # Determine label: use detected label, or fall back to index
                    conn_label = info['label'] or ('Yes' if j == 0 else 'No')
                    conn_type = ConnectionType.YES if conn_label == 'Yes' else ConnectionType.NO
                    
                    if info['type'] == 'skip':
                        # Direct arrow to target step
                        target_id = step_id_map.get(info['target'], f"STEP_{info['target']}")
                        connections.append(Connection(
                            from_node=node_id,
                            to_node=target_id,
                            label=conn_label,
                            connection_type=conn_type
                        ))
                    
                    elif info['type'] == 'retry':
                        # Loop-back arrow to target step
                        target_id = step_id_map.get(info['target'], f"STEP_{info['target']}")
                        connections.append(Connection(
                            from_node=node_id,
                            to_node=target_id,
                            label=conn_label,
                            connection_type=ConnectionType.LOOP
                        ))
                    
                    elif info['type'] == 'continue':
                        # Flow continues to next step - add to endpoints with label
                        local_endpoints.append((node_id, conn_label))
                    
                    elif info['type'] == 'terminator':
                        # Create terminator node (e.g. "Setup complete")
                        branch_id = f"{node_id}_TERM"
                        term_label = info['action_text'] or 'Complete'
                        # Capitalize first letter
                        term_label = term_label[0].upper() + term_label[1:] if term_label else 'Complete'
                        
                        term_node = FlowchartNode(
                            id=branch_id,
                            node_type=NodeType.TERMINATOR,
                            label=term_label,
                            original_text=branch_text,
                            confidence=1.0,
                            alternatives=[]
                        )
                        nodes.append(term_node)
                        connections.append(Connection(
                            from_node=node_id,
                            to_node=branch_id,
                            label=conn_label,
                            connection_type=conn_type
                        ))
                        # Terminator connects to END (handled at the end)
                    
                    elif info['type'] == 'action':
                        # Create action node with meaningful text
                        branch_id = f"{node_id}_ACTION_{j}"
                        action_label = info['action_text']
                        action_label = action_label[0].upper() + action_label[1:] if action_label else 'Process'
                        
                        action_node = FlowchartNode(
                            id=branch_id,
                            node_type=NodeType.PROCESS,
                            label=action_label,
                            original_text=branch_text,
                            confidence=confidence * 0.9,
                            alternatives=[]
                        )
                        nodes.append(action_node)
                        connections.append(Connection(
                            from_node=node_id,
                            to_node=branch_id,
                            label=conn_label,
                            connection_type=conn_type
                        ))
                        local_endpoints.append((branch_id, None))

                branch_endpoints = local_endpoints
                prev_node_id = None  # Branches handle connections
            else:
                prev_node_id = node_id

        # END node
        end_node = FlowchartNode(
            id="END",
            node_type=NodeType.TERMINATOR,
            label="End",
            original_text="End",
            confidence=1.0
        )
        nodes.append(end_node)
        
        if has_end_step and end_step.step_number:
            step_id_map[end_step.step_number] = "END"

        # Connect remaining endpoints to END
        if branch_endpoints:
            for ep_id, ep_label in branch_endpoints:
                conn = Connection(
                    from_node=ep_id,
                    to_node="END",
                    connection_type=ConnectionType.NORMAL
                )
                if ep_label:
                    conn.label = ep_label
                connections.append(conn)
        elif prev_node_id:
            connections.append(Connection(
                from_node=prev_node_id,
                to_node="END",
                connection_type=ConnectionType.NORMAL
            ))
        
        # Connect all inline terminators to END
        for node in nodes:
            if node.node_type == NodeType.TERMINATOR and node.id not in ("START", "END"):
                has_outgoing = any(c.from_node == node.id for c in connections)
                if not has_outgoing:
                    connections.append(Connection(
                        from_node=node.id,
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
        return f"NODE_{index}"

    def _create_node_label(self, step: WorkflowStep) -> str:
        """Create concise node label from step text with step number."""
        if step.is_decision:
            text = step.text
            if not text.endswith('?'):
                text += '?'
            if step.step_number:
                return f"{step.step_number}. {text}"
            return text
        
        if step.step_number:
            return f"{step.step_number}. {step.text}"
        
        return step.text
