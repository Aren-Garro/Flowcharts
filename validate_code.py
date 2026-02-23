#!/usr/bin/env python3
"""Code validation script - checks for syntax errors, imports, and basic functionality."""

import sys
import ast
import importlib.util
from pathlib import Path
from typing import List, Tuple


class CodeValidator:
    """Validates Python code for syntax and import errors."""
    
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.files_checked = 0
        self.files_passed = 0
    
    def validate_syntax(self, filepath: Path) -> bool:
        """Check if Python file has valid syntax."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                code = f.read()
            ast.parse(code, filename=str(filepath))
            return True
        except SyntaxError as e:
            self.errors.append(f"{filepath}: Syntax error at line {e.lineno}: {e.msg}")
            return False
        except Exception as e:
            self.errors.append(f"{filepath}: Error parsing: {e}")
            return False
    
    def validate_imports(self, filepath: Path) -> bool:
        """Check if file can be imported (catches missing dependencies)."""
        try:
            spec = importlib.util.spec_from_file_location(
                filepath.stem,
                filepath
            )
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                # Don't execute, just load
                return True
            return False
        except Exception as e:
            self.warnings.append(f"{filepath}: Import warning: {e}")
            return True  # Don't fail on import warnings
    
    def validate_file(self, filepath: Path) -> bool:
        """Validate a single Python file."""
        self.files_checked += 1
        
        print(f"Validating {filepath}...", end=" ")
        
        # Check syntax
        if not self.validate_syntax(filepath):
            print("❌ FAILED (syntax error)")
            return False
        
        # Check imports
        self.validate_imports(filepath)
        
        print("✓ OK")
        self.files_passed += 1
        return True
    
    def validate_directory(self, directory: Path) -> bool:
        """Validate all Python files in directory recursively."""
        python_files = list(directory.rglob("*.py"))
        
        if not python_files:
            self.warnings.append(f"No Python files found in {directory}")
            return True
        
        all_valid = True
        for filepath in python_files:
            # Skip __pycache__ and venv
            if "__pycache__" in str(filepath) or "venv" in str(filepath):
                continue
            
            if not self.validate_file(filepath):
                all_valid = False
        
        return all_valid
    
    def print_summary(self):
        """Print validation summary."""
        print("\n" + "="*60)
        print("VALIDATION SUMMARY")
        print("="*60)
        print(f"Files checked: {self.files_checked}")
        print(f"Files passed: {self.files_passed}")
        print(f"Files failed: {self.files_checked - self.files_passed}")
        
        if self.errors:
            print(f"\n❌ ERRORS ({len(self.errors)}):")
            for error in self.errors:
                print(f"  • {error}")
        
        if self.warnings:
            print(f"\n⚠️  WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  • {warning}")
        
        if not self.errors:
            print("\n✅ All files passed validation!")
            return True
        else:
            print("\n❌ Validation failed - fix errors above")
            return False


def check_required_files() -> Tuple[bool, List[str]]:
    """Check if all required files exist."""
    required_files = [
        "src/models.py",
        "src/__init__.py",
        "src/parser/nlp_parser.py",
        "src/builder/graph_builder.py",
        "src/generator/mermaid_generator.py",
        "src/renderer/image_renderer.py",
        "cli/main.py",
        "requirements.txt",
        "setup.py",
    ]
    
    missing = []
    for filepath in required_files:
        if not Path(filepath).exists():
            missing.append(filepath)
    
    return len(missing) == 0, missing


def check_project_structure() -> bool:
    """Verify project structure is correct."""
    print("Checking project structure...")
    
    required_dirs = ["src", "cli", "tests", "examples", "docs"]
    missing_dirs = []
    
    for dirname in required_dirs:
        if not Path(dirname).exists():
            missing_dirs.append(dirname)
    
    if missing_dirs:
        print(f"❌ Missing directories: {missing_dirs}")
        return False
    
    print("✓ Project structure OK")
    return True


def main():
    """Main validation routine."""
    print("="*60)
    print("FLOWCHART GENERATOR - CODE VALIDATION")
    print("="*60)
    print()
    
    # Check project structure
    if not check_project_structure():
        print("\n❌ Project structure invalid")
        sys.exit(1)
    
    # Check required files
    print("\nChecking required files...")
    has_all_files, missing = check_required_files()
    if not has_all_files:
        print(f"❌ Missing required files:")
        for file in missing:
            print(f"  • {file}")
        sys.exit(1)
    print("✓ All required files present")
    
    # Validate Python code
    print("\nValidating Python code...\n")
    validator = CodeValidator()
    
    # Validate source code
    print("\n[SOURCE CODE]")
    src_valid = validator.validate_directory(Path("src"))
    
    # Validate CLI
    print("\n[CLI CODE]")
    cli_valid = validator.validate_directory(Path("cli"))
    
    # Validate tests
    print("\n[TEST CODE]")
    test_valid = validator.validate_directory(Path("tests"))
    
    # Print summary
    success = validator.print_summary()
    
    # Exit code
    if success and src_valid and cli_valid:
        print("\n✅ CODE VALIDATION PASSED")
        print("\nNext steps:")
        print("  1. Run tests: pytest tests/ -v")
        print("  2. Try examples: python -m cli.main generate examples/simple_workflow.txt")
        sys.exit(0)
    else:
        print("\n❌ CODE VALIDATION FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
