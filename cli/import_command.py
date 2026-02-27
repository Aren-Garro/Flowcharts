"""Import command for processing various document formats.

Phase 2+3: supports multi-renderer and extraction method routing via PipelineConfig.
"""

from pathlib import Path
from typing import Optional, Tuple

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.builder.validator import ISO5807Validator
from src.importers.content_extractor import ContentExtractor
from src.importers.document_parser import DocumentParser
from src.pipeline import FlowchartPipeline, PipelineConfig

console = Console()


def _build_pipeline(
    pipeline_config: Optional[PipelineConfig],
    *,
    direction: str,
    theme: str,
    validate: bool,
) -> Tuple[FlowchartPipeline, PipelineConfig]:
    config = pipeline_config or PipelineConfig(direction=direction, theme=theme, validate=validate)
    return FlowchartPipeline(config), config


def _parse_input_source(parser: DocumentParser, *, input_file: Optional[Path], clipboard: bool) -> Optional[dict]:
    if clipboard:
        console.print("[cyan]Reading from clipboard...[/cyan]")
        return parser.parse_clipboard()

    if not input_file:
        console.print("[red]No input source specified[/red]")
        return None

    console.print(f"[cyan]Reading document: {input_file}[/cyan]")
    if not input_file.exists():
        console.print(f"[red]File not found: {input_file}[/red]")
        return None
    return parser.parse(input_file)


def _print_metadata(metadata: dict) -> None:
    if not metadata:
        return

    info_table = Table(show_header=False, box=None)
    info_table.add_column("Key", style="cyan")
    info_table.add_column("Value", style="white")

    if "filename" in metadata:
        info_table.add_row("File", metadata["filename"])
    if "pages" in metadata:
        info_table.add_row("Pages", str(metadata["pages"]))
    if "size" in metadata:
        info_table.add_row("Size", f"{metadata['size'] / 1024:.1f} KB")

    console.print(info_table)


def _extract_workflow_text(raw_text: str) -> Tuple[str, list, ContentExtractor]:
    console.print("[cyan]Detecting workflow content...[/cyan]")
    extractor = ContentExtractor()
    workflows = extractor.extract_workflows(raw_text)

    if not workflows:
        console.print("[yellow]No clear workflow detected. Trying full content...[/yellow]")
        workflow_text = extractor.preprocess_for_parser(raw_text)
    else:
        best_workflow = max(workflows, key=lambda w: w["confidence"])
        console.print(
            f"[green]Found workflow: {best_workflow['title']} "
            f"(confidence: {best_workflow['confidence']:.0%})[/green]"
        )
        workflow_text = extractor.preprocess_for_parser(best_workflow["content"])

    summary = extractor.get_workflow_summary(workflow_text)
    summary_table = Table(show_header=False, box=None)
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Count", style="yellow")
    summary_table.add_row("Total lines", str(summary["total_lines"]))
    summary_table.add_row("Numbered steps", str(summary["numbered_steps"]))
    summary_table.add_row("Decision points", str(summary["decision_steps"]))
    console.print(summary_table)
    console.print()

    return workflow_text, workflows, extractor


def _confirm_preview(workflow_text: str, preview: bool) -> bool:
    if not preview:
        return True

    console.print(
        Panel(
            workflow_text[:500] + ("..." if len(workflow_text) > 500 else ""),
            title="[bold]Workflow Preview[/bold]",
            border_style="blue",
        )
    )
    if not typer.confirm("\nContinue with this workflow?", default=True):
        console.print("[yellow]Cancelled[/yellow]")
        return False
    console.print()
    return True


def _resolve_title(input_file: Optional[Path], workflows: list) -> str:
    if input_file:
        return input_file.stem.replace("_", " ").replace("-", " ").title()
    if workflows and workflows[0].get("title"):
        return workflows[0]["title"]
    return "Imported Workflow"


def _validate_flowchart(flowchart, validate_enabled: bool) -> bool:
    if not validate_enabled:
        return True

    console.print("[cyan]Validating ISO 5807 compliance...[/cyan]")
    validator = ISO5807Validator()
    is_valid, errors, warnings = validator.validate(flowchart)

    if errors:
        console.print("[red]\nValidation Errors:[/red]")
        for error in errors:
            console.print(f"  [red]- {error}[/red]")
    if warnings:
        console.print("[yellow]\nValidation Warnings:[/yellow]")
        for warning in warnings:
            console.print(f"  [yellow]- {warning}[/yellow]")

    if is_valid:
        console.print("[green]Flowchart is ISO 5807 compliant[/green]")
        console.print()
        return True

    console.print("[red]Flowchart has validation errors[/red]")
    if not typer.confirm("\nContinue anyway?", default=False):
        return False
    console.print()
    return True


def _resolve_output_path(output: Optional[Path], input_file: Optional[Path], output_format: str) -> Path:
    if output is not None:
        resolved = output
    elif input_file:
        resolved = input_file.with_suffix(f".{output_format}")
    else:
        resolved = Path(f"workflow.{output_format}")

    resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved


def _render_with_fallback(
    pipeline: FlowchartPipeline,
    pipeline_config: PipelineConfig,
    flowchart,
    output: Path,
    output_format: str,
) -> Optional[Path]:
    console.print(f"[cyan]Rendering to {output_format.upper()} via {pipeline_config.renderer}...[/cyan]")
    success = pipeline.render(flowchart, str(output), format=output_format)
    if success:
        return output

    if pipeline_config.renderer in ("mermaid", "html"):
        return None

    console.print(f"[yellow]{pipeline_config.renderer} failed. Falling back to HTML...[/yellow]")
    html_output = output.with_suffix(".html")
    if pipeline._render_html(flowchart, str(html_output)):
        console.print(f"[green]Fallback HTML saved to: {html_output}[/green]")
        return html_output
    return None


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
    """Import document, extract workflow, and generate flowchart."""
    del width, height

    console.print("\n[bold blue]Smart Document Import[/bold blue]\n")

    pipeline, pipeline_config = _build_pipeline(
        pipeline_config,
        direction=direction,
        theme=theme,
        validate=validate,
    )

    console.print(f"[dim]  Extraction: {pipeline_config.extraction} | Renderer: {pipeline_config.renderer}[/dim]")
    if pipeline_config.extraction == "local-llm" and pipeline_config.model_path:
        console.print(f"[dim]  Model: {pipeline_config.model_path}[/dim]")
    console.print()

    parser = DocumentParser()
    result = _parse_input_source(parser, input_file=input_file, clipboard=clipboard)
    if not result:
        return False
    if not result["success"]:
        console.print(f"[red]Parse error: {result.get('error', 'Unknown error')}[/red]")
        return False

    raw_text = result["text"]
    metadata = result.get("metadata", {})
    _print_metadata(metadata)
    console.print(f"[green]Extracted {len(raw_text)} characters[/green]\n")

    workflow_text, workflows, _ = _extract_workflow_text(raw_text)
    if not _confirm_preview(workflow_text, preview):
        return False

    console.print("[cyan]Parsing workflow structure...[/cyan]")
    steps = pipeline.extract_steps(workflow_text)
    console.print(f"[green]Parsed {len(steps)} workflow steps[/green]")

    console.print("[cyan]Building flowchart graph...[/cyan]")
    title = _resolve_title(input_file, workflows)
    flowchart = pipeline.build_flowchart(steps, title=title)
    console.print(
        f"[green]Created {len(flowchart.nodes)} nodes and "
        f"{len(flowchart.connections)} connections[/green]"
    )

    if not _validate_flowchart(flowchart, validate):
        return False

    resolved_output = _resolve_output_path(output, input_file, format)
    rendered_output = _render_with_fallback(
        pipeline,
        pipeline_config,
        flowchart,
        resolved_output,
        format,
    )
    if not rendered_output:
        return False

    console.print(f"\n[bold green]Success! Flowchart saved to: {rendered_output}[/bold green]")
    console.print("\n[dim]Tip: Use --preview to review extracted workflow before generating[/dim]")
    console.print("[dim]Tip: Use 'flowchart renderers' to see available rendering engines[/dim]")
    return True
