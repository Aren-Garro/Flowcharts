"""Dynamic pipeline router for extraction and rendering method selection.

Routes processing through the appropriate extraction engine (heuristic vs LLM)
and rendering backend (mermaid, graphviz, d2, kroki) based on user configuration
and available system capabilities.
"""

import warnings
from typing import Optional, List, Literal
from pathlib import Path

from src.models import Flowchart, WorkflowStep
from src.parser.nlp_parser import NLPParser
from src.parser.entity_ruler import classify_with_entity_rules
from src.builder.graph_builder import GraphBuilder
from src.builder.validator import ISO5807Validator
from src.generator.mermaid_generator import MermaidGenerator


ExtractionMethod = Literal["heuristic", "local-llm", "auto"]
RendererType = Literal["mermaid", "graphviz", "d2", "kroki", "html"]


class PipelineConfig:
    """Configuration for the flowchart generation pipeline."""

    def __init__(
        self,
        extraction: ExtractionMethod = "heuristic",
        renderer: RendererType = "mermaid",
        model_path: Optional[str] = None,
        n_gpu_layers: int = -1,
        n_ctx: int = 8192,
        direction: str = "TD",
        theme: str = "default",
        validate: bool = True,
        kroki_url: str = "http://localhost:8000",
        graphviz_engine: str = "dot",
        d2_layout: str = "elk",
    ):
        self.extraction = extraction
        self.renderer = renderer
        self.model_path = model_path
        self.n_gpu_layers = n_gpu_layers
        self.n_ctx = n_ctx
        self.direction = direction
        self.theme = theme
        self.validate = validate
        self.kroki_url = kroki_url
        self.graphviz_engine = graphviz_engine
        self.d2_layout = d2_layout


class FlowchartPipeline:
    """Unified pipeline for text → flowchart generation.

    Supports dynamic routing between extraction methods and renderers
    based on configuration and hardware capabilities.
    """

    def __init__(self, config: Optional[PipelineConfig] = None):
        self.config = config or PipelineConfig()
        self._llm_extractor = None

    def extract_steps(self, text: str) -> List[WorkflowStep]:
        """Extract workflow steps from text using configured method."""
        method = self.config.extraction

        if method == "auto":
            method = self._detect_best_method()

        if method == "local-llm":
            return self._extract_with_llm(text)
        else:
            return self._extract_with_heuristic(text)

    def build_flowchart(self, steps: List[WorkflowStep], title: str = "Flowchart") -> Flowchart:
        """Build flowchart from extracted steps."""
        builder = GraphBuilder()
        flowchart = builder.build(steps, title=title)

        if self.config.validate:
            validator = ISO5807Validator()
            is_valid, errors, warns = validator.validate(flowchart)
            if errors:
                for err in errors:
                    warnings.warn(f"Validation error: {err}")

        return flowchart

    def render(
        self,
        flowchart: Flowchart,
        output_path: str,
        format: str = "png",
    ) -> bool:
        """Render flowchart using configured renderer."""
        renderer_type = self.config.renderer

        if renderer_type == "graphviz":
            return self._render_graphviz(flowchart, output_path, format)
        elif renderer_type == "d2":
            return self._render_d2(flowchart, output_path, format)
        elif renderer_type == "kroki":
            return self._render_kroki(flowchart, output_path, format)
        elif renderer_type == "html":
            return self._render_html(flowchart, output_path)
        else:
            return self._render_mermaid(flowchart, output_path, format)

    def process(self, text: str, output_path: str, title: str = "Flowchart", format: str = "png") -> bool:
        """Full pipeline: text → extract → build → render."""
        steps = self.extract_steps(text)
        if not steps:
            warnings.warn("No workflow steps extracted.")
            return False

        flowchart = self.build_flowchart(steps, title=title)
        return self.render(flowchart, output_path, format=format)

    # ── Private methods ──

    def _detect_best_method(self) -> str:
        """Auto-detect the best extraction method."""
        if self.config.model_path:
            try:
                from src.parser.llm_extractor import LLMExtractor
                ext = LLMExtractor(model_path=self.config.model_path)
                if ext.available:
                    return "local-llm"
            except Exception:
                pass
        return "heuristic"

    def _extract_with_heuristic(self, text: str) -> List[WorkflowStep]:
        """Enhanced heuristic extraction with EntityRuler."""
        parser = NLPParser(use_spacy=True)
        steps = parser.parse(text)

        # Apply entity ruler post-classification for improved accuracy
        for step in steps:
            result = classify_with_entity_rules(step.text)
            if result:
                entity_type, entity_conf, entity_label = result
                # Only override if entity ruler has higher confidence
                if entity_conf > step.confidence:
                    step.node_type = entity_type
                    step.confidence = entity_conf

        return steps

    def _extract_with_llm(self, text: str) -> List[WorkflowStep]:
        """LLM-based extraction with Instructor validation."""
        try:
            from src.parser.llm_extractor import LLMExtractor

            if self._llm_extractor is None:
                self._llm_extractor = LLMExtractor(
                    model_path=self.config.model_path,
                    n_gpu_layers=self.config.n_gpu_layers,
                    n_ctx=self.config.n_ctx,
                )

            extraction = self._llm_extractor.extract(text)
            if extraction:
                return self._llm_extractor.extraction_to_workflow_steps(extraction)

        except Exception as e:
            warnings.warn(f"LLM extraction failed, falling back to heuristic: {e}")

        # Fallback to heuristic
        return self._extract_with_heuristic(text)

    def _render_mermaid(self, flowchart: Flowchart, output_path: str, format: str) -> bool:
        """Render via Mermaid (existing pipeline)."""
        from src.renderer.image_renderer import ImageRenderer

        generator = MermaidGenerator()
        mermaid_code = generator.generate_with_theme(flowchart, theme=self.config.theme)

        if format == "mmd":
            Path(output_path).write_text(mermaid_code, encoding="utf-8")
            return True
        elif format == "html":
            return self._render_html(flowchart, output_path)
        else:
            renderer = ImageRenderer()
            return renderer.render(mermaid_code, output_path, format=format)

    def _render_graphviz(self, flowchart: Flowchart, output_path: str, format: str) -> bool:
        """Render via native Graphviz."""
        from src.renderer.graphviz_renderer import GraphvizRenderer

        direction_map = {"TD": "TB", "LR": "LR", "BT": "BT", "RL": "RL"}
        rankdir = direction_map.get(self.config.direction, "TB")

        renderer = GraphvizRenderer(
            engine=self.config.graphviz_engine,
            rankdir=rankdir,
        )
        return renderer.render(flowchart, output_path, format=format)

    def _render_d2(self, flowchart: Flowchart, output_path: str, format: str) -> bool:
        """Render via D2 declarative language."""
        from src.renderer.d2_renderer import D2Renderer

        renderer = D2Renderer(layout=self.config.d2_layout)
        return renderer.render(flowchart, output_path, format=format)

    def _render_kroki(self, flowchart: Flowchart, output_path: str, format: str) -> bool:
        """Render via local Kroki container."""
        from src.renderer.kroki_renderer import KrokiRenderer

        # Generate Graphviz DOT source for Kroki
        from src.renderer.graphviz_renderer import GraphvizRenderer
        gv = GraphvizRenderer()
        dot_source = gv.generate_dot(flowchart)

        renderer = KrokiRenderer(base_url=self.config.kroki_url)
        return renderer.render_from_source(dot_source, "graphviz", output_path, format=format)

    def _render_html(self, flowchart: Flowchart, output_path: str) -> bool:
        """Render to standalone HTML with embedded Mermaid CDN."""
        from src.renderer.image_renderer import ImageRenderer

        generator = MermaidGenerator()
        mermaid_code = generator.generate_with_theme(flowchart, theme=self.config.theme)

        renderer = ImageRenderer()
        return renderer.render_html(
            mermaid_code,
            output_path,
            title=flowchart.title or "Flowchart",
        )
