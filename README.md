# ISO 5807 Flowchart Generator

🚀 **Production Ready** | ✅ **100+ Tests Passing** | 📊 **ISO 5807 Compliant** | 📄 **Import Any Document** | 🌐 **Web Interface**

**NLP-driven workflow visualization conforming to ISO 5807 standards**

Transform natural language workflow descriptions into professional, printable flowcharts. **Now with document import (PDF, DOCX, TXT) and local web interface!**

> **Status:** Production-ready with comprehensive testing and cross-platform support. See [PROJECT_STATUS.md](PROJECT_STATUS.md) for detailed metrics.

## ✨ New Features (Week 1-2 Complete)

### 📥 Document Import
- **Import any document**: PDF, DOCX, DOC, TXT, MD
- **Smart workflow detection**: Automatically finds and extracts workflows
- **Clipboard support**: Paste directly from anywhere
- **Preview mode**: Review extracted workflow before generating

```bash
# Import any document - it just works!
python -m cli.main import process.pdf
python -m cli.main import workflow.docx
python -m cli.main import --clipboard
```

### 🌐 Local Web Interface
- **Drag & drop**: Upload documents in your browser
- **Real-time preview**: See extracted workflow instantly
- **One-click generation**: Download flowcharts in any format
- **No internet required**: Runs 100% locally

```bash
# Start web interface
python web/app.py
# Visit http://localhost:5000
```

**See [IMPORT_GUIDE.md](IMPORT_GUIDE.md) for complete documentation!**

---

## Features

- 🧠 **Natural Language Processing**: Write workflows in plain English
- 📊 **ISO 5807 Compliant**: Industry-standard flowchart symbols
- 📄 **Import Documents**: PDF, DOCX, TXT, MD, or clipboard
- 🌐 **Web Interface**: Drag-and-drop browser interface
- 🔍 **Smart Detection**: Automatically finds workflows in documents
- 🎨 **Multiple Export Formats**: PNG, SVG, PDF, HTML, Mermaid
- ✅ **Automatic Validation**: Ensures flowchart correctness
- 🚀 **Plug & Play**: Simple input → clean output
- 📝 **Decision Support**: Automatic branch detection
- 🔄 **Loop Handling**: Recognizes iterative workflows
- 🧪 **Comprehensive Testing**: 100+ tests with 85% code coverage
- 🔧 **Cross-Platform**: Windows, macOS, Linux support
- 🎯 **CLI Interface**: Rich terminal output with progress indicators

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/Aren-Garro/Flowcharts.git
cd Flowcharts

# Automated setup (Linux/Mac)
chmod +x setup_dev.sh
./setup_dev.sh

# Or Windows
setup_dev.bat

# Manual installation
pip install -r requirements.txt

# Install spaCy language model (optional, for advanced NLP)
python -m spacy download en_core_web_sm

# For rendering (requires Node.js)
npm install -g @mermaid-js/mermaid-cli
```

### Method 1: Import Any Document (Easiest)

```bash
# Import PDF
python -m cli.main import document.pdf

# Import Word document
python -m cli.main import process.docx

# Import from clipboard
python -m cli.main import --clipboard

# With preview and options
python -m cli.main import process.pdf --preview -o flowchart.svg --theme dark
```

### Method 2: Web Interface (Most User-Friendly)

```bash
# Start local web server
python web/app.py
```

Then visit **http://localhost:5000** and:
1. Drag & drop your document (PDF, DOCX, TXT, MD)
2. Review extracted workflow
3. Click "Generate Flowchart"
4. Download your flowchart!

### Method 3: Traditional Workflow File

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

### CLI Commands

```bash
# NEW: Import any document
python -m cli.main import document.pdf
python -m cli.main import workflow.docx --preview
python -m cli.main import --clipboard -o output.png

# Generate from workflow text file
python -m cli.main generate input.txt -o output.png

# Validate ISO 5807 compliance
python -m cli.main validate input.txt

# Show ISO 5807 information
python -m cli.main info

# Display version
python -m cli.main version

# Additional options
python -m cli.main import doc.pdf -o output.svg --theme dark --direction LR
```

## Supported Document Formats

| Format | Extension | Library | Features |
|--------|-----------|---------|----------|
| PDF | .pdf | PyPDF2/pdfplumber | Text extraction, metadata |
| Word | .docx, .doc | python-docx | Paragraphs, tables, lists |
| Text | .txt | Built-in | Fast, no dependencies |
| Markdown | .md | Built-in | Headers, lists |
| Clipboard | - | pyperclip | Direct paste |

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
│   ├── renderer/
│   │   └── image_renderer.py  # Multi-format export
│   └── importers/             # NEW: Document parsing
│       ├── document_parser.py
│       └── content_extractor.py
├── cli/
│   ├── main.py                # Command-line interface
│   └── import_command.py      # NEW: Import command
├── web/                       # NEW: Web interface
│   ├── app.py
│   └── templates/
│       └── index.html
├── tests/                     # Comprehensive test suite (100+ tests)
├── examples/                  # Example workflows
└── docs/                      # Documentation
```

## Development Status

**✅ Version 0.2.0 - Production Ready with Import Features**

All core features implemented and thoroughly tested:

✅ Core data models  
✅ Pattern recognition system  
✅ NLP parser (spaCy integration)  
✅ Workflow analyzer  
✅ Graph builder  
✅ Mermaid.js generator  
✅ Image renderer (PNG, SVG, PDF, HTML)  
✅ CLI interface  
✅ ISO 5807 validation system  
✅ **Document parser (PDF, DOCX, TXT, MD)** ⭐ NEW  
✅ **Smart content extraction** ⭐ NEW  
✅ **Import command with auto-detection** ⭐ NEW  
✅ **Local web interface** ⭐ NEW  
✅ Comprehensive test suite (100+ tests)  
✅ CI/CD pipeline (GitHub Actions)  
✅ Cross-platform support  
✅ Production-grade error handling  

### Test Coverage

- **Unit Tests**: 82+ tests covering all core components
- **E2E Tests**: 25+ integration tests
- **Edge Cases**: 10+ tests for special scenarios
- **Code Coverage**: ~85%
- **Platforms**: Windows, macOS, Linux
- **Python Versions**: 3.9, 3.10, 3.11, 3.12

### Performance Metrics

- Document parsing: <1s for most PDFs/DOCX
- Workflow extraction: <100ms
- Simple workflow (5 steps): <100ms
- Complex workflow (20 steps): <500ms
- Very large workflow (100+ steps): <3s
- Image rendering: 2-5s (depends on mermaid-cli)

## Examples

The repository includes 6 validated example workflows:

- `simple_workflow.txt` - Basic linear flow
- `user_authentication.txt` - Decision branches
- `database_operations.txt` - Database symbols
- `data_processing_pipeline.txt` - Complex workflow
- `complex_decision.txt` - Nested decisions
- `loop_example.txt` - Loop patterns

Try them:
```bash
python -m cli.main generate examples/simple_workflow.txt -o test.png
# Or import and auto-process
python -m cli.main import examples/simple_workflow.txt
```

## Testing

Run the comprehensive test suite:

```bash
# Run all tests
python run_all_tests.py

# Run specific tests
pytest tests/test_e2e.py -v

# Validate code syntax
python validate_code.py

# Quick validation
python test_runner.py
```

## Roadmap

### Completed (Week 1-2)
- ✅ Document parser (PDF, DOCX, TXT, MD)
- ✅ Smart content extraction
- ✅ Enhanced CLI with auto-detection
- ✅ Local web interface with drag-and-drop

### Upcoming (Week 3-4)
- [ ] Cloud storage integration (Google Drive, Dropbox, OneDrive)
- [ ] Email integration
- [ ] Browser extension
- [ ] Desktop context menu integration
- [ ] Executable installers (Windows, macOS, Linux)

### Future Enhancements
- [ ] Additional output formats (BPMN, PlantUML, Visio XML)
- [ ] Performance optimization for very large workflows (>100 steps)
- [ ] Swimlane/actor support
- [ ] Custom theme system
- [ ] Template library
- [ ] VS Code extension
- [ ] Multi-language support
- [ ] REST API service

## Contributing

Contributions welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Quick Start for Contributors

```bash
# Clone and setup
git clone https://github.com/Aren-Garro/Flowcharts.git
cd Flowcharts
./setup_dev.sh  # or setup_dev.bat on Windows

# Run tests
python run_all_tests.py

# Before committing
black src/ cli/ tests/
flake8 src/ cli/ tests/ --max-line-length=120
pytest tests/ -v
```

## Documentation

- **[Import Guide](IMPORT_GUIDE.md)** ⭐ NEW - Complete guide for document import and web interface
- [Quick Start Guide](docs/QUICK_START.md)
- [API Reference](docs/API_REFERENCE.md)
- [Tutorial](docs/TUTORIAL.md)
- [Project Status](PROJECT_STATUS.md)
- [Windows Setup](WINDOWS_QUICK_START.md)
- [Testing Report](TESTING_REPORT.md)

## Known Limitations

1. **Image rendering requires mermaid-cli** - Workaround: Use .mmd or .html output formats
2. **spaCy model optional** - Graceful fallback to pattern-based parsing
3. **Large/complex diagrams may timeout** - 60s timeout with clear error message
4. **PDF must be text-based** - Scanned PDFs without OCR layer won't work
5. **DOCX only (not DOC)** - Old .doc format has limited support

## License

MIT License - See [LICENSE](LICENSE) file for details

## Author

**Aren Garro** - [GitHub](https://github.com/Aren-Garro)

## Acknowledgments

- ISO 5807:1985 Standard for flowchart symbols
- [Mermaid.js](https://mermaid.js.org/) for diagram rendering
- [spaCy](https://spacy.io/) for NLP capabilities
- [PyPDF2](https://pypdf2.readthedocs.io/) & [pdfplumber](https://github.com/jsvine/pdfplumber) for PDF parsing
- [python-docx](https://python-docx.readthedocs.io/) for Word document parsing

---

**Repository:** https://github.com/Aren-Garro/Flowcharts  
**Issues:** https://github.com/Aren-Garro/Flowcharts/issues  
**Last Updated:** February 23, 2026
