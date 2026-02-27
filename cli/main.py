"""Main CLI entry point with multi-renderer, extraction method,
quantization, adaptive auto-selection, and batch export support.

Phase 4: Added --quantization flag, enhanced `renderers` command.
Phase 5: `--extraction auto` and `--renderer auto` now use
CapabilityDetector for hardware-aware selection.
Enhancement 1: Added `batch` command for multi-workflow export.
"""

# Check Python version before importing dependencies
from src.version_check import check_python_version
check_python_version(raise_error=True)

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
from src.pipeline import FlowchartPipeline, PipelineConfig
from cli.import_command import import_and_generate
from cli.batch_command import batch_export
from cli.tutorial_command import tutorial_command

app = typer.Typer(
    name="flowchart",
    help="ISO 5807 Flowchart Generator - Transform workflows into professional flowcharts"
)
console = Console()


def _build_pipeline_config(
    extraction: str = "heuristic",
    renderer: str = "mermaid",
    model_path: Optional[str] = None,
    quantization: str = "5bit",
    direction: str = "TD",
    theme: str = "default",
    validate: bool = True,
    kroki_url: str = "http://localhost:8000",
    graphviz_engine: str = "dot",
    d2_layout: str = "elk",
    n_gpu_layers: int = -1,
    n_ctx: int = 8192,
) -> PipelineConfig:
    """Build a PipelineConfig from CLI options."""
    return PipelineConfig(
        extraction=extraction,
        renderer=renderer,
        model_path=model_path,
        quantization=quantization,
        direction=direction,
        theme=theme,
        validate=validate,
        kroki_url=kroki_url,
        graphviz_engine=graphviz_engine,
        d2_layout=d2_layout,
        n_gpu_layers=n_gpu_layers,
        n_ctx=n_ctx,
    )


@app.command()
def tutorial(
    skip_intro: bool = typer.Option(False, "--skip-intro", help="Skip introduction")
):
    """
    Interactive tutorial for new users.

    Learn how to create flowcharts step-by-step through hands-on examples.
    The tutorial covers basic workflows, decision branches, renderers, and
    batch processing.

    Example:
        flowchart tutorial
        flowchart tutorial --skip-intro
    """
    tutorial_command(skip_intro=skip_intro)


@app.command()
def batch(
    input_file: Path = typer.Argument(..., help="Input document (PDF, DOCX, TXT, MD)"),
    output_dir: Optional[Path] = typer.Option(None, "-o", "--output-dir", help="Output directory"),
    split_mode: str = typer.Option(
        "auto", "-s", "--split-mode", help="Split mode: auto, section, subsection, procedure, none"
    ),
    format: str = typer.Option("png", "-f", "--format", help="Output format (png, svg, pdf, html, mmd)"),
    zip_output: bool = typer.Option(False, "-z", "--zip", help="Create ZIP archive"),
    extraction: str = typer.Option(
        "heuristic", "--extraction", "-e", help="Extraction method: heuristic, local-llm, auto"
    ),
    renderer: str = typer.Option(
        "mermaid", "--renderer", "-r", help="Rendering engine: mermaid, graphviz, d2, kroki, html, auto"
    ),
    theme: str = typer.Option("default", "-t", "--theme", help="Mermaid theme"),
    direction: str = typer.Option("TD", "-d", "--direction", help="Flow direction (TD, LR, BT, RL)"),
    validate: bool = typer.Option(True, "--validate/--no-validate", help="Validate ISO 5807 compliance"),
    model_path: Optional[str] = typer.Option(
        None, "--model-path", help="Path to local GGUF model file for LLM extraction"
    ),
    quantization: str = typer.Option(
        "5bit", "--quantization", "-q", help="LLM quantization level: 4bit, 5bit, 8bit"
    ),
):
    """
    Export multiple workflows from a single document.

    The document will be split into separate workflows based on structure.
    Each workflow is exported as a separate flowchart.

    Split modes:
    - auto: Automatically detect best split strategy
    - section: Split by top-level sections/headings
    - subsection: Split by subsections (more granular)
    - procedure: Split by explicit procedure markers
    - none: Treat as single workflow

    Examples:
        flowchart batch manual.pdf
        flowchart batch setup.docx --split-mode section --format svg
        flowchart batch guide.docx --zip --split-mode subsection
        flowchart batch workflow.pdf -o ./output --format png
    """
    if not input_file.exists():
        console.print(f"[red]❌ Error: Input file not found: {input_file}[/red]")
        raise typer.Exit(1)

    config = _build_pipeline_config(
        extraction=extraction,
        renderer=renderer,
        model_path=model_path,
        quantization=quantization,
        direction=direction,
        theme=theme,
        validate=validate,
    )

    success = batch_export(
        input_file=input_file,
        output_dir=output_dir,
        split_mode=split_mode,
        format=format,
        zip_output=zip_output,
        pipeline_config=config,
    )

    if not success:
        raise typer.Exit(1)


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
    extraction: str = typer.Option(
        "heuristic", "--extraction", "-e", help="Extraction method: heuristic, local-llm, auto"
    ),
    renderer: str = typer.Option(
        "mermaid", "--renderer", "-r", help="Rendering engine: mermaid, graphviz, d2, kroki, html, auto"
    ),
    model_path: Optional[str] = typer.Option(
        None, "--model-path", help="Path to local GGUF model file for LLM extraction"
    ),
    quantization: str = typer.Option(
        "5bit", "--quantization", "-q", help="LLM quantization level: 4bit, 5bit, 8bit"
    ),
    n_gpu_layers: int = typer.Option(-1, "--gpu-layers", help="Number of GPU layers for LLM (-1 = all)"),
    n_ctx: int = typer.Option(8192, "--context-size", help="LLM context window size in tokens"),
    graphviz_engine: str = typer.Option(
        "dot", "--gv-engine", help="Graphviz layout engine: dot, neato, fdp, circo, twopi"
    ),
    d2_layout: str = typer.Option("elk", "--d2-layout", help="D2 layout engine: dagre, elk, tala"),
    kroki_url: str = typer.Option("http://localhost:8000", "--kroki-url", help="Local Kroki container URL"),
):
    """
    Import any document and automatically generate flowchart.

    Supports: PDF, DOCX, TXT, MD, and clipboard content.

    Examples:
        flowchart import document.pdf
        flowchart import workflow.docx -o output.png --renderer graphviz
        flowchart import --clipboard --extraction local-llm --model-path ./model.gguf
        flowchart import process.pdf --renderer auto --extraction auto
    """
    if not input_file and not clipboard:
        console.print("[red]❌ Error: Specify input file or use --clipboard[/red]")
        raise typer.Exit(1)

    config = _build_pipeline_config(
        extraction=extraction,
        renderer=renderer,
        model_path=model_path,
        quantization=quantization,
        direction=direction,
        theme=theme,
        validate=validate,
        kroki_url=kroki_url,
        graphviz_engine=graphviz_engine,
        d2_layout=d2_layout,
        n_gpu_layers=n_gpu_layers,
        n_ctx=n_ctx,
    )

    # Phase 5: Validate config against capabilities
    pipeline = FlowchartPipeline(config)
    config_issues = pipeline.validate_config()
    if config_issues:
        console.print("[yellow]\n⚠️  Configuration warnings:[/yellow]")
        for issue in config_issues:
            console.print(f"  [yellow]• {issue}[/yellow]")
        console.print()

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
        pipeline_config=config,
    )
    if not success:
        raise typer.Exit(1)


@app.command()
def generate(
    input_file: Path = typer.Argument(..., help="Input workflow text file"),
    output: Path = typer.Option("output.png", "-o", "--output", help="Output file path"),
    format: Optional[str] = typer.Option(None, "-f", "--format", help="Output format"),
    theme: str = typer.Option("default", "-t", "--theme", help="Mermaid theme"),
    direction: str = typer.Option("TD", "-d", "--direction", help="Flow direction"),
    validate: bool = typer.Option(True, "--validate/--no-validate", help="ISO 5807 validation"),
    width: int = typer.Option(3000, "-w", "--width", help="Output width in pixels"),
    height: int = typer.Option(2000, "-h", "--height", help="Output height in pixels"),
    extraction: str = typer.Option(
        "heuristic", "--extraction", "-e", help="Extraction: heuristic, local-llm, auto"
    ),
    renderer: str = typer.Option(
        "mermaid", "--renderer", "-r", help="Renderer: mermaid, graphviz, d2, kroki, html, auto"
    ),
    model_path: Optional[str] = typer.Option(None, "--model-path", help="GGUF model path"),
    quantization: str = typer.Option(
        "5bit", "--quantization", "-q", help="LLM quantization: 4bit, 5bit, 8bit"
    ),
    n_gpu_layers: int = typer.Option(-1, "--gpu-layers", help="GPU layers (-1 = all)"),
    n_ctx: int = typer.Option(8192, "--context-size", help="LLM context window"),
    graphviz_engine: str = typer.Option("dot", "--gv-engine", help="Graphviz engine"),
    d2_layout: str = typer.Option("elk", "--d2-layout", help="D2 layout engine"),
    kroki_url: str = typer.Option("http://localhost:8000", "--kroki-url", help="Kroki URL"),
):
    """
    Generate a flowchart from workflow text file.

    Examples:
        flowchart generate workflow.txt -o output.png
        flowchart generate workflow.txt --renderer auto --extraction auto
        flowchart generate workflow.txt --renderer graphviz --gv-engine neato
        flowchart generate workflow.txt --extraction local-llm -q 4bit --model-path ./model.gguf
    """
    console.print("[bold blue]⚙️  ISO 5807 Flowchart Generator[/bold blue]\n")

    if not input_file.exists():
        console.print(f"[red]❌ Error: Input file not found: {input_file}[/red]")
        raise typer.Exit(1)

    console.print(f"[cyan]📄 Reading workflow from: {input_file}[/cyan]")
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            workflow_text = f.read()
    except Exception as e:
        console.print(f"[red]❌ Error reading file: {e}[/red]")
        raise typer.Exit(1)

    config = _build_pipeline_config(
        extraction=extraction,
        renderer=renderer,
        model_path=model_path,
        quantization=quantization,
        direction=direction,
        theme=theme,
        validate=validate,
        kroki_url=kroki_url,
        graphviz_engine=graphviz_engine,
        d2_layout=d2_layout,
        n_gpu_layers=n_gpu_layers,
        n_ctx=n_ctx,
    )
    pipeline = FlowchartPipeline(config)

    # Phase 5: Config validation warnings
    config_issues = pipeline.validate_config()
    if config_issues:
        console.print("[yellow]⚠️  Configuration warnings:[/yellow]")
        for issue in config_issues:
            console.print(f"  [yellow]• {issue}[/yellow]")
        console.print()

    # Show active config (including auto-resolved values)
    caps = pipeline.get_capabilities()
    resolved_extraction = extraction if extraction != "auto" else caps["extractors"]["recommended"]
    resolved_renderer = renderer if renderer != "auto" else caps["renderers"]["recommended"]
    console.print(f"[dim]  Extraction: {resolved_extraction} | Renderer: {resolved_renderer}[/dim]")
    if extraction == "auto" or renderer == "auto":
        console.print("[dim]  (auto-selected based on system capabilities)[/dim]")
    if resolved_extraction == "local-llm" and model_path:
        console.print(f"[dim]  Model: {model_path} | Quantization: {quantization}[/dim]")
    if resolved_renderer == "graphviz":
        console.print(f"[dim]  Graphviz engine: {graphviz_engine}[/dim]")
    elif resolved_renderer == "d2":
        console.print(f"[dim]  D2 layout: {d2_layout}[/dim]")
    console.print()

    # Extract
    console.print("[cyan]🧠 Extracting workflow steps...[/cyan]")
    steps = pipeline.extract_steps(workflow_text)
    console.print(f"[green]✓ Extracted {len(steps)} workflow steps[/green]")

    # Build
    console.print("[cyan]🔨 Building flowchart graph...[/cyan]")
    title = input_file.stem.replace("_", " ").title()
    flowchart = pipeline.build_flowchart(steps, title=title)
    console.print(
        f"[green]✓ Created {len(flowchart.nodes)} nodes and {len(flowchart.connections)} connections[/green]"
    )

    # Validate
    if validate:
        console.print("[cyan]✅ Validating ISO 5807 compliance...[/cyan]")
        validator = ISO5807Validator()
        is_valid, errors, warnings_list = validator.validate(flowchart)
        if errors:
            console.print("[red]\n❌ Validation Errors:[/red]")
            for error in errors:
                console.print(f"  [red]• {error}[/red]")
        if warnings_list:
            console.print("[yellow]\n⚠️  Validation Warnings:[/yellow]")
            for w in warnings_list:
                console.print(f"  [yellow]• {w}[/yellow]")
        if is_valid:
            console.print("[green]✓ Flowchart is ISO 5807 compliant[/green]")
        else:
            console.print("[red]❌ Flowchart has validation errors[/red]")
            if not typer.confirm("\nContinue anyway?", default=False):
                raise typer.Exit(1)

    if format is None:
        format = output.suffix.lstrip(".")

    # Render (with automatic fallback from Phase 5)
    console.print(f"[cyan]🖨️ Rendering to {format.upper()} via {resolved_renderer}...[/cyan]")
    success = pipeline.render(flowchart, str(output), format=format)

    if not success:
        raise typer.Exit(1)

    console.print(f"\n[bold green]✅ Success! Flowchart saved to: {output}[/bold green]")


@app.command()
def validate(
    input_file: Path = typer.Argument(..., help="Input workflow text file"),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Detailed output"),
    extraction: str = typer.Option("heuristic", "--extraction", "-e", help="Extraction method"),
    model_path: Optional[str] = typer.Option(None, "--model-path", help="GGUF model path"),
):
    """
    Validate a workflow file for ISO 5807 compliance.

    Examples:
        flowchart validate workflow.txt
        flowchart validate workflow.txt --verbose --extraction auto
    """
    console.print("[bold blue]✅ ISO 5807 Validator[/bold blue]\n")

    if not input_file.exists():
        console.print(f"[red]❌ Error: Input file not found: {input_file}[/red]")
        raise typer.Exit(1)

    with open(input_file, "r", encoding="utf-8") as f:
        workflow_text = f.read()

    config = _build_pipeline_config(extraction=extraction, model_path=model_path)
    pipeline = FlowchartPipeline(config)
    steps = pipeline.extract_steps(workflow_text)

    if verbose:
        console.print(f"Extraction method: {extraction}")
        console.print(f"Parsed {len(steps)} workflow steps\n")

    builder = GraphBuilder()
    flowchart = builder.build(steps)

    if verbose:
        console.print(f"Nodes: {len(flowchart.nodes)}")
        console.print(f"Connections: {len(flowchart.connections)}\n")

    validator = ISO5807Validator()
    is_valid, errors, warnings_list = validator.validate(flowchart)

    if errors:
        console.print("[red]\n❌ Validation Errors:[/red]")
        for error in errors:
            console.print(f"  [red]• {error}[/red]")
    if warnings_list:
        console.print("[yellow]\n⚠️  Validation Warnings:[/yellow]")
        for w in warnings_list:
            console.print(f"  [yellow]• {w}[/yellow]")
    if not errors and not warnings_list:
        console.print("[green]✓ No issues found[/green]")

    if is_valid:
        console.print("\n[bold green]✅ ISO 5807 compliant[/bold green]")
        raise typer.Exit(0)
    else:
        console.print("\n[bold red]❌ Has validation errors[/bold red]")
        raise typer.Exit(1)


@app.command()
def renderers():
    """
    Show available rendering and extraction engines with system capabilities.

    Example:
        flowchart renderers
    """
    from src.capability_detector import CapabilityDetector

    console.print("[bold blue]🔍 System Capability Assessment[/bold blue]\n")

    detector = CapabilityDetector()
    caps = detector.detect()

    # Hardware
    hw_table = Table(show_header=True, header_style="bold cyan", title="Hardware")
    hw_table.add_column("Property", style="cyan", width=16)
    hw_table.add_column("Value", style="white")

    hw_table.add_row("Platform", f"{caps.platform} ({caps.arch})")
    hw_table.add_row("CPUs", str(caps.cpu_count))
    hw_table.add_row("Total RAM", f"{caps.total_ram_gb} GB")
    hw_table.add_row("Available RAM", f"{caps.available_ram_gb} GB")
    hw_table.add_row("GPU Backend", caps.gpu_backend or "CPU only")
    if caps.cuda_device_name:
        hw_table.add_row("GPU Device", caps.cuda_device_name)
        hw_table.add_row("GPU VRAM", f"{caps.cuda_vram_gb} GB")
    console.print(hw_table)

    # Renderers
    console.print("\n[bold blue]🎨 Rendering Engines[/bold blue]\n")
    r_table = Table(show_header=True, header_style="bold cyan")
    r_table.add_column("Engine", style="cyan", width=12)
    r_table.add_column("Status", width=14)
    r_table.add_column("Dependencies", style="dim")
    r_table.add_column("Best For", style="green")

    r_table.add_row(
        "mermaid",
        "[green]✓ Ready[/green]" if caps.has_mmdc_binary else "[yellow]⚠ HTML only[/yellow]",
        "Node.js + mermaid-cli",
        "HTML output, GitHub previews",
    )
    r_table.add_row(
        "graphviz",
        "[green]✓ Ready[/green]" if "graphviz" in caps.available_renderers else "[red]❌ Missing[/red]",
        "pip install graphviz + system binary",
        "Fast rendering, CI/CD",
    )
    r_table.add_row(
        "d2",
        "[green]✓ Ready[/green]" if "d2" in caps.available_renderers else "[red]❌ Missing[/red]",
        "D2 Go binary (d2lang.com)",
        "Modern aesthetics",
    )
    r_table.add_row(
        "kroki",
        "[green]✓ Ready[/green]" if caps.kroki_available else "[red]❌ Missing[/red]",
        "Docker: yuzutech/kroki",
        "Multi-engine, unified API",
    )
    r_table.add_row(
        "html", "[green]✓ Always[/green]", "None (pure Python)", "Air-gapped, zero-dep fallback"
    )
    console.print(r_table)

    # Extractors
    console.print("\n[bold blue]🧠 Extraction Engines[/bold blue]\n")
    e_table = Table(show_header=True, header_style="bold cyan")
    e_table.add_column("Method", style="cyan", width=12)
    e_table.add_column("Status", width=14)
    e_table.add_column("Dependencies", style="dim")
    e_table.add_column("Best For", style="green")

    e_table.add_row(
        "heuristic", "[green]✓ Ready[/green]", "spaCy + EntityRuler", "Fast, deterministic"
    )
    e_table.add_row(
        "local-llm",
        "[green]✓ Ready[/green]" if "local-llm" in caps.available_extractors else "[yellow]⚠ Install[/yellow]",
        "llama-cpp-python + instructor",
        "Semantic understanding",
    )
    console.print(e_table)

    # Recommendations
    console.print(
        f"\n[bold]Recommended:[/bold] --extraction {caps.recommended_extraction} --renderer {caps.recommended_renderer}"
    )

    if caps.warnings:
        console.print("\n[yellow]Warnings:[/yellow]")
        for w in caps.warnings:
            console.print(f"  [yellow]⚠ {w}[/yellow]")

    console.print("\n[dim]Use --extraction auto --renderer auto for adaptive selection[/dim]")


@app.command()
def info():
    """Display information about ISO 5807 standard and supported symbols."""
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


@app.command()
def version():
    """Display version information."""
    from src import __version__
    from src.version_check import get_version_info

    console.print(f"[bold]ISO 5807 Flowchart Generator[/bold] v{__version__}")
    console.print("Built with ❤️  by Aren Garro")
    console.print("[dim]Phase 5: Adaptive routing + WebSocket streaming[/dim]")
    console.print("[dim]Enhancement 1: Multi-workflow batch export[/dim]")
    
    # Show Python version info
    py_info = get_version_info()
    console.print(f"\n[dim]Python {py_info['current_version']} ")
    if py_info['is_recommended']:
        console.print("✓ Recommended version[/dim]")
    elif py_info['is_compatible']:
        console.print(f"(compatible, {py_info['recommended_version']} recommended)[/dim]")
    else:
        console.print("⚠️  Incompatible version![/dim]")


if __name__ == "__main__":
    app()
