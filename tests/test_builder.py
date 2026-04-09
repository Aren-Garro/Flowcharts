"""Tests for graph builder."""

from src.builder.graph_builder import GraphBuilder
from src.models import NodeType, WorkflowStep
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


def test_grouped_sop_transitions_connect_directly_to_existing_phase():
    steps = [
        WorkflowStep(step_number=1, text="Open repair ticket", action="open", node_type=NodeType.PROCESS, group="1. Intake"),
        WorkflowStep(step_number=2, text="Move the ticket to 'Label Sent to Customer'", action="move", node_type=NodeType.PROCESS, group="1. Intake"),
        WorkflowStep(step_number=3, text="Monitor shipment", action="monitor", node_type=NodeType.PROCESS, group="2. Label Sent to Customer"),
    ]

    flowchart = GraphBuilder().build(steps, title="Repair Pipeline")

    labels = [node.label for node in flowchart.nodes]
    assert all(not label.startswith("Move to:") for label in labels)
    assert "End Phase" not in labels
    assert any(conn.from_node == "STEP_2" and conn.to_node == "STEP_3" for conn in flowchart.connections)


def test_grouped_sop_unresolved_transition_becomes_clean_terminal():
    steps = [
        WorkflowStep(step_number=1, text="Pack repaired item", action="pack", node_type=NodeType.PROCESS, group="8. Paid"),
        WorkflowStep(step_number=2, text="Move the ticket to 'Released'", action="move", node_type=NodeType.PROCESS, group="8. Paid"),
    ]

    flowchart = GraphBuilder().build(steps, title="Repair Pipeline")

    labels_by_id = {node.id: node.label for node in flowchart.nodes}
    assert labels_by_id["END"] == "Released"
    assert all(not label.startswith("Move to:") for label in labels_by_id.values())
    assert any(conn.from_node == "STEP_2" and conn.to_node == "END" for conn in flowchart.connections)


def test_grouped_layout_places_phases_on_separate_rows():
    steps = [
        WorkflowStep(step_number=1, text="Open repair ticket", action="open", node_type=NodeType.PROCESS, group="1. Intake"),
        WorkflowStep(step_number=2, text="Verify submission", action="verify", node_type=NodeType.PROCESS, group="1. Intake"),
        WorkflowStep(step_number=3, text="Monitor shipment", action="monitor", node_type=NodeType.PROCESS, group="2. Label Sent to Customer"),
        WorkflowStep(step_number=4, text="Receive item", action="receive", node_type=NodeType.PROCESS, group="3. Item Received"),
    ]

    flowchart = GraphBuilder().build(steps, title="Repair Pipeline")
    positions = {node.id: node.position for node in flowchart.nodes if node.position}

    assert positions["STEP_1"][0] == positions["STEP_2"][0]
    assert positions["STEP_3"][0] > positions["STEP_1"][0]
    assert positions["STEP_4"][0] > positions["STEP_3"][0]
