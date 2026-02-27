"""Tests for polished export profile behavior on /api/render."""

from pathlib import Path

import web.app as web_app


app = web_app.app


def _write_png(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\nPNGDATA")


def test_render_polished_export_returns_file_and_renderer_headers(monkeypatch):
    def fake_render(_self, mermaid_code, output_path, format="png", width=3000, height=2000, background="white", theme="default"):
        _write_png(Path(output_path))
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


def test_render_rejects_invalid_pdf_artifact(monkeypatch):
    def fake_render(_self, mermaid_code, output_path, format="pdf", width=3000, height=2000, background="white", theme="default"):
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"NOT_A_PDF")
        return True

    monkeypatch.setattr(web_app.ImageRenderer, "render", fake_render)
    monkeypatch.setattr(web_app.ImageRenderer, "render_html", lambda _self, _code, _path, title="Flowchart": False)

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
