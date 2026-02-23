"""Import command for processing various document formats."""

import typer
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import print as rprint

from src.importers.document_parser import DocumentParser
from src.importers.content_extractor import ContentExtractor
from src.parser.nlp_parser import NLPParser
from src.builder.graph_builder import GraphBuilder
from src.builder.validator import ISO5807Validator
from src.generator.mermaid_generator import MermaidGenerator
from src.renderer.image_renderer import ImageRenderer

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
    
    Returns:
        True if successful, False otherwise
    """
    console.print("\n[bold blue]📥 Smart Document Import[/bold blue]\n")
    
    # Step 1: Parse document
    parser = DocumentParser()
    
    if clipboard:
        console.print("[cyan]📋 Reading from clipboard...[/cyan]")
        result = parser.parse_clipboard()
    elif input_file:
        console.print(f"[cyan]📄 Reading document: {input_file}[/cyan]")
        
        if not input_file.exists():
            console.print(f"[red]❌ File not found: {input_file}[/red]")
            return False
        
        result = parser.parse(input_file)
    else:
        console.print("[red]❌ No input source specified[/red]")
        return False
    
    if not result['success']:
        console.print(f"[red]❌ Parse error: {result.get('error', 'Unknown error')}[/red]")
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
    
    console.print(f"[green]✓ Extracted {len(raw_text)} characters[/green]\n")
    
    # Step 2: Extract workflow
    console.print("[cyan]🔍 Detecting workflow content...[/cyan]")
    extractor = ContentExtractor()
    
    workflows = extractor.extract_workflows(raw_text)
    
    if not workflows:
        console.print("[yellow]⚠️  No clear workflow detected. Trying full content...[/yellow]")
        workflow_text = extractor.preprocess_for_parser(raw_text)
    else:
        # Use best workflow
        best_workflow = max(workflows, key=lambda w: w['confidence'])
        console.print(f"[green]✓ Found workflow: {best_workflow['title']} "
                     f"(confidence: {best_workflow['confidence']:.0%})[/green]")
        workflow_text = extractor.preprocess_for_parser(best_workflow['content'])
    
    # Get workflow summary
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
    
    # Step 3: Parse workflow
    console.print("[cyan]🧠 Parsing workflow structure...[/cyan]")
    nlp_parser = NLPParser(use_spacy=True)
    steps = nlp_parser.parse(workflow_text)
    console.print(f"[green]✓ Parsed {len(steps)} workflow steps[/green]")
    
    # Step 4: Build flowchart
    console.print("[cyan]🔨 Building flowchart graph...[/cyan]")
    builder = GraphBuilder()
    
    # Generate title
    if input_file:
        title = input_file.stem.replace('_', ' ').replace('-', ' ').title()
    elif workflows and workflows[0]['title']:
        title = workflows[0]['title']
    else:
        title = "Imported Workflow"
    
    flowchart = builder.build(steps, title=title)
    console.print(f"[green]✓ Created {len(flowchart.nodes)} nodes and "
                 f"{len(flowchart.connections)} connections[/green]")
    
    # Step 5: Validate if requested
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
                return False
        console.print()
    
    # Step 6: Generate Mermaid code
    console.print("[cyan]🎨 Generating Mermaid.js code...[/cyan]")
    generator = MermaidGenerator()
    mermaid_code = generator.generate_with_theme(flowchart, theme=theme)
    console.print("[green]✓ Mermaid code generated[/green]")
    
    # Step 7: Determine output path
    if output is None:
        if input_file:
            output = input_file.with_suffix(f".{format}")
        else:
            output = Path(f"workflow.{format}")
    
    # Create output directory if needed
    output.parent.mkdir(parents=True, exist_ok=True)
    
    # Step 8: Render output
    console.print(f"[cyan]🖨️  Rendering to {format.upper()}...[/cyan]")
    
    if format == "mmd":
        with open(output, "w", encoding="utf-8") as f:
            f.write(mermaid_code)
        console.print(f"[green]✓ Saved Mermaid code to: {output}[/green]")
    
    elif format == "html":
        renderer = ImageRenderer()
        success = renderer.render_html(mermaid_code, str(output), title=title)
        if not success:
            return False
    
    elif format in ["png", "svg", "pdf"]:
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
            return False
    else:
        console.print(f"[red]❌ Unsupported format: {format}[/red]")
        return False
    
    console.print(f"\n[bold green]✅ Success! Flowchart saved to: {output}[/bold green]")
    
    # Optional: Show summary
    console.print("\n[dim]Tip: Use --preview to review extracted workflow before generating[/dim]")
    
    return True
