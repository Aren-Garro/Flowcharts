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
from typing import Dict, List, Optional, Set, Tuple

from src.models import Connection, ConnectionType, FlowchartNode, NodeType, WorkflowStep


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

    def _detect_skip_target(self, text: str) -> Optional[int]:
        # Check for "go to end" first
        if re.search(r'go\s+to\s+end', text, re.IGNORECASE):
            return -1  # Special marker for END

        if self._detect_loop_target(text):
            return None
        for pattern in self.SKIP_PATTERNS:
            m = pattern.search(text)
            if m:
                try:
                    return int(m.group(1))
                except (ValueError, IndexError):
                    pass
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
        for j, raw in enumerate(branches):
            info = self._classify_branch(raw)
            label = info['label'] or ('Yes' if j == 0 else 'No')
            branch_info_list.append((info, label, raw, j))

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
        local_eps: List[Tuple[str, Optional[str]]] = []

        for info, lbl, raw, j in branch_info_list:
            ctype = ConnectionType.YES if lbl == 'Yes' else ConnectionType.NO

            if info['type'] == 'skip':
                tid = step_id_map.get(info['target'], f"STEP_{info['target']}")
                connections.append(Connection(from_node=node_id, to_node=tid, label=lbl, connection_type=ctype))
            elif info['type'] == 'retry':
                tid = step_id_map.get(info['target'], f"STEP_{info['target']}")
                connections.append(
                    Connection(from_node=node_id, to_node=tid, label=lbl, connection_type=ConnectionType.LOOP)
                )
            elif info['type'] == 'continue':
                local_eps.append((node_id, lbl))
            elif info['type'] == 'terminator':
                connections.append(Connection(from_node=node_id, to_node="END", label=lbl, connection_type=ctype))
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
                    )
                )
                connections.append(Connection(from_node=node_id, to_node=bid, label=lbl, connection_type=ctype))
                local_eps.append((bid, None))

        return local_eps

    def analyze(self, steps: List[WorkflowStep]) -> Tuple[List[FlowchartNode], List[Connection]]:
        nodes: List[FlowchartNode] = []
        connections: List[Connection] = []
        step_id_map: Dict[int, str] = {}
        # Track terminator nodes created as branch endpoints
        terminator_nodes: Set[str] = set()
        # Each endpoint is (node_id, optional_label)
        branch_endpoints: List[Tuple[str, Optional[str]]] = []

        # Handle empty workflow
        if not steps:
            nodes.append(FlowchartNode(
                id="START", node_type=NodeType.TERMINATOR,
                label="Start", original_text="Start", confidence=1.0
            ))
            nodes.append(FlowchartNode(
                id="END", node_type=NodeType.TERMINATOR,
                label="End", original_text="End", confidence=1.0
            ))
            connections.append(Connection(
                from_node="START", to_node="END",
                connection_type=ConnectionType.NORMAL
            ))
            return nodes, connections

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
                confidence=conf, alternatives=alts
            )
            nodes.append(node)
            if step.step_number:
                step_id_map[step.step_number] = node_id

            # ── Connect from previous ────────────────────────────
            if branch_endpoints and prev_node_id is None:
                for ep_id, ep_lbl in branch_endpoints:
                    c = Connection(from_node=ep_id, to_node=node_id,
                                   connection_type=ConnectionType.NORMAL)
                    if ep_lbl:
                        c.label = ep_lbl
                    connections.append(c)
                branch_endpoints = []
            elif prev_node_id:
                connections.append(Connection(
                    from_node=prev_node_id, to_node=node_id,
                    connection_type=ConnectionType.NORMAL
                ))

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
            else:                prev_node_id = node_id

        # ── END node ─────────────────────────────────────────────
        nodes.append(FlowchartNode(
            id="END", node_type=NodeType.TERMINATOR,
            label="End", original_text="End", confidence=1.0
        ))
        if has_end and end_step and end_step.step_number:
            step_id_map[end_step.step_number] = "END"

        if branch_endpoints:
            for ep_id, ep_lbl in branch_endpoints:
                c = Connection(from_node=ep_id, to_node="END",
                               connection_type=ConnectionType.NORMAL)
                if ep_lbl:
                    c.label = ep_lbl
                connections.append(c)
        elif prev_node_id:
            connections.append(Connection(
                from_node=prev_node_id, to_node="END",
                connection_type=ConnectionType.NORMAL
            ))

        # Connect inline terminators to END ONLY if they have no outgoing connections
        # This prevents "END node has outgoing connections" errors
        for n in nodes:
            if (
                n.node_type == NodeType.TERMINATOR
                and n.id not in ("START", "END")
                and n.id in terminator_nodes
            ):  # Only branch terminators
                # Check if this terminator already has an outgoing connection
                has_outgoing = any(c.from_node == n.id for c in connections)
                if not has_outgoing:
                    connections.append(Connection(
                        from_node=n.id, to_node="END",
                        connection_type=ConnectionType.NORMAL
                    ))

        return nodes, connections
