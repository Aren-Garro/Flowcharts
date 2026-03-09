"""Fallback parser for environments where spaCy is incompatible."""

import re
from typing import List
from src.models import NodeType, WorkflowStep
from src.parser.iso_mapper import ISO5807Mapper
from src.parser.patterns import WorkflowPatterns

class FallbackParser:
    def __init__(self):
        self.mapper = ISO5807Mapper()

    def parse(self, text: str) -> List[WorkflowStep]:
        steps = []
        lines = text.split('\n')
        current_step = None
        current_group = None
        
        for i, line in enumerate(lines):
            clean = line.strip()
            if not clean:
                continue
                
            # Detect section headers
            if WorkflowPatterns.is_section_header(clean):
                current_group = clean
                continue

            # 1. Skip structural "noise" words and title pages
            # Clean numbers first, THEN check for noise
            text_no_numbers = re.sub(r'^\d+[\.\)]\s*', '', clean).strip().lower()
            if text_no_numbers in ["procedure:", "decision:", "special note:", "next-step:", "purpose", "entry-conditions:", "purpose:", "entry conditions:"]:
                continue
            if "sop" in text_no_numbers and len(clean) < 100:
                continue
            if text_no_numbers.startswith("this procedure outlines"):
                continue
                
            # 2. Identify line types
            is_bullet = bool(re.match(r'^[-*•]\s+', clean))
            is_condition = bool(re.match(r'^[-*•]?\s*(If\s+|Yes[:\s]|No[:\s]|True[:\s]|False[:\s])', clean, re.IGNORECASE))
            
            # 3. Handle Branches (If current step is a decision, absorb conditions and bullets as branches)
            if current_step and current_step.is_decision:
                if is_condition or is_bullet:
                    if current_step.branches is None:
                        current_step.branches = []
                    branch_text = re.sub(r'^[-*•]\s*', '', clean).strip()
                    current_step.branches.append(branch_text)
                    continue
                    
            # 4. Handle standard text bullets
            if current_step and is_bullet and not current_step.is_decision:
                current_step.text += f"<br/>{clean}"
                continue
                
            # 5. Create a new step
            clean_text = re.sub(r'^\d+[\.\)]\s*', '', clean)
            if not clean_text: continue
            
            node_type, conf, alts = self.mapper.map_from_text(clean_text)
            
            # Force decision mode if ISO mapper says it is (e.g. "Determine", "Verify")
            is_decision = WorkflowPatterns.is_decision(clean_text) or node_type == NodeType.DECISION
            if is_decision:
                node_type = NodeType.DECISION
                
            step = WorkflowStep(
                step_number=len(steps)+1,
                text=clean_text,
                action=clean_text.split()[0] if clean_text.split() else "Process",
                node_type=node_type,
                is_decision=is_decision,
                confidence=conf * 0.8,
                alternatives=alts or [],
                group=current_group
            )
            steps.append(step)
            current_step = step
            
        return steps
