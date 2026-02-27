"""Custom spaCy EntityRuler for domain-specific ISO 5807 workflow pattern matching.

Phase 1 Enhancement: Adds deterministic regex-based entity recognition
for workflow-specific terminology, significantly improving classification
accuracy beyond the generic en_core_web_sm model.
"""

import re
from typing import Dict, List, Optional, Tuple

from src.models import NodeType

# Domain-specific entity patterns mapping to ISO 5807 symbols
ENTITY_PATTERNS: Dict[str, dict] = {
    "CONDITIONAL_FORK": {
        "pattern": r"(?i)\b(if|in case of|whether|when|should|unless|provided that|assuming|given that|on condition)\b",
        "node_type": NodeType.DECISION,
        "confidence": 0.92,
        "description": "Conditional branching → Diamond",
    },
    "DATABASE_OP": {
        "pattern": (
            r"(?i)\b(query|insert|update|delete|commit|rollback|select|fetch from db|persist|upsert|"
            r"truncate|migrate|join tables|index|drop table|alter table)\b"
        ),
        "node_type": NodeType.DATABASE,
        "confidence": 0.90,
        "description": "Database operation → Cylinder",
    },
    "MANUAL_INTERVENTION": {
        "pattern": (
            r"(?i)\b(wait for|manually review|human review|manual check|manually approve|hand off|"
            r"escalate to|operator input|technician|physically|in person)\b"
        ),
        "node_type": NodeType.MANUAL,
        "confidence": 0.88,
        "description": "Manual operation → Trapezoid",
    },
    "DOCUMENT_GEN": {
        "pattern": (
            r"(?i)\b(generate report|export pdf|create document|print report|write log|emit certificate|"
            r"produce invoice|draft memo|compile summary|generate receipt)\b"
        ),
        "node_type": NodeType.DOCUMENT,
        "confidence": 0.90,
        "description": "Document generation → Wavy Rectangle",
    },
    "SUB_ROUTINE": {
        "pattern": (
            r"(?i)\b(invoke api|call function|execute procedure|run subroutine|trigger webhook|call service|"
            r"invoke method|run script|execute module|call endpoint)\b"
        ),
        "node_type": NodeType.PREDEFINED,
        "confidence": 0.88,
        "description": "Subroutine/API call → Double Rectangle",
    },
    "IO_OPERATION": {
        "pattern": (
            r"(?i)\b(read file|write file|upload|download|receive data|send data|transmit|stream|pipe output|"
            r"accept input|read from|write to|scan barcode|capture image)\b"
        ),
        "node_type": NodeType.IO,
        "confidence": 0.88,
        "description": "I/O operation → Parallelogram",
    },
    "DISPLAY_OP": {
        "pattern": (
            r"(?i)\b(display message|show notification|alert user|render view|preview|pop up|toast "
            r"notification|show dialog|display error|show warning|show confirmation)\b"
        ),
        "node_type": NodeType.DISPLAY,
        "confidence": 0.88,
        "description": "Display operation → Hexagon",
    },
    "TERMINATOR": {
        "pattern": r"(?i)^\s*(start|begin|end|stop|finish|terminate|exit|halt|complete|done|initialize|launch)\s*$",
        "node_type": NodeType.TERMINATOR,
        "confidence": 0.95,
        "description": "Start/End → Oval",
    },
}

# Compiled patterns for performance
_COMPILED_PATTERNS: Dict[str, re.Pattern] = {}


def _get_compiled_patterns() -> Dict[str, re.Pattern]:
    """Lazy-compile regex patterns for reuse."""
    global _COMPILED_PATTERNS
    if not _COMPILED_PATTERNS:
        _COMPILED_PATTERNS = {
            name: re.compile(cfg["pattern"])
            for name, cfg in ENTITY_PATTERNS.items()
        }
    return _COMPILED_PATTERNS


def classify_with_entity_rules(text: str) -> Optional[Tuple[NodeType, float, str]]:
    """Classify text using domain-specific entity patterns.

    Returns:
        Tuple of (NodeType, confidence, entity_label) if matched, else None.
        Patterns are checked in priority order (most specific first).
    """
    if not text or not text.strip():
        return None

    compiled = _get_compiled_patterns()

    # Priority order: more specific patterns first
    priority_order = [
        "TERMINATOR",
        "CONDITIONAL_FORK",
        "DATABASE_OP",
        "SUB_ROUTINE",
        "DOCUMENT_GEN",
        "MANUAL_INTERVENTION",
        "IO_OPERATION",
        "DISPLAY_OP",
    ]

    for entity_name in priority_order:
        pattern = compiled.get(entity_name)
        cfg = ENTITY_PATTERNS.get(entity_name)
        if pattern and cfg and pattern.search(text):
            return cfg["node_type"], cfg["confidence"], entity_name

    return None


def setup_spacy_entity_ruler(nlp):
    """Add custom EntityRuler to an existing spaCy pipeline.

    This adds domain-specific pattern matching directly into the spaCy
    pipeline so entities are recognized during standard doc processing.

    Args:
        nlp: A loaded spaCy Language object.

    Returns:
        The modified nlp object with EntityRuler added.
    """
    try:
        # Create ruler patterns in spaCy format
        ruler_patterns = []
        for entity_name, cfg in ENTITY_PATTERNS.items():
            # Extract keywords from regex for spaCy token matching
            keywords = _extract_keywords_from_pattern(cfg["pattern"])
            for keyword in keywords:
                tokens = keyword.strip().split()
                if len(tokens) == 1:
                    ruler_patterns.append({
                        "label": entity_name,
                        "pattern": tokens[0],
                    })
                else:
                    ruler_patterns.append({
                        "label": entity_name,
                        "pattern": [{"LOWER": t.lower()} for t in tokens],
                    })

        # Add ruler to pipeline
        if "entity_ruler" not in nlp.pipe_names:
            ruler = nlp.add_pipe("entity_ruler", before="ner")
            ruler.add_patterns(ruler_patterns)

        return nlp

    except Exception as e:
        import warnings
        warnings.warn(f"Failed to add EntityRuler to spaCy pipeline: {e}")
        return nlp


def _extract_keywords_from_pattern(pattern: str) -> List[str]:
    """Extract keyword phrases from a regex pattern for spaCy token matching."""
    # Remove regex metacharacters and extract plain text alternatives
    clean = pattern.replace(r"(?i)", "").replace(r"\b", "")
    clean = clean.strip("()")
    # Split on | to get alternatives
    keywords = [k.strip() for k in clean.split("|") if k.strip()]
    # Filter out regex-only entries
    keywords = [k for k in keywords if re.match(r'^[a-zA-Z\s]+$', k)]
    return keywords
