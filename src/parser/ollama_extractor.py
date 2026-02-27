"""Ollama-based workflow extraction using local chat completions.

This module mirrors the local-llm extraction contract so pipeline callers
can switch between providers without changing downstream graph generation.
"""

import json
import warnings
from typing import Any, Dict, List, Optional
from urllib import error as urlerror
from urllib import request as urlrequest

from src.parser.llm_extractor import (
    ISOShapeType,
    LLMWorkflowExtraction,
    SYSTEM_PROMPT,
)
from src.models import NodeType, WorkflowStep


def discover_ollama_models(base_url: str = "http://localhost:11434", timeout: float = 3.0) -> Dict[str, Any]:
    """Return Ollama availability and model list from `/api/tags`."""
    base = (base_url or "http://localhost:11434").rstrip("/")
    endpoint = f"{base}/api/tags"
    result: Dict[str, Any] = {
        "available": False,
        "reachable": False,
        "base_url": base,
        "models": [],
        "warnings": [],
        "error": None,
    }

    try:
        req = urlrequest.Request(endpoint, method="GET")
        with urlrequest.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
        payload = json.loads(body) if body else {}
        models = payload.get("models") or []
        normalized = []
        for model in models:
            size_bytes = model.get("size") or 0
            normalized.append(
                {
                    "name": model.get("name", ""),
                    "size_gb": round(float(size_bytes) / (1024 ** 3), 2) if size_bytes else None,
                    "modified_at": model.get("modified_at"),
                }
            )
        result["reachable"] = True
        result["available"] = len(normalized) > 0
        result["models"] = sorted(normalized, key=lambda m: m["name"])
        if not normalized:
            result["warnings"].append("Ollama reachable but no models found. Pull a model first.")
    except urlerror.URLError as e:
        result["error"] = str(e.reason) if hasattr(e, "reason") else str(e)
        result["warnings"].append("Could not reach Ollama service.")
    except Exception as e:
        result["error"] = str(e)
        result["warnings"].append("Unexpected error while querying Ollama models.")

    return result


class OllamaExtractor:
    """Extract workflow structures using a local Ollama model."""

    def __init__(
        self,
        model: Optional[str] = None,
        base_url: str = "http://localhost:11434",
        temperature: float = 0.1,
        timeout: float = 90.0,
    ):
        self.model = model
        self.base_url = (base_url or "http://localhost:11434").rstrip("/")
        self.temperature = temperature
        self.timeout = timeout

    def extract(self, text: str) -> Optional[LLMWorkflowExtraction]:
        """Extract structured workflow JSON from Ollama chat API."""
        selected_model = self.model
        if not selected_model:
            info = discover_ollama_models(self.base_url)
            models = info.get("models") or []
            if models:
                selected_model = models[0]["name"]
            else:
                warnings.warn("No Ollama model configured or discovered.")
                return None

        payload = {
            "model": selected_model,
            "stream": False,
            "format": "json",
            "options": {"temperature": self.temperature},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Extract the workflow from this text:\n\n{text}"},
            ],
        }

        try:
            req = urlrequest.Request(
                f"{self.base_url}/api/chat",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlrequest.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8", errors="replace")
            response_payload = json.loads(body) if body else {}
            content = (((response_payload.get("message") or {}).get("content")) or "").strip()
            if not content:
                warnings.warn("Ollama returned empty content.")
                return None

            parsed_json = self._parse_json_content(content)
            if parsed_json is None:
                warnings.warn("Failed to parse Ollama JSON output.")
                return None

            normalized = self._normalize_extraction_payload(parsed_json)
            extraction = LLMWorkflowExtraction.model_validate(normalized)
            if not extraction.steps:
                return None
            return extraction
        except Exception as e:
            warnings.warn(f"Ollama extraction error: {e}")
            return None

    @staticmethod
    def _normalize_extraction_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Adapt common Ollama response shapes into `LLMWorkflowExtraction` schema."""
        steps_payload = payload.get("steps")
        if isinstance(steps_payload, list):
            if all(isinstance(item, dict) and "step_id" in item and "description" in item and "iso_shape" in item for item in steps_payload):
                return payload
            payload = {"title": payload.get("title") or "Extracted Workflow", "workflow": steps_payload}

        workflow_steps = payload.get("workflow")
        if not isinstance(workflow_steps, list):
            return payload

        shape_aliases = {
            "start": "terminator",
            "end": "terminator",
            "input": "io",
            "output": "io",
            "input_output": "io",
            "subprocess": "predefined",
            "sub-process": "predefined",
        }

        normalized_steps = []
        for idx, step in enumerate(workflow_steps, start=1):
            if not isinstance(step, dict):
                continue
            step_id = str(step.get("step_id") or step.get("id") or f"step_{idx}")
            description = (
                step.get("description")
                or step.get("label")
                or step.get("text")
                or step.get("name")
                or f"Step {idx}"
            )
            raw_shape = str(
                step.get("iso_shape")
                or step.get("shape")
                or step.get("category")
                or step.get("type")
                or "process"
            ).strip().lower()
            iso_shape = shape_aliases.get(raw_shape, raw_shape)
            if iso_shape not in {item.value for item in ISOShapeType}:
                iso_shape = "process"
            connected_to = step.get("connected_to") or step.get("next") or []
            if isinstance(connected_to, str):
                connected_to = [connected_to]
            if not isinstance(connected_to, list):
                connected_to = []
            connected_to = [str(item) for item in connected_to if item]
            edge_label = step.get("edge_label") or step.get("branch") or step.get("condition")
            normalized_steps.append(
                {
                    "step_id": step_id,
                    "description": str(description),
                    "iso_shape": iso_shape,
                    "connected_to": connected_to,
                    "edge_label": str(edge_label) if edge_label else None,
                }
            )

        return {
            "title": payload.get("title") or "Extracted Workflow",
            "steps": normalized_steps,
        }

    @staticmethod
    def _parse_json_content(content: str) -> Optional[Dict[str, Any]]:
        """Parse response content as JSON with a brace-delimited fallback."""
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            start = content.find("{")
            end = content.rfind("}")
            if start >= 0 and end > start:
                try:
                    return json.loads(content[start:end + 1])
                except json.JSONDecodeError:
                    return None
            return None

    @staticmethod
    def extraction_to_workflow_steps(extraction: LLMWorkflowExtraction) -> List[WorkflowStep]:
        """Convert LLM extraction schema into pipeline WorkflowStep objects."""
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

        steps: List[WorkflowStep] = []
        for i, llm_step in enumerate(extraction.steps):
            node_type = shape_to_node.get(llm_step.iso_shape, NodeType.PROCESS)
            is_decision = node_type == NodeType.DECISION
            branches = None
            if is_decision and llm_step.connected_to:
                branches = []
                for conn_id in llm_step.connected_to:
                    branches.append(f"{llm_step.edge_label or 'Yes'}: {conn_id}")

            steps.append(
                WorkflowStep(
                    step_number=i + 1,
                    text=llm_step.description,
                    action=llm_step.description.split()[0] if llm_step.description else "Process",
                    subject=None,
                    object=None,
                    is_decision=is_decision,
                    is_loop=False,
                    branches=branches if branches else (["Yes", "No"] if is_decision else None),
                    node_type=node_type,
                    confidence=0.88,
                    alternatives=[],
                )
            )
        return steps
