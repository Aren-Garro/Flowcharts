"""Shared validation and normalization for pipeline-facing options.

Keeps CLI and web API behavior consistent for supported values and aliases.
"""

from typing import Dict, List, Optional

VALID_EXTRACTIONS = {"heuristic", "local-llm", "ollama", "auto"}
VALID_RENDERERS = {"mermaid", "graphviz", "d2", "kroki", "html", "auto"}
VALID_QUANTIZATIONS = {"4bit", "5bit", "8bit"}
VALID_DIRECTIONS = {"TD", "LR", "BT", "RL"}
VALID_FORMATS = {"png", "svg", "pdf", "html", "mmd"}
VALID_SPLIT_MODES = {"auto", "section", "subsection", "procedure", "none"}

# Soft compatibility aliases. These emit warnings and should be removed in a future minor release.
_EXTRACTION_ALIASES = {"llm": "local-llm"}
_RENDERER_ALIASES = {"dot": "graphviz"}


def normalize_pipeline_options(options: Dict[str, Optional[str]]) -> Dict[str, object]:
    """Normalize and validate pipeline options.

    Returns:
        Dict with:
            - normalized: normalized option dictionary
            - errors: list of blocking errors
            - warnings: list of non-blocking warnings
    """
    normalized = dict(options)
    errors: List[str] = []
    warnings: List[str] = []

    extraction = normalized.get("extraction")
    if extraction:
        lower = extraction.lower()
        if lower in _EXTRACTION_ALIASES:
            mapped = _EXTRACTION_ALIASES[lower]
            warnings.append(
                f"Extraction alias '{extraction}' is deprecated; use '{mapped}' instead."
            )
            normalized["extraction"] = mapped
            lower = mapped
        if lower not in VALID_EXTRACTIONS:
            errors.append(
                f"Invalid extraction '{extraction}'. Valid values: {', '.join(sorted(VALID_EXTRACTIONS))}"
            )

    renderer = normalized.get("renderer")
    if renderer:
        lower = renderer.lower()
        if lower in _RENDERER_ALIASES:
            mapped = _RENDERER_ALIASES[lower]
            warnings.append(
                f"Renderer alias '{renderer}' is deprecated; use '{mapped}' instead."
            )
            normalized["renderer"] = mapped
            lower = mapped
        if lower not in VALID_RENDERERS:
            errors.append(
                f"Invalid renderer '{renderer}'. Valid values: {', '.join(sorted(VALID_RENDERERS))}"
            )

    quantization = normalized.get("quantization")
    if quantization and quantization not in VALID_QUANTIZATIONS:
        errors.append(
            f"Invalid quantization '{quantization}'. Valid values: {', '.join(sorted(VALID_QUANTIZATIONS))}"
        )

    direction = normalized.get("direction")
    if direction and direction not in VALID_DIRECTIONS:
        errors.append(
            f"Invalid direction '{direction}'. Valid values: {', '.join(sorted(VALID_DIRECTIONS))}"
        )

    output_format = normalized.get("format")
    if output_format:
        lower = output_format.lower()
        normalized["format"] = lower
        if lower not in VALID_FORMATS:
            errors.append(
                f"Invalid format '{output_format}'. Valid values: {', '.join(sorted(VALID_FORMATS))}"
            )

    split_mode = normalized.get("split_mode")
    if split_mode:
        lower = split_mode.lower()
        normalized["split_mode"] = lower
        if lower not in VALID_SPLIT_MODES:
            errors.append(
                f"Invalid split mode '{split_mode}'. Valid values: {', '.join(sorted(VALID_SPLIT_MODES))}"
            )

    return {
        "normalized": normalized,
        "errors": errors,
        "warnings": warnings,
    }
