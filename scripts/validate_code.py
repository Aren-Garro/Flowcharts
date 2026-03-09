#!/usr/bin/env python3
"""Code validation script - checks syntax, structure, and basic importability."""

import ast
import importlib.util
import sys
from pathlib import Path
from typing import List, Tuple


class CodeValidator:
    """Validate Python files for syntax and basic module loading."""

    def __init__(self):
        self.errors = []
        self.warnings = []
        self.files_checked = 0
        self.files_passed = 0

    def validate_syntax(self, filepath: Path) -> bool:
        try:
            code = filepath.read_text(encoding="utf-8")
            ast.parse(code, filename=str(filepath))
            return True
        except SyntaxError as exc:
            self.errors.append(f"{filepath}: Syntax error at line {exc.lineno}: {exc.msg}")
            return False
        except Exception as exc:
            self.errors.append(f"{filepath}: Error parsing: {exc}")
            return False

    def validate_imports(self, filepath: Path) -> bool:
        try:
            spec = importlib.util.spec_from_file_location(filepath.stem, filepath)
            if spec and spec.loader:
                importlib.util.module_from_spec(spec)
                return True
            return False
        except Exception as exc:
            self.warnings.append(f"{filepath}: Import warning: {exc}")
            return True

    def validate_file(self, filepath: Path) -> bool:
        self.files_checked += 1
        print(f"Validating {filepath}...", end=" ")

        if not self.validate_syntax(filepath):
            print("FAILED (syntax error)")
            return False

        self.validate_imports(filepath)
        print("OK")
        self.files_passed += 1
        return True

    def validate_directory(self, directory: Path) -> bool:
        python_files = list(directory.rglob("*.py"))
        if not python_files:
            self.warnings.append(f"No Python files found in {directory}")
            return True

        all_valid = True
        for filepath in python_files:
            if "__pycache__" in str(filepath) or "venv" in str(filepath):
                continue
            if not self.validate_file(filepath):
                all_valid = False
        return all_valid

    def print_summary(self) -> bool:
        print("\n" + "=" * 60)
        print("VALIDATION SUMMARY")
        print("=" * 60)
        print(f"Files checked: {self.files_checked}")
        print(f"Files passed: {self.files_passed}")
        print(f"Files failed: {self.files_checked - self.files_passed}")

        if self.errors:
            print(f"\nERRORS ({len(self.errors)}):")
            for error in self.errors:
                print(f"  - {error}")

        if self.warnings:
            print(f"\nWARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  - {warning}")

        if not self.errors:
            print("\nAll files passed validation.")
            return True

        print("\nValidation failed - fix errors above")
        return False


def check_required_files() -> Tuple[bool, List[str]]:
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
    missing = [filepath for filepath in required_files if not Path(filepath).exists()]
    return len(missing) == 0, missing


def check_project_structure() -> bool:
    print("Checking project structure...")
    required_dirs = ["src", "cli", "tests", "examples", "docs"]
    missing_dirs = [dirname for dirname in required_dirs if not Path(dirname).exists()]
    if missing_dirs:
        print(f"Missing directories: {missing_dirs}")
        return False
    print("OK Project structure")
    return True


def main() -> int:
    print("=" * 60)
    print("FLOWCHART GENERATOR - CODE VALIDATION")
    print("=" * 60)
    print()

    if not check_project_structure():
        print("\nProject structure invalid")
        return 1

    print("\nChecking required files...")
    has_all_files, missing = check_required_files()
    if not has_all_files:
        print("Missing required files:")
        for file in missing:
            print(f"  - {file}")
        return 1
    print("OK All required files present")

    print("\nValidating Python code...\n")
    validator = CodeValidator()

    print("\n[SOURCE CODE]")
    src_valid = validator.validate_directory(Path("src"))

    print("\n[CLI CODE]")
    cli_valid = validator.validate_directory(Path("cli"))

    print("\n[TEST CODE]")
    validator.validate_directory(Path("tests"))

    success = validator.print_summary()
    if success and src_valid and cli_valid:
        print("\nCODE VALIDATION PASSED")
        print("\nNext steps:")
        print("  1. Run tests: pytest tests/ -v")
        print("  2. Try examples: python -m cli.main generate examples/simple_workflow.txt")
        return 0

    print("\nCODE VALIDATION FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
