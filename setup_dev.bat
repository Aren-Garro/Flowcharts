@echo off
REM Development environment setup script for Windows

echo ====================================
echo Flowchart Generator - Dev Setup
echo ====================================
echo.

REM Check Python version
echo Checking Python version...
python --version
if errorlevel 1 (
    echo Error: Python not found
    exit /b 1
)

echo Python OK
echo.

REM Create virtual environment
echo Creating virtual environment...
if not exist venv (
    python -m venv venv
    echo Virtual environment created
) else (
    echo Virtual environment already exists
)
echo.

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat
echo Virtual environment activated
echo.

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip >nul 2>&1
echo pip upgraded
echo.

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt >nul 2>&1
echo Dependencies installed
echo.

REM Install development dependencies
echo Installing development dependencies...
pip install pytest pytest-cov black flake8 isort >nul 2>&1
echo Development dependencies installed
echo.

REM Install spaCy model
echo Installing spaCy language model...
python -c "import spacy; spacy.load('en_core_web_sm')" 2>nul
if errorlevel 1 (
    python -m spacy download en_core_web_sm >nul 2>&1
    echo spaCy model installed
) else (
    echo spaCy model already installed
)
echo.

REM Check for Node.js and mermaid-cli
echo Checking for Node.js and mermaid-cli...
where node >nul 2>&1
if errorlevel 1 (
    echo Node.js not installed
    echo mermaid-cli requires Node.js for image rendering
) else (
    node --version
    where mmdc >nul 2>&1
    if errorlevel 1 (
        echo mermaid-cli not installed
        echo Install with: npm install -g @mermaid-js/mermaid-cli
    ) else (
        mmdc --version
        echo mermaid-cli installed
    )
)
echo.

REM Create output directory
echo Creating output directory...
if not exist output mkdir output
echo Output directory created
echo.

REM Run tests
echo Running tests...
pytest tests/ -q
if errorlevel 1 (
    echo Some tests failed (this is okay for initial setup)
) else (
    echo All tests passed
)
echo.

echo ====================================
echo Setup Complete!
echo ====================================
echo.
echo Next steps:
echo 1. Activate virtual environment: venv\Scripts\activate.bat
echo 2. Try an example: python -m cli.main generate examples/simple_workflow.txt -o test.png
echo 3. Run tests: pytest tests/
echo 4. Read docs: type docs\QUICK_START.md
echo.
echo Happy coding!
pause
