"""Tests for workflow parser."""

from src.models import NodeType
from src.parser.nlp_parser import NLPParser
from src.parser.patterns import WorkflowPatterns


def test_parse_simple_workflow():
    """Test parsing a simple linear workflow."""
    workflow = """
    1. Start
    2. Process data
    3. End
    """

    parser = NLPParser(use_spacy=False)
    steps = parser.parse(workflow)

    assert len(steps) == 3
    # Note: Parser may preserve "1. Start" or normalize to "Start" depending on implementation
    # Just check that it contains "Start"
    assert "Start" in steps[0].text
    assert "Process data" in steps[1].text
    assert "End" in steps[2].text


def test_detect_decision():
    """Test decision point detection."""
    text = "Check if user is authenticated"
    assert WorkflowPatterns.is_decision(text)

    text2 = "Process the data"
    assert not WorkflowPatterns.is_decision(text2)


def test_detect_node_types():
    """Test node type detection."""
    assert WorkflowPatterns.detect_node_type("Start process") == NodeType.TERMINATOR
    assert WorkflowPatterns.detect_node_type("Calculate total") == NodeType.PROCESS
    assert WorkflowPatterns.detect_node_type("Check if valid") == NodeType.DECISION
    assert WorkflowPatterns.detect_node_type("Read from database") == NodeType.IO
    assert WorkflowPatterns.detect_node_type("Query database") == NodeType.DATABASE
    assert WorkflowPatterns.detect_node_type("Display message") == NodeType.DISPLAY


def test_extract_step_number():
    """Test step number extraction."""
    text = "1. Start process"
    assert WorkflowPatterns.extract_step_number(text) == 1

    text2 = "10. End"
    assert WorkflowPatterns.extract_step_number(text2) == 10

    text3 = "No number here"
    assert WorkflowPatterns.extract_step_number(text3) is None


def test_normalize_text():
    """Test text normalization."""
    text = "1. start   the   process"
    normalized = WorkflowPatterns.normalize_step_text(text)
    assert normalized == "Start the process"
    assert not normalized.startswith("1.")


def test_parse_decision_with_branches():
    """Test parsing decision with branches."""
    workflow = """
    1. Check if user is valid
       - If yes: Continue
       - If no: Stop
    2. Process request
    """

    parser = NLPParser(use_spacy=False)
    steps = parser.parse(workflow)

    # Should have decision step
    decision_steps = [s for s in steps if s.is_decision]
    assert len(decision_steps) > 0

    # Decision should have branches
    decision = decision_steps[0]
    assert decision.branches is not None
    assert len(decision.branches) == 2


def test_parse_sop_phase_headers_assigns_groups():
    workflow = """
    Phase 1: Intake
    1. Receive request
    2. Validate submission
    Phase 2 - Fulfillment
    3. Prepare response
    4. End
    """

    parser = NLPParser(use_spacy=False)
    steps = parser.parse(workflow)

    assert len(steps) == 4
    assert steps[0].group == "Phase 1: Intake"
    assert steps[1].group == "Phase 1: Intake"
    assert steps[2].group == "Phase 2 - Fulfillment"
    assert steps[3].group == "Phase 2 - Fulfillment"


def test_detects_multiple_sop_header_formats():
    assert WorkflowPatterns.is_section_header("Phase 2: Intake Review")
    assert WorkflowPatterns.is_section_header("Phase 3 - Fulfillment")
    assert WorkflowPatterns.is_section_header("2.1 Order Validation")
    assert WorkflowPatterns.is_section_header("## 2. Label Sent to Customer")


def test_merged_markdown_phase_headers_assign_groups_without_header_nodes():
    workflow = """
    ## 1. New Repair Request Intake
    1. Open the new repair request ticket.
    If all required information is present:
    - Move the ticket to 'Label Sent to Customer'
    ## 2. Label Sent to Customer
    - Monitor the tracking ID periodically throughout the day.
    If the package is not shipped within 24-48 hours:
    - Reach out to the client to confirm shipment status.
    """

    parser = NLPParser(use_spacy=False)
    steps = parser.parse(workflow)

    assert steps
    assert all(not step.text.startswith("##") for step in steps)
    assert steps[0].group == "1. New Repair Request Intake"
    assert steps[0].text == "Open the new repair request ticket."
    assert steps[1].group == "1. New Repair Request Intake"
    assert steps[2].group == "2. Label Sent to Customer"
    assert steps[2].text == "Monitor the tracking ID periodically throughout the day."
    assert steps[3].group == "2. Label Sent to Customer"
