# Document Import & Web Interface Guide

## 🚀 Quick Start

The Flowcharts tool now supports **importing any document** and features a **local web interface** for drag-and-drop flowchart generation!

## Installation

```bash
# Install all dependencies
pip install -r requirements.txt

# Install optional dependencies for full functionality
pip install PyPDF2 pdfplumber python-docx pyperclip flask flask-cors
```

---

## Method 1: Command Line Import (Fastest)

### Import Any Document

```bash
# Import PDF
python -m cli.main import document.pdf

# Import Word document
python -m cli.main import process.docx

# Import text/markdown
python -m cli.main import workflow.txt
python -m cli.main import readme.md

# Import from clipboard
python -m cli.main import --clipboard
```

### With Options

```bash
# Specify output file
python -m cli.main import document.pdf -o flowchart.png

# Choose output format
python -m cli.main import document.pdf -f svg
python -m cli.main import document.pdf -f pdf
python -m cli.main import document.pdf -f html

# Preview before generating
python -m cli.main import document.pdf --preview

# Change theme
python -m cli.main import document.pdf --theme dark

# Change direction (LR = left-right, TD = top-down)
python -m cli.main import document.pdf -d LR
```

### Complete Example

```bash
python -m cli.main import my_process.docx -o process_flow.svg --theme forest --preview
```

---

## Method 2: Local Web Interface (Most User-Friendly)

### Start the Web Server

```bash
python web/app.py
```

This will start a local server at **http://localhost:5000**

### Features

- 📎 **Drag & Drop** - Drop any PDF, DOCX, TXT, or MD file
- 📋 **Clipboard Support** - Paste workflow text directly
- 🔍 **Smart Detection** - Automatically finds workflow content
- 📊 **Live Preview** - See extracted workflow before generating
- ⚙️ **Format Options** - PNG, SVG, PDF, or HTML output
- 🎨 **Theme Selection** - Choose from 4 themes
- 📥 **Instant Download** - One-click flowchart generation

### Using the Web Interface

1. **Upload Document**
   - Drag and drop file onto upload area
   - OR click to browse files
   - OR paste from clipboard

2. **Review Extracted Workflow**
   - See workflow text preview
   - Check statistics (steps, decisions, confidence)

3. **Configure Options**
   - Choose output format (PNG, SVG, PDF, HTML)
   - Select theme (Default, Forest, Dark, Neutral)

4. **Generate**
   - Click "Generate Flowchart"
   - File downloads automatically

---

## Supported Document Formats

### PDF Files (.pdf)
- **Supports**: Text-based PDFs, scanned PDFs with OCR text layer
- **Best for**: Process documents, manuals, reports
- **Libraries**: PyPDF2 or pdfplumber (automatically detected)

```bash
python -m cli.main import procedure.pdf
```

### Word Documents (.docx, .doc)
- **Supports**: Modern Word documents (.docx)
- **Best for**: Business processes, SOPs, documentation
- **Extracts**: Paragraphs, tables, numbered lists

```bash
python -m cli.main import workflow.docx
```

### Text Files (.txt, .md)
- **Supports**: Plain text, Markdown
- **Best for**: Simple workflows, code documentation
- **Fastest**: No additional dependencies needed

```bash
python -m cli.main import steps.txt
python -m cli.main import process.md
```

### Clipboard
- **Supports**: Any text content
- **Best for**: Quick workflows, copy-paste from emails/web

```bash
python -m cli.main import --clipboard
```

---

## How Smart Detection Works

### Workflow Detection

The content extractor looks for:

1. **Numbered Steps**
   - `1. First step`
   - `2. Second step`
   - `3) Third step`

2. **Workflow Keywords**
   - start, begin, initialize
   - process, workflow, procedure
   - end, finish, complete

3. **Decision Points**
   - "If... then..."
   - "Check if..."
   - "Validate..."

4. **Flow Indicators**
   - Database operations
   - User input/output
   - Display/show actions

### Confidence Scoring

- **90-100%**: Clear numbered workflow with decisions
- **70-89%**: Well-structured with workflow keywords
- **50-69%**: Detected patterns but may need review
- **<50%**: Uncertain, preview recommended

Use `--preview` flag to review before generating!

---

## Examples

### Example 1: Import PDF Process Document

```bash
python -m cli.main import "Company Onboarding Process.pdf" -o onboarding.png --preview
```

**Output:**
```
📥 Smart Document Import

📄 Reading document: Company Onboarding Process.pdf
File: Company Onboarding Process.pdf
Pages: 5
Size: 248.3 KB
✓ Extracted 12847 characters

🔍 Detecting workflow content...
✓ Found workflow: Employee Onboarding Process (confidence: 95%)

Total lines: 15
Numbered steps: 12
Decision points: 3

[Preview shown]

Continue with this workflow? [Y/n]: y

✓ Parsed 12 workflow steps
✓ Created 14 nodes and 16 connections
✅ Success! Flowchart saved to: onboarding.png
```

### Example 2: Quick Clipboard Workflow

1. Copy workflow text from email/document
2. Run:
```bash
python -m cli.main import --clipboard -o quick_flow.svg
```

### Example 3: Word Document with Multiple Workflows

```bash
python -m cli.main import "Standard Operating Procedures.docx" --preview
```

The tool will:
- Detect all workflow sections
- Show the highest confidence workflow
- Allow you to confirm before generating

### Example 4: Batch Processing

```bash
# Process multiple PDFs
for file in *.pdf; do
    python -m cli.main import "$file" -o "${file%.pdf}.png"
done
```

---

## Advanced Usage

### Custom Output Directory

```bash
python -m cli.main import document.pdf -o output/flowcharts/result.png
```

### Different Formats for Same Source

```bash
# Generate PNG for sharing
python -m cli.main import process.docx -o process.png

# Generate SVG for editing
python -m cli.main import process.docx -o process.svg

# Generate PDF for printing
python -m cli.main import process.docx -o process.pdf

# Generate HTML for web
python -m cli.main import process.docx -o process.html
```

### API Usage (Web Interface)

```python
import requests

# Upload file
with open('document.pdf', 'rb') as f:
    files = {'file': f}
    response = requests.post('http://localhost:5000/api/upload', files=files)
    data = response.json()

# Generate flowchart
response = requests.post('http://localhost:5000/api/generate', json={
    'workflow_text': data['workflow_text'],
    'title': data['title'],
    'format': 'png',
    'theme': 'default'
})

# Save result
with open('output.png', 'wb') as f:
    f.write(response.content)
```

---

## Troubleshooting

### "PDF support not available"

```bash
pip install PyPDF2 pdfplumber
```

### "DOCX support not available"

```bash
pip install python-docx
```

### "Clipboard support not available"

```bash
pip install pyperclip
```

### No workflow detected

Try these options:

1. **Use --preview** to see extracted content
```bash
python -m cli.main import document.pdf --preview
```

2. **Check document format** - Ensure it's text-based, not scanned images

3. **Manual extraction** - Export text from document and save as .txt

4. **Traditional method** - Use original `generate` command with formatted text file

### Web interface not starting

```bash
# Check Flask is installed
pip install flask flask-cors

# Try different port
port=8000 python web/app.py
```

---

## Tips for Best Results

### Document Formatting

✅ **Good:**
```
1. User enters credentials
2. System validates login
3. Check if valid
   - If yes: Load dashboard
   - If no: Show error
4. End
```

❌ **Poor:**
```
First the user logs in then the system checks and either shows
the dashboard or an error message.
```

### Workflow Structure

- Use numbered lists (1, 2, 3...)
- Include start/end points
- Mark decisions clearly ("If... then...")
- Use active verbs (validate, check, process)
- Keep steps concise

### Multi-Section Documents

- Use clear section headers
- Separate workflows with headers
- Tool will automatically detect best section
- Use `--preview` to verify correct section

---

## Comparison: CLI vs Web Interface

| Feature | CLI Import | Web Interface |
|---------|-----------|---------------|
| Speed | ⚡ Fastest | 🐌 Slower (browser overhead) |
| Automation | ✅ Yes | ❌ No |
| Preview | 📝 Text only | 🖌 Visual |
| Batch processing | ✅ Yes | ❌ No |
| User-friendly | 👥 Technical users | 👥 Anyone |
| Clipboard | ✅ Yes | ✅ Yes |
| Multiple formats | ✅ Yes | ✅ Yes |

**Recommendation:**
- **CLI**: For automation, scripts, batch processing
- **Web**: For one-off conversions, demos, non-technical users

---

## What's Next?

Upcoming features:
- ☁️ Cloud storage integration (Google Drive, Dropbox)
- 📧 Email import
- 🔄 Batch processing UI
- 🌐 Browser extension
- 📦 Executable installer
- ➡️ Context menu integration

---

## Need Help?

- **Issues**: https://github.com/Aren-Garro/Flowcharts/issues
- **Examples**: See `examples/` directory
- **Full docs**: See `README.md`

---

**Happy flowcharting! 🎉**
