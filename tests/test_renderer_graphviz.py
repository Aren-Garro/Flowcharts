"""Graphviz renderer behavior tests."""

from src.models import Connection, ConnectionType
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
