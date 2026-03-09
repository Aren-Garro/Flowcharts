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
        """Split text into steps based on lines and numbers."""
        steps = []
        lines = text.split('\n')
        
        for i, line in enumerate(lines):
            clean = line.strip()
            if not clean:
                continue
                
            # Remove leading numbers like "1. ", "2) "
            clean = re.sub(r'^\d+[\.\)]\s*', '', clean)
            
            if not clean:
                continue

            # Determine node type using simple mapper
            node_type, conf, _ = self.mapper.map_from_text(clean)
            
            steps.append(WorkflowStep(
                id=f"STEP_{i+1}",
                text=clean,
                node_type=node_type,
                confidence=conf * 0.8  # Lower confidence for fallback
            ))
            
        return steps
