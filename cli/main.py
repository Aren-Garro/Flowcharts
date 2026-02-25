"""Main CLI entry point with multi-renderer and extraction method support."""

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

app = typer.Typer(
    name="flowchart",
    help="ISO 5807 Flowchart Generator - Transform workflows into professional flowcharts"
)
console = Console()


# === Shared pipeline config builder ===

def _build_pipeline_config(
    extraction: str = "heuristic",
    renderer: str = "mermaid",
    model_path: Optional[str] = None,
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
        direction=direction,
        theme=theme,
        validate=validate,
        kroki_url=kroki_url,
        graphviz_engine=graphviz_engine,
        d2_layout=d2_layout,
        n_gpu_layers=n_gpu_layers,
        n_ctx=n_ctx,
    )


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
    # Phase 2: New pipeline options
    extraction: str = typer.Option("heuristic", "--extraction", "-e",
        help="Extraction method: heuristic, local-llm, auto"),
    renderer: str = typer.Option("mermaid", "--renderer", "-r",
        help="Rendering engine: mermaid, graphviz, d2, kroki, html"),
    model_path: Optional[str] = typer.Option(None, "--model-path",
        help="Path to local GGUF model file for LLM extraction"),
    n_gpu_layers: int = typer.Option(-1, "--gpu-layers",
        help="Number of GPU layers for LLM (-1 = all)"),
    n_ctx: int = typer.Option(8192, "--context-size",
        help="LLM context window size in tokens"),
    graphviz_engine: str = typer.Option("dot", "--gv-engine",
        help="Graphviz layout engine: dot, neato, fdp, circo, twopi"),
    d2_layout: str = typer.Option("elk", "--d2-layout",
        help="D2 layout engine: dagre, elk, tala"),
    kroki_url: str = typer.Option("http://localhost:8000", "--kroki-url",
        help="Local Kroki container URL"),
):
    """
    Import any document and automatically generate flowchart.
    
    Supports: PDF, DOCX, TXT, MD, and clipboard content.
    Automatically detects and extracts workflow content.
    
    Examples:
        flowchart import document.pdf
        flowchart import workflow.docx -o output.png --renderer graphviz
        flowchart import --clipboard --extraction local-llm --model-path ./model.gguf
        flowchart import process.pdf --renderer d2 --d2-layout elk
    """
    if not input_file and not clipboard:
        console.print("[red]\u274c Error: Specify input file or use --clipboard[/red]")
        console.print("\nUsage: flowchart import [FILE] or flowchart import --clipboard")
        raise typer.Exit(1)
    
    # Build pipeline config from CLI flags
    config = _build_pipeline_config(
        extraction=extraction,
        renderer=renderer,
        model_path=model_path,
        direction=direction,
        theme=theme,
        validate=validate,
        kroki_url=kroki_url,
        graphviz_engine=graphviz_engine,
        d2_layout=d2_layout,
        n_gpu_layers=n_gpu_layers,
        n_ctx=n_ctx,
    )
    
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
    output: Path = typer.Option(
        "output.png", "-o", "--output",
        help="Output file path (png, svg, pdf, html, mmd)"
    ),
    format: Optional[str] = typer.Option(
        None, "-f", "--format",
        help="Output format (auto-detected from extension if not specified)"
    ),
    theme: str = typer.Option("default", "-t", "--theme",
        help="Mermaid theme (default, forest, dark, neutral)"),
    direction: str = typer.Option("TD", "-d", "--direction",
        help="Flow direction (TD=top-down, LR=left-right, BT=bottom-top, RL=right-left)"),
    validate: bool = typer.Option(True, "--validate/--no-validate",
        help="Validate ISO 5807 compliance"),
    width: int = typer.Option(3000, "-w", "--width",
        help="Output width in pixels (for PNG/PDF)"),
    height: int = typer.Option(2000, "-h", "--height",
        help="Output height in pixels (for PNG/PDF)"),
    # Phase 2: New pipeline options
    extraction: str = typer.Option("heuristic", "--extraction", "-e",
        help="Extraction method: heuristic, local-llm, auto"),
    renderer: str = typer.Option("mermaid", "--renderer", "-r",
        help="Rendering engine: mermaid, graphviz, d2, kroki, html"),
    model_path: Optional[str] = typer.Option(None, "--model-path",
        help="Path to local GGUF model file for LLM extraction"),
    n_gpu_layers: int = typer.Option(-1, "--gpu-layers",
        help="Number of GPU layers for LLM (-1 = all)"),
    n_ctx: int = typer.Option(8192, "--context-size",
        help="LLM context window size in tokens"),
    graphviz_engine: str = typer.Option("dot", "--gv-engine",
        help="Graphviz layout engine: dot, neato, fdp, circo, twopi"),
    d2_layout: str = typer.Option("elk", "--d2-layout",
        help="D2 layout engine: dagre, elk, tala"),
    kroki_url: str = typer.Option("http://localhost:8000", "--kroki-url",
        help="Local Kroki container URL"),
):
    """
    Generate a flowchart from workflow text file.
    
    Examples:
        flowchart generate workflow.txt -o output.png
        flowchart generate workflow.txt -o diagram.svg --renderer graphviz
        flowchart generate workflow.txt --extraction local-llm --model-path ./model.gguf
        flowchart generate workflow.txt --renderer d2 --d2-layout tala
    """
    console.print("[bold blue]\u2699\ufe0f  ISO 5807 Flowchart Generator[/bold blue]\n")
    
    if not input_file.exists():
        console.print(f"[red]\u274c Error: Input file not found: {input_file}[/red]")
        raise typer.Exit(1)
    
    # Read input
    console.print(f"[cyan]\U0001f4c4 Reading workflow from: {input_file}[/cyan]")
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            workflow_text = f.read()
    except Exception as e:
        console.print(f"[red]\u274c Error reading file: {e}[/red]")
        raise typer.Exit(1)
    
    # Build pipeline config
    config = _build_pipeline_config(
        extraction=extraction,
        renderer=renderer,
        model_path=model_path,
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
    
    # Display active configuration
    console.print(f"[dim]  Extraction: {extraction} | Renderer: {renderer}[/dim]")
    if extraction == "local-llm" and model_path:
        console.print(f"[dim]  Model: {model_path}[/dim]")
    if renderer == "graphviz":
        console.print(f"[dim]  Graphviz engine: {graphviz_engine}[/dim]")
    elif renderer == "d2":
        console.print(f"[dim]  D2 layout: {d2_layout}[/dim]")
    elif renderer == "kroki":
        console.print(f"[dim]  Kroki URL: {kroki_url}[/dim]")
    console.print()
    
    # Extract steps via pipeline
    console.print("[cyan]\U0001f9e0 Extracting workflow steps...[/cyan]")
    steps = pipeline.extract_steps(workflow_text)
    console.print(f"[green]\u2713 Extracted {len(steps)} workflow steps[/green]")
    
    # Build flowchart
    console.print("[cyan]\U0001f528 Building flowchart graph...[/cyan]")
    title = input_file.stem.replace('_', ' ').title()
    flowchart = pipeline.build_flowchart(steps, title=title)
    console.print(f"[green]\u2713 Created {len(flowchart.nodes)} nodes and {len(flowchart.connections)} connections[/green]")
    
    # Validate
    if validate:
        console.print("[cyan]\u2705 Validating ISO 5807 compliance...[/cyan]")
        validator = ISO5807Validator()
        is_valid, errors, warnings = validator.validate(flowchart)
        
        if errors:
            console.print("[red]\n\u274c Validation Errors:[/red]")
            for error in errors:
                console.print(f"  [red]\u2022 {error}[/red]")
        if warnings:
            console.print("[yellow]\n\u26a0\ufe0f  Validation Warnings:[/yellow]")
            for warning in warnings:
                console.print(f"  [yellow]\u2022 {warning}[/yellow]")
        if is_valid:
            console.print("[green]\u2713 Flowchart is ISO 5807 compliant[/green]")
        else:
            console.print("[red]\u274c Flowchart has validation errors[/red]")
            if not typer.confirm("\nContinue anyway?", default=False):
                raise typer.Exit(1)
    
    # Determine output format
    if format is None:
        format = output.suffix.lstrip('.')
    
    # Render via pipeline
    console.print(f"[cyan]\U0001f5a8\ufe0f Rendering to {format.upper()} via {renderer}...[/cyan]")
    success = pipeline.render(flowchart, str(output), format=format)
    
    if not success:
        # Fallback: try mermaid HTML if other renderer failed
        if renderer != "mermaid" and renderer != "html":
            console.print(f"[yellow]\u26a0\ufe0f  {renderer} renderer failed. Falling back to HTML...[/yellow]")
            success = pipeline._render_html(flowchart, str(output.with_suffix('.html')))
            if success:
                console.print(f"[green]\u2713 Fallback HTML saved to: {output.with_suffix('.html')}[/green]")
        if not success:
            raise typer.Exit(1)
    
    console.print(f"\n[bold green]\u2705 Success! Flowchart saved to: {output}[/bold green]")


@app.command()
def validate(
    input_file: Path = typer.Argument(..., help="Input workflow text file"),
    verbose: bool = typer.Option(False, "-v", "--verbose", help="Show detailed output"),
    extraction: str = typer.Option("heuristic", "--extraction", "-e",
        help="Extraction method: heuristic, local-llm, auto"),
    model_path: Optional[str] = typer.Option(None, "--model-path",
        help="Path to local GGUF model file for LLM extraction"),
):
    """
    Validate a workflow file for ISO 5807 compliance without generating output.
    
    Examples:
        flowchart validate workflow.txt
        flowchart validate workflow.txt --verbose
        flowchart validate workflow.txt --extraction local-llm --model-path ./model.gguf
    """
    console.print("[bold blue]\u2705 ISO 5807 Validator[/bold blue]\n")
    
    if not input_file.exists():
        console.print(f"[red]\u274c Error: Input file not found: {input_file}[/red]")
        raise typer.Exit(1)
    
    with open(input_file, "r", encoding="utf-8") as f:
        workflow_text = f.read()
    
    # Use pipeline for extraction
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
    is_valid, errors, warnings = validator.validate(flowchart)
    
    if errors:
        console.print("[red]\n\u274c Validation Errors:[/red]")
        for error in errors:
            console.print(f"  [red]\u2022 {error}[/red]")
    if warnings:
        console.print("[yellow]\n\u26a0\ufe0f  Validation Warnings:[/yellow]")
        for warning in warnings:
            console.print(f"  [yellow]\u2022 {warning}[/yellow]")
    if not errors and not warnings:
        console.print("[green]\u2713 No issues found[/green]")
    
    if is_valid:
        console.print("\n[bold green]\u2705 Flowchart is ISO 5807 compliant[/bold green]")
        raise typer.Exit(0)
    else:
        console.print("\n[bold red]\u274c Flowchart has validation errors[/bold red]")
        raise typer.Exit(1)


@app.command()
def renderers():
    """
    Show available rendering engines and their status.
    
    Example:
        flowchart renderers
    """
    console.print("[bold blue]\U0001f3a8 Available Rendering Engines[/bold blue]\n")
    
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Engine", style="cyan", width=12)
    table.add_column("Status", width=12)
    table.add_column("Dependencies", style="dim")
    table.add_column("Best For", style="green")
    
    # Mermaid
    from src.renderer.image_renderer import ImageRenderer
    mermaid_renderer = ImageRenderer()
    mermaid_ok = mermaid_renderer.mmdc_path is not None
    table.add_row(
        "mermaid",
        "[green]\u2713 Ready[/green]" if mermaid_ok else "[yellow]\u26a0 HTML only[/yellow]",
        "Node.js + mermaid-cli (optional)",
        "HTML output, GitHub/GitLab previews"
    )
    
    # Graphviz
    try:
        from src.renderer.graphviz_renderer import GraphvizRenderer
        gv = GraphvizRenderer()
        gv_ok = gv.available
    except Exception:
        gv_ok = False
    table.add_row(
        "graphviz",
        "[green]\u2713 Ready[/green]" if gv_ok else "[red]\u274c Missing[/red]",
        "pip install graphviz + system binary",
        "Fast rendering, CI/CD pipelines"
    )
    
    # D2
    try:
        from src.renderer.d2_renderer import D2Renderer
        d2 = D2Renderer()
        d2_ok = d2.available
    except Exception:
        d2_ok = False
    table.add_row(
        "d2",
        "[green]\u2713 Ready[/green]" if d2_ok else "[red]\u274c Missing[/red]",
        "D2 Go binary (d2lang.com)",
        "Modern aesthetics, complex layouts"
    )
    
    # Kroki
    try:
        from src.renderer.kroki_renderer import KrokiRenderer
        kroki = KrokiRenderer()
        kroki_ok = kroki.available
    except Exception:
        kroki_ok = False
    table.add_row(
        "kroki",
        "[green]\u2713 Ready[/green]" if kroki_ok else "[red]\u274c Missing[/red]",
        "Docker: yuzutech/kroki",
        "Multi-engine, unified API"
    )
    
    console.print(table)
    
    # Extraction engines
    console.print("\n[bold blue]\U0001f9e0 Extraction Engines[/bold blue]\n")
    
    ext_table = Table(show_header=True, header_style="bold cyan")
    ext_table.add_column("Method", style="cyan", width=12)
    ext_table.add_column("Status", width=12)
    ext_table.add_column("Dependencies", style="dim")
    ext_table.add_column("Best For", style="green")
    
    # Heuristic
    ext_table.add_row(
        "heuristic",
        "[green]\u2713 Ready[/green]",
        "spaCy + EntityRuler (built-in)",
        "Fast, low resource, deterministic"
    )
    
    # Local LLM
    try:
        from src.parser.llm_extractor import LLMExtractor
        llm = LLMExtractor()
        llm_ok = llm.available
    except Exception:
        llm_ok = False
    ext_table.add_row(
        "local-llm",
        "[green]\u2713 Ready[/green]" if llm_ok else "[yellow]\u26a0 Install needed[/yellow]",
        "pip install llama-cpp-python instructor",
        "Complex workflows, semantic understanding"
    )
    
    console.print(ext_table)
    
    console.print("\n[dim]Use --renderer and --extraction flags to select engines[/dim]")


@app.command()
def info():
    """
    Display information about ISO 5807 standard and supported symbols.
    """
    console.print("[bold blue]\U0001f4ca ISO 5807 Flowchart Standard[/bold blue]\n")
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
    console.print("Built with \u2764\ufe0f  by Aren Garro")
    console.print("[dim]Phase 2+3: Multi-renderer + LLM extraction support[/dim]")


if __name__ == "__main__":
    app()
