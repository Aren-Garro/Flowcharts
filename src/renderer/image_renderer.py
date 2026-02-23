"""Image renderer for multi-format export."""

import subprocess
import os
import shutil
from pathlib import Path
from typing import Optional, Literal


class ImageRenderer:
    """Render Mermaid flowcharts to various image formats."""
    
    def __init__(self):
        self.mmdc_path = self._find_mmdc()
    
    def _find_mmdc(self) -> Optional[str]:
        """Find mermaid-cli (mmdc) executable."""
        # Check if mmdc is in PATH using shutil.which (cross-platform)
        mmdc = shutil.which("mmdc")
        if mmdc:
            return mmdc
        
        # Check npx mmdc as fallback
        npx = shutil.which("npx")
        if npx:
            try:
                result = subprocess.run(
                    ["npx", "-y", "@mermaid-js/mermaid-cli", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    return "npx -y @mermaid-js/mermaid-cli"
            except (FileNotFoundError, subprocess.TimeoutExpired):
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
            print("\n⚠️  Warning: mermaid-cli (mmdc) not found.")
            print("   Image rendering requires mermaid-cli to be installed.")
            print("\n   Install with: npm install -g @mermaid-js/mermaid-cli")
            print("   Or use npx: npx -y @mermaid-js/mermaid-cli")
            print("\n   For now, use .mmd or .html output formats.")
            return False
        
        # Write mermaid code to temporary file
        temp_mmd = Path(output_path).with_suffix(".mmd.temp")
        
        try:
            # Ensure output directory exists
            output_dir = Path(output_path).parent
            output_dir.mkdir(parents=True, exist_ok=True)
            
            with open(temp_mmd, "w", encoding="utf-8") as f:
                f.write(mermaid_code)
            
            # Build mmdc command
            if " " in self.mmdc_path:  # npx command
                cmd = self.mmdc_path.split() + [
                    "-i", str(temp_mmd),
                    "-o", output_path,
                    "-b", background,
                    "-t", theme
                ]
            else:
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
                text=True,
                timeout=60  # 60 second timeout
            )
            
            if result.returncode != 0:
                print(f"Error rendering: {result.stderr}")
                if "puppeteer" in result.stderr.lower():
                    print("\nTip: Try installing Puppeteer: npm install -g puppeteer")
                return False
            
            print(f"✓ Successfully rendered to: {output_path}")
            return True
            
        except subprocess.TimeoutExpired:
            print("Error: Rendering timeout (60s). The diagram may be too complex.")
            return False
        except Exception as e:
            print(f"Error during rendering: {e}")
            return False
        
        finally:
            # Clean up temp file
            try:
                if temp_mmd.exists():
                    temp_mmd.unlink()
            except Exception:
                pass  # Ignore cleanup errors
    
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
        # Escape for HTML
        safe_title = title.replace('<', '&lt;').replace('>', '&gt;')
        
        html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{safe_title}</title>
    <script type="module">
        import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
        mermaid.initialize({{ startOnLoad: true, theme: 'default' }});
    </script>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #333;
            border-bottom: 3px solid #4CAF50;
            padding-bottom: 10px;
            margin-top: 0;
        }}
        .mermaid {{
            text-align: center;
            margin: 30px 0;
            overflow-x: auto;
        }}
        .footer {{
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #e0e0e0;
            text-align: center;
            color: #666;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{safe_title}</h1>
        <div class="mermaid">
{mermaid_code}
        </div>
        <div class="footer">
            Generated with ISO 5807 Flowchart Generator
        </div>
    </div>
</body>
</html>
"""
        
        try:
            # Ensure output directory exists
            output_dir = Path(output_path).parent
            output_dir.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(html_template)
            
            print(f"✓ Successfully generated HTML: {output_path}")
            print(f"  Open in browser: file://{Path(output_path).absolute()}")
            return True
        
        except Exception as e:
            print(f"Error generating HTML: {e}")
            return False
