"""Image renderer for multi-format export."""

import subprocess
import os
from pathlib import Path
from typing import Optional, Literal


class ImageRenderer:
    """Render Mermaid flowcharts to various image formats."""
    
    def __init__(self):
        self.mmdc_path = self._find_mmdc()
    
    def _find_mmdc(self) -> Optional[str]:
        """Find mermaid-cli (mmdc) executable."""
        # Check if mmdc is in PATH
        try:
            result = subprocess.run(
                ["mmdc", "--version"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return "mmdc"
        except FileNotFoundError:
            pass
        
        return None
    
    def render(
        self,
        mermaid_code: str,
        output_path: str,
        format: Literal["png", "svg", "pdf"] = "png",
        width: int = 3000,
        height: int = 2000,
        background: str = "white",
        theme: str = "default"
    ) -> bool:
        """
        Render Mermaid code to image file.
        
        Args:
            mermaid_code: Mermaid.js flowchart code
            output_path: Path for output file
            format: Output format (png, svg, pdf)
            width: Image width in pixels
            height: Image height in pixels
            background: Background color
            theme: Mermaid theme (default, forest, dark, neutral)
            
        Returns:
            True if successful, False otherwise
        """
        if not self.mmdc_path:
            print("Error: mermaid-cli (mmdc) not found.")
            print("Install with: npm install -g @mermaid-js/mermaid-cli")
            return False
        
        # Write mermaid code to temporary file
        temp_mmd = Path(output_path).with_suffix(".mmd")
        
        try:
            with open(temp_mmd, "w", encoding="utf-8") as f:
                f.write(mermaid_code)
            
            # Build mmdc command
            cmd = [
                self.mmdc_path,
                "-i", str(temp_mmd),
                "-o", output_path,
                "-b", background,
                "-t", theme
            ]
            
            # Add format-specific options
            if format in ["png", "pdf"]:
                cmd.extend(["-w", str(width), "-H", str(height)])
            
            # Execute rendering
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                print(f"Error rendering: {result.stderr}")
                return False
            
            print(f"Successfully rendered to: {output_path}")
            return True
            
        except Exception as e:
            print(f"Error during rendering: {e}")
            return False
        
        finally:
            # Clean up temp file
            if temp_mmd.exists():
                temp_mmd.unlink()
    
    def render_html(self, mermaid_code: str, output_path: str, title: str = "Flowchart") -> bool:
        """
        Render Mermaid code to interactive HTML file.
        
        Args:
            mermaid_code: Mermaid.js flowchart code
            output_path: Path for output HTML file
            title: Page title
            
        Returns:
            True if successful, False otherwise
        """
        html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <script type="module">
        import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
        mermaid.initialize({{ startOnLoad: true, theme: 'default' }});
    </script>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #333;
            border-bottom: 2px solid #4CAF50;
            padding-bottom: 10px;
        }}
        .mermaid {{
            text-align: center;
            margin: 20px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{title}</h1>
        <div class="mermaid">
{mermaid_code}
        </div>
    </div>
</body>
</html>
"""
        
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(html_template)
            
            print(f"Successfully generated HTML: {output_path}")
            return True
        
        except Exception as e:
            print(f"Error generating HTML: {e}")
            return False
