# ISO 5807 Flowchart Generator 🚀

**Turn process notes into professional, enterprise-ready flowcharts—100% locally.**

[![ISO 5807 Compliant](https://img.shields.io/badge/ISO-5807-blue)](docs/reports/ISO_5807_SPEC.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Local AI](https://img.shields.io/badge/Local-AI-green)](docs/QUICKSTART.md)

This generator uses NLP and local LLMs to transform natural language descriptions into standards-compliant flowcharts. No cloud dependencies, no API costs, and total data privacy.

---

## 🌟 Key Features

*   **Smart Extraction:** Uses spaCy NLP or local LLMs (Llama-3, Mistral) to understand your workflow.
*   **ISO 5807 Standards:** Automatically maps actions to the correct symbols (Decisions, Databases, I/O, etc.).
*   **Multi-Engine Rendering:** Export to high-quality PNG, PDF, or SVG via **Graphviz**, **D2**, or **Mermaid**.
*   **Batch Processing:** Process entire manuals and export dozens of flowcharts at once into a ZIP archive.
*   **Guided Web UI:** A modern, browser-based interface with a 3-step wizard for first-time users.

---

## 🚀 Quick Start (30 Seconds)

### 1. Install
```bash
git clone https://github.com/Aren-Garro/Flowcharts.git
cd Flowcharts
python -m venv .venv
# Windows: .\.venv\Scripts\Activate.ps1 | Linux/macOS: source .venv/bin/activate
pip install .
python -m spacy download en_core_web_sm
```

### 2. Choose Your Interface

#### **Option A: Web Studio (Recommended)**
```bash
python web/app.py
# Open http://localhost:5000 in your browser
```

#### **Option B: Power CLI**
```bash
# Generate a polished PNG using Graphviz
python -m cli.main generate examples/user_authentication.txt -o auth.png --renderer graphviz
```

---

## 🛠️ Core Workflows

### Document Import
Turn a PDF or Word manual into a set of flowcharts:
```bash
python -m cli.main batch manual.pdf --split-mode auto --zip -o my_flowcharts.zip
```

### Advanced AI Extraction
Use a local GGUF model for complex semantic understanding:
```bash
python -m cli.main generate logic.txt --extraction local-llm --model-path ./models/llama3.gguf
```

---

## 📐 ISO 5807 Symbol Support

| Symbol | Shape | Best For | Example |
| :--- | :---: | :--- | :--- |
| **Terminator** | Oval | Start/End points | "Start", "End" |
| **Process** | Rect | General operations | "Calculate total" |
| **Decision** | Diamond | Conditional logic | "Is user valid?" |
| **Data I/O** | Parallelogram | Input/Output | "Read CSV file" |
| **Database** | Cylinder | Storage operations | "Query User DB" |
| **Manual** | Trapezoid | Human intervention | "Wait for approval" |

---

## 📚 Documentation Index

Our documentation has been reorganized for clarity:

*   **[Quick Start Guide](docs/QUICKSTART.md)** - Full installation and tier selection.
*   **[ISO 5807 Spec](docs/ISO_5807_SPEC.md)** - Detailed mapping of symbols and rules.
*   **[Import Guide](docs/reports/IMPORT_GUIDE.md)** - How to process PDFs, Word docs, and more.
*   **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Solutions for common installation issues.
*   **[Project Status](docs/reports/PROJECT_STATUS.md)** - Current metrics and roadmap.

---

## 🤝 Contributing

We welcome contributions! Please see our **[Contributing Guide](docs/reports/CONTRIBUTING.md)** to get started.

1. Fork the repo
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

**Author:** [Aren Garro](https://github.com/Aren-Garro)  
**Last Updated:** March 9, 2026 - v2.1.1 (UX/UI & Hygiene Update)
