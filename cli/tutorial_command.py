"""Interactive tutorial command for new users."""
import os
import time
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

console = Console()


def tutorial_command(skip_intro: bool = typer.Option(False, "--skip-intro", help="Skip introduction")):
    """Interactive tutorial to learn flowchart generation."""
    
    if not skip_intro:
        console.print(Panel.fit(
            "[bold cyan]🎓 Flowchart Generator Tutorial[/bold cyan]\n\n"
            "Welcome! This interactive guide will teach you how to create\n"
            "professional flowcharts from plain text descriptions.\n\n"
            "[dim]This tutorial takes about 5 minutes.[/dim]",
            border_style="cyan"
        ))
        
        if not Confirm.ask("\n[yellow]Ready to start?[/yellow]", default=True):
            console.print("[dim]Tutorial cancelled. Run 'flowchart tutorial' when ready![/dim]")
            return
    
    # Create tutorial workspace
    tutorial_dir = Path("flowchart_tutorial")
    tutorial_dir.mkdir(exist_ok=True)
    os.chdir(tutorial_dir)
    
    console.print("\n[green]✓[/green] Created tutorial workspace: [cyan]flowchart_tutorial/[/cyan]")
    time.sleep(1)
    
    # Step 1: Simple workflow
    step_1_simple_workflow()
    
    # Step 2: Decision branches
    step_2_decision_workflow()
    
    # Step 3: Different renderers
    step_3_renderers()
    
    # Step 4: Batch processing
    step_4_batch_processing()
    
    # Step 5: Advanced features
    step_5_advanced()
    
    # Completion
    console.print(Panel.fit(
        "[bold green]🎉 Tutorial Complete![/bold green]\n\n"
        "You've learned the basics of flowchart generation.\n\n"
        "[bold]Next Steps:[/bold]\n"
        "• Try the examples in [cyan]examples/[/cyan]\n"
        "• Read [cyan]QUICKSTART.md[/cyan] for detailed docs\n"
        "• Check [cyan]--help[/cyan] on any command\n"
        "• Visit [link]https://github.com/Aren-Garro/Flowcharts[/link]\n\n"
        "[dim]Tutorial files saved in: flowchart_tutorial/[/dim]",
        border_style="green"
    ))


def step_1_simple_workflow():
    """Step 1: Create a simple linear workflow."""
    console.print("\n[bold cyan]📝 Step 1: Your First Flowchart[/bold cyan]")
    console.print("Let's create a simple workflow with just a few steps.\n")
    
    workflow_text = """1. Start application
2. Load configuration file
3. Initialize database connection
4. Display main menu
5. End"""
    
    console.print("[bold]Here's a simple workflow:[/bold]")
    console.print(Panel(workflow_text, border_style="blue"))
    
    if not Confirm.ask("\n[yellow]Generate this flowchart?[/yellow]", default=True):
        return
    
    # Write workflow file
    with open("simple_workflow.txt", "w") as f:
        f.write(workflow_text)
    
    console.print("\n[green]✓[/green] Created [cyan]simple_workflow.txt[/cyan]")
    
    # Show command
    cmd = "flowchart generate simple_workflow.txt -o simple.png --renderer graphviz"
    console.print(f"\n[bold]Command:[/bold] [cyan]{cmd}[/cyan]")
    
    if Confirm.ask("\n[yellow]Run this command?[/yellow]", default=True):
        console.print("\n[dim]Running command...[/dim]")
        os.system(cmd)
        console.print("\n[green]✓[/green] Flowchart generated: [cyan]simple.png[/cyan]")
        time.sleep(1)


def step_2_decision_workflow():
    """Step 2: Add decision branches."""
    console.print("\n[bold cyan]🔀 Step 2: Decision Branches[/bold cyan]")
    console.print("Flowcharts often include decisions. Let's add some!\n")
    
    workflow_text = """1. User attempts login
2. Check if credentials are valid
   - If yes: Load user profile
   - If no: Display error message
3. Check if account is active
   - If yes: Show dashboard
   - If no: Display suspension notice
4. End"""
    
    console.print("[bold]Workflow with decisions:[/bold]")
    console.print(Panel(workflow_text, border_style="blue"))
    
    if not Confirm.ask("\n[yellow]Generate this flowchart?[/yellow]", default=True):
        return
    
    with open("login_workflow.txt", "w") as f:
        f.write(workflow_text)
    
    console.print("\n[green]✓[/green] Created [cyan]login_workflow.txt[/cyan]")
    
    cmd = "flowchart generate login_workflow.txt -o login.svg --renderer graphviz -f svg"
    console.print(f"\n[bold]Command:[/bold] [cyan]{cmd}[/cyan]")
    console.print("[dim]Note: We're using SVG format this time (scalable!)[/dim]")
    
    if Confirm.ask("\n[yellow]Run this command?[/yellow]", default=True):
        console.print("\n[dim]Running command...[/dim]")
        os.system(cmd)
        console.print("\n[green]✓[/green] Flowchart generated: [cyan]login.svg[/cyan]")
        time.sleep(1)


def step_3_renderers():
    """Step 3: Try different renderers."""
    console.print("\n[bold cyan]🎨 Step 3: Different Rendering Engines[/bold cyan]")
    console.print("The tool supports multiple rendering engines. Let's compare!\n")
    
    console.print("[bold]Available renderers:[/bold]")
    console.print("• [cyan]graphviz[/cyan] - Fast, production-ready (C-compiled)")
    console.print("• [cyan]html[/cyan] - Zero dependencies, works anywhere")
    console.print("• [cyan]d2[/cyan] - Modern, beautiful diagrams")
    console.print("• [cyan]mermaid[/cyan] - GitHub/GitLab compatible")
    
    renderer = Prompt.ask(
        "\n[yellow]Which renderer to try?[/yellow]",
        choices=["graphviz", "html", "d2", "mermaid", "skip"],
        default="html"
    )
    
    if renderer == "skip":
        return
    
    cmd = f"flowchart generate login_workflow.txt -o login_{renderer}.{'html' if renderer == 'html' else 'png'} --renderer {renderer}"
    console.print(f"\n[bold]Command:[/bold] [cyan]{cmd}[/cyan]")
    
    if Confirm.ask("\n[yellow]Run this command?[/yellow]", default=True):
        console.print("\n[dim]Running command...[/dim]")
        os.system(cmd)
        console.print(f"\n[green]✓[/green] Flowchart generated with {renderer} renderer!")
        time.sleep(1)


def step_4_batch_processing():
    """Step 4: Batch processing demo."""
    console.print("\n[bold cyan]📦 Step 4: Batch Processing[/bold cyan]")
    console.print("Process multiple workflows from a single document!\n")
    
    multi_workflow = """Section 1: User Registration
1. User fills registration form
2. Validate email format
3. Check if email already exists
   - If yes: Show error
   - If no: Create account
4. Send verification email
5. End

Section 2: Password Reset
1. User requests password reset
2. Verify email exists
3. Generate reset token
4. Send reset email
5. User clicks link
6. Display password change form
7. Update password
8. End"""
    
    console.print("[bold]Multi-section document:[/bold]")
    console.print(Panel(multi_workflow, border_style="blue", title="multi_workflows.txt"))
    
    if not Confirm.ask("\n[yellow]Generate batch flowcharts?[/yellow]", default=True):
        return
    
    with open("multi_workflows.txt", "w") as f:
        f.write(multi_workflow)
    
    cmd = "flowchart batch multi_workflows.txt --split-mode section --format png"
    console.print(f"\n[bold]Command:[/bold] [cyan]{cmd}[/cyan]")
    console.print("[dim]This will create separate flowcharts for each section[/dim]")
    
    if Confirm.ask("\n[yellow]Run this command?[/yellow]", default=True):
        console.print("\n[dim]Running command...[/dim]")
        os.system(cmd)
        console.print("\n[green]✓[/green] Multiple flowcharts generated in [cyan]flowcharts/[/cyan] directory!")
        time.sleep(1)


def step_5_advanced():
    """Step 5: Advanced features overview."""
    console.print("\n[bold cyan]🚀 Step 5: Advanced Features[/bold cyan]")
    console.print("Here are some powerful features you can explore:\n")
    
    features = [
        ("Local AI Extraction", "--extraction local-llm", "Use local LLM for complex workflows"),
        ("Document Import", "flowchart import document.pdf", "Extract workflows from PDFs/DOCX"),
        ("Custom Themes", "--theme dark", "Apply visual themes"),
        ("Configuration File", ".flowchartrc", "Save your preferred settings"),
        ("Validation", "flowchart validate workflow.txt", "Check ISO 5807 compliance"),
    ]
    
    for title, cmd, desc in features:
        console.print(f"[bold cyan]•[/bold cyan] [bold]{title}[/bold]")
        console.print(f"  [dim]{desc}[/dim]")
        console.print(f"  [green]{cmd}[/green]\n")
    
    console.print("[bold]Pro Tip:[/bold] Run [cyan]flowchart --help[/cyan] to see all commands!")
    time.sleep(2)


if __name__ == "__main__":
    typer.run(tutorial_command)
