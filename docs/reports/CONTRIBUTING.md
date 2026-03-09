# Contributing to ISO 5807 Flowchart Generator

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to the project.

## Code of Conduct

Be respectful, inclusive, and collaborative. We're all here to build something useful.

## Getting Started

### 1. Fork and Clone

```bash
# Fork the repository on GitHub, then clone your fork
git clone https://github.com/YOUR-USERNAME/Flowcharts.git
cd Flowcharts

# Add upstream remote
git remote add upstream https://github.com/Aren-Garro/Flowcharts.git
```

### 2. Set Up Development Environment

**On Mac/Linux:**
```bash
chmod +x setup_dev.sh
./setup_dev.sh
```

**On Windows:**
```cmd
setup_dev.bat
```

**Manual Setup:**
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt
pip install pytest pytest-cov black flake8 isort

# Install spaCy model
python -m spacy download en_core_web_sm

# Install mermaid-cli (optional, for rendering)
npm install -g @mermaid-js/mermaid-cli
```

### 3. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

## Development Workflow

### Running Tests

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run specific test file
pytest tests/test_parser.py -v

# Run quick validation
python test_runner.py
```

### Code Style

We use:
- **Black** for code formatting
- **isort** for import sorting
- **flake8** for linting

```bash
# Format code
black src/ tests/ cli/

# Sort imports
isort src/ tests/ cli/

# Check linting
flake8 src/ tests/ cli/ --max-line-length=120

# Run all checks
black --check src/ tests/ cli/
isort --check-only src/ tests/ cli/
flake8 src/ tests/ cli/ --max-line-length=120
```

### Testing Your Changes

```bash
# Test with examples
python -m cli.main generate examples/simple_workflow.txt -o test_output.png
python -m cli.main validate examples/database_operations.txt

# Test edge cases
python -m cli.main generate examples/complex_decision.txt -o complex.svg --theme dark
```

## Types of Contributions

### 1. Bug Fixes

- Create an issue describing the bug
- Reference the issue in your PR
- Include test case that reproduces the bug
- Ensure all tests pass

### 2. New Features

- Discuss the feature in an issue first
- Follow existing code patterns
- Add tests for new functionality
- Update documentation

### 3. Documentation

- Fix typos and improve clarity
- Add examples and use cases
- Keep formatting consistent
- Test code examples

### 4. Performance Improvements

- Provide benchmarks showing improvement
- Ensure no functionality regression
- Document any API changes

## Pull Request Process

### 1. Before Submitting

- [ ] All tests pass: `pytest tests/`
- [ ] Code is formatted: `black src/ tests/ cli/`
- [ ] Imports are sorted: `isort src/ tests/ cli/`
- [ ] No linting errors: `flake8 src/ tests/ cli/`
- [ ] New tests added for new functionality
- [ ] Documentation updated
- [ ] Examples work correctly

### 2. Commit Messages

Use clear, descriptive commit messages:

```
Add support for swimlane diagrams

- Implement swimlane parser
- Add swimlane node types
- Update Mermaid generator
- Add tests and examples

Fixes #123
```

### 3. Submit Pull Request

1. Push your branch to your fork
2. Open a PR against `main` branch
3. Fill out the PR template
4. Link related issues
5. Wait for review

### 4. Code Review

- Address reviewer feedback
- Keep commits focused and logical
- Be responsive to comments
- Ask questions if unclear

## Project Structure

```
src/
  models.py              # Core data models
  parser/                # NLP parsing
    nlp_parser.py
    workflow_analyzer.py
    patterns.py
  builder/               # Graph construction
    graph_builder.py
    validator.py
  generator/             # Code generation
    mermaid_generator.py
  renderer/              # Output rendering
    image_renderer.py

cli/
  main.py                # CLI interface

tests/                   # Test suite
  test_parser.py
  test_builder.py
  test_generator.py

examples/                # Example workflows
docs/                    # Documentation
```

## Coding Guidelines

### Python Style

- Follow PEP 8
- Use type hints
- Write docstrings for public functions
- Keep functions focused and small
- Use meaningful variable names

### Example:

```python
from typing import List, Optional
from src.models import WorkflowStep, NodeType

def parse_workflow(text: str, use_spacy: bool = True) -> List[WorkflowStep]:
    """
    Parse workflow text into structured steps.
    
    Args:
        text: Raw workflow description text
        use_spacy: Whether to use spaCy for NLP parsing
        
    Returns:
        List of parsed workflow steps
        
    Raises:
        ValueError: If text is empty or invalid
    """
    if not text:
        raise ValueError("Workflow text cannot be empty")
    
    # Implementation
    steps = []
    # ...
    return steps
```

### Testing Guidelines

- Write tests for all new functionality
- Use descriptive test names
- Test edge cases and error conditions
- Keep tests isolated and independent
- Use fixtures for common setup

```python
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
    assert steps[0].text == "Start"
    assert steps[1].text == "Process data"
    assert steps[2].text == "End"
```

## Areas Needing Help

### High Priority

1. **Additional Output Formats**
   - BPMN export
   - PlantUML format
   - Visio XML

2. **Performance Optimization**
   - Caching for repeated operations
   - Parallel processing for large workflows
   - Memory optimization

3. **Enhanced Validation**
   - More ISO 5807 compliance checks
   - Best practice recommendations
   - Workflow complexity metrics

### Medium Priority

4. **Swimlane Support**
   - Actor/role-based swimlanes
   - Cross-functional flowcharts
   - Department-level grouping

5. **Theme System**
   - Custom color schemes
   - Corporate branding support
   - Accessibility themes (high contrast)

6. **Template Library**
   - Pre-built workflow templates
   - Industry-specific patterns
   - Common process templates

### Lower Priority

7. **Web Interface**
   - Browser-based editor
   - Real-time preview
   - Drag-and-drop interface

8. **VS Code Extension**
   - Syntax highlighting
   - Live preview
   - Quick commands

9. **Additional Language Support**
   - Multi-language workflow parsing
   - Internationalized output
   - Translation support

## Questions?

- **General Questions**: Open a [GitHub Discussion](https://github.com/Aren-Garro/Flowcharts/discussions)
- **Bug Reports**: Create an [Issue](https://github.com/Aren-Garro/Flowcharts/issues)
- **Feature Requests**: Open an [Issue](https://github.com/Aren-Garro/Flowcharts/issues) with `[Feature]` tag

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

## Recognition

Contributors will be acknowledged in:
- README.md
- Release notes
- Project documentation

Thank you for contributing! 

