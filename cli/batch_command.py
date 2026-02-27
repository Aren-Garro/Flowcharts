"""Batch export command for multi-workflow documents."""

import zipfile
from pathlib import Path
from typing import Optional

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

    if not result['success']:
        raise ValueError(f"Failed to parse document: {result.get('error', 'Unknown error')}")

    # Extract workflow content
    raw_text = result['text']
    extractor = ContentExtractor()
    workflows = extractor.extract_workflows(raw_text)

    if workflows:
        # Use best workflow
        best_workflow = max(workflows, key=lambda w: w['confidence'])
        return extractor.preprocess_for_parser(best_workflow['content'])
    else:
        # Use full content
        return extractor.preprocess_for_parser(raw_text)


def batch_export(
    input_file: Path,
    output_dir: Optional[Path] = None,
    split_mode: str = 'auto',
    format: str = 'png',
    zip_output: bool = False,
    pipeline_config: Optional[PipelineConfig] = None,
) -> bool:
    """Export multiple workflows from a single document.

    Args:
        input_file: Source document (PDF, DOCX, TXT, MD)
        output_dir: Output directory (default: input_file_workflows/)
        split_mode: How to split: 'auto', 'section', 'subsection', 'procedure', 'none'
        format: Output format (png, svg, pdf, html, mmd)
        zip_output: Create ZIP archive instead of directory
        pipeline_config: Pipeline configuration

    Returns:
        True if successful
    """
    console.print("[bold blue]📦 Batch Workflow Export[/bold blue]\n")

    # Read document
    console.print(f"[cyan]📄 Reading document: {input_file}[/cyan]")
    try:
        text = _read_document(input_file)
        if not text:
            console.print("[red]❌ Failed to read document[/red]")
            return False
    except Exception as e:
        console.print(f"[red]❌ Error reading document: {e}[/red]")
        return False

    # Detect workflows
    console.print(f"[cyan]🔍 Detecting workflows (mode: {split_mode})...[/cyan]")
    detector = WorkflowDetector(split_mode=split_mode)
    workflows = detector.detect_workflows(text)
    console.print(f"[green]✓ Detected {len(workflows)} workflow(s)[/green]\n")

    if not workflows:
        console.print("[red]❌ No workflows detected[/red]")
        return False

    # Setup output
    if output_dir is None:
        output_dir = input_file.parent / f"{input_file.stem}_workflows"

    if zip_output:
        zip_path = output_dir.with_suffix('.zip')
        console.print(f"[cyan]📦 Creating ZIP archive: {zip_path}[/cyan]")
    else:
        output_dir.mkdir(parents=True, exist_ok=True)
        console.print(f"[cyan]📁 Output directory: {output_dir}[/cyan]")

    # Initialize pipeline
    if pipeline_config is None:
        pipeline_config = PipelineConfig()
    pipeline = FlowchartPipeline(pipeline_config)

    # Process each workflow
    success_count = 0
    failed_count = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Processing workflows...", total=len(workflows))

        for i, workflow in enumerate(workflows, 1):
            workflow_name = workflow.title or f"Workflow_{i}"
            # Sanitize filename
            safe_name = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in workflow_name)
            safe_name = safe_name.strip().replace(' ', '_')

            progress.update(task, description=f"Processing: {safe_name}")

            try:
                # Extract steps
                steps = pipeline.extract_steps(workflow.content)
                if not steps:
                    console.print(f"[yellow]⚠️  Skipping {safe_name}: No steps found[/yellow]")
                    failed_count += 1
                    progress.advance(task)
                    continue

                # Build flowchart
                flowchart = pipeline.build_flowchart(steps, title=workflow_name)

                # Render
                if zip_output:
                    # Render to temp location
                    temp_dir = output_dir.parent / ".temp_batch"
                    temp_dir.mkdir(exist_ok=True)
                    output_file = temp_dir / f"{safe_name}.{format}"
                else:
                    output_file = output_dir / f"{safe_name}.{format}"

                success = pipeline.render(flowchart, str(output_file), format=format)

                if success:
                    success_count += 1
                else:
                    console.print(f"[yellow]⚠️  Failed to render: {safe_name}[/yellow]")
                    failed_count += 1

            except Exception as e:
                console.print(f"[red]❌ Error processing {safe_name}: {e}[/red]")
                failed_count += 1

            progress.advance(task)

    # Create ZIP if requested
    if zip_output and success_count > 0:
        temp_dir = output_dir.parent / ".temp_batch"
        zip_path = output_dir.with_suffix('.zip')

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file in temp_dir.glob(f"*.{format}"):
                zf.write(file, arcname=file.name)

        # Cleanup temp
        import shutil
        shutil.rmtree(temp_dir)

        console.print(f"\n[bold green]✅ Created ZIP archive: {zip_path}[/bold green]")
    elif not zip_output:
        console.print(f"\n[bold green]✅ Exported to directory: {output_dir}[/bold green]")

    # Summary
    console.print(f"\n[bold]Summary:[/bold]")
    console.print(f"  Successful: {success_count}")
    console.print(f"  Failed: {failed_count}")
    console.print(f"  Total: {len(workflows)}")

    return success_count > 0
