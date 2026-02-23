"""Pattern definitions for workflow text analysis.

Phase 2: Enhanced loop patterns, cross-reference detection,
parallel action patterns.
"""

import re
from typing import Dict, List, Optional
from src.models import NodeType


class WorkflowPatterns:
    """Centralized patterns for NLP workflow parsing."""

    PROCESS_VERBS = [
        'process', 'calculate', 'validate', 'transform', 'convert',
        'update', 'create', 'generate', 'execute', 'perform',
        'compute', 'determine', 'analyze', 'evaluate', 'modify',
        'change', 'set', 'configure', 'initialize', 'prepare'
    ]

    DECISION_PATTERNS = [
        r'\bif\b', r'\bwhether\b', r'\bcheck if\b', r'\bverify if\b',
        r'\bis\b.*\?', r'\bdoes\b.*\?', r'\bcan\b.*\?', r'\bshould\b.*\?',
        r'\bhas\b.*\?', r'\bwhen\b', r'\bin case\b', r'\bdepending on\b',
        r'\bselect\s+(?:one|from|between)\b', r'\bchoose\b',
        r'\bverify\s+that\b', r'\bensure\s+that\b',
        r'\bconfirm\s+(?:that|if|whether)\b',
    ]

    IO_VERBS = [
        'read', 'write', 'input', 'output', 'receive', 'send',
        'get', 'put', 'accept', 'return', 'submit', 'enter',
        'collect', 'gather', 'obtain', 'provide', 'upload',
        'download', 'import', 'export', 'scan', 'capture', 'transmit'
    ]

    DATABASE_VERBS = [
        'query', 'select', 'insert', 'update', 'delete', 'save',
        'fetch', 'retrieve', 'store', 'persist', 'load', 'find',
        'search', 'lookup', 'add to database', 'remove from database',
        'cache', 'index'
    ]

    DISPLAY_VERBS = [
        'display', 'show', 'render', 'present', 'visualize',
        'draw', 'print to screen', 'output to screen',
        'alert', 'notify', 'prompt', 'preview'
    ]

    DOCUMENT_VERBS = [
        'print', 'export', 'generate report', 'create document',
        'produce document', 'write to file', 'save report',
        'log', 'record', 'archive', 'document'
    ]

    TERMINATOR_KEYWORDS = [
        'start', 'begin', 'end', 'finish', 'stop', 'terminate',
        'exit', 'complete', 'done'
    ]

    LOOP_PATTERNS = [
        r'\bfor each\b', r'\bwhile\b', r'\brepeat\b', r'\bloop\b',
        r'\biterate\b', r'\buntil\b', r'\breturn to step\b',
        r'\bgo back to\b', r'\bcontinue\b',
        r'\brepeat\s+(?:from\s+)?step\s+\d+\b',
        r'\bloop\s+back\s+to\b',
        r'\brestart\s+(?:at|from)\b',
        r'\bresume\s+(?:at|from)\b',
        r'\bretry\b',
        r'\bredo\b',
        r'\bcycle\s+(?:back|through)\b',
    ]

    CROSSREF_PATTERNS = [
        r'\bsee\s+section\b',
        r'\brefer\s+to\b',
        r'\bas\s+described\s+in\b',
        r'\bfollow\s+procedure\b',
        r'\bper\s+(?:section|procedure|protocol|guideline)\b',
        r'\busing\s+(?:method|protocol)\b',
        r'\baccording\s+to\s+(?:section|procedure)\b',
    ]

    PARALLEL_PATTERNS = [
        r'\bmeanwhile\b',
        r'\bsimultaneously\b',
        r'\bat\s+the\s+same\s+time\b',
        r'\bin\s+parallel\b',
        r'\bconcurrently\b',
    ]

    POSITIVE_BRANCHES = ['yes', 'true', 'valid', 'success', 'pass', 'approved', 'correct', 'complete']
    NEGATIVE_BRANCHES = ['no', 'false', 'invalid', 'failure', 'fail', 'rejected', 'incorrect', 'incomplete']

    @classmethod
    def detect_node_type(cls, text: str) -> NodeType:
        """Detect the appropriate node type based on text content."""
        text_lower = text.lower()

        if any(keyword in text_lower for keyword in cls.TERMINATOR_KEYWORDS):
            return NodeType.TERMINATOR
        if cls.is_crossref(text_lower):
            return NodeType.PREDEFINED
        if any(re.search(pattern, text_lower) for pattern in cls.DECISION_PATTERNS):
            return NodeType.DECISION
        if any(verb in text_lower for verb in cls.DATABASE_VERBS):
            return NodeType.DATABASE
        if any(verb in text_lower for verb in cls.DISPLAY_VERBS):
            return NodeType.DISPLAY
        if any(verb in text_lower for verb in cls.DOCUMENT_VERBS):
            return NodeType.DOCUMENT
        if any(verb in text_lower for verb in cls.IO_VERBS):
            return NodeType.IO
        return NodeType.PROCESS

    @classmethod
    def is_decision(cls, text: str) -> bool:
        """Check if text represents a decision point."""
        text_lower = text.lower()
        return any(re.search(pattern, text_lower) for pattern in cls.DECISION_PATTERNS)

    @classmethod
    def is_loop(cls, text: str) -> bool:
        """Check if text represents a loop."""
        text_lower = text.lower()
        return any(re.search(pattern, text_lower) for pattern in cls.LOOP_PATTERNS)

    @classmethod
    def is_crossref(cls, text: str) -> bool:
        """Check if text contains a cross-reference to another procedure."""
        text_lower = text.lower() if text else ''
        return any(re.search(pattern, text_lower) for pattern in cls.CROSSREF_PATTERNS)

    @classmethod
    def is_parallel(cls, text: str) -> bool:
        """Check if text indicates a parallel action."""
        text_lower = text.lower() if text else ''
        return any(re.search(pattern, text_lower) for pattern in cls.PARALLEL_PATTERNS)

    @classmethod
    def extract_loop_target(cls, text: str) -> Optional[int]:
        """Extract step number from loop-back references."""
        match = re.search(r'(?:return|go back|repeat from|loop back to|restart at|resume from)\s+(?:to\s+)?step\s+(\d+)', text, re.IGNORECASE)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                pass
        return None

    @classmethod
    def extract_decision_branches(cls, text: str) -> List[str]:
        """Extract branch labels from decision text."""
        branches = []
        text_lower = text.lower()

        if_match = re.search(r'if\s+(.+?)[:,]', text_lower)
        if if_match:
            branches.append("Yes")
            branches.append("No")
            return branches

        has_yes = any(word in text_lower for word in cls.POSITIVE_BRANCHES)
        has_no = any(word in text_lower for word in cls.NEGATIVE_BRANCHES)

        if has_yes:
            branches.append("Yes")
        if has_no:
            branches.append("No")

        if not branches:
            branches = ["Yes", "No"]

        return branches

    @classmethod
    def normalize_step_text(cls, text: str) -> str:
        """Normalize and clean step text."""
        text = re.sub(r'^\d+[.)]\s*', '', text)
        text = ' '.join(text.split())
        if text:
            text = text[0].upper() + text[1:]
        return text.strip()

    @classmethod
    def extract_step_number(cls, text: str) -> Optional[int]:
        """Extract step number from text."""
        match = re.match(r'^(\d+)[.)]\s*', text)
        if match:
            return int(match.group(1))
        return None
