"""Dynamic pipeline router for extraction and rendering method selection.

Phase 1-3: Core routing between extraction engines and renderers.
Phase 5: Adaptive auto-detection via CapabilityDetector with
hardware-aware fallback and universal accessibility.
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


ExtractionMethod = Literal["heuristic", "local-llm", "ollama", "auto"]
RendererType = Literal["mermaid", "graphviz", "d2", "kroki", "html"]
Quantization = Literal["4bit", "5bit", "8bit"]


class PipelineConfig:
    """Configuration for the flowchart generation pipeline."""

    def __init__(
        self,
        extraction: ExtractionMethod = "heuristic",
        renderer: RendererType = "mermaid",
        model_path: Optional[str] = None,
        ollama_model: Optional[str] = None,
        ollama_base_url: str = "http://localhost:11434",
        quantization: str = "5bit",
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
        self.ollama_model = ollama_model
        self.ollama_base_url = ollama_base_url
        self.quantization = quantization
        self.n_gpu_layers = n_gpu_layers
        self.n_ctx = n_ctx
        self.direction = direction
        self.theme = theme
        self.validate = validate
        self.kroki_url = kroki_url
        self.graphviz_engine = graphviz_engine
        self.d2_layout = d2_layout


class FlowchartPipeline:
    """Unified pipeline for text -> flowchart generation.

    Phase 5: Now integrates CapabilityDetector for hardware-aware
    auto-detection of best extraction method and renderer.
    Falls back gracefully on constrained environments.
    """

    def __init__(self, config: Optional[PipelineConfig] = None):
        self.config = config or PipelineConfig()
        self._llm_extractor = None
        self._ollama_extractor = None
        self._capability_detector = None
        self._last_render_metadata = {}
        self._last_extraction_metadata = {}

    @property
    def capability_detector(self):
        """Lazy-initialized capability detector."""
        if self._capability_detector is None:
            from src.capability_detector import CapabilityDetector
            self._capability_detector = CapabilityDetector(
                kroki_url=self.config.kroki_url,
                ollama_base_url=self.config.ollama_base_url,
            )
        return self._capability_detector

    def extract_steps(self, text: str) -> List[WorkflowStep]:
        """Extract workflow steps from text using configured method."""
        requested_method = self.config.extraction
        resolved_method = requested_method

        if resolved_method == "auto":
            resolved_method = self._auto_select_extraction()

        if resolved_method == "local-llm":
            steps = self._extract_with_llm(text)
        elif resolved_method == "ollama":
            steps = self._extract_with_ollama(text)
        else:
            steps = self._extract_with_heuristic(text)

        fallback_used = False
        fallback_reason = None
        final_method = resolved_method
        if resolved_method != "heuristic" and not steps:
            fallback_used = True
            fallback_reason = f"{resolved_method} extraction returned no steps"
            warnings.warn(f"{fallback_reason}. Falling back to heuristic.")
            steps = self._extract_with_heuristic(text)
            final_method = "heuristic"

        self._last_extraction_metadata = {
            "requested_extraction": requested_method,
            "resolved_extraction": resolved_method,
            "final_extraction": final_method,
            "fallback_used": fallback_used,
            "fallback_reason": fallback_reason,
        }
        return steps

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
        """Render flowchart using configured renderer with adaptive fallback."""
        requested_renderer = self.config.renderer
        renderer_type = requested_renderer

        if renderer_type == "auto":
            renderer_type = self._auto_select_renderer()

        fallback_chain = []
        final_renderer = renderer_type

        # Attempt primary renderer
        success = self._dispatch_render(renderer_type, flowchart, output_path, format)

        if not success and renderer_type not in ('mermaid', 'html'):
            # Fallback chain: try mermaid -> html
            warnings.warn(f"{renderer_type} render failed, trying mermaid fallback...")
            fallback_chain.append("mermaid")
            final_renderer = "mermaid"
            success = self._dispatch_render('mermaid', flowchart, output_path, format)

        if not success:
            # Ultimate fallback: pure Python HTML
            warnings.warn("All renderers failed. Falling back to pure HTML.")
            html_path = str(Path(output_path).with_suffix('.html'))
            fallback_chain.append("html")
            final_renderer = "html"
            success = self._render_html(flowchart, html_path)
            if success:
                output_path = html_path

        self._last_render_metadata = {
            "requested_renderer": requested_renderer,
            "resolved_renderer": renderer_type,
            "fallback_chain": fallback_chain,
            "final_renderer": final_renderer,
            "success": success,
            "output_path": output_path,
            "format": format,
        }

        return success

    def process(self, text: str, output_path: str, title: str = "Flowchart", format: str = "png") -> bool:
        """Full pipeline: text -> extract -> build -> render."""
        steps = self.extract_steps(text)
        if not steps:
            warnings.warn("No workflow steps extracted.")
            return False

        flowchart = self.build_flowchart(steps, title=title)
        return self.render(flowchart, output_path, format=format)

    def get_capabilities(self) -> dict:
        """Return system capabilities summary."""
        return self.capability_detector.get_summary()

    def get_last_render_metadata(self) -> dict:
        """Return metadata from the most recent render attempt."""
        return dict(self._last_render_metadata)

    def get_last_extraction_metadata(self) -> dict:
        """Return metadata from the most recent extraction attempt."""
        return dict(self._last_extraction_metadata)

    def validate_config(self) -> List[str]:
        """Validate current config against system capabilities."""
        return self.capability_detector.validate_config(self.config)

    # ── Auto-selection (Phase 5) ──

    def _auto_select_extraction(self) -> str:
        """Auto-detect the best extraction method using CapabilityDetector."""
        caps = self.capability_detector.detect()

        # Explicit provider preferences first
        if self.config.ollama_model:
            if 'ollama' in caps.available_extractors:
                return 'ollama'
            warnings.warn("Ollama model provided but Ollama is unavailable. Falling back.")

        # If a model path is explicitly provided, try LLM first
        if self.config.model_path:
            if 'local-llm' in caps.available_extractors:
                return 'local-llm'
            else:
                warnings.warn(
                    "Model path provided but local-llm prerequisites not met. "
                    "Falling back to heuristic."
                )

        return caps.recommended_extraction

    def _auto_select_renderer(self) -> str:
        """Auto-detect the best renderer using CapabilityDetector."""
        caps = self.capability_detector.detect()
        return caps.recommended_renderer

    # ── Dispatch ──

    def _dispatch_render(
        self,
        renderer_type: str,
        flowchart: Flowchart,
        output_path: str,
        format: str,
    ) -> bool:
        """Dispatch to specific renderer."""
        try:
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
        except Exception as e:
            warnings.warn(f"{renderer_type} renderer error: {e}")
            return False

    # ── Extraction Methods ──

    def _extract_with_heuristic(self, text: str) -> List[WorkflowStep]:
        """Enhanced heuristic extraction with EntityRuler."""
        parser = NLPParser(use_spacy=True)
        steps = parser.parse(text)

        for step in steps:
            result = classify_with_entity_rules(step.text)
            if result:
                entity_type, entity_conf, entity_label = result
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
            warnings.warn(f"LLM extraction failed: {e}")

        return []

    def _extract_with_ollama(self, text: str) -> List[WorkflowStep]:
        """Ollama-based extraction with schema validation."""
        try:
            from src.parser.ollama_extractor import OllamaExtractor

            self._ollama_extractor = OllamaExtractor(
                model=self.config.ollama_model,
                base_url=self.config.ollama_base_url,
            )
            extraction = self._ollama_extractor.extract(text)
            if extraction:
                return self._ollama_extractor.extraction_to_workflow_steps(extraction)
        except Exception as e:
            warnings.warn(f"Ollama extraction failed: {e}")

        return []

    # ── Renderers ──

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
        from src.renderer.graphviz_renderer import GraphvizRenderer

        gv = GraphvizRenderer()
        dot_source = gv.generate_dot(flowchart)

        renderer = KrokiRenderer(base_url=self.config.kroki_url)
        return renderer.render_from_source(dot_source, "graphviz", output_path, format=format)

    def _render_html(self, flowchart: Flowchart, output_path: str) -> bool:
        """Render to standalone HTML with embedded Mermaid CDN.

        This is the pure-Python fallback that works in air-gapped
        environments — no Docker, no binaries, no Node.js.
        """
        from src.renderer.image_renderer import ImageRenderer

        generator = MermaidGenerator()
        mermaid_code = generator.generate_with_theme(flowchart, theme=self.config.theme)

        renderer = ImageRenderer()
        return renderer.render_html(
            mermaid_code,
            output_path,
            title=flowchart.title or "Flowchart",
        )
