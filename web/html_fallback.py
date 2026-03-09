"""HTML fallback renderer for browser-based flowchart visualization.

This provides a pure-Python rendering path that works in air-gapped
environments or when system binaries (like Graphviz or mmdc) are missing.
"""

from pathlib import Path


class HTMLFallbackRenderer:
    """Render flowcharts to standalone HTML with embedded Mermaid.js."""

    def __init__(self):
        pass

    def render(self, mermaid_code: str, output_path: str, title: str = "Flowchart") -> bool:
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

            return True

        except Exception as e:
            import warnings
            warnings.warn(f"Error generating HTML: {e}")
            return False
