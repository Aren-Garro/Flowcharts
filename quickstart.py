#!/usr/bin/env python3
"""Interactive quickstart script for Flowcharts.

Run this to test all features:
    python quickstart.py
"""

import subprocess
import sys
from pathlib import Path


def print_header(text):
    print("\n" + "="*60)
    print(f"  {text}")
    print("="*60 + "\n")


def run_command(cmd, description):
    print(f"\n🚀 {description}")
    print(f"   Command: {cmd}\n")
    result = subprocess.run(cmd, shell=True)
    return result.returncode == 0


def check_dependencies():
    print_header("🔍 Checking Dependencies")
    
    dependencies = [
        ("spacy", "pip install spacy"),
        ("pydantic", "pip install pydantic"),
        ("typer", "pip install typer"),
        ("rich", "pip install rich"),
        ("PyPDF2", "pip install PyPDF2"),
        ("pdfplumber", "pip install pdfplumber"),
        ("docx", "pip install python-docx"),
        ("flask", "pip install flask flask-cors"),
    ]
    
    missing = []
    for module, install_cmd in dependencies:
        try:
            __import__(module.replace('-', '_'))
            print(f"  ✅ {module}")
        except ImportError:
            print(f"  ❌ {module} - Missing")
            missing.append(install_cmd)
    
    if missing:
        print("\n⚠️  Missing dependencies detected!")
        print("\nInstall all at once:")
        print("  pip install -r requirements.txt\n")
        return False
    
    print("\n✅ All dependencies installed!")
    return True


def test_cli_import():
    print_header("📥 Testing CLI Import")
    
    # Check if examples exist
    example_file = Path("examples/simple_workflow.txt")
    if not example_file.exists():
        print("⚠️  Example files not found. Skipping CLI test.")
        return
    
    print("Testing with example workflow...\n")
    
    # Test import command
    cmd = f"python -m cli.main import {example_file} -o quickstart_test.png"
    success = run_command(cmd, "Importing example workflow")
    
    if success and Path("quickstart_test.png").exists():
        print("\n✅ CLI import successful!")
        print(f"   Output: quickstart_test.png")
        
        # Clean up
        Path("quickstart_test.png").unlink()
    else:
        print("\n❌ CLI import failed")


def test_web_interface():
    print_header("🌐 Testing Web Interface")
    
    print("Web interface can be started with:\n")
    print("  python web/app.py\n")
    print("Then visit: http://localhost:5000\n")
    
    response = input("Start web interface now? (y/N): ").strip().lower()
    
    if response == 'y':
        print("\n🚀 Starting web interface...")
        print("Press Ctrl+C to stop\n")
        try:
            subprocess.run(["python", "web/app.py"])
        except KeyboardInterrupt:
            print("\n\n✅ Web interface stopped")


def show_usage_examples():
    print_header("📚 Usage Examples")
    
    examples = [
        ("Import PDF", "python -m cli.main import document.pdf"),
        ("Import DOCX", "python -m cli.main import workflow.docx"),
        ("Import with preview", "python -m cli.main import doc.pdf --preview"),
        ("Import from clipboard", "python -m cli.main import --clipboard"),
        ("Generate from text", "python -m cli.main generate workflow.txt -o output.png"),
        ("Web interface", "python web/app.py"),
    ]
    
    for desc, cmd in examples:
        print(f"  • {desc}:")
        print(f"    {cmd}\n")


def show_next_steps():
    print_header("✅ Setup Complete!")
    
    print("Your Flowcharts tool is ready to use!\n")
    print("📄 Documentation:")
    print("  • README.md - Main documentation")
    print("  • IMPORT_GUIDE.md - Document import guide")
    print("  • examples/ - Sample workflows\n")
    
    print("🚀 Quick Commands:")
    print("  • Import any document:  python -m cli.main import document.pdf")
    print("  • Start web interface:  python web/app.py")
    print("  • Run tests:            python run_all_tests.py\n")
    
    print("🐛 Issues or questions?")
    print("  https://github.com/Aren-Garro/Flowcharts/issues\n")


def main():
    print("\n" + "⭐"*30)
    print("  ISO 5807 Flowchart Generator")
    print("  Interactive Quickstart")
    print("⭐"*30)
    
    # Check Python version
    if sys.version_info < (3, 9):
        print("\n❌ Error: Python 3.9 or higher required")
        print(f"   Current version: {sys.version}")
        return 1
    
    print(f"\n✅ Python {sys.version_info.major}.{sys.version_info.minor}")
    
    # Check dependencies
    deps_ok = check_dependencies()
    
    if not deps_ok:
        response = input("\nInstall dependencies now? (Y/n): ").strip().lower()
        if response != 'n':
            run_command("pip install -r requirements.txt", "Installing dependencies")
            print("\n✅ Dependencies installed! Please run quickstart.py again.")
            return 0
        else:
            print("\n⚠️  Please install dependencies manually and run again.")
            return 1
    
    # Test CLI import
    test_cli_import()
    
    # Show usage examples
    show_usage_examples()
    
    # Ask about web interface
    test_web_interface()
    
    # Show next steps
    show_next_steps()
    
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n❌ Cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        sys.exit(1)
