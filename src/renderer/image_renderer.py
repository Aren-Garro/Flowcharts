"""Image renderer for multi-format export."""

import shutil
import subprocess
from pathlib import Path
from typing import Literal, Optional


class ImageRenderer:
    """Render Mermaid flowcharts to various image formats."""

    _MMDC_PATH_CACHE: Optional[str] = None
    _MMDC_PATH_CHECKED = False

    def __init__(self):
        self.mmdc_path = self._find_mmdc()

    def _find_mmdc(self) -> Optional[str]:
        """Find mermaid-cli (mmdc) executable."""
        if ImageRenderer._MMDC_PATH_CHECKED:
            return ImageRenderer._MMDC_PATH_CACHE

        # Check if mmdc is in PATH using shutil.which (cross-platform)
        mmdc = shutil.which("mmdc")
        if mmdc:
            ImageRenderer._MMDC_PATH_CACHE = mmdc
            ImageRenderer._MMDC_PATH_CHECKED = True
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
                    ImageRenderer._MMDC_PATH_CACHE = "npx -y @mermaid-js/mermaid-cli"
                    ImageRenderer._MMDC_PATH_CHECKED = True
                    return ImageRenderer._MMDC_PATH_CACHE
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass

        ImageRenderer._MMDC_PATH_CACHE = None
        ImageRenderer._MMDC_PATH_CHECKED = True
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
            print("\nWarning: mermaid-cli (mmdc) not found.")
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
                encoding="utf-8",
                errors="replace",
                timeout=60  # 60 second timeout
            )

            if result.returncode != 0:
                stderr = result.stderr or ""
                stdout = result.stdout or ""
                detail = stderr.strip() or stdout.strip() or f"mmdc exited with code {result.returncode}"
                print(f"Error rendering: {detail}")
                if "puppeteer" in detail.lower():
                    print("\nTip: Try installing Puppeteer: npm install -g puppeteer")
                return False

            print(f"Successfully rendered to: {output_path}")
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
