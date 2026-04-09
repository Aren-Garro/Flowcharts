"""Tests for Mermaid generator."""

from src.builder.graph_builder import GraphBuilder
from src.generator.mermaid_generator import MermaidGenerator
from src.models import Connection, Flowchart, FlowchartNode, NodeType
from src.parser.nlp_parser import NLPParser


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
    assert "curve" in code
    assert "basis" in code


def test_generate_with_theme_respects_direction_and_groups():
    flowchart = Flowchart(
        title="SOP Flow",
        nodes=[
            FlowchartNode(id="A", node_type=NodeType.PROCESS, label="Receive request", group="Phase 1: Intake"),
            FlowchartNode(id="B", node_type=NodeType.PROCESS, label="Validate request", group="Phase 1: Intake"),
            FlowchartNode(id="C", node_type=NodeType.PROCESS, label="Prepare response", group="Phase 2: Fulfillment"),
        ],
        connections=[
            Connection(from_node="A", to_node="B"),
            Connection(from_node="B", to_node="C"),
        ],
    )

    generator = MermaidGenerator()
    code = generator.generate_with_theme(flowchart, theme="neutral", direction="LR")

    assert "flowchart LR" in code
    assert '["Phase 1: Intake"]' in code
    assert '["Phase 2: Fulfillment"]' in code


def test_generator_decodes_html_entities_in_labels():
    flowchart = Flowchart(
        title="Entity Test",
        nodes=[
            FlowchartNode(id="START", node_type=NodeType.TERMINATOR, label="Don&#39;t Start"),
            FlowchartNode(id="END", node_type=NodeType.TERMINATOR, label="Finish"),
        ],
        connections=[Connection(from_node="START", to_node="END", label="it&#39;s ok")],
    )

    generator = MermaidGenerator()
    code = generator.generate(flowchart)

    assert "Don&#39;t" not in code
    assert "it&#39;s ok" not in code
    assert "Don't Start" in code
    assert "it's ok" in code


def test_generator_normalizes_double_quotes_for_mermaid_parse_safety():
    flowchart = Flowchart(
        title="Quote Test",
        nodes=[
            FlowchartNode(
                id="A",
                node_type=NodeType.PROCESS,
                label='Click Next Select "repair your computer"',
            ),
            FlowchartNode(id="B", node_type=NodeType.TERMINATOR, label="End"),
        ],
        connections=[Connection(from_node="A", to_node="B", label='User said "yes"')],
    )

    generator = MermaidGenerator()
    code = generator.generate(flowchart)

    assert '\\"' not in code
    assert '"repair your computer"' not in code
    assert "'repair your computer'" in code
    assert "'yes'" in code
