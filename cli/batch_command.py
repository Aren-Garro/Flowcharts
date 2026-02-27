"""Batch export command for multi-workflow documents."""

import shutil
import zipfile
from pathlib import Path
from typing import Optional, Tuple

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.importers.content_extractor import ContentExtractor
from src.importers.document_parser import DocumentParser
from src.importers.workflow_detector import WorkflowDetector
from src.pipeline import FlowchartPipeline, PipelineConfig

console = Console()


def _read_document(input_file: Path) -> str:
    """Read document and extract text content."""
    parser = DocumentParser()
    result = parser.parse(input_file)

    if not result["success"]:
        raise ValueError(f"Failed to parse document: {result.get('error', 'Unknown error')}")

    raw_text = result["text"]
    extractor = ContentExtractor()
    workflows = extractor.extract_workflows(raw_text)

    if workflows:
        best_workflow = max(workflows, key=lambda w: w["confidence"])
        return extractor.preprocess_for_parser(best_workflow["content"])
    return extractor.preprocess_for_parser(raw_text)


def _resolve_output_paths(
    input_file: Path,
    output_dir: Optional[Path],
    zip_output: bool,
) -> Tuple[Path, Optional[Path]]:
    resolved_output_dir = output_dir or (input_file.parent / f"{input_file.stem}_workflows")
    zip_path = resolved_output_dir.with_suffix(".zip") if zip_output else None
    return resolved_output_dir, zip_path


def _sanitize_workflow_name(workflow_name: str) -> str:
    safe_name = "".join(c if c.isalnum() or c in (" ", "-", "_") else "_" for c in workflow_name)
    return safe_name.strip().replace(" ", "_")


def _resolve_output_file(
    *,
    output_dir: Path,
    safe_name: str,
    output_format: str,
    zip_output: bool,
) -> Path:
    if not zip_output:
        return output_dir / f"{safe_name}.{output_format}"

    temp_dir = output_dir.parent / ".temp_batch"
    temp_dir.mkdir(exist_ok=True)
    return temp_dir / f"{safe_name}.{output_format}"


def _process_single_workflow(
    *,
    pipeline: FlowchartPipeline,
    workflow,
    workflow_name: str,
    output_dir: Path,
    output_format: str,
    zip_output: bool,
) -> str:
    """Process one workflow and return status: ok, no_steps, or failed_render."""
    steps = pipeline.extract_steps(workflow.content)
    if not steps:
        return "no_steps"

    flowchart = pipeline.build_flowchart(steps, title=workflow_name)
    safe_name = _sanitize_workflow_name(workflow_name)
    output_file = _resolve_output_file(
        output_dir=output_dir,
        safe_name=safe_name,
        output_format=output_format,
        zip_output=zip_output,
    )
    if pipeline.render(flowchart, str(output_file), format=output_format):
        return "ok"
    return "failed_render"


def _finalize_zip_export(output_dir: Path, output_format: str) -> Path:
    temp_dir = output_dir.parent / ".temp_batch"
    zip_path = output_dir.with_suffix(".zip")

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in temp_dir.glob(f"*.{output_format}"):
            zf.write(file, arcname=file.name)

    shutil.rmtree(temp_dir)
    return zip_path


def _run_batch_processing(
    *,
    pipeline: FlowchartPipeline,
    workflows,
    output_dir: Path,
    output_format: str,
    zip_output: bool,
) -> Tuple[int, int]:
    success_count = 0
    failed_count = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Processing workflows...", total=len(workflows))

        for index, workflow in enumerate(workflows, 1):
            workflow_name = workflow.title or f"Workflow_{index}"
            safe_name = _sanitize_workflow_name(workflow_name)
            progress.update(task, description=f"Processing: {safe_name}")

            try:
                status = _process_single_workflow(
                    pipeline=pipeline,
                    workflow=workflow,
                    workflow_name=workflow_name,
                    output_dir=output_dir,
                    output_format=output_format,
                    zip_output=zip_output,
                )
                if status == "ok":
                    success_count += 1
                else:
                    failed_count += 1
                    if status == "no_steps":
                        console.print(f"[yellow]Skipping {safe_name}: No steps found[/yellow]")
                    else:
                        console.print(f"[yellow]Failed to render: {safe_name}[/yellow]")
            except Exception as exc:
                failed_count += 1
                console.print(f"[red]Error processing {safe_name}: {exc}[/red]")

            progress.advance(task)

    return success_count, failed_count


def batch_export(
    input_file: Path,
    output_dir: Optional[Path] = None,
    split_mode: str = "auto",
    format: str = "png",
    zip_output: bool = False,
    pipeline_config: Optional[PipelineConfig] = None,
) -> bool:
    """Export multiple workflows from a single document."""
    console.print("[bold blue]Batch Workflow Export[/bold blue]\n")
    console.print(f"[cyan]Reading document: {input_file}[/cyan]")

    try:
        text = _read_document(input_file)
    except Exception as exc:
        console.print(f"[red]Error reading document: {exc}[/red]")
        return False

    if not text:
        console.print("[red]Failed to read document[/red]")
        return False

    console.print(f"[cyan]Detecting workflows (mode: {split_mode})...[/cyan]")
    detector = WorkflowDetector(split_mode=split_mode)
    workflows = detector.detect_workflows(text)
    console.print(f"[green]Detected {len(workflows)} workflow(s)[/green]\n")

    if not workflows:
        console.print("[red]No workflows detected[/red]")
        return False

    output_dir, zip_path = _resolve_output_paths(input_file, output_dir, zip_output)
    if zip_output:
        console.print(f"[cyan]Creating ZIP archive: {zip_path}[/cyan]")
    else:
        output_dir.mkdir(parents=True, exist_ok=True)
        console.print(f"[cyan]Output directory: {output_dir}[/cyan]")

    pipeline = FlowchartPipeline(pipeline_config or PipelineConfig())

    success_count, failed_count = _run_batch_processing(
        pipeline=pipeline,
        workflows=workflows,
        output_dir=output_dir,
        output_format=format,
        zip_output=zip_output,
    )

    if zip_output and success_count > 0:
        zip_path = _finalize_zip_export(output_dir, format)
        console.print(f"\n[bold green]Created ZIP archive: {zip_path}[/bold green]")
    elif not zip_output:
        console.print(f"\n[bold green]Exported to directory: {output_dir}[/bold green]")

    console.print("\n[bold]Summary:[/bold]")
    console.print(f"  Successful: {success_count}")
    console.print(f"  Failed: {failed_count}")
    console.print(f"  Total: {len(workflows)}")

    return success_count > 0
