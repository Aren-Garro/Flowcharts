#!/bin/bash
# Development environment setup script

set -e

echo "===================================="
echo "Flowchart Generator - Dev Setup"
echo "===================================="
echo ""

# Check Python version
echo "Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python version: $PYTHON_VERSION"

if ! python3 -c 'import sys; assert sys.version_info >= (3,9)' 2>/dev/null; then
    echo "Error: Python 3.9 or higher is required"
    exit 1
fi

echo "✓ Python version OK"
echo ""

# Create virtual environment
echo "Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi
echo ""

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate
echo "✓ Virtual environment activated"
echo ""

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip > /dev/null 2>&1
echo "✓ pip upgraded"
echo ""

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt > /dev/null 2>&1
echo "✓ Dependencies installed"
echo ""

# Install development dependencies
echo "Installing development dependencies..."
pip install pytest pytest-cov black flake8 isort > /dev/null 2>&1
echo "✓ Development dependencies installed"
echo ""

# Install spaCy model
echo "Installing spaCy language model..."
if python -c "import spacy; spacy.load('en_core_web_sm')" 2>/dev/null; then
    echo "✓ spaCy model already installed"
else
    python -m spacy download en_core_web_sm > /dev/null 2>&1
    echo "✓ spaCy model installed"
fi
echo ""

# Check for Node.js and mermaid-cli
echo "Checking for Node.js and mermaid-cli..."
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    echo "Node.js version: $NODE_VERSION"
    
    if command -v mmdc &> /dev/null; then
        MMDC_VERSION=$(mmdc --version | head -n 1)
        echo "mermaid-cli version: $MMDC_VERSION"
        echo "✓ mermaid-cli installed"
    else
        echo "⚠️  mermaid-cli not installed"
        echo "Install with: npm install -g @mermaid-js/mermaid-cli"
    fi
else
    echo "⚠️  Node.js not installed"
    echo "mermaid-cli requires Node.js for image rendering"
fi
echo ""

# Create output directory
echo "Creating output directory..."
mkdir -p output
echo "✓ Output directory created"
echo ""

# Run tests
echo "Running tests..."
if pytest tests/ -q; then
    echo "✓ All tests passed"
else
    echo "⚠️  Some tests failed (this is okay for initial setup)"
fi
echo ""

echo "===================================="
echo "Setup Complete!"
echo "===================================="
echo ""
echo "Next steps:"
echo "1. Activate virtual environment: source venv/bin/activate"
echo "2. Try an example: python -m cli.main generate examples/simple_workflow.txt -o test.png"
echo "3. Run tests: pytest tests/"
echo "4. Read docs: cat docs/QUICK_START.md"
echo ""
echo "Happy coding!"
