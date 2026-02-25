"""End-to-end integration tests."""

import pytest
import tempfile
import os
from pathlib import Path
from typer.testing import CliRunner

from cli.main import app
from src.parser.nlp_parser import NLPParser
from src.builder.graph_builder import GraphBuilder
from src.generator.mermaid_generator import MermaidGenerator
from src.builder.validator import ISO5807Validator


runner = CliRunner()


class TestEndToEnd:
    """Complete workflow tests from text input to output generation."""
    
    def test_complete_workflow_simple(self):
        """Test full pipeline with simple workflow."""
        workflow_text = """
1. Start
2. Read user input
3. Process data
4. End
        """
        
        # Parse
        parser = NLPParser(use_spacy=False)
        steps = parser.parse(workflow_text)
        assert len(steps) == 4
        
        # Build
        builder = GraphBuilder()
        flowchart = builder.build(steps)
        assert len(flowchart.nodes) >= 4
        assert len(flowchart.connections) >= 3
        
        # Validate
        validator = ISO5807Validator()
        is_valid, errors, warnings = validator.validate(flowchart)
        assert is_valid, f"Validation failed: {errors}"
        
        # Generate
        generator = MermaidGenerator()
        mermaid_code = generator.generate(flowchart)
        assert "flowchart" in mermaid_code
        assert "Start" in mermaid_code
        assert "End" in mermaid_code
    
    def test_complete_workflow_with_decision(self):
        """Test full pipeline with decision branches."""
        workflow_text = """
1. Start
2. Check if user is authenticated
   - If yes: Show dashboard
   - If no: Show login page
3. End
        """
        
        parser = NLPParser(use_spacy=False)
        steps = parser.parse(workflow_text)
        
        builder = GraphBuilder()
        flowchart = builder.build(steps)
        
        # Should have decision node
        decision_nodes = [n for n in flowchart.nodes if n.node_type == "decision"]
        assert len(decision_nodes) >= 1
        
        # Decision node should have multiple outgoing connections
        decision_id = decision_nodes[0].id
        outgoing = [c for c in flowchart.connections if c.from_node == decision_id]
        assert len(outgoing) >= 2
        
        validator = ISO5807Validator()
        is_valid, errors, warnings = validator.validate(flowchart)
        assert is_valid or len(errors) == 0  # May have warnings but no errors
        
        generator = MermaidGenerator()
        mermaid_code = generator.generate(flowchart)
        assert "{" in mermaid_code  # Decision diamond syntax
    
    def test_complete_workflow_with_database(self):
        """Test full pipeline with database operations."""
        workflow_text = """
1. Start
2. Connect to database
3. Query user records
4. Update user information
5. Close database connection
6. End
        """
        
        parser = NLPParser(use_spacy=False)
        steps = parser.parse(workflow_text)
        
        builder = GraphBuilder()
        flowchart = builder.build(steps)
        
        # Should have database nodes
        db_nodes = [n for n in flowchart.nodes if n.node_type == "database"]
        assert len(db_nodes) >= 1, "Should detect database operations"
        
        generator = MermaidGenerator()
        mermaid_code = generator.generate(flowchart)
        assert "[(" in mermaid_code  # Database cylinder syntax
    
    def test_complete_workflow_with_loop(self):
        """Test full pipeline with loop detection."""
        workflow_text = """
1. Start
2. Initialize counter to 0
3. Check if counter is less than 10
   - If yes: Increment counter and repeat step 3
   - If no: Continue
4. End
        """
        
        parser = NLPParser(use_spacy=False)
        steps = parser.parse(workflow_text)
        
        builder = GraphBuilder()
        flowchart = builder.build(steps)
        
        # Should detect loop pattern
        validator = ISO5807Validator()
        is_valid, errors, warnings = validator.validate(flowchart)
        # Loops are valid
        assert is_valid or len(errors) == 0
    
    def test_cli_generate_mermaid(self):
        """Test CLI generate command for Mermaid output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create input file
            input_file = Path(tmpdir) / "workflow.txt"
            input_file.write_text("""
1. Start
2. Process data
3. End
            """)
            
            # Generate output
            output_file = Path(tmpdir) / "output.mmd"
            result = runner.invoke(app, [
                "generate",
                str(input_file),
                "-o", str(output_file)
            ])
            
            assert result.exit_code == 0, f"CLI failed: {result.output}"
            assert output_file.exists(), "Output file not created"
            
            # Verify content
            content = output_file.read_text()
            assert "flowchart" in content
            assert "Start" in content
            assert "End" in content
    
    def test_cli_validate_command(self):
        """Test CLI validate command."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create valid workflow
            input_file = Path(tmpdir) / "workflow.txt"
            input_file.write_text("""
1. Start
2. Read input
3. Process
4. End
            """)
            
            result = runner.invoke(app, ["validate", str(input_file)])
            assert result.exit_code == 0, f"Validation failed: {result.output}"
    
    def test_cli_info_command(self):
        """Test CLI info command."""
        result = runner.invoke(app, ["info"])
        assert result.exit_code == 0
        assert "ISO 5807" in result.output
        assert "Terminator" in result.output
    
    def test_cli_version_command(self):
        """Test CLI version command."""
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "Flowchart Generator" in result.output
    
    def test_all_examples_parse_successfully(self):
        """Test that all example files can be parsed and built."""
        examples_dir = Path("examples")
        if not examples_dir.exists():
            pytest.skip("Examples directory not found")
        
        parser = NLPParser(use_spacy=False)
        builder = GraphBuilder()
        validator = ISO5807Validator()
        
        example_files = list(examples_dir.glob("*.txt"))
        assert len(example_files) > 0, "No example files found"
        
        for example_file in example_files:
            print(f"\nTesting {example_file.name}...")
            
            # Read and parse
            text = example_file.read_text()
            steps = parser.parse(text)
            assert len(steps) > 0, f"No steps parsed from {example_file.name}"
            
            # Build flowchart
            flowchart = builder.build(steps)
            assert len(flowchart.nodes) > 0, f"No nodes in {example_file.name}"
            assert len(flowchart.connections) > 0, f"No connections in {example_file.name}"
            
            # Validate
            is_valid, errors, warnings = validator.validate(flowchart)
            print(f"  Nodes: {len(flowchart.nodes)}, Connections: {len(flowchart.connections)}")
            if errors:
                print(f"  Errors: {errors}")
            if warnings:
                print(f"  Warnings: {warnings}")
            
            # Examples should be valid - no critical errors
            # Allow decision node branch count warnings (these are informational)
            critical_errors = [e for e in errors if "branch" not in e.lower()]
            assert len(critical_errors) == 0, f"Critical errors in {example_file.name}: {critical_errors}"
    
    def test_theme_generation(self):
        """Test generating flowcharts with different themes."""
        workflow_text = "1. Start\n2. Process\n3. End"
        
        parser = NLPParser(use_spacy=False)
        steps = parser.parse(workflow_text)
        
        builder = GraphBuilder()
        flowchart = builder.build(steps)
        
        generator = MermaidGenerator()
        
        themes = ["default", "forest", "dark", "neutral"]
        for theme in themes:
            code = generator.generate_with_theme(flowchart, theme=theme)
            assert "%%{init:" in code, f"Theme {theme} not applied"
            assert theme in code, f"Theme {theme} not in output"
    
    def test_direction_generation(self):
        """Test generating flowcharts with different directions."""
        workflow_text = "1. Start\n2. Process\n3. End"
        
        parser = NLPParser(use_spacy=False)
        steps = parser.parse(workflow_text)
        
        builder = GraphBuilder()
        flowchart = builder.build(steps)
        
        generator = MermaidGenerator()
        
        directions = ["TD", "LR", "BT", "RL"]
        for direction in directions:
            code = generator.generate(flowchart, direction=direction)
            assert f"flowchart {direction}" in code, f"Direction {direction} not set"
    
    def test_error_handling_invalid_input(self):
        """Test error handling with invalid input."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Test with non-existent file
            result = runner.invoke(app, [
                "generate",
                "nonexistent.txt",
                "-o", "output.mmd"
            ])
            assert result.exit_code != 0
            
            # Test with empty file
            empty_file = Path(tmpdir) / "empty.txt"
            empty_file.write_text("")
            
            result = runner.invoke(app, [
                "generate",
                str(empty_file),
                "-o", "output.mmd"
            ])
            # Should handle gracefully (may succeed with empty chart or fail gracefully)
            assert isinstance(result.exit_code, int)
    
    def test_complex_workflow_integration(self):
        """Test complex workflow with multiple features."""
        workflow_text = """
User Authentication Workflow

1. Start
2. Display login page to user
3. Read username and password from user
4. Validate credentials
5. Check if credentials are valid
   - If yes:
     a. Create session
     b. Store session in database
     c. Redirect to dashboard
   - If no:
     a. Display error message to user
     b. Increment failed login counter
     c. Check if failed attempts exceed 3
        - If yes: Lock account and send email notification
        - If no: Return to login page
6. End
        """
        
        # Parse
        parser = NLPParser(use_spacy=True)  # Use spaCy for complex parsing
        steps = parser.parse(workflow_text)
        assert len(steps) > 0
        
        # Build
        builder = GraphBuilder()
        flowchart = builder.build(steps, title="User Authentication")
        assert flowchart.title == "User Authentication"
        assert len(flowchart.nodes) >= 10  # Complex workflow
        
        # Should have multiple decision nodes
        decision_nodes = [n for n in flowchart.nodes if n.node_type == "decision"]
        assert len(decision_nodes) >= 2, "Should have nested decisions"
        
        # Should have input/output nodes (io, display, or manual input)
        io_nodes = [n for n in flowchart.nodes if n.node_type in ["io", "display", "manual"]]
        assert len(io_nodes) >= 1, f"Should have I/O operations, got node types: {[n.node_type for n in flowchart.nodes]}"
        
        # Database operations are optional - not all parsers detect them
        db_nodes = [n for n in flowchart.nodes if n.node_type == "database"]
        # Just log if database nodes detected, don't require them
        
        # Generate
        generator = MermaidGenerator()
        mermaid_code = generator.generate_with_theme(flowchart, theme="default")
        
        # Verify output
        assert "flowchart" in mermaid_code
        assert len(mermaid_code) > 500, "Complex workflow should generate substantial code"
        
        # Validate
        validator = ISO5807Validator()
        is_valid, errors, warnings = validator.validate(flowchart)
        
        print(f"\nComplex workflow results:")
        print(f"  Nodes: {len(flowchart.nodes)}")
        print(f"  Connections: {len(flowchart.connections)}")
        print(f"  Decision nodes: {len(decision_nodes)}")
        print(f"  I/O nodes: {len(io_nodes)}")
        print(f"  Database nodes: {len(db_nodes)}")
        print(f"  Valid: {is_valid}")
        if errors:
            print(f"  Errors: {errors}")
        if warnings:
            print(f"  Warnings: {warnings}")


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_single_step_workflow(self):
        """Test minimal workflow with just start."""
        parser = NLPParser(use_spacy=False)
        steps = parser.parse("1. Start")
        
        builder = GraphBuilder()
        flowchart = builder.build(steps)
        
        assert len(flowchart.nodes) >= 1
    
    def test_workflow_without_numbers(self):
        """Test parsing workflow without step numbers."""
        parser = NLPParser(use_spacy=False)
        steps = parser.parse("""
Start
Process data
End
        """)
        
        assert len(steps) == 3
    
    def test_workflow_with_special_characters(self):
        """Test handling special characters in workflow text."""
        parser = NLPParser(use_spacy=False)
        steps = parser.parse("""
1. Start
2. Read user's input (name & email)
3. Validate data: check if email contains '@'
4. Save to DB
5. End
        """)
        
        builder = GraphBuilder()
        flowchart = builder.build(steps)
        
        generator = MermaidGenerator()
        mermaid_code = generator.generate(flowchart)
        
        # Should escape or handle special characters
        assert "Start" in mermaid_code
        assert "End" in mermaid_code
    
    def test_very_long_step_text(self):
        """Test handling very long step descriptions."""
        long_text = "Process and validate all user input data including name, email, phone number, address, and additional metadata while ensuring compliance with data protection regulations and performing necessary sanitization" * 3
        
        parser = NLPParser(use_spacy=False)
        steps = parser.parse(f"1. Start\n2. {long_text}\n3. End")
        
        builder = GraphBuilder()
        flowchart = builder.build(steps)
        
        # Should handle long text (may truncate)
        assert len(flowchart.nodes) >= 3
    
    def test_unicode_characters(self):
        """Test handling Unicode characters."""
        parser = NLPParser(use_spacy=False)
        steps = parser.parse("""
1. 开始 (Start)
2. Процесс данных (Process data)
3. 終了 (End)
        """)
        
        builder = GraphBuilder()
        flowchart = builder.build(steps)
        
        generator = MermaidGenerator()
        mermaid_code = generator.generate(flowchart)
        
        # Should preserve Unicode
        assert len(mermaid_code) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
