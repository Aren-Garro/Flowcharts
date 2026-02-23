"""Semantic analysis of parsed workflow steps."""

from typing import List, Dict, Tuple
from src.models import WorkflowStep, FlowchartNode, Connection, NodeType, ConnectionType


class WorkflowAnalyzer:
    """Analyze workflow steps and build flowchart structure."""
    
    def __init__(self):
        self.node_counter = 0
    
    def analyze(self, steps: List[WorkflowStep]) -> Tuple[List[FlowchartNode], List[Connection]]:
        """
        Analyze workflow steps and create flowchart nodes and connections.
        
        Args:
            steps: List of parsed workflow steps
            
        Returns:
            Tuple of (nodes, connections)
        """
        nodes = []
        connections = []
        
        # Ensure we have a start node
        if not steps or steps[0].node_type != NodeType.TERMINATOR:
            start_node = FlowchartNode(
                id="START",
                node_type=NodeType.TERMINATOR,
                label="Start",
                original_text="Start"
            )
            nodes.append(start_node)
            prev_node_id = "START"
        else:
            prev_node_id = None
        
        # Process each step
        for i, step in enumerate(steps):
            node_id = self._generate_node_id(step, i)
            
            # Create node
            node = FlowchartNode(
                id=node_id,
                node_type=step.node_type or NodeType.PROCESS,
                label=self._create_node_label(step),
                original_text=step.text
            )
            nodes.append(node)
            
            # Create connection from previous node
            if prev_node_id:
                connection = Connection(
                    from_node=prev_node_id,
                    to_node=node_id,
                    connection_type=ConnectionType.NORMAL
                )
                connections.append(connection)
            
            # Handle decision branches
            if step.is_decision and step.branches:
                # Create nodes for each branch
                for j, branch_text in enumerate(step.branches):
                    branch_id = f"{node_id}_BRANCH_{j}"
                    branch_label = self._extract_branch_label(branch_text)
                    
                    # Determine branch node type
                    branch_node_type = NodeType.PROCESS
                    if "end" in branch_text.lower() or "stop" in branch_text.lower():
                        branch_node_type = NodeType.TERMINATOR
                    
                    branch_node = FlowchartNode(
                        id=branch_id,
                        node_type=branch_node_type,
                        label=branch_label,
                        original_text=branch_text
                    )
                    nodes.append(branch_node)
                    
                    # Create connection with branch label
                    conn_label = "Yes" if j == 0 else "No"
                    conn_type = ConnectionType.YES if j == 0 else ConnectionType.NO
                    
                    branch_connection = Connection(
                        from_node=node_id,
                        to_node=branch_id,
                        label=conn_label,
                        connection_type=conn_type
                    )
                    connections.append(branch_connection)
                
                # Don't automatically connect after decision - branches handle it
                prev_node_id = None
            else:
                prev_node_id = node_id
        
        # Ensure we have an end node
        last_node = nodes[-1] if nodes else None
        if not last_node or last_node.node_type != NodeType.TERMINATOR:
            end_node = FlowchartNode(
                id="END",
                node_type=NodeType.TERMINATOR,
                label="End",
                original_text="End"
            )
            nodes.append(end_node)
            
            if prev_node_id:
                connection = Connection(
                    from_node=prev_node_id,
                    to_node="END",
                    connection_type=ConnectionType.NORMAL
                )
                connections.append(connection)
        
        return nodes, connections
    
    def _generate_node_id(self, step: WorkflowStep, index: int) -> str:
        """
        Generate unique node ID.
        
        Args:
            step: Workflow step
            index: Step index
            
        Returns:
            Unique node ID
        """
        if step.node_type == NodeType.TERMINATOR:
            if "start" in step.text.lower():
                return "START"
            elif "end" in step.text.lower():
                return "END"
        
        # Use step number if available, otherwise use index
        if step.step_number:
            return f"STEP_{step.step_number}"
        else:
            return f"NODE_{index}"
    
    def _create_node_label(self, step: WorkflowStep) -> str:
        """
        Create concise node label from step text.
        
        Args:
            step: Workflow step
            
        Returns:
            Node label text
        """
        # For terminators, use simple labels
        if step.node_type == NodeType.TERMINATOR:
            if "start" in step.text.lower():
                return "Start"
            elif "end" in step.text.lower():
                return "End"
        
        # For decisions, format as question
        if step.is_decision:
            text = step.text
            if not text.endswith('?'):
                text += '?'
            return text
        
        # For other nodes, use cleaned text
        return step.text
    
    def _extract_branch_label(self, branch_text: str) -> str:
        """
        Extract clean label from branch text.
        
        Args:
            branch_text: Raw branch text
            
        Returns:
            Clean branch label
        """
        # Remove "if yes:", "if no:", etc.
        text = branch_text.lower()
        text = text.replace('if yes:', '').replace('if no:', '')
        text = text.replace('yes:', '').replace('no:', '')
        text = text.strip()
        
        # Capitalize first letter
        if text:
            text = text[0].upper() + text[1:]
        
        return text
