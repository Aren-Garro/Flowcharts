# ISO 5807 Flowchart Generator

**NLP-driven workflow visualization conforming to ISO 5807 standards**

Transform natural language workflow descriptions into professional, printable flowcharts with a simple command.

## Features

- 🧠 **Natural Language Processing**: Write workflows in plain English
- 📊 **ISO 5807 Compliant**: Industry-standard flowchart symbols
- 🎨 **Multiple Export Formats**: PNG, SVG, PDF, HTML
- ✅ **Automatic Validation**: Ensures flowchart correctness
- 🚀 **Plug & Play**: Simple input → clean output
- 📝 **Decision Support**: Automatic branch detection
- 🔄 **Loop Handling**: Recognizes iterative workflows

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/Aren-Garro/Flowcharts.git
cd Flowcharts

# Install dependencies
pip install -r requirements.txt

# Install spaCy language model (optional, for advanced NLP)
python -m spacy download en_core_web_sm

# For rendering (requires Node.js)
npm install -g @mermaid-js/mermaid-cli
```

### Basic Usage

#### 1. Create a workflow file (`workflow.txt`):

```
1. User logs into system
2. System authenticates credentials
3. Check if credentials are valid
   - If yes: Load user dashboard
   - If no: Display error message
4. Query user preferences from database
5. Display personalized dashboard
6. End
```

#### 2. Generate flowchart:

```bash
python -m cli.main generate workflow.txt -o output.png
```

#### 3. View output:

Your flowchart is ready in `output.png`!

## ISO 5807 Symbol Support

The generator automatically maps workflow actions to ISO 5807 standard symbols:

| Symbol | Shape | Use Case | Example |
|--------|-------|----------|----------|
| **Terminator** | Oval | Start/End points | "Start process", "End" |
| **Process** | Rectangle | Processing steps | "Validate input", "Calculate total" |
| **Decision** | Diamond | Conditional branching | "Is user authenticated?" |
| **Input/Output** | Parallelogram | Data I/O | "Read file", "Output result" |
| **Database** | Cylinder | Database operations | "Query database", "Save record" |
| **Display** | Hexagon | Screen output | "Show message", "Render page" |
| **Document** | Wavy Rectangle | Document generation | "Print report", "Export PDF" |
| **Predefined** | Double Rectangle | Sub-routines | "Call API", "Execute function" |
| **Manual** | Trapezoid | Manual operations | "Wait for approval" |

## Workflow Syntax

### Simple Linear Flow

```
1. Start
2. Read user input
3. Process data
4. Save results
5. End
```

### With Decision Points

```
1. Start application
2. Check if user is logged in
   - If yes: Show dashboard
   - If no: Redirect to login
3. End
```

### With Loops

```
1. Start
2. Initialize counter
3. Read next record
4. Process record
5. Check if more records exist
   - If yes: Return to step 3
   - If no: Continue
6. Generate summary
7. End
```

### Complex Example

```
1. User submits order
2. Validate order details
3. Check if items are in stock
   - If yes: Continue to step 4
   - If no: Display out-of-stock message and end
4. Calculate total price from database
5. Process payment
6. Check if payment successful
   - If yes: Generate invoice document
   - If no: Display payment error
7. Send confirmation email
8. End
```

## Project Structure

```
Flowcharts/
├── src/
│   ├── models.py              # Data models (Node, Connection, Flowchart)
│   ├── parser/
│   │   ├── nlp_parser.py      # Natural language parser
│   │   ├── workflow_analyzer.py # Semantic analysis
│   │   └── patterns.py        # Pattern definitions
│   ├── builder/
│   │   ├── graph_builder.py   # Graph construction
│   │   └── validator.py       # ISO 5807 validation
│   ├── generator/
│   │   └── mermaid_generator.py # Mermaid.js code generation
│   └── renderer/
│       └── image_renderer.py  # Multi-format export
├── cli/
│   └── main.py                # Command-line interface
├── tests/                     # Unit tests
├── examples/                  # Example workflows
└── docs/                      # Documentation
```

## Development Status

✅ Core data models  
✅ Pattern recognition system  
✅ NLP parser (spaCy integration)  
✅ Workflow analyzer  
🚧 Graph builder (in progress)  
🚧 Mermaid.js generator (in progress)  
⏳ Image renderer  
⏳ CLI interface  
⏳ Validation system  

## Roadmap

- [ ] Complete core engine
- [ ] Multi-format export (PNG, SVG, PDF)
- [ ] Interactive HTML viewer
- [ ] Theme support
- [ ] Swimlane diagrams
- [ ] Web API interface
- [ ] VS Code extension

## Contributing

Contributions welcome! Please feel free to submit a Pull Request.

## License

MIT License - See LICENSE file for details

## Author

Aren Garro - [GitHub](https://github.com/Aren-Garro)

## Acknowledgments

- ISO 5807:1985 Standard for flowchart symbols
- [Mermaid.js](https://mermaid.js.org/) for diagram rendering
- [spaCy](https://spacy.io/) for NLP capabilities
