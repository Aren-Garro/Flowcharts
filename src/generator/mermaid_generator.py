"""Mermaid.js code generator for flowcharts."""

from typing import Dict, List
from src.models import Flowchart, FlowchartNode, Connection, NodeType, MermaidShape


class MermaidGenerator:
    """Generate Mermaid.js flowchart syntax from Flowchart model."""
    
    # Mapping from ISO 5807 node types to Mermaid shapes
    NODE_TYPE_TO_SHAPE: Dict[NodeType, tuple[str, str]] = {
        NodeType.TERMINATOR: ("([{}])", "stadium"),      # Stadium shape
        NodeType.PROCESS: ("[{}]", "rect"),              # Rectangle
        NodeType.DECISION: ("{{{}}}", "diamond"),        # Diamond
        NodeType.IO: ("[/{}/]", "lean-r"),               # Parallelogram
        NodeType.DATABASE: ("[({})]", "cyl"),            # Cylinder
        NodeType.DISPLAY: ("{{{{{}}}}}", "hex"),        # Hexagon
        NodeType.DOCUMENT: ("[[{}]]", "doc"),            # Document
        NodeType.PREDEFINED: ("[[{}]]", "subroutine"),   # Subroutine
        NodeType.MANUAL: ("[/{}\\]", "trap-b"),         # Trapezoid
        NodeType.CONNECTOR: ("(({}))", "circle"),        # Circle
    }
    
    def __init__(self):
        self.direction = "TD"  # Top to Down (can be TD, LR, BT, RL)
    
    def generate(self, flowchart: Flowchart, direction: str = "TD") -> str:
        """
        Generate Mermaid.js flowchart code.
        
        Args:
            flowchart: Flowchart model to convert
            direction: Flow direction (TD=top-down, LR=left-right, etc.)
            
        Returns:
            Mermaid.js flowchart code as string
        """
        self.direction = direction
        lines = []
        
        # Start with flowchart declaration
        lines.append(f"flowchart {self.direction}")
        
        # Add title as comment if present
        if flowchart.title:
            lines.append(f"    %% {flowchart.title}")
        
        # Generate node definitions
        for node in flowchart.nodes:
            node_def = self._generate_node(node)
            lines.append(f"    {node_def}")
        
        # Add blank line between nodes and connections
        lines.append("")
        
        # Generate connections
        for connection in flowchart.connections:
            conn_def = self._generate_connection(connection)
            lines.append(f"    {conn_def}")
        
        # Add styling for special nodes
        lines.append("")
        lines.extend(self._generate_styles(flowchart))
        
        return "\n".join(lines)
    
    def _generate_node(self, node: FlowchartNode) -> str:
        """
        Generate Mermaid node definition.
        
        Args:
            node: FlowchartNode to convert
            
        Returns:
            Mermaid node definition string
        """
        # Get shape syntax for node type
        shape_template, _ = self.NODE_TYPE_TO_SHAPE.get(
            node.node_type,
            ("[{}]", "rect")  # Default to rectangle
        )
        
        # Clean label text (escape special characters)
        label = self._escape_label(node.label)
        
        # Format: NodeID[Label] or NodeID([Label]) etc.
        node_def = f"{node.id}{shape_template.format(label)}"
        
        return node_def
    
    def _generate_connection(self, connection: Connection) -> str:
        """
        Generate Mermaid connection definition.
        
        Args:
            connection: Connection to convert
            
        Returns:
            Mermaid connection definition string
        """
        # Basic arrow: A --> B
        arrow = "-->"
        
        # Add label if present: A -->|Label| B
        if connection.label:
            label = self._escape_label(connection.label)
            return f"{connection.from_node} -->|{label}| {connection.to_node}"
        else:
            return f"{connection.from_node} {arrow} {connection.to_node}"
    
    def _escape_label(self, text: str) -> str:
        """
        Escape special characters in labels for Mermaid.
        
        Args:
            text: Text to escape
            
        Returns:
            Escaped text
        """
        # Escape quotes
        text = text.replace('"', '&quot;')
        
        # Replace problematic characters
        text = text.replace('#', '&num;')
        
        return text
    
    def _generate_styles(self, flowchart: Flowchart) -> List[str]:
        """
        Generate CSS styling for special nodes.
        
        Args:
            flowchart: Flowchart to style
            
        Returns:
            List of style definition lines
        """
        styles = []
        
        # Find special nodes to style
        start_nodes = []
        end_nodes = []
        decision_nodes = []
        
        for node in flowchart.nodes:
            if node.node_type == NodeType.TERMINATOR:
                if "start" in node.label.lower() or "begin" in node.label.lower():
                    start_nodes.append(node.id)
                elif "end" in node.label.lower() or "finish" in node.label.lower():
                    end_nodes.append(node.id)
            elif node.node_type == NodeType.DECISION:
                decision_nodes.append(node.id)
        
        # Style start nodes (green)
        for node_id in start_nodes:
            styles.append(f"    style {node_id} fill:#90EE90,stroke:#333,stroke-width:2px")
        
        # Style end nodes (pink/red)
        for node_id in end_nodes:
            styles.append(f"    style {node_id} fill:#FFB6C1,stroke:#333,stroke-width:2px")
        
        # Style decision nodes (yellow)
        for node_id in decision_nodes:
            styles.append(f"    style {node_id} fill:#FFE4B5,stroke:#333,stroke-width:2px")
        
        return styles
    
    def generate_with_theme(self, flowchart: Flowchart, theme: str = "default") -> str:
        """
        Generate Mermaid code with specific theme.
        
        Args:
            flowchart: Flowchart to generate
            theme: Theme name (default, forest, dark, neutral)
            
        Returns:
            Mermaid code with theme directive
        """
        code = self.generate(flowchart)
        
        # Add theme directive
        theme_line = f"%%{{init: {{'theme':'{theme}'}}}}%%"
        
        return f"{theme_line}\n{code}"
