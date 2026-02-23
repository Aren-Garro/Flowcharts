"""Data models for flowchart generation."""

from enum import Enum
from typing import Optional, List, Tuple
from pydantic import BaseModel, Field


class NodeType(str, Enum):
    """ISO 5807 flowchart symbol types."""
    TERMINATOR = "terminator"          # Start/End - Oval
    PROCESS = "process"                # Process - Rectangle
    DECISION = "decision"              # Decision - Diamond
    IO = "io"                          # Input/Output - Parallelogram
    DATABASE = "database"              # Database - Cylinder
    DISPLAY = "display"                # Display - Hexagon
    DOCUMENT = "document"              # Document - Rectangle with wavy bottom
    PREDEFINED = "predefined"          # Predefined process - Double-sided rectangle
    MANUAL = "manual"                  # Manual operation - Trapezoid
    CONNECTOR = "connector"            # Connector - Circle


class MermaidShape(str, Enum):
    """Mermaid.js shape syntax mapping."""
    STADIUM = "stadium"                # ([text])  - Terminator
    RECT = "rect"                      # [text]    - Process
    DIAMOND = "diamond"                # {text}    - Decision
    LEAN_RIGHT = "lean-r"              # [/text/]  - IO
    CYLINDER = "cyl"                   # [(text)]  - Database
    HEXAGON = "hex"                    # {{text}}  - Display
    DOC = "doc"                        # [[text]]  - Document
    SUBROUTINE = "subroutine"          # [[text]]  - Predefined
    TRAPEZOID = "trap-b"               # [/text\]  - Manual
    CIRCLE = "circle"                  # ((text))  - Connector


class ConnectionType(str, Enum):
    """Connection/edge types between nodes."""
    NORMAL = "normal"                  # Standard flow
    TRUE = "true"                      # Decision: true branch
    FALSE = "false"                    # Decision: false branch
    YES = "yes"                        # Decision: yes branch
    NO = "no"                          # Decision: no branch
    LOOP = "loop"                      # Loop back connection


class Connection(BaseModel):
    """Represents a connection between two flowchart nodes."""
    from_node: str = Field(..., description="Source node ID")
    to_node: str = Field(..., description="Target node ID")
    label: Optional[str] = Field(None, description="Edge label (e.g., 'Yes', 'No')")
    connection_type: ConnectionType = Field(ConnectionType.NORMAL, description="Type of connection")

    class Config:
        use_enum_values = True


class FlowchartNode(BaseModel):
    """Represents a single node in the flowchart."""
    id: str = Field(..., description="Unique node identifier")
    node_type: NodeType = Field(..., description="ISO 5807 symbol type")
    label: str = Field(..., description="Node text content")
    original_text: Optional[str] = Field(None, description="Original workflow step text")
    position: Optional[Tuple[int, int]] = Field(None, description="Layout position (x, y)")
    
    class Config:
        use_enum_values = True


class Flowchart(BaseModel):
    """Complete flowchart representation."""
    nodes: List[FlowchartNode] = Field(default_factory=list, description="List of flowchart nodes")
    connections: List[Connection] = Field(default_factory=list, description="List of connections between nodes")
    title: Optional[str] = Field(None, description="Flowchart title")
    description: Optional[str] = Field(None, description="Flowchart description")
    
    def add_node(self, node: FlowchartNode) -> None:
        """Add a node to the flowchart."""
        self.nodes.append(node)
    
    def add_connection(self, connection: Connection) -> None:
        """Add a connection to the flowchart."""
        self.connections.append(connection)
    
    def get_node(self, node_id: str) -> Optional[FlowchartNode]:
        """Retrieve a node by ID."""
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None
    
    def validate_structure(self) -> Tuple[bool, List[str]]:
        """Validate flowchart structure. Returns (is_valid, error_messages)."""
        errors = []
        
        # Check for at least one start node
        start_nodes = [n for n in self.nodes if n.node_type == NodeType.TERMINATOR and "start" in n.label.lower()]
        if not start_nodes:
            errors.append("Missing START node (terminator)")
        elif len(start_nodes) > 1:
            errors.append(f"Multiple START nodes found: {len(start_nodes)}")
        
        # Check for at least one end node
        end_nodes = [n for n in self.nodes if n.node_type == NodeType.TERMINATOR and "end" in n.label.lower()]
        if not end_nodes:
            errors.append("Missing END node (terminator)")
        
        # Check for orphaned nodes (no incoming or outgoing connections)
        node_ids = {n.id for n in self.nodes}
        connected_nodes = set()
        for conn in self.connections:
            connected_nodes.add(conn.from_node)
            connected_nodes.add(conn.to_node)
        
        orphaned = node_ids - connected_nodes
        # Start nodes may not have incoming connections
        orphaned = orphaned - {n.id for n in start_nodes}
        if orphaned:
            errors.append(f"Orphaned nodes found: {orphaned}")
        
        # Validate decision nodes have multiple branches
        for node in self.nodes:
            if node.node_type == NodeType.DECISION:
                outgoing = [c for c in self.connections if c.from_node == node.id]
                if len(outgoing) < 2:
                    errors.append(f"Decision node '{node.id}' has fewer than 2 branches")
        
        return len(errors) == 0, errors


class WorkflowStep(BaseModel):
    """Parsed workflow step from natural language."""
    step_number: Optional[int] = Field(None, description="Step sequence number")
    text: str = Field(..., description="Original step text")
    action: str = Field(..., description="Extracted action/verb")
    subject: Optional[str] = Field(None, description="Subject performing action")
    object: Optional[str] = Field(None, description="Object being acted upon")
    is_decision: bool = Field(False, description="Whether this is a decision point")
    is_loop: bool = Field(False, description="Whether this involves looping")
    branches: Optional[List[str]] = Field(None, description="Decision branches (if applicable)")
    node_type: Optional[NodeType] = Field(None, description="Inferred flowchart node type")
