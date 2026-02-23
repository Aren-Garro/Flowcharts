# 🪟 Windows Quick Start Guide

**Complete guide for running the ISO 5807 Flowchart Generator on Windows**

---

## ⚡ Prerequisites

- ✅ Python 3.9+ installed
- ✅ PowerShell (comes with Windows)
- ✅ Git (to clone the repository)

---

## 📥 Step 1: Get the Code

```powershell
# Navigate to where you want the project
cd ~\Documents\GitHub

# Clone the repository
git clone https://github.com/Aren-Garro/Flowcharts.git

# Enter the directory
cd Flowcharts
```

---

## 📦 Step 2: Install Dependencies

```powershell
# Install all required packages
py -m pip install -r requirements.txt

# Optional: Install spaCy language model for better parsing
py -m spacy download en_core_web_sm
```

---

## 🎯 Step 3: Create Your First Flowchart

### Method 1: Simple Workflow

```powershell
# Create a workflow file (use @"..."@ for proper UTF-8 encoding)
@"
1. Start application
2. Get user input
3. Validate data
4. Check if data is valid
   - If yes: Save to database
   - If no: Show error message
5. Display success confirmation
6. End
"@ | Out-File -FilePath workflow.txt -Encoding utf8

# Generate HTML (easiest to view)
py -m cli.main generate workflow.txt -o workflow.html

# Open in browser
start workflow.html
```

### Method 2: Use Example Files

```powershell
# Generate from built-in examples
py -m cli.main generate examples\simple_workflow.txt -o simple.html
py -m cli.main generate examples\database_operations.txt -o database.html
py -m cli.main generate examples\complex_decision.txt -o complex.html

# Open them
start simple.html
start database.html
start complex.html
```

---

## 📝 Output Formats

### Mermaid Code (.mmd)

```powershell
# Generate Mermaid code
py -m cli.main generate workflow.txt -o output.mmd

# View the code
cat output.mmd

# Copy and paste into https://mermaid.live/ to visualize
```

### HTML (Recommended for Windows)

```powershell
# Generate interactive HTML
py -m cli.main generate workflow.txt -o output.html

# Open in browser
start output.html
```

### Images (PNG, SVG, PDF) - Requires Node.js

```powershell
# First, install Node.js from https://nodejs.org/
# Then install mermaid-cli:
npm install -g @mermaid-js/mermaid-cli

# Now you can generate images:
py -m cli.main generate workflow.txt -o output.png
py -m cli.main generate workflow.txt -o output.svg
py -m cli.main generate workflow.txt -o output.pdf
```

---

## ⚠️ Common Issues & Solutions

### Issue 1: "python not recognized"

**Solution:** Use `py` instead of `python` on Windows

```powershell
# ✅ Correct:
py -m cli.main generate workflow.txt -o output.html

# ❌ Wrong:
python -m cli.main generate workflow.txt -o output.html
```

### Issue 2: "UTF-8 codec can't decode"

**Solution:** Always use `@"..."@ | Out-File -Encoding utf8` for creating text files

```powershell
# ✅ Correct:
@"
1. Start
2. Process
3. End
"@ | Out-File -FilePath test.txt -Encoding utf8

# ❌ Wrong (causes encoding errors):
echo "1. Start" > test.txt
```

### Issue 3: "ModuleNotFoundError"

**Solution:** Install dependencies

```powershell
py -m pip install -r requirements.txt
```

### Issue 4: Working directory issues

**Solution:** Make sure you're in the Flowcharts directory

```powershell
# Check current directory
cd

# Should show: C:\Users\YourName\Documents\GitHub\Flowcharts
# If not, navigate there:
cd C:\Users\YourName\Documents\GitHub\Flowcharts
```

### Issue 5: spaCy warnings

**Solution:** The tool works without spaCy (fallback parser), but for best results:

```powershell
py -m spacy download en_core_web_sm
```

---

## 📚 Workflow Syntax Examples

### Simple Linear Flow

```text
1. Start
2. Read user input
3. Process data
4. Save results
5. End
```

### With Decision Points

```text
1. Start application
2. Check if user is logged in
   - If yes: Show dashboard
   - If no: Redirect to login
3. End
```

### With Database Operations

```text
1. User submits form
2. Validate input
3. Query database for existing record
4. Check if record exists
   - If yes: Update existing record
   - If no: Insert new record
5. Save changes to database
6. Display confirmation
7. End
```

### With Loops

```text
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

---

## 🔄 Complete Workflow Example

**Create this file:**

```powershell
@"
1. User logs into system
2. System authenticates credentials
3. Check if credentials are valid
   - If yes: Load user dashboard
   - If no: Display error message and end
4. Query user preferences from database
5. Check if preferences exist
   - If yes: Apply custom settings
   - If no: Use default settings
6. Display personalized dashboard
7. Wait for user action
8. Check user action type
   - If logout: Clear session and end
   - If continue: Return to step 7
9. End
"@ | Out-File -FilePath complete_workflow.txt -Encoding utf8

# Generate flowchart
py -m cli.main generate complete_workflow.txt -o complete.html

# View it
start complete.html
```

---

## 🎨 Customization Options

### Validate Only (Don't Generate)

```powershell
py -m cli.main validate workflow.txt
```

### Generate Multiple Formats

```powershell
# Generate all formats at once
py -m cli.main generate workflow.txt -o output.mmd
py -m cli.main generate workflow.txt -o output.html

# If mermaid-cli is installed:
py -m cli.main generate workflow.txt -o output.png
py -m cli.main generate workflow.txt -o output.svg
py -m cli.main generate workflow.txt -o output.pdf
```

---

## ✅ Verification Steps

**1. Check Python is working:**

```powershell
py --version
# Should show: Python 3.13.x or higher
```

**2. Check dependencies are installed:**

```powershell
py -c "import pydantic; print('✓ Pydantic OK')"
py -c "import spacy; print('✓ spaCy OK')"
py -c "import click; print('✓ Click OK')"
```

**3. Check you're in the right directory:**

```powershell
dir
# Should show: cli/, src/, examples/, tests/, requirements.txt, etc.
```

**4. Run help command:**

```powershell
py -m cli.main --help
```

**5. Test with example:**

```powershell
py -m cli.main generate examples\simple_workflow.txt -o test.html
start test.html
```

---

## 🚀 Production Usage

### Batch Process Multiple Files

```powershell
# Process all .txt files in a directory
Get-ChildItem -Path .\workflows\*.txt | ForEach-Object {
    $outputName = $_.BaseName + ".html"
    py -m cli.main generate $_.FullName -o "output\$outputName"
}
```

### Create a Workflow Template

```powershell
# Save this as new_workflow_template.txt
@"
1. Start [Description of start]
2. [First action]
3. [Second action]
4. Check if [condition]
   - If yes: [Action for yes]
   - If no: [Action for no]
5. [Final action]
6. End
"@ | Out-File -FilePath new_workflow_template.txt -Encoding utf8
```

### Integration with CI/CD

```powershell
# Validate workflow files in CI/CD pipeline
py -m cli.main validate workflow.txt
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Workflow is valid"
    py -m cli.main generate workflow.txt -o output.png
} else {
    Write-Host "✗ Workflow validation failed"
    exit 1
}
```

---

## 📊 ISO 5807 Symbol Reference

The generator automatically detects and applies ISO 5807 symbols:

| Symbol | Shape | Detected From |
|--------|-------|---------------|
| **Terminator** | Oval (Green/Pink) | "Start", "End", "Begin", "Finish" |
| **Process** | Rectangle (Blue) | Most action verbs: "Calculate", "Process", "Update" |
| **Decision** | Diamond (Yellow) | "Check if", "Is", "Does", questions, If/else statements |
| **Input/Output** | Parallelogram (Purple) | "Read", "Input", "Output", "Get", "Display", "Print" |
| **Database** | Cylinder | "Query", "Save to database", "Retrieve from", "Store" |
| **Document** | Wavy Rectangle | "Generate report", "Print document", "Create invoice" |
| **Manual** | Trapezoid | "Wait for approval", "Manual review", "User confirms" |

---

## 🎓 Learning Resources

- **Tutorial:** `docs/TUTORIAL.md`
- **API Reference:** `docs/API_REFERENCE.md`
- **Examples:** `examples/` directory
- **Testing Guide:** `TESTING_REPORT.md`
- **Contributing:** `CONTRIBUTING.md`

---

## 💡 Pro Tips

1. **Always use UTF-8 encoding** when creating workflow files
2. **Use HTML output** for quick viewing (no extra tools needed)
3. **Number your steps** for best results (1., 2., 3., etc.)
4. **Be clear with decisions** - Use "If yes/no" or "If true/false"
5. **Keep it simple** - Break complex workflows into smaller ones
6. **Use the examples** as templates for your own workflows

---

## 🆘 Getting Help

**If you encounter issues:**

1. Check this guide first
2. Review `STARTUP_GUIDE.md` for common problems
3. Run diagnostics:
   ```powershell
   py --version
   py -m cli.main --help
   dir examples
   ```
4. Try the examples:
   ```powershell
   py -m cli.main generate examples\simple_workflow.txt -o test.html
   ```
5. Check GitHub Issues or create a new one

---

## ✨ Quick Reference Card

```powershell
# CREATE FILE (proper UTF-8 encoding)
@"..text.."@ | Out-File -FilePath file.txt -Encoding utf8

# GENERATE HTML (easiest)
py -m cli.main generate input.txt -o output.html

# GENERATE MERMAID CODE
py -m cli.main generate input.txt -o output.mmd

# VALIDATE ONLY
py -m cli.main validate input.txt

# OPEN IN BROWSER
start output.html

# VIEW MERMAID CODE
cat output.mmd

# GET HELP
py -m cli.main --help
py -m cli.main generate --help
```

---

## 🎉 Success!

You're now ready to create ISO 5807 compliant flowcharts on Windows!

**Next steps:**
1. Create your first workflow
2. Generate the flowchart
3. View it in your browser
4. Share with your team!

Happy flowcharting! 🚀
