# Advanced Usage Guide

## Table of Contents

1. [Programmatic Usage](#programmatic-usage)
2. [Advanced Workflow Syntax](#advanced-workflow-syntax)
3. [Customization](#customization)
4. [Integration Examples](#integration-examples)
5. [Troubleshooting](#troubleshooting)

---

## Programmatic Usage

### Basic Python API

```python
from src.parser.nlp_parser import NLPParser
from src.builder.graph_builder import GraphBuilder
from src.generator.mermaid_generator import MermaidGenerator
from src.renderer.image_renderer import ImageRenderer

# Parse workflow text
workflow_text = """
1. Start
2. Process data
3. Check if valid
   - If yes: Save result
   - If no: Report error
4. End
"""

parser = NLPParser(use_spacy=True)
steps = parser.parse(workflow_text)

# Build flowchart
builder = GraphBuilder()
flowchart = builder.build(steps, title="My Process")

# Generate Mermaid code
generator = MermaidGenerator()
mermaid_code = generator.generate(flowchart, direction="TD")

# Render to image
renderer = ImageRenderer()
renderer.render(
    mermaid_code,
    "output.png",
    format="png",
    width=3000,
    height=2000
)
```

### Validation Example

```python
from src.builder.validator import ISO5807Validator

# Validate flowchart
validator = ISO5807Validator()
is_valid, errors, warnings = validator.validate(flowchart)

if is_valid:
    print("Flowchart is ISO 5807 compliant")
else:
    print("Validation errors:")
    for error in errors:
        print(f"  - {error}")

if warnings:
    print("Warnings:")
    for warning in warnings:
        print(f"  - {warning}")
```

### Custom Node Creation

```python
from src.models import FlowchartNode, Connection, Flowchart, NodeType

# Create custom flowchart manually
flowchart = Flowchart(title="Custom Flow")

# Add nodes
start = FlowchartNode(
    id="START",
    node_type=NodeType.TERMINATOR,
    label="Start Process"
)

process = FlowchartNode(
    id="PROC1",
    node_type=NodeType.PROCESS,
    label="Execute Task"
)

end = FlowchartNode(
    id="END",
    node_type=NodeType.TERMINATOR,
    label="End Process"
)

flowchart.add_node(start)
flowchart.add_node(process)
flowchart.add_node(end)

# Add connections
flowchart.add_connection(Connection(
    from_node="START",
    to_node="PROC1"
))

flowchart.add_connection(Connection(
    from_node="PROC1",
    to_node="END"
))
```

---

## Advanced Workflow Syntax

### Nested Decisions

```
1. Start
2. Check user type
   - If admin: Check permissions
     - If granted: Access admin panel
     - If denied: Show error
   - If regular: Show user dashboard
3. End
```

### Multiple End Points

```
1. Start
2. Validate input
3. Check if valid
   - If yes: Continue to step 4
   - If no: End with error
4. Process data
5. End successfully
```

### Parallel Paths

```
1. Start
2. Split into parallel tasks
   - Task A: Process dataset A
   - Task B: Process dataset B
3. Wait for both tasks
4. Merge results
5. End
```

### Complex Loops

```
1. Start
2. Initialize batch processor
3. Read next batch from database
4. Check if batch exists
   - If yes: Continue
   - If no: Go to step 9
5. Process batch
6. Check if errors occurred
   - If yes: Log error and continue
   - If no: Continue
7. Save results to database
8. Return to step 3
9. Generate summary report
10. End
```

### Error Handling Patterns

```
1. Start
2. Try to connect to database
3. Check if connection successful
   - If yes: Continue to step 4
   - If no: Wait 5 seconds and retry step 2
4. Query data from database
5. Check if query successful
   - If yes: Process results
   - If no: Log error and end
6. Display results
7. End
```

---

## Customization

### Custom Themes

```python
generator = MermaidGenerator()

# Available themes
themes = ["default", "forest", "dark", "neutral"]

for theme in themes:
    code = generator.generate_with_theme(flowchart, theme=theme)
    renderer.render(code, f"output_{theme}.png", theme=theme)
```

### Custom Symbol Mapping

Extend pattern recognition:

```python
from src.parser.patterns import WorkflowPatterns

# Add custom verbs
WorkflowPatterns.PROCESS_VERBS.extend([
    'synthesize', 'aggregate', 'consolidate'
])

WorkflowPatterns.DATABASE_VERBS.extend([
    'upsert', 'merge', 'replicate'
])
```

### Custom Output Formats

```python
class CustomRenderer(ImageRenderer):
    def render_pdf_with_metadata(self, mermaid_code, output_path, metadata):
        # Custom PDF generation with metadata
        pass
```

---

## Integration Examples

### Flask Web API

```python
from flask import Flask, request, send_file
from src.parser.nlp_parser import NLPParser
from src.builder.graph_builder import GraphBuilder
from src.generator.mermaid_generator import MermaidGenerator
from src.renderer.image_renderer import ImageRenderer
import tempfile

app = Flask(__name__)

@app.route('/generate', methods=['POST'])
def generate_flowchart():
    workflow_text = request.json.get('workflow')
    
    # Parse and build
    parser = NLPParser(use_spacy=True)
    steps = parser.parse(workflow_text)
    builder = GraphBuilder()
    flowchart = builder.build(steps)
    
    # Generate
    generator = MermaidGenerator()
    code = generator.generate(flowchart)
    
    # Render to temp file
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        renderer = ImageRenderer()
        renderer.render(code, tmp.name)
        return send_file(tmp.name, mimetype='image/png')

if __name__ == '__main__':
    app.run(debug=True)
```

### GitHub Actions Integration

```yaml
name: Generate Flowcharts

on:
  push:
    paths:
      - 'workflows/*.txt'

jobs:
  generate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Setup Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.10'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          python -m spacy download en_core_web_sm
          npm install -g @mermaid-js/mermaid-cli
      
      - name: Generate flowcharts
        run: |
          for file in workflows/*.txt; do
            python -m cli.main generate "$file" -o "output/$(basename "$file" .txt).png"
          done
      
      - name: Upload artifacts
        uses: actions/upload-artifact@v2
        with:
          name: flowcharts
          path: output/*.png
```

### Jupyter Notebook Usage

```python
# In Jupyter notebook
from IPython.display import Image, display
from src.parser.nlp_parser import NLPParser
from src.builder.graph_builder import GraphBuilder
from src.generator.mermaid_generator import MermaidGenerator
from src.renderer.image_renderer import ImageRenderer

# Define workflow
workflow = """
1. Load dataset
2. Preprocess data
3. Train model
4. Evaluate performance
5. Check if accuracy is acceptable
   - If yes: Deploy model
   - If no: Return to step 3 with different parameters
6. End
"""

# Generate
parser = NLPParser(use_spacy=True)
steps = parser.parse(workflow)
builder = GraphBuilder()
flowchart = builder.build(steps, title="ML Pipeline")
generator = MermaidGenerator()
code = generator.generate(flowchart)

# Render and display
renderer = ImageRenderer()
renderer.render(code, "ml_pipeline.png")
display(Image(filename="ml_pipeline.png"))
```

### VS Code Extension (Concept)

```json
{
  "contributes": {
    "commands": [
      {
        "command": "flowchart.generate",
        "title": "Generate Flowchart from Selection"
      }
    ],
    "keybindings": [
      {
        "command": "flowchart.generate",
        "key": "ctrl+shift+f",
        "when": "editorTextFocus"
      }
    ]
  }
}
```

---

## Troubleshooting

### Performance Issues

**Problem**: Slow parsing for large workflows

**Solution**: Disable spaCy for simple workflows

```python
parser = NLPParser(use_spacy=False)  # Use pattern-based parsing
```

### Memory Issues

**Problem**: High memory usage with large images

**Solution**: Reduce output dimensions

```bash
python -m cli.main generate workflow.txt -o output.png --width 2000 --height 1500
```

### Layout Issues

**Problem**: Overlapping nodes

**Solution**: Use left-to-right layout for wide flowcharts

```bash
python -m cli.main generate workflow.txt -o output.png --direction LR
```

### Validation Failures

**Problem**: "Decision node has fewer than 2 branches"

**Solution**: Ensure all decision steps have explicit branches:

```
# ❌ Incorrect
3. Check if valid
4. Continue processing

# ✅ Correct
3. Check if valid
   - If yes: Continue processing
   - If no: Stop
```

### Rendering Failures

**Problem**: "mmdc not found"

**Solution**:

```bash
# Install mermaid-cli globally
npm install -g @mermaid-js/mermaid-cli

# Or use local installation
npx @mermaid-js/mermaid-cli -i input.mmd -o output.png
```

**Alternative**: Generate HTML instead

```bash
python -m cli.main generate workflow.txt -o output.html
```

### Import Errors

**Problem**: "No module named 'src'"

**Solution**: Ensure you're running from project root

```bash
cd /path/to/Flowcharts
python -m cli.main generate workflow.txt -o output.png
```

---

## Best Practices

### 1. Version Control

Store workflow files in version control:

```
project/
  workflows/
    login_flow.txt
    payment_flow.txt
    signup_flow.txt
  output/
    login_flow.png
    payment_flow.png
    signup_flow.png
```

### 2. Automated Generation

Use pre-commit hooks:

```bash
#!/bin/bash
# .git/hooks/pre-commit

for file in workflows/*.txt; do
  python -m cli.main generate "$file" -o "docs/diagrams/$(basename "$file" .txt).png"
done

git add docs/diagrams/
```

### 3. Documentation Integration

Embed in markdown documentation:

```markdown
## Login Flow

![Login Flowchart](diagrams/login_flow.png)

The login process follows these steps:
1. User enters credentials
2. System validates...
```

### 4. Testing

Validate workflows in CI/CD:

```bash
# In CI pipeline
python -m cli.main validate workflows/*.txt
```

### 5. Modular Workflows

Break complex processes into sub-workflows:

```
main_process.txt -> Calls authentication_flow
authentication_flow.txt -> Standalone validation process
payment_processing.txt -> Separate payment logic
```

---

## Additional Resources

- [ISO 5807 Specification](ISO_5807_SPEC.md)
- [Quick Start Guide](QUICK_START.md)
- [Example Workflows](../examples/)
- [Test Suite](../tests/)
