"""Local LLM-based workflow extraction using llama-cpp-python.

Phase 2 Enhancement: Provides zero-shot structured workflow extraction
using quantized open-weight models running entirely locally.
No API keys, no cloud services, no recurring costs.

Requires:
    pip install llama-cpp-python instructor
"""

import warnings
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

from src.models import NodeType


# ── Pydantic schemas for structured LLM output ──

class ISOShapeType(str, Enum):
    """Restricted ISO 5807 shape types for LLM output validation."""
    TERMINATOR = "terminator"
    PROCESS = "process"
    DECISION = "decision"
    IO = "io"
    DATABASE = "database"
    DISPLAY = "display"
    DOCUMENT = "document"
    PREDEFINED = "predefined"
    MANUAL = "manual"
    CONNECTOR = "connector"


class LLMWorkflowStep(BaseModel):
    """A single workflow step extracted by the LLM."""
    step_id: str = Field(..., description="Unique identifier e.g. 'step_1', 'decision_2'")
    description: str = Field(..., description="Concise imperative text for the flowchart node")
    iso_shape: ISOShapeType = Field(..., description="ISO 5807 shape type")
    connected_to: List[str] = Field(default_factory=list, description="List of step_ids this connects to")
    edge_label: Optional[str] = Field(None, description="Label on outgoing edge (e.g. 'Yes', 'No')")


class LLMWorkflowExtraction(BaseModel):
    """Complete workflow extraction from LLM."""
    title: Optional[str] = Field(None, description="Workflow title")
    steps: List[LLMWorkflowStep] = Field(..., description="Ordered list of workflow steps")


# ── System prompt for extraction ──

SYSTEM_PROMPT = """You are a workflow extraction engine. Analyze the given text and extract a structured flowchart.

Rules:
1. Extract each procedural step chronologically.
2. For every conditional decision, explicitly identify the 'True'/'Yes' pathway and the 'False'/'No' pathway.
3. Every workflow MUST start with a terminator (start) and end with a terminator (end).
4. Categorize each step strictly using these ISO 5807 types:
   - terminator: Start/End points
   - process: Standard processing steps
   - decision: Conditional branching (if/when/whether)
   - io: Input/Output operations (read/write/send/receive)
   - database: Database operations (query/insert/update/delete)
   - display: Display/notification operations
   - document: Document/report generation
   - predefined: Subroutine/API calls
   - manual: Manual/human intervention steps
   - connector: Flow connectors
5. Use concise, imperative labels (max 10 words per step).
6. Return ONLY valid JSON matching the required schema.
"""


# ── Sliding window chunker ──

def chunk_document(text: str, max_tokens: int = 6000, overlap_tokens: int = 500) -> List[str]:
    """Split document into overlapping chunks for LLM context window.

    Args:
        text: Full document text.
        max_tokens: Maximum tokens per chunk (rough word estimate).
        overlap_tokens: Token overlap between chunks.

    Returns:
        List of text chunks.
    """
    # Rough approximation: 1 token ≈ 0.75 words
    max_words = int(max_tokens * 0.75)
    overlap_words = int(overlap_tokens * 0.75)

    words = text.split()
    if len(words) <= max_words:
        return [text]

    chunks = []
    start = 0
    while start < len(words):
        end = min(start + max_words, len(words))
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        if end >= len(words):
            break
        start = end - overlap_words

    return chunks


# ── LLM Extractor class ──

class LLMExtractor:
    """Extract workflow structures using a local quantized LLM.

    Uses llama-cpp-python for inference and Instructor for
    Pydantic schema validation with automatic self-correction.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        n_gpu_layers: int = -1,
        n_ctx: int = 8192,
        temperature: float = 0.1,
        max_retries: int = 3,
    ):
        self.model_path = model_path
        self.n_gpu_layers = n_gpu_layers
        self.n_ctx = n_ctx
        self.temperature = temperature
        self.max_retries = max_retries
        self._llm = None
        self._client = None
        self._available = None

    @property
    def available(self) -> bool:
        """Check if LLM dependencies are installed."""
        if self._available is None:
            try:
                __import__("llama_cpp")
                __import__("instructor")
                self._available = True
            except ImportError:
                self._available = False
        return self._available

    def _init_model(self):
        """Lazily initialize the LLM model and Instructor client."""
        if self._client is not None:
            return

        if not self.model_path:
            raise ValueError(
                "No model_path specified. Provide a path to a GGUF model file.\n"
                "Download models from: https://huggingface.co/models?search=gguf"
            )

        try:
            from llama_cpp import Llama
            import instructor

            self._llm = Llama(
                model_path=self.model_path,
                n_gpu_layers=self.n_gpu_layers,
                n_ctx=self.n_ctx,
                verbose=False,
            )

            # Wrap with Instructor for structured output validation
            self._client = instructor.from_llama(
                self._llm,
                mode=instructor.Mode.JSON,
            )

        except Exception as e:
            raise RuntimeError(f"Failed to initialize LLM: {e}")

    def extract(self, text: str) -> Optional[LLMWorkflowExtraction]:
        """Extract workflow from text using the local LLM.

        Args:
            text: Workflow/process description text.

        Returns:
            LLMWorkflowExtraction with structured steps, or None on failure.
        """
        if not self.available:
            warnings.warn(
                "LLM extraction unavailable. Install: pip install llama-cpp-python instructor"
            )
            return None

        self._init_model()

        # Chunk if document is too large
        chunks = chunk_document(text, max_tokens=self.n_ctx - 2000)

        all_steps = []
        for i, chunk in enumerate(chunks):
            try:
                result = self._extract_chunk(chunk, chunk_index=i)
                if result and result.steps:
                    all_steps.extend(result.steps)
            except Exception as e:
                warnings.warn(f"LLM extraction failed for chunk {i}: {e}")
                continue

        if not all_steps:
            return None

        return LLMWorkflowExtraction(
            title=f"Extracted Workflow",
            steps=all_steps,
        )

    def _extract_chunk(self, chunk: str, chunk_index: int = 0) -> Optional[LLMWorkflowExtraction]:
        """Extract from a single text chunk with Instructor validation."""
        user_prompt = f"Extract the workflow from this text:\n\n{chunk}"

        try:
            result = self._client.chat.completions.create(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                response_model=LLMWorkflowExtraction,
                max_retries=self.max_retries,
                temperature=self.temperature,
            )
            return result

        except Exception as e:
            warnings.warn(f"LLM extraction error: {e}")
            return None

    def extraction_to_workflow_steps(self, extraction: LLMWorkflowExtraction):
        """Convert LLM extraction to standard WorkflowStep objects.

        This bridges the LLM output to the existing graph_builder pipeline.
        """
        from src.models import WorkflowStep

        steps = []
        shape_to_node = {
            ISOShapeType.TERMINATOR: NodeType.TERMINATOR,
            ISOShapeType.PROCESS: NodeType.PROCESS,
            ISOShapeType.DECISION: NodeType.DECISION,
            ISOShapeType.IO: NodeType.IO,
            ISOShapeType.DATABASE: NodeType.DATABASE,
            ISOShapeType.DISPLAY: NodeType.DISPLAY,
            ISOShapeType.DOCUMENT: NodeType.DOCUMENT,
            ISOShapeType.PREDEFINED: NodeType.PREDEFINED,
            ISOShapeType.MANUAL: NodeType.MANUAL,
            ISOShapeType.CONNECTOR: NodeType.CONNECTOR,
        }

        for i, llm_step in enumerate(extraction.steps):
            node_type = shape_to_node.get(llm_step.iso_shape, NodeType.PROCESS)
            is_decision = node_type == NodeType.DECISION

            branches = None
            if is_decision and llm_step.connected_to:
                branches = []
                for conn_id in llm_step.connected_to:
                    label = llm_step.edge_label or "Yes"
                    branches.append(f"{label}: {conn_id}")

            step = WorkflowStep(
                step_number=i + 1,
                text=llm_step.description,
                action=llm_step.description.split()[0] if llm_step.description else "Process",
                subject=None,
                object=None,
                is_decision=is_decision,
                is_loop=False,
                branches=branches if branches else (["Yes", "No"] if is_decision else None),
                node_type=node_type,
                confidence=0.90,
                alternatives=[],
            )
            steps.append(step)

        return steps
