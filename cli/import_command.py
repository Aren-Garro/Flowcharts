"""Import command for processing various document formats.

Phase 2+3: Now supports multi-renderer and extraction method routing
via PipelineConfig passed from CLI flags.
"""

import typer
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.importers.document_parser import DocumentParser
from src.importers.content_extractor import ContentExtractor
from src.builder.validator import ISO5807Validator
from src.pipeline import FlowchartPipeline, PipelineConfig

console = Console()


def import_and_generate(
    input_file: Optional[Path] = None,
    output: Optional[Path] = None,
    clipboard: bool = False,
    format: str = "png",
    theme: str = "default",
    direction: str = "TD",
    validate: bool = True,
    preview: bool = False,
    width: int = 3000,
    height: int = 2000,
    pipeline_config: Optional[PipelineConfig] = None,
) -> bool:
    """
    Import document, extract workflow, and generate flowchart.
    
    Args:
        input_file: Path to document (PDF, DOCX, TXT, MD)
        output: Output file path (auto-generated if not provided)
        clipboard: Use clipboard content instead of file
        format: Output format
        theme: Mermaid theme
        direction: Flow direction
        validate: Validate ISO 5807 compliance
        preview: Show preview before generating
        width: Output width
        height: Output height
        pipeline_config: Pipeline configuration for extraction/rendering method
    
    Returns:
        True if successful, False otherwise
    """
    console.print("\n[bold blue]\U0001f4e5 Smart Document Import[/bold blue]\n")
    
    # Use pipeline config or create default
    if pipeline_config is None:
        pipeline_config = PipelineConfig(
            direction=direction,
            theme=theme,
            validate=validate,
        )
    
    pipeline = FlowchartPipeline(pipeline_config)
    
    # Display active configuration
    console.print(f"[dim]  Extraction: {pipeline_config.extraction} | Renderer: {pipeline_config.renderer}[/dim]")
    if pipeline_config.extraction == "local-llm" and pipeline_config.model_path:
        console.print(f"[dim]  Model: {pipeline_config.model_path}[/dim]")
    console.print()
    
    # Step 1: Parse document
    parser = DocumentParser()
    
    if clipboard:
        console.print("[cyan]\U0001f4cb Reading from clipboard...[/cyan]")
        result = parser.parse_clipboard()
    elif input_file:
        console.print(f"[cyan]\U0001f4c4 Reading document: {input_file}[/cyan]")
        if not input_file.exists():
            console.print(f"[red]\u274c File not found: {input_file}[/red]")
            return False
        result = parser.parse(input_file)
    else:
        console.print("[red]\u274c No input source specified[/red]")
        return False
    
    if not result['success']:
        console.print(f"[red]\u274c Parse error: {result.get('error', 'Unknown error')}[/red]")
        return False
    
    raw_text = result['text']
    metadata = result.get('metadata', {})
    
    # Show file info
    if metadata:
        info_table = Table(show_header=False, box=None)
        info_table.add_column("Key", style="cyan")
        info_table.add_column("Value", style="white")
        if 'filename' in metadata:
            info_table.add_row("File", metadata['filename'])
        if 'pages' in metadata:
            info_table.add_row("Pages", str(metadata['pages']))
        if 'size' in metadata:
            size_kb = metadata['size'] / 1024
            info_table.add_row("Size", f"{size_kb:.1f} KB")
        console.print(info_table)
    
    console.print(f"[green]\u2713 Extracted {len(raw_text)} characters[/green]\n")
    
    # Step 2: Extract workflow
    console.print("[cyan]\U0001f50d Detecting workflow content...[/cyan]")
    extractor = ContentExtractor()
    workflows = extractor.extract_workflows(raw_text)
    
    if not workflows:
        console.print("[yellow]\u26a0\ufe0f  No clear workflow detected. Trying full content...[/yellow]")
        workflow_text = extractor.preprocess_for_parser(raw_text)
    else:
        best_workflow = max(workflows, key=lambda w: w['confidence'])
        console.print(f"[green]\u2713 Found workflow: {best_workflow['title']} "
                     f"(confidence: {best_workflow['confidence']:.0%})[/green]")
        workflow_text = extractor.preprocess_for_parser(best_workflow['content'])
    
    summary = extractor.get_workflow_summary(workflow_text)
    
    summary_table = Table(show_header=False, box=None)
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Count", style="yellow")
    summary_table.add_row("Total lines", str(summary['total_lines']))
    summary_table.add_row("Numbered steps", str(summary['numbered_steps']))
    summary_table.add_row("Decision points", str(summary['decision_steps']))
    console.print(summary_table)
    console.print()
    
    # Preview if requested
    if preview:
        console.print(Panel(
            workflow_text[:500] + ("..." if len(workflow_text) > 500 else ""),
            title="[bold]Workflow Preview[/bold]",
            border_style="blue"
        ))
        if not typer.confirm("\nContinue with this workflow?", default=True):
            console.print("[yellow]Cancelled[/yellow]")
            return False
        console.print()
    
    # Step 3: Parse workflow through pipeline (uses configured extraction method)
    console.print("[cyan]\U0001f9e0 Parsing workflow structure...[/cyan]")
    steps = pipeline.extract_steps(workflow_text)
    console.print(f"[green]\u2713 Parsed {len(steps)} workflow steps[/green]")
    
    # Step 4: Build flowchart
    console.print("[cyan]\U0001f528 Building flowchart graph...[/cyan]")
    if input_file:
        title = input_file.stem.replace('_', ' ').replace('-', ' ').title()
    elif workflows and workflows[0]['title']:
        title = workflows[0]['title']
    else:
        title = "Imported Workflow"
    
    flowchart = pipeline.build_flowchart(steps, title=title)
    console.print(f"[green]\u2713 Created {len(flowchart.nodes)} nodes and "
                 f"{len(flowchart.connections)} connections[/green]")
    
    # Step 5: Validate
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
                return False
        console.print()
    
    # Step 6: Determine output path
    if output is None:
        if input_file:
            output = input_file.with_suffix(f".{format}")
        else:
            output = Path(f"workflow.{format}")
    output.parent.mkdir(parents=True, exist_ok=True)
    
    # Step 7: Render via pipeline (uses configured renderer)
    console.print(f"[cyan]\U0001f5a8\ufe0f  Rendering to {format.upper()} via {pipeline_config.renderer}...[/cyan]")
    
    success = pipeline.render(flowchart, str(output), format=format)
    
    if not success:
        # Fallback: try HTML rendering
        if pipeline_config.renderer not in ("mermaid", "html"):
            console.print(f"[yellow]\u26a0\ufe0f  {pipeline_config.renderer} failed. Falling back to HTML...[/yellow]")
            html_output = output.with_suffix('.html')
            success = pipeline._render_html(flowchart, str(html_output))
            if success:
                console.print(f"[green]\u2713 Fallback HTML saved to: {html_output}[/green]")
                output = html_output
        
        if not success:
            return False
    
    console.print(f"\n[bold green]\u2705 Success! Flowchart saved to: {output}[/bold green]")
    console.print("\n[dim]Tip: Use --preview to review extracted workflow before generating[/dim]")
    console.print("[dim]Tip: Use 'flowchart renderers' to see available rendering engines[/dim]")
    
    return True
