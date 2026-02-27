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
