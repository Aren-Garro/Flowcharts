"""Tests for polished export profile behavior on /api/render."""

import base64
from io import BytesIO
from pathlib import Path

import web.app as web_app
from PIL import Image
from PyPDF2 import PdfReader


app = web_app.app


def _write_png(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\nPNGDATA")


def test_render_polished_export_returns_file_and_renderer_headers(monkeypatch):
    def fake_render(_self, mermaid_code, output_path, format="png", width=3000, height=2000, background="white", theme="default"):
        _write_png(Path(output_path))
        assert width >= 4200
        assert height >= 2800
        assert background == "white"
        return True

    monkeypatch.setattr(web_app.ImageRenderer, "render", fake_render)

    with app.test_client() as client:
        response = client.post(
            "/api/render",
            json={
                "mermaid_code": "flowchart TD\nA-->B",
                "format": "png",
                "renderer": "graphviz",
                "profile": "polished",
                "quality_mode": "draft_allowed",
            },
        )
        assert response.status_code == 200
        assert response.data.startswith(b"\x89PNG\r\n\x1a\n")
        assert response.headers.get("X-Flowchart-Profile") == "polished"
        assert response.headers.get("X-Flowchart-Requested-Renderer") == "graphviz"
        assert response.headers.get("X-Flowchart-Resolved-Renderer") in {"mermaid", "graphviz"}
        assert response.headers.get("X-Flowchart-Export-Strategy") in {"mermaid-polished", "graphviz-polished"}
        assert "print-ready" in (response.headers.get("X-Flowchart-Export-Notice") or "").lower()


def test_render_rejects_invalid_pdf_artifact(monkeypatch):
    def fake_render(_self, mermaid_code, output_path, format="pdf", width=3000, height=2000, background="white", theme="default"):
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"NOT_A_PDF")
        return True

    monkeypatch.setattr(web_app.ImageRenderer, "render", fake_render)
    monkeypatch.setattr(web_app.HTMLFallbackRenderer, "render", lambda _self, _code, _path, title="Flowchart": False)

    with app.test_client() as client:
        response = client.post(
            "/api/render",
            json={
                "mermaid_code": "flowchart TD\nA-->B",
                "format": "pdf",
                "renderer": "mermaid",
                "profile": "polished",
                "strict_artifact_checks": True,
            },
        )
        assert response.status_code == 500
        payload = response.get_json()
        assert isinstance(payload, dict)
        assert "Artifact validation failed" in payload.get("error", "")


def test_render_accepts_client_png_data_url_for_pdf():
    image = Image.new("RGBA", (1800, 1200), (255, 255, 255, 255))
    buf = BytesIO()
    image.save(buf, format="PNG")
    png_bytes = buf.getvalue()
    data_url = "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")

    with app.test_client() as client:
        response = client.post(
            "/api/render",
            json={
                "renderer": "graphviz",
                "format": "pdf",
                "profile": "polished",
                "png_data_url": data_url,
            },
        )

    assert response.status_code == 200
    assert response.headers.get("X-Flowchart-Resolved-Renderer") == "client-layout"
    assert response.headers.get("X-Flowchart-Export-Strategy") == "client-layout-polished"
    assert response.data.startswith(b"%PDF")
    reader = PdfReader(BytesIO(response.data))
    page = reader.pages[0]
    assert float(page.mediabox.width) == 792.0
    assert float(page.mediabox.height) == 612.0


def test_render_accepts_tall_client_png_data_url_for_paginated_pdf():
    image = Image.new("RGBA", (1800, 7200), (255, 255, 255, 255))
    buf = BytesIO()
    image.save(buf, format="PNG")
    png_bytes = buf.getvalue()
    data_url = "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")

    with app.test_client() as client:
        response = client.post(
            "/api/render",
            json={
                "renderer": "graphviz",
                "format": "pdf",
                "profile": "polished",
                "png_data_url": data_url,
            },
        )

    assert response.status_code == 200
    assert response.headers.get("X-Flowchart-Resolved-Renderer") == "client-layout"
    assert response.headers.get("X-Flowchart-Export-Strategy") == "client-layout-polished"
    assert response.data.startswith(b"%PDF")
    reader = PdfReader(BytesIO(response.data))
    assert len(reader.pages) > 1
    first_page = reader.pages[0]
    assert float(first_page.mediabox.width) == 612.0
    assert float(first_page.mediabox.height) == 792.0


def test_render_workflow_pdf_uses_printable_pages(monkeypatch):
    def fake_process(self, workflow_text, output_path, format="png"):
        image = Image.new("RGB", (1800, 7200), (255, 255, 255))
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path, format="PNG")
        self._test_output_path = str(output_path)
        return True

    def fake_render_meta(self):
        return {
            "requested_renderer": "graphviz",
            "resolved_renderer": "graphviz",
            "final_renderer": "graphviz",
            "fallback_chain": [],
            "success": True,
            "output_path": getattr(self, "_test_output_path", ""),
            "format": "png",
        }

    monkeypatch.setattr(web_app.FlowchartPipeline, "process", fake_process)
    monkeypatch.setattr(web_app.FlowchartPipeline, "get_last_render_metadata", fake_render_meta)

    with app.test_client() as client:
        response = client.post(
            "/api/render",
            json={
                "workflow_text": "1. Start\n2. Perform very tall flow\n3. End",
                "renderer": "graphviz",
                "preferred_renderer": "graphviz",
                "format": "pdf",
                "profile": "polished",
                "direction": "LR",
                "extraction": "rules",
            },
        )

    assert response.status_code == 200
    assert response.headers.get("X-Flowchart-Resolved-Renderer") == "graphviz"
    assert response.headers.get("X-Flowchart-PDF-Layout") == "printable-pages"
    assert response.headers.get("X-Flowchart-Export-Strategy") == "graphviz-polished"
    reader = PdfReader(BytesIO(response.data))
    assert len(reader.pages) > 1
    first_page = reader.pages[0]
    assert float(first_page.mediabox.width) == 612.0
    assert float(first_page.mediabox.height) == 792.0


def test_render_client_png_data_url_png_returns_strategy_headers():
    image = Image.new("RGBA", (2200, 1400), (255, 255, 255, 255))
    buf = BytesIO()
    image.save(buf, format="PNG")
    png_bytes = buf.getvalue()
    data_url = "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")

    with app.test_client() as client:
        response = client.post(
            "/api/render",
            json={
                "renderer": "graphviz",
                "format": "png",
                "profile": "polished",
                "png_data_url": data_url,
            },
        )

    assert response.status_code == 200
    assert response.data.startswith(b"\x89PNG\r\n\x1a\n")
    assert response.headers.get("X-Flowchart-Resolved-Renderer") == "client-layout"
    assert response.headers.get("X-Flowchart-Export-Strategy") == "client-layout-polished"
    assert int(response.headers.get("X-Flowchart-Artifact-Bytes") or "0") == len(png_bytes)
