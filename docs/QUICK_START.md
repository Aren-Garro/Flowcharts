# Quick Start Guide

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/Aren-Garro/Flowcharts.git
cd Flowcharts
```

### 2. Set Up Python Environment

```bash
# Create virtual environment (recommended)
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Install spaCy Language Model (Optional)

For advanced NLP parsing:

```bash
python -m spacy download en_core_web_sm
```

### 4. Install Mermaid CLI (For Image Export)

Requires Node.js:

```bash
npm install -g @mermaid-js/mermaid-cli
```

## Your First Flowchart

### Step 1: Create Workflow File

Create a file called `my_workflow.txt`:

```
1. Start
2. User enters credentials
3. System validates credentials
4. Check if credentials are valid
   - If yes: Load dashboard
   - If no: Display error
5. End
```

### Step 2: Generate Flowchart

```bash
python -m cli.main generate my_workflow.txt -o my_flowchart.png
```

### Step 3: View Result

Open `my_flowchart.png` to see your flowchart!

## Command Reference

### Generate Flowchart

```bash
# Basic usage
python -m cli.main generate workflow.txt -o output.png

# Generate SVG (vector, scalable)
python -m cli.main generate workflow.txt -o output.svg

# Generate PDF
python -m cli.main generate workflow.txt -o output.pdf

# Generate interactive HTML
python -m cli.main generate workflow.txt -o output.html

# Generate raw Mermaid code
python -m cli.main generate workflow.txt -o output.mmd

# With theme
python -m cli.main generate workflow.txt -o output.png --theme dark

# Custom dimensions
python -m cli.main generate workflow.txt -o output.png --width 4000 --height 3000

# Left-to-right flow
python -m cli.main generate workflow.txt -o output.png --direction LR
```

### Validate Workflow

```bash
# Quick validation
python -m cli.main validate workflow.txt

# Verbose output
python -m cli.main validate workflow.txt --verbose
```

### View Symbol Information

```bash
python -m cli.main info
```

### Check Version

```bash
python -m cli.main version
```

## Workflow Syntax Guide

### Linear Flow

```
1. Start
2. Step one
3. Step two
4. Step three
5. End
```

### With Decisions

```
1. Start
2. Check condition
   - If yes: Do action A
   - If no: Do action B
3. End
```

### With Database Operations

```
1. Start
2. Query user data from database
3. Update record in database
4. Save to database
5. End
```

### With Loops

```
1. Start
2. Read next item
3. Process item
4. Check if more items
   - If yes: Return to step 2
   - If no: Continue
5. End
```

### Action Keywords

The parser automatically detects node types based on action verbs:

- **Process**: calculate, validate, transform, update, create
- **Input/Output**: read, write, input, output, send, receive
- **Database**: query, select, insert, update, delete, save
- **Display**: show, display, render, present
- **Document**: print, export, generate report
- **Decision**: check if, whether, is, does, can

## Examples

See the `examples/` directory for complete workflow examples:

- `simple_workflow.txt` - Basic linear flow
- `database_operations.txt` - Database interactions
- `complex_decision.txt` - Multiple decision points
- `loop_example.txt` - Iterative processing

## Troubleshooting

### "mmdc not found" Error

Install mermaid-cli:

```bash
npm install -g @mermaid-js/mermaid-cli
```

### spaCy Model Not Found

The system will fall back to pattern-based parsing. For better results, install:

```bash
python -m spacy download en_core_web_sm
```

### Import Errors

Make sure you're in the project root directory and virtual environment is activated:

```bash
cd Flowcharts
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

## Next Steps

- Read [ISO_5807_SPEC.md](ISO_5807_SPEC.md) for detailed standard information
- Check [USAGE.md](USAGE.md) for advanced usage patterns
- Run tests: `pytest tests/`
- Contribute: See main README for guidelines
