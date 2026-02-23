"""Pattern definitions for workflow text analysis."""

import re
from typing import Dict, List, Pattern
from src.models import NodeType


class WorkflowPatterns:
    """Centralized patterns for NLP workflow parsing."""
    
    # Action verb patterns mapped to node types
    PROCESS_VERBS = [
        'process', 'calculate', 'validate', 'transform', 'convert',
        'update', 'create', 'generate', 'execute', 'perform',
        'compute', 'determine', 'analyze', 'evaluate', 'modify',
        'change', 'set', 'configure', 'initialize', 'prepare'
    ]
    
    DECISION_PATTERNS = [
        r'\bif\b', r'\bwhether\b', r'\bcheck if\b', r'\bverify if\b',
        r'\bis\b.*\?', r'\bdoes\b.*\?', r'\bcan\b.*\?', r'\bshould\b.*\?',
        r'\bhas\b.*\?', r'\bwhen\b', r'\bin case\b', r'\bdepending on\b'
    ]
    
    IO_VERBS = [
        'read', 'write', 'input', 'output', 'receive', 'send',
        'get', 'put', 'accept', 'return', 'submit', 'enter',
        'collect', 'gather', 'obtain', 'provide'
    ]
    
    DATABASE_VERBS = [
        'query', 'select', 'insert', 'update', 'delete', 'save',
        'fetch', 'retrieve', 'store', 'persist', 'load', 'find',
        'search', 'lookup', 'add to database', 'remove from database'
    ]
    
    DISPLAY_VERBS = [
        'display', 'show', 'render', 'present', 'visualize',
        'draw', 'print to screen', 'output to screen'
    ]
    
    DOCUMENT_VERBS = [
        'print', 'export', 'generate report', 'create document',
        'produce document', 'write to file', 'save report'
    ]
    
    TERMINATOR_KEYWORDS = [
        'start', 'begin', 'end', 'finish', 'stop', 'terminate',
        'exit', 'complete', 'done'
    ]
    
    LOOP_PATTERNS = [
        r'\bfor each\b', r'\bwhile\b', r'\brepeat\b', r'\bloop\b',
        r'\biterate\b', r'\buntil\b', r'\breturn to step\b',
        r'\bgo back to\b', r'\bcontinue\b'
    ]
    
    # Branch labels for decision nodes
    POSITIVE_BRANCHES = ['yes', 'true', 'valid', 'success', 'pass', 'approved']
    NEGATIVE_BRANCHES = ['no', 'false', 'invalid', 'failure', 'fail', 'rejected']
    
    @classmethod
    def detect_node_type(cls, text: str) -> NodeType:
        """Detect the appropriate node type based on text content."""
        text_lower = text.lower()
        
        # Check for terminator keywords
        if any(keyword in text_lower for keyword in cls.TERMINATOR_KEYWORDS):
            return NodeType.TERMINATOR
        
        # Check for decision patterns
        if any(re.search(pattern, text_lower) for pattern in cls.DECISION_PATTERNS):
            return NodeType.DECISION
        
        # Check for database operations
        if any(verb in text_lower for verb in cls.DATABASE_VERBS):
            return NodeType.DATABASE
        
        # Check for display operations
        if any(verb in text_lower for verb in cls.DISPLAY_VERBS):
            return NodeType.DISPLAY
        
        # Check for document operations
        if any(verb in text_lower for verb in cls.DOCUMENT_VERBS):
            return NodeType.DOCUMENT
        
        # Check for I/O operations
        if any(verb in text_lower for verb in cls.IO_VERBS):
            return NodeType.IO
        
        # Default to process
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
    def extract_decision_branches(cls, text: str) -> List[str]:
        """Extract branch labels from decision text."""
        branches = []
        text_lower = text.lower()
        
        # Look for explicit branch definitions
        if_match = re.search(r'if\s+(.+?)[:,]', text_lower)
        if if_match:
            branches.append("Yes")
            branches.append("No")
            return branches
        
        # Look for explicit yes/no mentions
        has_yes = any(word in text_lower for word in cls.POSITIVE_BRANCHES)
        has_no = any(word in text_lower for word in cls.NEGATIVE_BRANCHES)
        
        if has_yes:
            branches.append("Yes")
        if has_no:
            branches.append("No")
        
        # Default branches for decision nodes
        if not branches:
            branches = ["Yes", "No"]
        
        return branches
    
    @classmethod
    def normalize_step_text(cls, text: str) -> str:
        """Normalize and clean step text."""
        # Remove step numbers
        text = re.sub(r'^\d+[.)]\s*', '', text)
        
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        # Capitalize first letter
        if text:
            text = text[0].upper() + text[1:]
        
        return text.strip()
    
    @classmethod
    def extract_step_number(cls, text: str) -> int | None:
        """Extract step number from text."""
        match = re.match(r'^(\d+)[.)]\s*', text)
        if match:
            return int(match.group(1))
        return None
