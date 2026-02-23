"""Tests for Mermaid generator."""

import pytest
from src.parser.nlp_parser import NLPParser
from src.builder.graph_builder import GraphBuilder
from src.generator.mermaid_generator import MermaidGenerator


def test_generate_mermaid_code():
    """Test Mermaid code generation."""
    workflow = """
    1. Start
    2. Process data
    3. End
    """
    
    parser = NLPParser(use_spacy=False)
    steps = parser.parse(workflow)
    
    builder = GraphBuilder()
    flowchart = builder.build(steps)
    
    generator = MermaidGenerator()
    code = generator.generate(flowchart)
    
    assert code.startswith("flowchart")
    assert "START" in code or "Start" in code
    assert "END" in code or "End" in code
    assert "-->" in code  # Should have connections


def test_generate_with_theme():
    """Test Mermaid code generation with theme."""
    workflow = "1. Start\n2. End"
    
    parser = NLPParser(use_spacy=False)
    steps = parser.parse(workflow)
    
    builder = GraphBuilder()
    flowchart = builder.build(steps)
    
    generator = MermaidGenerator()
    code = generator.generate_with_theme(flowchart, theme="dark")
    
    assert "theme" in code
    assert "dark" in code
