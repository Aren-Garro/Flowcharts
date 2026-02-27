"""Kroki unified renderer for multi-engine diagram rendering.

Provides a single interface to Mermaid, Graphviz, D2, PlantUML,
and more via a locally deployed Docker container.

Setup:
    docker run -d -p 8000:8000 yuzutech/kroki

Usage:
    renderer = KrokiRenderer(base_url="http://localhost:8000")
    renderer.render_from_source(mermaid_code, "mermaid", "output.svg")
"""

import base64
import zlib
import warnings
from pathlib import Path
from typing import Literal

try:
    import urllib.request
    import urllib.error
    URLLIB_AVAILABLE = True
except ImportError:
    URLLIB_AVAILABLE = False


SUPPORTED_ENGINES = [
    "mermaid",
    "graphviz",
    "d2",
    "plantuml",
    "blockdiag",
    "actdiag",
    "nwdiag",
    "c4plantuml",
    "excalidraw",
]


class KrokiRenderer:
    """Unified diagram renderer via local Kroki instance.

    Kroki unifies all major diagramming engines behind a single
    HTTP API, deployed as a local Docker container for fee-free,
    private operation.
    """

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")
        self._available = None

    @property
    def available(self) -> bool:
        """Check if Kroki instance is reachable."""
        if self._available is None:
            try:
                req = urllib.request.Request(f"{self.base_url}/health")
                resp = urllib.request.urlopen(req, timeout=3)
                self._available = resp.status == 200
            except Exception:
                self._available = False
        return self._available

    def render_from_source(
        self,
        source: str,
        engine: str,
        output_path: str,
        format: Literal["svg", "png", "pdf"] = "svg",
    ) -> bool:
        """Render diagram source via Kroki API.

        Args:
            source: Diagram source code (Mermaid, DOT, D2, etc.).
            engine: Diagram engine name.
            output_path: Output file path.
            format: Output format.

        Returns:
            True if successful.
        """
        if engine not in SUPPORTED_ENGINES:
            warnings.warn(f"Unsupported Kroki engine: {engine}. Supported: {SUPPORTED_ENGINES}")
            return False

        if not self.available:
            warnings.warn(
                "Kroki not available. Start with:\n"
                "  docker run -d -p 8000:8000 yuzutech/kroki"
            )
            return False

        try:
            # Compress and encode the source
            compressed = zlib.compress(source.encode("utf-8"), 9)
            encoded = base64.urlsafe_b64encode(compressed).decode("ascii")

            # Build URL
            url = f"{self.base_url}/{engine}/{format}/{encoded}"

            # Fetch rendered image
            req = urllib.request.Request(url)
            resp = urllib.request.urlopen(req, timeout=30)
            data = resp.read()

            # Write to file
            out = Path(output_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(data)

            print(f"✓ Kroki ({engine}) rendered: {output_path}")
            return True

        except urllib.error.URLError as e:
            warnings.warn(f"Kroki request failed: {e}")
            return False
        except Exception as e:
            warnings.warn(f"Kroki rendering error: {e}")
            return False
