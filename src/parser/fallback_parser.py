"""Fallback parser for environments where spaCy is incompatible (e.g. Python 3.14+)."""

import re
from typing import List, Optional, Tuple
from src.models import NodeType, WorkflowStep
from src.parser.iso_mapper import ISO5807Mapper

class FallbackParser:
    """Deterministic pattern-based parser used when spaCy fails."""

    def __init__(self):
        self.mapper = ISO5807Mapper()

    def parse(self, text: str) -> List[WorkflowStep]:
        """Split text into steps with decision branch grouping."""
        steps = []
        raw_lines = text.split('\n')
        lines = []
        
        # Pre-process lines to handle bullets and whitespace
        for line in raw_lines:
            if line.strip():
                lines.append(line)
        
        i = 0
        while i < len(lines):
            line = lines[i]
            clean = line.strip()
            
            # Remove leading numbers like "1. ", "2) "
            clean_step = re.sub(r'^\d+[\.\)]\s*', '', clean)
            if not clean_step:
                i += 1
                continue

            node_type, conf, alternatives = self.mapper.map_from_text(clean_step)
            
            # Extract simple action
            words = clean_step.split()
            action = words[0] if words else "Process"
            is_decision = node_type == NodeType.DECISION or clean_step.endswith('?')
            
            branches = []
            # Look ahead for branches if this is a decision
            if is_decision:
                j = i + 1
                while j < len(lines):
                    next_line = lines[j].strip()
                    # Detect if next line is a branch: "If yes:", "- No:", "   Yes:"
                    if re.match(r'^(?:if\s+)?(?:yes|no|true|false|valid|invalid)\b', next_line, re.I) or \
                       next_line.startswith('-'):
                        branches.append(re.sub(r'^[-\*•]\s*', '', next_line))
                        j += 1
                    else:
                        break
                # If we found branches, skip those lines in the main loop
                if branches:
                    i = j - 1

            steps.append(WorkflowStep(
                id=f"STEP_{len(steps)+1}",
                text=clean_step,
                action=action,
                node_type=NodeType.DECISION if is_decision else node_type,
                is_decision=is_decision,
                branches=branches if branches else None,
                confidence=conf * 0.8,
                alternatives=alternatives or []
            ))
            i += 1
            
        return steps
