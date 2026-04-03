"""Graphviz renderer behavior tests."""

from src.models import Connection, ConnectionType, Flowchart, FlowchartNode, NodeType
from src.renderer.graphviz_renderer import GraphvizRenderer


class _DotRecorder:
    def __init__(self):
        self.calls = []

    def edge(self, from_node, to_node, **attrs):
        self.calls.append((from_node, to_node, attrs))


def test_graphviz_edge_uses_xlabel_for_labeled_edges():
    renderer = GraphvizRenderer()
    dot = _DotRecorder()
    conn = Connection(from_node="A", to_node="B", label="Yes", connection_type=ConnectionType.NORMAL)

    renderer._add_edge(dot, conn)

    assert len(dot.calls) == 1
    attrs = dot.calls[0][2]
    assert attrs.get("xlabel") == " Yes "
    assert "label" not in attrs


def test_graphviz_branch_edges_use_side_ports_for_vertical_layout():
    renderer = GraphvizRenderer(rankdir="TB")
    dot = _DotRecorder()

    renderer._add_edge(
        dot,
        Connection(from_node="DECIDE", to_node="YES_PATH", label="Yes", connection_type=ConnectionType.YES),
    )
    renderer._add_edge(
        dot,
        Connection(from_node="DECIDE", to_node="NO_PATH", label="No", connection_type=ConnectionType.NO),
    )

    assert dot.calls[0][0] == "DECIDE:e"
    assert dot.calls[0][1] == "YES_PATH:w"
    assert dot.calls[0][2]["minlen"] == "3"
    assert dot.calls[1][0] == "DECIDE:w"
    assert dot.calls[1][1] == "NO_PATH:e"
    assert dot.calls[1][2]["minlen"] == "3"


def test_graphviz_generate_dot_uses_roomier_layout_for_complex_flowcharts():
    nodes = [
        FlowchartNode(
            id=f"N{i}",
            node_type=NodeType.DECISION if i % 4 == 0 else NodeType.PROCESS,
            label=f"Step {i} handles a fairly detailed workflow action for export readability",
        )
        for i in range(1, 22)
    ]
    connections = [
        Connection(from_node=f"N{i}", to_node=f"N{i + 1}", connection_type=ConnectionType.NORMAL)
        for i in range(1, 21)
    ]
    flowchart = Flowchart(nodes=nodes, connections=connections, title="Complex Export")

    dot_source = GraphvizRenderer().generate_dot(flowchart)

    assert 'nodesep=1.1' in dot_source
    assert 'ranksep=1.35' in dot_source
    assert 'outputorder=edgesfirst' in dot_source
    assert 'margin="0.24,0.16"' in dot_source


def test_graphviz_low_confidence_nodes_keep_rounded_style():
    flowchart = Flowchart(
        title="Confidence Export",
        nodes=[
            FlowchartNode(id="A", node_type=NodeType.PROCESS, label="Review request", confidence=0.5),
        ],
        connections=[],
    )

    dot_source = GraphvizRenderer().generate_dot(flowchart)

    assert 'style="filled,rounded,dashed"' in dot_source
    assert 'color="#C58A2B"' in dot_source


def test_graphviz_generate_dot_uses_phased_sop_spacing():
    groups = [
        "1. Intake",
        "2. Label Sent",
        "3. Shipped",
        "4. Received",
        "5. Repair",
    ]
    nodes = [
        FlowchartNode(id=f"N{i}", node_type=NodeType.PROCESS, label=f"Step {i}", group=groups[i - 1])
        for i in range(1, 6)
    ]
    connections = [
        Connection(from_node=f"N{i}", to_node=f"N{i + 1}", connection_type=ConnectionType.NORMAL)
        for i in range(1, 5)
    ]

    dot_source = GraphvizRenderer().generate_dot(Flowchart(nodes=nodes, connections=connections, title="Phased SOP"))

    assert 'nodesep=1.25' in dot_source
    assert 'ranksep=1.7' in dot_source
    assert 'margin="0.32,0.2"' in dot_source
