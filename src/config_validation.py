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


def _normalize_with_alias(
    normalized: Dict[str, Optional[str]],
    key: str,
    aliases: Dict[str, str],
    valid_values: set,
    warnings: List[str],
    errors: List[str],
    label: str,
) -> None:
    value = normalized.get(key)
    if not value:
        return

    lower = value.lower()
    if lower in aliases:
        mapped = aliases[lower]
        warnings.append(
            f"{label} alias '{value}' is deprecated; use '{mapped}' instead."
        )
        normalized[key] = mapped
        lower = mapped
    else:
        normalized[key] = lower

    if lower not in valid_values:
        errors.append(
            f"Invalid {label.lower()} '{value}'. Valid values: {', '.join(sorted(valid_values))}"
        )


def _normalize_and_validate_lowercase(
    normalized: Dict[str, Optional[str]],
    key: str,
    valid_values: set,
    errors: List[str],
    label: str,
) -> None:
    value = normalized.get(key)
    if not value:
        return

    lower = value.lower()
    normalized[key] = lower
    if lower not in valid_values:
        errors.append(
            f"Invalid {label.lower()} '{value}'. Valid values: {', '.join(sorted(valid_values))}"
        )


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

    _normalize_with_alias(
        normalized=normalized,
        key="extraction",
        aliases=_EXTRACTION_ALIASES,
        valid_values=VALID_EXTRACTIONS,
        warnings=warnings,
        errors=errors,
        label="Extraction",
    )
    _normalize_with_alias(
        normalized=normalized,
        key="renderer",
        aliases=_RENDERER_ALIASES,
        valid_values=VALID_RENDERERS,
        warnings=warnings,
        errors=errors,
        label="Renderer",
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

    _normalize_and_validate_lowercase(
        normalized=normalized,
        key="format",
        valid_values=VALID_FORMATS,
        errors=errors,
        label="Format",
    )
    _normalize_and_validate_lowercase(
        normalized=normalized,
        key="split_mode",
        valid_values=VALID_SPLIT_MODES,
        errors=errors,
        label="Split mode",
    )

    return {
        "normalized": normalized,
        "errors": errors,
        "warnings": warnings,
    }
