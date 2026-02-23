"""Data models for flowchart generation."""

from enum import Enum
from typing import Optional, List, Tuple
from pydantic import BaseModel, Field


class NodeType(str, Enum):
    """ISO 5807 flowchart symbol types."""
    TERMINATOR = "terminator"
    PROCESS = "process"
    DECISION = "decision"
    IO = "io"
    DATABASE = "database"
    DISPLAY = "display"
    DOCUMENT = "document"
    PREDEFINED = "predefined"
    MANUAL = "manual"
    CONNECTOR = "connector"


class MermaidShape(str, Enum):
    """Mermaid.js shape syntax mapping."""
    STADIUM = "stadium"
    RECT = "rect"
    DIAMOND = "diamond"
    LEAN_RIGHT = "lean-r"
    CYLINDER = "cyl"
    HEXAGON = "hex"
    DOC = "doc"
    SUBROUTINE = "subroutine"
    TRAPEZOID = "trap-b"
    CIRCLE = "circle"


class ConnectionType(str, Enum):
    """Connection/edge types between nodes."""
    NORMAL = "normal"
    TRUE = "true"
    FALSE = "false"
    YES = "yes"
    NO = "no"
    LOOP = "loop"


class Connection(BaseModel):
    """Represents a connection between two flowchart nodes."""
    from_node: str = Field(..., description="Source node ID")
    to_node: str = Field(..., description="Target node ID")
    label: Optional[str] = Field(None, description="Edge label")
    connection_type: ConnectionType = Field(ConnectionType.NORMAL)

    class Config:
        use_enum_values = True


class FlowchartNode(BaseModel):
    """Represents a single node in the flowchart."""
    id: str = Field(..., description="Unique node identifier")
    node_type: NodeType = Field(..., description="ISO 5807 symbol type")
    label: str = Field(..., description="Node text content")
    original_text: Optional[str] = Field(None, description="Original workflow step text")
    position: Optional[Tuple[int, int]] = Field(None, description="Layout position (x, y)")
    confidence: float = Field(1.0, description="Confidence in node type classification (0-1)")
    alternatives: List[NodeType] = Field(default_factory=list, description="Alternative node types")

    class Config:
        use_enum_values = True


class Flowchart(BaseModel):
    """Complete flowchart representation."""
    nodes: List[FlowchartNode] = Field(default_factory=list)
    connections: List[Connection] = Field(default_factory=list)
    title: Optional[str] = Field(None)
    description: Optional[str] = Field(None)

    def add_node(self, node: FlowchartNode) -> None:
        self.nodes.append(node)

    def add_connection(self, connection: Connection) -> None:
        self.connections.append(connection)

    def get_node(self, node_id: str) -> Optional[FlowchartNode]:
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None

    def validate_structure(self) -> Tuple[bool, List[str]]:
        errors = []
        start_nodes = [n for n in self.nodes if n.node_type == NodeType.TERMINATOR and "start" in n.label.lower()]
        if not start_nodes:
            errors.append("Missing START node (terminator)")
        elif len(start_nodes) > 1:
            errors.append(f"Multiple START nodes found: {len(start_nodes)}")
        end_nodes = [n for n in self.nodes if n.node_type == NodeType.TERMINATOR and "end" in n.label.lower()]
        if not end_nodes:
            errors.append("Missing END node (terminator)")
        node_ids = {n.id for n in self.nodes}
        connected_nodes = set()
        for conn in self.connections:
            connected_nodes.add(conn.from_node)
            connected_nodes.add(conn.to_node)
        orphaned = node_ids - connected_nodes - {n.id for n in start_nodes}
        if orphaned:
            errors.append(f"Orphaned nodes found: {orphaned}")
        for node in self.nodes:
            if node.node_type == NodeType.DECISION:
                outgoing = [c for c in self.connections if c.from_node == node.id]
                if len(outgoing) < 2:
                    errors.append(f"Decision node '{node.id}' has fewer than 2 branches")
        return len(errors) == 0, errors


class WorkflowStep(BaseModel):
    """Parsed workflow step from natural language."""
    step_number: Optional[int] = Field(None)
    text: str = Field(..., description="Original step text")
    action: str = Field(..., description="Extracted action/verb")
    subject: Optional[str] = Field(None)
    object: Optional[str] = Field(None)
    is_decision: bool = Field(False)
    is_loop: bool = Field(False)
    branches: Optional[List[str]] = Field(None)
    node_type: Optional[NodeType] = Field(None)
    confidence: float = Field(1.0, description="Confidence in classification")
    alternatives: List[NodeType] = Field(default_factory=list)
