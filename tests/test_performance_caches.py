"""Performance-related cache regression tests."""

from src.parser import nlp_parser
from src.renderer.image_renderer import ImageRenderer


def test_nlp_parser_spacy_model_load_is_cached(monkeypatch):
    class DummySpacy:
        load_calls = 0

        @staticmethod
        def load(_name):
            DummySpacy.load_calls += 1
            return object()

    monkeypatch.setattr(nlp_parser, "SPACY_AVAILABLE", True)
    monkeypatch.setattr(nlp_parser, "spacy", DummySpacy)
    nlp_parser.NLPParser._SPACY_MODEL = None
    nlp_parser.NLPParser._SPACY_MODEL_LOAD_FAILED = False

    first = nlp_parser.NLPParser(use_spacy=True)
    second = nlp_parser.NLPParser(use_spacy=True)

    assert first.nlp is not None
    assert second.nlp is not None
    assert DummySpacy.load_calls == 1


def test_image_renderer_mmdc_lookup_is_cached(monkeypatch):
    calls = {"which": 0, "run": 0}

    def fake_which(name):
        calls["which"] += 1
        if name == "mmdc":
            return None
        if name == "npx":
            return "npx"
        return None

    class DummyResult:
        returncode = 0

    def fake_run(*_args, **_kwargs):
        calls["run"] += 1
        return DummyResult()

    monkeypatch.setattr("src.renderer.image_renderer.shutil.which", fake_which)
    monkeypatch.setattr("src.renderer.image_renderer.subprocess.run", fake_run)
    ImageRenderer._MMDC_PATH_CACHE = None
    ImageRenderer._MMDC_PATH_CHECKED = False

    r1 = ImageRenderer()
    r2 = ImageRenderer()

    assert r1.mmdc_path == "npx -y @mermaid-js/mermaid-cli"
    assert r2.mmdc_path == "npx -y @mermaid-js/mermaid-cli"
    assert calls["run"] == 1
