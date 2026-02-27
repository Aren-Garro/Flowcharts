"""Tests for graph builder."""

from src.builder.graph_builder import GraphBuilder
from src.models import NodeType
from src.parser.nlp_parser import NLPParser


def test_build_simple_flowchart():
    """Test building a simple flowchart."""
    workflow = """
    1. Start
    2. Process data
    3. End
    """

    parser = NLPParser(use_spacy=False)
    steps = parser.parse(workflow)

    builder = GraphBuilder()
    flowchart = builder.build(steps)

    assert len(flowchart.nodes) >= 3
    assert len(flowchart.connections) >= 2


def test_flowchart_has_start_and_end():
    """Test that flowchart has start and end nodes."""
    workflow = "1. Process data\n2. Save result"

    parser = NLPParser(use_spacy=False)
    steps = parser.parse(workflow)

    builder = GraphBuilder()
    flowchart = builder.build(steps)

    # Should have terminators
    terminators = [n for n in flowchart.nodes if n.node_type == NodeType.TERMINATOR]
    assert len(terminators) >= 2


def test_validate_structure():
    """Test flowchart structure validation."""
    workflow = """
    1. Start
    2. Process data
    3. End
    """

    parser = NLPParser(use_spacy=False)
    steps = parser.parse(workflow)

    builder = GraphBuilder()
    flowchart = builder.build(steps)

    is_valid, errors = flowchart.validate_structure()
    assert is_valid or len(errors) == 0  # Should be valid or have no critical errors
