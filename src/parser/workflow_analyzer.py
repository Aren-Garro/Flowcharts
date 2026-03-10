"""Semantic analysis of parsed workflow steps.

Phase 2: Loop detection, cross-reference handling, confidence propagation,
and decision branch reconnection.

ISO 5807 principles enforced:
- Decisions have exactly 2 exits: Yes and No
- Skip/Continue = direct arrow to target (no intermediate node)
- Retry = loop-back arrow to target (no intermediate node)
- Continue = flow to next step (no intermediate node)
- Terminators = rounded rectangle connecting to END
- All decision arrows labeled Yes or No

Bug fix: Prevent END nodes from having outgoing connections
Bug fix: Handle empty or single-step workflows gracefully
Bug fix: Prevent Yes/No branches from connecting to same node
"""

import re
from typing import Dict, List, Optional, Tuple

from src.models import Connection, ConnectionType, FlowchartNode, NodeType, WorkflowStep
from src.parser.patterns import WorkflowPatterns


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
        re.compile(r'go\s+to\s+end', re.IGNORECASE),
        # Ultimate state transition regex: matches anything after 'to' or 'into'
        re.compile(r'(?:move|change|update|proceed)\s+(?:the\s+)?(?:ticket|deal|item|record|status|workflow)\s+(?:to|into)\s+[\'"]?(.*?)[\'"]?$', re.IGNORECASE)
    ]

    CROSSREF_PATTERNS = [
        re.compile(
            r'(?:see|refer to|per|follow|as described in)\s+(?:section|procedure|process)\s+[\w.]+',
            re.IGNORECASE,
        ),
        re.compile(
            r'(?:using|per|follow)\s+(?:method|protocol|guideline)\s+[\w.]+',
            re.IGNORECASE,
        ),
    ]

    TERMINATOR_PHRASES = [
        'setup complete', 'process complete', 'complete', 'done',
        'finished', 'end', 'stop', 'terminate', 'exit'
    ]

    def __init__(self):
        self.node_counter = 0

    # ── Helpers ──────────────────────────────────────────────────

    def _is_terminator_text(self, text: str) -> bool:
        t = text.strip().lower()
        return t in (
            'start',
            'begin',
            'end',
            'finish',
            'stop',
            'done',
            'terminate',
            'complete',
            'setup complete',
        )

    def _detect_loop_target(self, text: str) -> Optional[int]:
        for pattern in self.LOOP_BACK_PATTERNS:
            m = pattern.search(text)
            if m:
                try:
                    return int(m.group(1))
                except (ValueError, IndexError):
                    pass
        return None

    def _detect_skip_target(self, text: str):
        if re.search(r'go\s+to\s+end', text, re.IGNORECASE):
            return -1
        if self._detect_loop_target(text):
            return None
            
        for pattern in self.SKIP_PATTERNS:
            m = pattern.search(text)
            if m:
                val = m.group(1).strip()
                # If it's a number, return as integer. Otherwise, return the string!
                if val.isdigit():
                    return int(val)
                return val 
        return None

    def _is_crossref(self, text: str) -> bool:
        for pattern in self.CROSSREF_PATTERNS:
            if pattern.search(text):
                return True
        return False

    def _strip_branch_prefix(self, text: str) -> str:
        """Remove 'If yes:', 'If no:', 'Yes:', 'No:' prefixes."""
        return re.sub(
            r'^(?:if\s+)?(?:yes|no)\s*[:\-]?\s*',
            '', text, flags=re.IGNORECASE
        ).strip()

    def _detect_branch_label(self, text: str) -> str:
        """Detect Yes/No from the branch prefix text."""
        t = text.strip().lower()
        if re.match(r'^(?:if\s+)?yes\b', t):
            return 'Yes'
        if re.match(r'^(?:if\s+)?no\b', t):
            return 'No'
        return ''

    def _classify_branch(self, branch_text: str) -> dict:
        """Classify a branch and extract all metadata."""
        label = self._detect_branch_label(branch_text)
        action_part = self._strip_branch_prefix(branch_text)

        # Skip/goto?
        skip = self._detect_skip_target(action_part)
        if skip is not None:
            # -1 means "go to end"
            if skip == -1:
                return {'label': label, 'type': 'terminator', 'target': None, 'text': 'End'}
            return {'label': label, 'type': 'skip', 'target': skip, 'text': action_part}

        # Retry/loop-back?
        loop = self._detect_loop_target(action_part)
        if loop:
            return {'label': label, 'type': 'retry', 'target': loop, 'text': action_part}

        # Plain continue?
        if action_part.lower() in ('continue', 'proceed', 'next', 'go on', ''):
            return {'label': label, 'type': 'continue', 'target': None, 'text': ''}

        # Terminator phrase?
        if any(p in action_part.lower() for p in self.TERMINATOR_PHRASES):
            return {'label': label, 'type': 'terminator', 'target': None, 'text': action_part}

        # Action with text
        return {'label': label, 'type': 'action', 'target': None, 'text': action_part}

    def _generate_node_id(self, step: WorkflowStep, index: int) -> str:
        if step.step_number:
            return f"STEP_{step.step_number}"
        return f"NODE_{index}"

    def _create_node_label(self, step: WorkflowStep) -> str:
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

    # ── Main analysis ───────────────────────────────────────────

    def _prepare_branch_info(self, branches: List[str]) -> List[Tuple[dict, str, str, int]]:
        branch_info_list = []
        current_label = 'Yes'
        condition_count = 0
        
        for j, raw in enumerate(branches):
            info = self._classify_branch(raw)
            is_new_condition = bool(re.match(r'^(If\s+|Yes[:\s]|No[:\s]|True[:\s]|False[:\s])', raw, re.IGNORECASE))
            
            # When a new "If" condition starts, assign it a new branch path (Yes, then No)
            if is_new_condition:
                if info['label']:
                    current_label = info['label']
                else:
                    current_label = 'Yes' if condition_count == 0 else 'No'
                condition_count += 1
                
            branch_info_list.append((info, current_label, raw, j))

        # Filter out redundant 'continue' statements
        continue_indices = [j for info, _, _, j in branch_info_list if info["type"] == "continue"]
        if len(continue_indices) <= 1:
            return branch_info_list

        first_continue = continue_indices[0]
        normalized = []
        for info, label, raw, j in branch_info_list:
            if j in continue_indices and j != first_continue:
                normalized.append(
                    ({'label': label, 'type': 'action', 'target': None, 'text': 'Continue'}, label, raw, j)
                )
            else:
                normalized.append((info, label, raw, j))
                
        return normalized

    def _apply_branch_info(
        self,
        *,
        node_id: str,
        branch_info_list: List[Tuple[dict, str, str, int]],
        step_id_map: Dict[int, str],
        nodes: List[FlowchartNode],
        connections: List[Connection],
        confidence: float,
    ) -> List[Tuple[str, Optional[str]]]:
        from collections import defaultdict

        local_eps: List[Tuple[str, Optional[str]]] = []
        
        # 1. Group actions by their branch label (e.g., 'Yes' or 'No')
        groups = defaultdict(list)
        for item in branch_info_list:
            lbl = item[1]
            groups[lbl].append(item)

        # 2. Process each branch group as a sequential chain
        for lbl, items in groups.items():
            ctype = ConnectionType.YES if lbl == 'Yes' else ConnectionType.NO
            
            # Start the chain at the main decision node
            current_source = node_id
            current_label = lbl
            current_ctype = ctype
            
            last_endpoint = None

            for i, (info, _, raw, j) in enumerate(items):
                if info['type'] == 'skip':
                    target = info['target']
                    if isinstance(target, str):
                        # FIX: Create a LOCAL terminator node instead of a global string target
                        phase_id = f"PHASE_{target.upper().replace(' ', '_')}_{current_source}_{j}"
                        
                        nodes.append(FlowchartNode(
                            id=phase_id, 
                            node_type=NodeType.TERMINATOR,
                            label=f"Move to: {target}",
                            confidence=0.9,
                            group=next((n.group for n in nodes if n.id == node_id), None)
                        ))
                        
                        connections.append(Connection(
                            from_node=current_source, 
                            to_node=phase_id, 
                            label=current_label, 
                            connection_type=current_ctype
                        ))
                    else:
                        tid = step_id_map.get(target, f"STEP_{target}")
                        connections.append(Connection(from_node=current_source, to_node=tid, label=current_label, connection_type=current_ctype))
                    last_endpoint = None
                
                elif info['type'] == 'retry':
                    tid = step_id_map.get(info['target'], f"STEP_{info['target']}")
                    connections.append(
                        Connection(from_node=current_source, to_node=tid, label=current_label, connection_type=ConnectionType.LOOP)
                    )
                    last_endpoint = None
                
                elif info['type'] == 'continue':
                    last_endpoint = (current_source, current_label)
                
                elif info['type'] == 'terminator':
                    connections.append(Connection(from_node=current_source, to_node="END", label=current_label, connection_type=current_ctype))
                    last_endpoint = None
                
                elif info['type'] == 'action':
                    bid = f"{node_id}_ACTION_{j}"
                    alabel = info['text']
                    alabel = alabel[0].upper() + alabel[1:] if alabel else 'Process'
                    
                    nodes.append(
                        FlowchartNode(
                            id=bid,
                            node_type=NodeType.PROCESS,
                            label=alabel,
                            original_text=raw,
                            confidence=confidence * 0.9,
                            alternatives=[],
                            group=next((n.group for n in nodes if n.id == node_id), None)
                        )
                    )
                    # Connect to the previous node in this chain
                    connections.append(Connection(from_node=current_source, to_node=bid, label=current_label, connection_type=current_ctype))
                    
                    # Update variables so the NEXT action connects to THIS action
                    current_source = bid
                    current_label = None  # Only the first edge leaving the diamond gets the 'Yes'/'No' label
                    current_ctype = ConnectionType.NORMAL
                    last_endpoint = (bid, None)

            # 3. Only pass the VERY LAST node of the chain to connect to the next main flowchart step
            if last_endpoint:
                local_eps.append(last_endpoint)

        return local_eps

    def _build_empty_flowchart(self) -> Tuple[List[FlowchartNode], List[Connection]]:
        nodes = [
            FlowchartNode(id="START", node_type=NodeType.TERMINATOR, label="Start", original_text="Start", confidence=1.0),
            FlowchartNode(id="END", node_type=NodeType.TERMINATOR, label="End", original_text="End", confidence=1.0),
        ]
        connections = [Connection(from_node="START", to_node="END", connection_type=ConnectionType.NORMAL)]
        return nodes, connections

    def _connect_from_previous(
        self,
        *,
        node_id: str,
        prev_node_id: Optional[str],
        branch_endpoints: List[Tuple[str, Optional[str]]],
        connections: List[Connection],
    ) -> List[Tuple[str, Optional[str]]]:
        if branch_endpoints and prev_node_id is None:
            for endpoint_id, endpoint_label in branch_endpoints:
                connection = Connection(
                    from_node=endpoint_id,
                    to_node=node_id,
                    connection_type=ConnectionType.NORMAL,
                )
                if endpoint_label:
                    connection.label = endpoint_label
                connections.append(connection)
            return []

        if prev_node_id:
            connections.append(Connection(from_node=prev_node_id, to_node=node_id, connection_type=ConnectionType.NORMAL))
        return branch_endpoints

    def _connect_end(
        self,
        *,
        branch_endpoints: List[Tuple[str, Optional[str]]],
        prev_node_id: Optional[str],
        connections: List[Connection],
    ) -> None:
        if branch_endpoints:
            for endpoint_id, endpoint_label in branch_endpoints:
                connection = Connection(from_node=endpoint_id, to_node="END", connection_type=ConnectionType.NORMAL)
                if endpoint_label:
                    connection.label = endpoint_label
                connections.append(connection)
            return

        if prev_node_id:
            connections.append(Connection(from_node=prev_node_id, to_node="END", connection_type=ConnectionType.NORMAL))

    def analyze(self, steps: List[WorkflowStep]) -> Tuple[List[FlowchartNode], List[Connection]]:
        nodes: List[FlowchartNode] = []
        connections: List[Connection] = []
        step_id_map: Dict[int, str] = {}
        # Each endpoint is (node_id, optional_label)
        branch_endpoints: List[Tuple[str, Optional[str]]] = []

        # Handle empty workflow
        if not steps:
            return self._build_empty_flowchart()

        # ── Start / End detection ────────────────────────────────
        has_start = steps and self._is_terminator_text(steps[0].text)
        has_end = steps and len(steps) > 0 and self._is_terminator_text(steps[-1].text)

        nodes.append(FlowchartNode(
            id="START", node_type=NodeType.TERMINATOR,
            label="Start", original_text="Start", confidence=1.0
        ))
        if has_start and steps[0].step_number:
            step_id_map[steps[0].step_number] = "START"
        prev_node_id = "START"

        end_step = None
        if has_start:
            steps = steps[1:]
        if has_end and len(steps) > 0:
            end_step = steps[-1]
            steps = steps[:-1]

        # ── Process each step ────────────────────────────────────
        current_group = None 
        
        for i, step in enumerate(steps):
            node_id = self._generate_node_id(step, i)
            etype = step.node_type or NodeType.PROCESS
            conf = step.confidence if hasattr(step, 'confidence') else 1.0
            alts = step.alternatives if hasattr(step, 'alternatives') else []

            if self._is_crossref(step.text):
                etype = NodeType.PREDEFINED
                conf = max(conf, 0.85)

            node = FlowchartNode(
                id=node_id, node_type=etype,
                label=self._create_node_label(step),
                original_text=step.text,
                confidence=conf, alternatives=alts,
                group=getattr(step, 'group', None)
            )
            nodes.append(node)
            if step.step_number:
                step_id_map[step.step_number] = node_id

            # ---> NEW FIX: ISOLATE SECTIONS <---
            step_group = getattr(step, 'group', None)
            if current_group is not None and step_group != current_group:
                # Cap off any dangling linear steps from the previous phase
                if prev_node_id:
                    end_id = f"END_PHASE_{prev_node_id}"
                    nodes.append(FlowchartNode(id=end_id, node_type=NodeType.TERMINATOR, label="End Phase", confidence=1.0))
                    connections.append(Connection(from_node=prev_node_id, to_node=end_id, connection_type=ConnectionType.NORMAL))
                    prev_node_id = None
                
                # Cap off any dangling decision branches from the previous phase
                for ep_id, ep_label in branch_endpoints:
                    end_id = f"END_PHASE_{ep_id}"
                    nodes.append(FlowchartNode(id=end_id, node_type=NodeType.TERMINATOR, label="End Phase", confidence=1.0))
                    conn = Connection(from_node=ep_id, to_node=end_id, connection_type=ConnectionType.NORMAL)
                    if ep_label: conn.label = ep_label
                    connections.append(conn)
                branch_endpoints = []
                
            current_group = step_group
            # ---> END NEW FIX <---

            # ── Check for State Transition ────────────────────────
            target_phase = WorkflowPatterns.detect_state_transition(step.text)
            if target_phase:
                # Append the current node_id to make the phase transition unique and localized
                phase_id = f"PHASE_{target_phase.upper().replace(' ', '_')}_{node_id}"
                connections.append(Connection(
                    from_node=node_id, 
                    to_node=phase_id, 
                    label="Transition",
                    connection_type=ConnectionType.NORMAL
                ))
                
                # Always create a new localized node right next to the current step
                nodes.append(FlowchartNode(
                    id=phase_id, 
                    node_type=NodeType.TERMINATOR,
                    label=f"Move to: {target_phase}",
                    original_text=step.text,
                    confidence=0.9
                ))
                prev_node_id = None # Break linear flow
            else:
                # ── Connect from previous ────────────────────────────
                branch_endpoints = self._connect_from_previous(
                    node_id=node_id,
                    prev_node_id=prev_node_id,
                    branch_endpoints=branch_endpoints,
                    connections=connections,
                )

            # ── Decision branches ────────────────────────────────
            if step.is_decision and step.branches:
                branch_info_list = self._prepare_branch_info(step.branches)
                local_eps = self._apply_branch_info(
                    node_id=node_id,
                    branch_info_list=branch_info_list,
                    step_id_map=step_id_map,
                    nodes=nodes,
                    connections=connections,
                    confidence=conf,
                )

                branch_endpoints = local_eps
                prev_node_id = None
            else:
                prev_node_id = node_id

        # ── END node ─────────────────────────────────────────────
        nodes.append(FlowchartNode(
            id="END", node_type=NodeType.TERMINATOR,
            label="End", original_text="End", confidence=1.0
        ))
        if has_end and end_step and end_step.step_number:
            step_id_map[end_step.step_number] = "END"

        self._connect_end(
            branch_endpoints=branch_endpoints,
            prev_node_id=prev_node_id,
            connections=connections,
        )

        # ── Post-processing: Decision Safeguard ──────────────────
        self._ensure_decision_validity(nodes, connections)

        return nodes, connections

    def _ensure_decision_validity(self, nodes: List[FlowchartNode], connections: List[Connection]) -> None:
        """Ensure all decision nodes have at least 2 outgoing connections."""
        for node in nodes:
            if node.node_type == NodeType.DECISION:
                outgoing = [c for c in connections if c.from_node == node.id]
                if len(outgoing) < 2:
                    # Create a LOCAL end node instead of wiring to the global "END"
                    has_yes = any("yes" in (c.label or "").lower() for c in outgoing)
                    label = "No" if has_yes else "Yes"
                    local_end_id = f"END_{node.id}"
                    
                    nodes.append(FlowchartNode(id=local_end_id, node_type=NodeType.TERMINATOR, label="End", confidence=1.0))
                    connections.append(Connection(
                        from_node=node.id,
                        to_node=local_end_id,
                        label=label,
                        connection_type=ConnectionType.NO if label == "No" else ConnectionType.YES
                    ))
