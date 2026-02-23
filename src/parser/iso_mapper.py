"""ISO 5807 Smart Mapper: verb+object → flowchart symbol type.

Maps NLP-extracted action verbs and their objects to the correct
ISO 5807 flowchart symbol, instead of defaulting everything to rectangles.
"""

import re
from typing import List, Optional, Tuple
from src.models import NodeType


class ISO5807Mapper:
    """Map parsed action+object pairs to ISO 5807 node types with confidence."""

    # Verb → default node type
    VERB_MAP = {
        # I/O operations → Parallelogram
        'read': NodeType.IO, 'write': NodeType.IO,
        'input': NodeType.IO, 'output': NodeType.IO,
        'receive': NodeType.IO, 'send': NodeType.IO,
        'upload': NodeType.IO, 'download': NodeType.IO,
        'import': NodeType.IO, 'export': NodeType.IO,
        'load': NodeType.IO, 'scan': NodeType.IO,
        'capture': NodeType.IO, 'transmit': NodeType.IO,

        # Display operations → Hexagon
        'display': NodeType.DISPLAY, 'show': NodeType.DISPLAY,
        'alert': NodeType.DISPLAY, 'render': NodeType.DISPLAY,
        'preview': NodeType.DISPLAY, 'view': NodeType.DISPLAY,
        'notify': NodeType.DISPLAY, 'prompt': NodeType.DISPLAY,

        # Database operations → Cylinder
        'store': NodeType.DATABASE, 'query': NodeType.DATABASE,
        'fetch': NodeType.DATABASE, 'persist': NodeType.DATABASE,
        'cache': NodeType.DATABASE, 'index': NodeType.DATABASE,
        'lookup': NodeType.DATABASE,

        # Document operations → Document shape
        'log': NodeType.DOCUMENT, 'report': NodeType.DOCUMENT,
        'record': NodeType.DOCUMENT, 'document': NodeType.DOCUMENT,
        'print': NodeType.DOCUMENT, 'archive': NodeType.DOCUMENT,

        # Decision verbs → Diamond
        'check': NodeType.DECISION, 'verify': NodeType.DECISION,
        'validate': NodeType.DECISION, 'test': NodeType.DECISION,
        'compare': NodeType.DECISION, 'evaluate': NodeType.DECISION,
        'determine': NodeType.DECISION, 'assess': NodeType.DECISION,
        'confirm': NodeType.DECISION,

        # Manual operations → Trapezoid
        'enter': NodeType.MANUAL, 'type': NodeType.MANUAL,
        'fill': NodeType.MANUAL, 'sign': NodeType.MANUAL,
        'approve': NodeType.MANUAL,
    }

    # Object keywords that override verb-based mapping
    OBJECT_OVERRIDES = {
        'database': NodeType.DATABASE,
        'db': NodeType.DATABASE,
        'table': NodeType.DATABASE,
        'record': NodeType.DATABASE,
        'collection': NodeType.DATABASE,
        'file': NodeType.IO,
        'disk': NodeType.IO,
        'drive': NodeType.IO,
        'port': NodeType.IO,
        'screen': NodeType.DISPLAY,
        'monitor': NodeType.DISPLAY,
        'console': NodeType.DISPLAY,
        'dialog': NodeType.DISPLAY,
        'popup': NodeType.DISPLAY,
        'message': NodeType.DISPLAY,
        'user': NodeType.MANUAL,
        'operator': NodeType.MANUAL,
        'technician': NodeType.MANUAL,
        'api': NodeType.PREDEFINED,
        'service': NodeType.PREDEFINED,
        'function': NodeType.PREDEFINED,
        'procedure': NodeType.PREDEFINED,
        'subroutine': NodeType.PREDEFINED,
        'module': NodeType.PREDEFINED,
        'report': NodeType.DOCUMENT,
        'document': NodeType.DOCUMENT,
        'log': NodeType.DOCUMENT,
        'form': NodeType.DOCUMENT,
        'certificate': NodeType.DOCUMENT,
    }

    # Cross-reference patterns → Predefined Process
    CROSSREF_PATTERNS = [
        r'see\s+section',
        r'refer\s+to',
        r'as\s+described\s+in',
        r'follow\s+procedure',
        r'per\s+section',
        r'using\s+method',
    ]

    # Conditional patterns → Decision
    CONDITIONAL_PATTERNS = [
        r'^if\s+',
        r'^when\s+',
        r'^whether\s+',
        r'^should\s+',
        r'^does\s+',
        r'^is\s+.*\?',
        r'^has\s+.*\?',
        r'^can\s+.*\?',
        r'\bif\s+(successful|failed|error|yes|no|true|false)\b',
    ]

    def __init__(self):
        self._compiled_crossref = [re.compile(p, re.IGNORECASE) for p in self.CROSSREF_PATTERNS]
        self._compiled_conditional = [re.compile(p, re.IGNORECASE) for p in self.CONDITIONAL_PATTERNS]

    def map(self, action: str, objects: List[str], full_text: str = '') -> Tuple[NodeType, float, List[NodeType]]:
        """
        Determine ISO 5807 node type from parsed components.

        Returns:
            Tuple of (node_type, confidence, alternatives)
        """
        text_lower = full_text.lower() if full_text else ''

        # Check cross-references first → Predefined Process
        for pattern in self._compiled_crossref:
            if pattern.search(text_lower):
                return NodeType.PREDEFINED, 0.9, [NodeType.PROCESS]

        # Check conditionals → Decision
        for pattern in self._compiled_conditional:
            if pattern.search(text_lower):
                return NodeType.DECISION, 0.85, [NodeType.PROCESS]

        # Object overrides (more specific than verb)
        for obj in objects:
            obj_lower = obj.lower()
            for key, ntype in self.OBJECT_OVERRIDES.items():
                if key in obj_lower:
                    alternatives = [NodeType.PROCESS]
                    if ntype != NodeType.DATABASE:
                        alternatives.append(NodeType.DATABASE)
                    return ntype, 0.8, alternatives

        # Verb-based mapping
        action_lower = action.lower() if action else ''
        if action_lower in self.VERB_MAP:
            ntype = self.VERB_MAP[action_lower]
            # Higher confidence for unambiguous verbs
            confidence = 0.85 if ntype in (NodeType.DECISION, NodeType.IO) else 0.7
            alternatives = [NodeType.PROCESS]
            return ntype, confidence, alternatives

        # Default: Process rectangle
        return NodeType.PROCESS, 0.6, [NodeType.MANUAL, NodeType.IO]

    def map_from_text(self, text: str) -> Tuple[NodeType, float, List[NodeType]]:
        """Convenience: map directly from raw step text."""
        words = text.strip().split()
        if not words:
            return NodeType.PROCESS, 0.5, []

        action = words[0]
        objects = words[1:] if len(words) > 1 else []
        return self.map(action, objects, text)
