"""Graph builder for flowchart construction."""

from typing import List, Dict, Optional, Tuple
from src.models import Flowchart, FlowchartNode, Connection, WorkflowStep
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
