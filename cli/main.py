"""Main CLI entry point."""

import typer
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich import print as rprint

from src.parser.nlp_parser import NLPParser
from src.builder.graph_builder import GraphBuilder
from src.builder.validator import ISO5807Validator
from src.generator.mermaid_generator import MermaidGenerator
from src.renderer.image_renderer import ImageRenderer
from cli.import_command import import_and_generate

app = typer.Typer(
    name="flowchart",
    help="ISO 5807 Flowchart Generator - Transform workflows into professional flowcharts"
)
console = Console()


@app.command(name="import")
def import_document(
    input_file: Optional[Path] = typer.Argument(None, help="Input document (PDF, DOCX, TXT, MD)"),
    output: Optional[Path] = typer.Option(None, "-o", "--output", help="Output file path"),
    clipboard: bool = typer.Option(False, "-c", "--clipboard", help="Import from clipboard"),
    format: str = typer.Option("png", "-f", "--format", help="Output format (png, svg, pdf, html, mmd)"),
    theme: str = typer.Option("default", "-t", "--theme", help="Mermaid theme"),
    direction: str = typer.Option("TD", "-d", "--direction", help="Flow direction (TD, LR, BT, RL)"),
    validate: bool = typer.Option(True, "--validate/--no-validate", help="Validate ISO 5807 compliance"),
    preview: bool = typer.Option(False, "-p", "--preview", help="Preview extracted workflow before generating"),
    width: int = typer.Option(3000, "-w", "--width", help="Output width in pixels"),
    height: int = typer.Option(2000, "-h", "--height", help="Output height in pixels"),
):
    """
    Import any document and automatically generate flowchart.
    
    Supports: PDF, DOCX, TXT, MD, and clipboard content.
    Automatically detects and extracts workflow content.
    
    Examples:
        flowchart import document.pdf
        flowchart import workflow.docx -o output.png
        flowchart import --clipboard
        flowchart import process.pdf --preview
    """
    if not input_file and not clipboard:
        console.print("[red]❌ Error: Specify input file or use --clipboard[/red]")
        console.print("\nUsage: flowchart import [FILE] or flowchart import --clipboard")
        raise typer.Exit(1)
    
    success = import_and_generate(
        input_file=input_file,
        output=output,
        clipboard=clipboard,
        format=format,
        theme=theme,
        direction=direction,
        validate=validate,
        preview=preview,
        width=width,
        height=height,
    )
    
    if not success:
        raise typer.Exit(1)


@app.command()
def generate(
    input_file: Path = typer.Argument(..., help="Input workflow text file"),
    output: Path = typer.Option(
        "output.png",
        "-o", "--output",
        help="Output file path (png, svg, pdf, html, mmd)"
    ),
    format: Optional[str] = typer.Option(
        None,
        "-f", "--format",
        help="Output format (auto-detected from extension if not specified)"
    ),
    theme: str = typer.Option(
        "default",
        "-t", "--theme",
        help="Mermaid theme (default, forest, dark, neutral)"
    ),
    direction: str = typer.Option(
        "TD",
        "-d", "--direction",
        help="Flow direction (TD=top-down, LR=left-right, BT=bottom-top, RL=right-left)"
    ),
    validate: bool = typer.Option(
        True,
        "--validate/--no-validate",
        help="Validate ISO 5807 compliance"
    ),
    width: int = typer.Option(
        3000,
        "-w", "--width",
        help="Output width in pixels (for PNG/PDF)"
    ),
    height: int = typer.Option(
        2000,
        "-h", "--height",
        help="Output height in pixels (for PNG/PDF)"
    ),
):
    """
    Generate a flowchart from workflow text file.
    
    Example:
        flowchart generate workflow.txt -o output.png
        flowchart generate workflow.txt -o diagram.svg --theme dark
    """
    console.print("[bold blue]⚙️  ISO 5807 Flowchart Generator[/bold blue]\n")
    
    # Check input file exists
    if not input_file.exists():
        console.print(f"[red]❌ Error: Input file not found: {input_file}[/red]")
        raise typer.Exit(1)
    
    # Read input
    console.print(f"[cyan]📄 Reading workflow from: {input_file}[/cyan]")
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            workflow_text = f.read()
    except Exception as e:
        console.print(f"[red]❌ Error reading file: {e}[/red]")
        raise typer.Exit(1)
    
    # Parse workflow
    console.print("[cyan]🧠 Parsing workflow...[/cyan]")
    parser = NLPParser(use_spacy=True)
    steps = parser.parse(workflow_text)
    console.print(f"[green]✓ Parsed {len(steps)} workflow steps[/green]")
    
    # Build flowchart
    console.print("[cyan]🔨 Building flowchart graph...[/cyan]")
    builder = GraphBuilder()
    title = input_file.stem.replace('_', ' ').title()
    flowchart = builder.build(steps, title=title)
    console.print(f"[green]✓ Created {len(flowchart.nodes)} nodes and {len(flowchart.connections)} connections[/green]")
    
    # Validate if requested
    if validate:
        console.print("[cyan]✅ Validating ISO 5807 compliance...[/cyan]")
        validator = ISO5807Validator()
        is_valid, errors, warnings = validator.validate(flowchart)
        
        if errors:
            console.print("[red]\n❌ Validation Errors:[/red]")
            for error in errors:
                console.print(f"  [red]• {error}[/red]")
        
        if warnings:
            console.print("[yellow]\n⚠️  Validation Warnings:[/yellow]")
            for warning in warnings:
                console.print(f"  [yellow]• {warning}[/yellow]")
        
        if is_valid:
            console.print("[green]✓ Flowchart is ISO 5807 compliant[/green]")
        else:
            console.print("[red]❌ Flowchart has validation errors[/red]")
            if not typer.confirm("\nContinue anyway?", default=False):
                raise typer.Exit(1)
    
    # Generate Mermaid code
    console.print("[cyan]🎨 Generating Mermaid.js code...[/cyan]")
    generator = MermaidGenerator()
    mermaid_code = generator.generate_with_theme(flowchart, theme=theme)
    console.print("[green]✓ Mermaid code generated[/green]")
    
    # Determine output format
    if format is None:
        format = output.suffix.lstrip('.')
    
    # Render output
    console.print(f"[cyan]🖨️ Rendering to {format.upper()}...[/cyan]")
    
    if format == "mmd":
        # Just save Mermaid code
        with open(output, "w", encoding="utf-8") as f:
            f.write(mermaid_code)
        console.print(f"[green]✓ Saved Mermaid code to: {output}[/green]")
    
    elif format == "html":
        # Render to interactive HTML
        renderer = ImageRenderer()
        success = renderer.render_html(mermaid_code, str(output), title=title)
        if not success:
            raise typer.Exit(1)
    
    elif format in ["png", "svg", "pdf"]:
        # Render to image format
        renderer = ImageRenderer()
        success = renderer.render(
            mermaid_code,
            str(output),
            format=format,
            width=width,
            height=height,
            theme=theme
        )
        if not success:
            raise typer.Exit(1)
    
    else:
        console.print(f"[red]❌ Unsupported format: {format}[/red]")
        console.print("Supported formats: png, svg, pdf, html, mmd")
        raise typer.Exit(1)
    
    console.print(f"\n[bold green]✅ Success! Flowchart saved to: {output}[/bold green]")


@app.command()
def validate(
    input_file: Path = typer.Argument(..., help="Input workflow text file"),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Show detailed output")
):
    """
    Validate a workflow file for ISO 5807 compliance without generating output.
    
    Example:
        flowchart validate workflow.txt
        flowchart validate workflow.txt --verbose
    """
    console.print("[bold blue]✅ ISO 5807 Validator[/bold blue]\n")
    
    # Check input file
    if not input_file.exists():
        console.print(f"[red]❌ Error: Input file not found: {input_file}[/red]")
        raise typer.Exit(1)
    
    # Read and parse
    with open(input_file, "r", encoding="utf-8") as f:
        workflow_text = f.read()
    
    parser = NLPParser(use_spacy=True)
    steps = parser.parse(workflow_text)
    
    if verbose:
        console.print(f"Parsed {len(steps)} workflow steps\n")
    
    # Build flowchart
    builder = GraphBuilder()
    flowchart = builder.build(steps)
    
    if verbose:
        console.print(f"Nodes: {len(flowchart.nodes)}")
        console.print(f"Connections: {len(flowchart.connections)}\n")
    
    # Validate
    validator = ISO5807Validator()
    is_valid, errors, warnings = validator.validate(flowchart)
    
    # Display results
    if errors:
        console.print("[red]\n❌ Validation Errors:[/red]")
        for error in errors:
            console.print(f"  [red]• {error}[/red]")
    
    if warnings:
        console.print("[yellow]\n⚠️  Validation Warnings:[/yellow]")
        for warning in warnings:
            console.print(f"  [yellow]• {warning}[/yellow]")
    
    if not errors and not warnings:
        console.print("[green]✓ No issues found[/green]")
    
    if is_valid:
        console.print("\n[bold green]✅ Flowchart is ISO 5807 compliant[/bold green]")
        raise typer.Exit(0)
    else:
        console.print("\n[bold red]❌ Flowchart has validation errors[/bold red]")
        raise typer.Exit(1)


@app.command()
def info():
    """
    Display information about ISO 5807 standard and supported symbols.
    """
    console.print("[bold blue]📊 ISO 5807 Flowchart Standard[/bold blue]\n")
    
    console.print("[bold]Supported Symbols:[/bold]\n")
    
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Symbol", style="cyan")
    table.add_column("Shape", style="yellow")
    table.add_column("Use Case", style="green")
    
    symbols = [
        ("Terminator", "Oval", "Start/End points"),
        ("Process", "Rectangle", "Processing steps"),
        ("Decision", "Diamond", "Conditional branching"),
        ("Input/Output", "Parallelogram", "Data I/O operations"),
        ("Database", "Cylinder", "Database operations"),
        ("Display", "Hexagon", "Screen output"),
        ("Document", "Wavy Rectangle", "Document generation"),
        ("Predefined", "Double Rectangle", "Sub-routines/functions"),
        ("Manual", "Trapezoid", "Manual operations"),
    ]
    
    for symbol, shape, use_case in symbols:
        table.add_row(symbol, shape, use_case)
    
    console.print(table)
    
    console.print("\n[bold]Example Workflow Syntax:[/bold]\n")
    console.print("""
1. Start
2. Read user input
3. Validate data
4. Check if data is valid
   - If yes: Save to database
   - If no: Display error message
5. End
    """)


@app.command()
def version():
    """Display version information."""
    from src import __version__
    console.print(f"[bold]ISO 5807 Flowchart Generator[/bold] v{__version__}")
    console.print("Built with ❤️  by Aren Garro")


if __name__ == "__main__":
    app()
