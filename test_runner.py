#!/usr/bin/env python3
"""Test runner script for quick validation."""

import sys
import subprocess
from pathlib import Path
from rich.console import Console
from rich.table import Table

console = Console()


def run_tests():
    """Run the test suite."""
    console.print("\n[bold blue]🧪 Running Test Suite[/bold blue]\n")
    
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-v"],
        capture_output=False
    )
    
    return result.returncode == 0


def generate_examples():
    """Generate flowcharts from example workflows."""
    console.print("\n[bold blue]🎨 Generating Example Flowcharts[/bold blue]\n")
    
    examples_dir = Path("examples")
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    examples = list(examples_dir.glob("*.txt"))
    
    if not examples:
        console.print("[yellow]No example files found[/yellow]")
        return True
    
    success_count = 0
    
    for example_file in examples:
        output_file = output_dir / f"{example_file.stem}.png"
        
        console.print(f"[cyan]Generating {example_file.name}...[/cyan]")
        
        result = subprocess.run(
            [
                sys.executable, "-m", "cli.main",
                "generate",
                str(example_file),
                "-o", str(output_file),
                "--no-validate"  # Skip validation for faster generation
            ],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            console.print(f"[green]✓ Generated {output_file.name}[/green]")
            success_count += 1
        else:
            console.print(f"[red]❌ Failed to generate {output_file.name}[/red]")
            if result.stderr:
                console.print(f"[red]{result.stderr}[/red]")
    
    console.print(f"\n[bold]Generated {success_count}/{len(examples)} examples[/bold]")
    return success_count == len(examples)


def validate_examples():
    """Validate example workflows."""
    console.print("\n[bold blue]✅ Validating Example Workflows[/bold blue]\n")
    
    examples_dir = Path("examples")
    examples = list(examples_dir.glob("*.txt"))
    
    if not examples:
        console.print("[yellow]No example files found[/yellow]")
        return True
    
    results = []
    
    for example_file in examples:
        console.print(f"[cyan]Validating {example_file.name}...[/cyan]")
        
        result = subprocess.run(
            [
                sys.executable, "-m", "cli.main",
                "validate",
                str(example_file)
            ],
            capture_output=True,
            text=True
        )
        
        is_valid = result.returncode == 0
        results.append((example_file.name, is_valid))
        
        if is_valid:
            console.print(f"[green]✓ Valid[/green]")
        else:
            console.print(f"[yellow]⚠️  Has warnings/errors[/yellow]")
    
    # Summary table
    console.print("\n[bold]Validation Summary:[/bold]\n")
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Example", style="cyan")
    table.add_column("Status", style="green")
    
    for name, is_valid in results:
        status = "✅ Valid" if is_valid else "⚠️  Warnings"
        table.add_row(name, status)
    
    console.print(table)
    
    return all(is_valid for _, is_valid in results)


def check_dependencies():
    """Check if required dependencies are installed."""
    console.print("\n[bold blue]🔍 Checking Dependencies[/bold blue]\n")
    
    dependencies = {
        "Python": [sys.executable, "--version"],
        "pip": [sys.executable, "-m", "pip", "--version"],
        "pytest": [sys.executable, "-m", "pytest", "--version"],
        "spaCy": [sys.executable, "-c", "import spacy; print(spacy.__version__)"],
        "mermaid-cli": ["mmdc", "--version"]
    }
    
    results = {}
    
    for name, cmd in dependencies.items():
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                version = result.stdout.strip().split('\n')[0]
                results[name] = (True, version)
                console.print(f"[green]✓ {name}: {version}[/green]")
            else:
                results[name] = (False, "Not working")
                console.print(f"[red]❌ {name}: Not working[/red]")
        except FileNotFoundError:
            results[name] = (False, "Not installed")
            console.print(f"[yellow]⚠️  {name}: Not installed[/yellow]")
    
    # Check spaCy model
    try:
        result = subprocess.run(
            [sys.executable, "-c", "import spacy; spacy.load('en_core_web_sm')"],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            console.print("[green]✓ spaCy model: en_core_web_sm installed[/green]")
        else:
            console.print("[yellow]⚠️  spaCy model: en_core_web_sm not installed (optional)[/yellow]")
    except Exception:
        console.print("[yellow]⚠️  spaCy model: Could not check[/yellow]")
    
    return all(installed for installed, _ in results.values())


def main():
    """Run all checks."""
    console.print("[bold]ISO 5807 Flowchart Generator - Test Runner[/bold]")
    console.print("=" * 60)
    
    # Check dependencies
    deps_ok = check_dependencies()
    
    if not deps_ok:
        console.print("\n[yellow]⚠️  Some dependencies are missing but tests will continue[/yellow]")
    
    # Run tests
    tests_passed = False
    try:
        tests_passed = run_tests()
    except Exception as e:
        console.print(f"[red]Error running tests: {e}[/red]")
    
    # Validate examples
    validation_passed = validate_examples()
    
    # Generate examples (only if mermaid-cli is available)
    generation_passed = True
    try:
        subprocess.run(["mmdc", "--version"], capture_output=True, check=True)
        generation_passed = generate_examples()
    except (FileNotFoundError, subprocess.CalledProcessError):
        console.print("\n[yellow]⚠️  Skipping example generation (mermaid-cli not installed)[/yellow]")
    
    # Summary
    console.print("\n" + "=" * 60)
    console.print("[bold]Summary:[/bold]\n")
    
    results = [
        ("Dependencies", deps_ok),
        ("Unit Tests", tests_passed),
        ("Example Validation", validation_passed),
        ("Example Generation", generation_passed)
    ]
    
    for name, passed in results:
        status = "[green]✅ PASSED[/green]" if passed else "[red]❌ FAILED[/red]"
        console.print(f"{name}: {status}")
    
    all_passed = all(passed for _, passed in results)
    
    if all_passed:
        console.print("\n[bold green]✅ All checks passed![/bold green]")
        return 0
    else:
        console.print("\n[bold red]❌ Some checks failed[/bold red]")
        return 1


if __name__ == "__main__":
    sys.exit(main())
