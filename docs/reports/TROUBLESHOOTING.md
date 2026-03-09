# Troubleshooting Guide

**Last Updated:** February 25, 2026

---

## Table of Contents

1. [Installation Issues](#installation-issues)
2. [Validation Errors](#validation-errors)
3. [Rendering Problems](#rendering-problems)
4. [Import Failures](#import-failures)
5. [Performance Issues](#performance-issues)
6. [Common Errors](#common-errors)

---

## Installation Issues

### "No module named 'spacy'"

**Problem:** Missing spaCy dependency

**Solution:**
```bash
pip install spacy>=3.8.0
python -m spacy download en_core_web_sm
```

### "No module named 'typer'"

**Problem:** Missing CLI dependencies

**Solution:**
```bash
pip install -r requirements.txt
```

### "graphviz not found"

**Problem:** Graphviz binary not installed on system

**Solution:**

**Windows:**
```powershell
choco install graphviz
# OR download from: https://graphviz.org/download/
```

**macOS:**
```bash
brew install graphviz
```

**Linux:**
```bash
sudo apt-get install graphviz  # Debian/Ubuntu
sudo yum install graphviz      # RHEL/CentOS
```

### Virtual Environment Issues

**Problem:** Commands not found after installation

**Solution:**
```bash
# Make sure venv is activated
source venv/bin/activate  # Linux/macOS
.\venv\Scripts\Activate.ps1  # Windows PowerShell

# Verify installation
pip list | grep iso-flowchart
```

---

## Validation Errors

### "Decision node has fewer than 2 branches"

**Problem:** Decision node with only one branch

**Bad:**
```
3. Check if user is admin
   - If yes: Grant access
4. End
```

**Good:**
```
3. Check if user is admin
   - If yes: Grant access
   - If no: Deny access
4. End
```

### "END node has outgoing connection(s)"

**Problem:** Text says "end" but workflow continues

**Bad:**
```
3. Check if valid
   - If no: Display error and end
4. Continue processing
```

**Good:**
```
3. Check if valid
   - If no: Display error and go to step 10
   - If yes: Continue processing
4. Continue processing
...
10. End
```

### "Decision node has unlabeled branch(es)"

**Problem:** Branch without yes/no/condition label

**Bad:**
```
3. Check status
   - Continue to next step
```

**Good:**
```
3. Check status
   - If active: Continue to next step
   - If inactive: Skip to step 10
```

---

## Rendering Problems

### HTML Renderer Shows Blank Page

**Problem:** JavaScript disabled or file opened incorrectly

**Solution:**
```bash
# Ensure output has .html extension
flowchart generate input.txt -o output.html --renderer html

# Open in browser (not text editor)
open output.html  # macOS
start output.html # Windows
xdg-open output.html # Linux
```

### Graphviz Produces Error

**Problem:** Invalid DOT syntax or Graphviz not in PATH

**Solution:**
```bash
# Test Graphviz installation
dot -V

# If not found, reinstall Graphviz
# Then add to PATH (Windows)
setx PATH "%PATH%;C:\Program Files\Graphviz\bin"

# Verify flowchart generation
flowchart generate input.txt -o output.png --renderer graphviz --format png
```

### Mermaid Rendering Issues

**Problem:** Mermaid syntax errors

**Solution:**
```bash
# Generate to file first
flowchart generate input.txt -o output.mmd --renderer mermaid

# Test in Mermaid Live Editor
# https://mermaid.live/

# Check for syntax issues
cat output.mmd
```

### D2 Not Rendering

**Problem:** D2 not installed or in PATH

**Solution:**
```bash
# Install D2
curl -fsSL https://d2lang.com/install.sh | sh -s --

# Verify installation
d2 --version

# Generate diagram
flowchart generate input.txt -o output.svg --renderer d2 --format svg
```

---

## Import Failures

### PDF Import Returns Empty

**Problem:** PDF is image-based or encrypted

**Solutions:**

1. **Check if PDF has text:**
```bash
# Try extracting text manually
python -c "import PyPDF2; print(PyPDF2.PdfReader('file.pdf').pages[0].extract_text())"
```

2. **If image-based PDF:**
   - Use OCR first (Adobe, Tesseract)
   - Convert to text-based PDF
   - Then import

3. **If encrypted:**
```bash
# Decrypt PDF first
python -c "import PyPDF2; reader = PyPDF2.PdfReader('file.pdf'); reader.decrypt('password')"
```

### DOCX Import Fails

**Problem:** Corrupted document or unsupported format

**Solution:**
```bash
# Verify DOCX is valid
python -c "from docx import Document; doc = Document('file.docx'); print(len(doc.paragraphs))"

# If fails, try:
# 1. Open in Word and re-save
# 2. Convert to plain text first
# 3. Check for embedded objects/macros
```

### Batch Processing Finds No Workflows

**Problem:** Workflow detection threshold too strict

**Solution:**
```bash
# Use different split modes
flowchart batch document.pdf --split-mode section  # Try sections
flowchart batch document.pdf --split-mode page     # Or pages

# Lower detection threshold
flowchart batch document.pdf --min-steps 3  # Instead of default 5
```

---

## Performance Issues

### Slow NLP Processing

**Problem:** Large documents taking too long

**Solution:**
```bash
# Use pattern-based extraction (faster)
flowchart generate input.txt --extraction-method pattern

# Instead of LLM extraction
flowchart generate input.txt --extraction-method llm
```

### High Memory Usage

**Problem:** Processing very large documents

**Solution:**
```bash
# Process in chunks
flowchart batch large_doc.pdf --split-mode page

# Or split manually first
split -l 1000 large_file.txt chunk_
for file in chunk_*; do
    flowchart generate $file -o ${file}.html
done
```

### LLM Extraction Hangs

**Problem:** Model not responding or GPU issues

**Solution:**
```bash
# Check if model is loaded
ls ~/.cache/huggingface/  # Or model path

# Try CPU-only mode
export CUDA_VISIBLE_DEVICES=""
flowchart generate input.txt --extraction-method llm

# Or use smaller model
flowchart generate input.txt --model-path path/to/smaller/model.gguf
```

---

## Common Errors

### "FileNotFoundError: [Errno 2] No such file or directory"

**Cause:** Input file path incorrect

**Solution:**
```bash
# Use absolute path
flowchart generate /full/path/to/input.txt -o output.html

# Or verify relative path
pwd
ls input.txt  # Check file exists
```

### "PermissionError: [Errno 13] Permission denied"

**Cause:** No write permission for output directory

**Solution:**
```bash
# Check permissions
ls -l output_directory/

# Change permissions
chmod 755 output_directory/

# Or write to different location
flowchart generate input.txt -o ~/Desktop/output.html
```

### "ValueError: Workflow must have at least one step"

**Cause:** No valid workflow detected in input

**Solution:**
```bash
# Check input format
cat input.txt

# Ensure numbered steps:
# Good:
# 1. First step
# 2. Second step

# Bad:
# - First step
# - Second step
```

### "ModuleNotFoundError: No module named 'cli.main'"

**Cause:** Package not installed or PYTHONPATH issue

**Solution:**
```bash
# If running from source:
python -m cli.main generate input.txt -o output.html

# If installed via pip:
flowchart generate input.txt -o output.html

# Check installation
pip show iso-flowchart-generator
```

### "RuntimeError: spaCy model not found"

**Cause:** Missing language model

**Solution:**
```bash
# Install English model
python -m spacy download en_core_web_sm

# Verify installation
python -c "import spacy; nlp = spacy.load('en_core_web_sm'); print('OK')"
```

---

## Validation Bypass

**For testing purposes only:**

```bash
# Skip validation (not recommended for production)
flowchart generate input.txt -o output.html --skip-validation

# Or ignore specific warnings
flowchart generate input.txt -o output.html --allow-warnings
```

---

## Debug Mode

**Enable verbose logging:**

```bash
# Set log level
export LOG_LEVEL=DEBUG
flowchart generate input.txt -o output.html

# Or use verbose flag
flowchart generate input.txt -o output.html --verbose

# Save debug output
flowchart generate input.txt -o output.html --verbose 2> debug.log
```

---

## Getting Help

### Still Having Issues?

1. **Check existing issues:** https://github.com/Aren-Garro/Flowcharts/issues
2. **Create new issue with:**
   - Error message (full traceback)
   - Input file (or sample)
   - Command used
   - Environment (OS, Python version)
   - Output of `pip list`

3. **Ask in Discussions:** https://github.com/Aren-Garro/Flowcharts/discussions

### Provide Debug Information

```bash
# System info
python --version
pip --version
uname -a  # Linux/macOS
systeminfo  # Windows

# Package versions
pip list | grep -E "spacy|typer|pydantic|flask"

# Test basic functionality
echo -e "1. Start\n2. Process\n3. End" | flowchart generate - -o test.html --renderer html
```

---

## Quick Reference

### Common Commands

```bash
# Basic generation
flowchart generate input.txt -o output.html --renderer html

# Validate only
flowchart validate input.txt

# Batch processing
flowchart batch document.pdf --split-mode section

# Different renderers
flowchart generate input.txt -o output.png --renderer graphviz --format png
flowchart generate input.txt -o output.svg --renderer d2 --format svg
flowchart generate input.txt -o output.mmd --renderer mermaid

# Web interface
python web/app.py
# Then open: http://localhost:5000
```

### Environment Variables

```bash
# Model path
export FLOWCHART_MODEL_PATH="/path/to/model.gguf"

# Log level
export LOG_LEVEL="DEBUG"  # or INFO, WARNING, ERROR

# Temp directory
export TMPDIR="/path/to/temp"

# Disable GPU
export CUDA_VISIBLE_DEVICES=""
```

---

**Last Updated:** February 25, 2026  
**Version:** 2.1.0  
**Maintainer:** Aren Garro
