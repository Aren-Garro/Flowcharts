"""Fallback parser for environments where spaCy is incompatible (e.g. Python 3.14+)."""

import re
from typing import List
from src.models import NodeType, WorkflowStep
from src.parser.iso_mapper import ISO5807Mapper
from src.parser.patterns import WorkflowPatterns

class FallbackParser:
    """Pattern-based parser used when spaCy fails."""

    def __init__(self):
        self.mapper = ISO5807Mapper()

    def parse(self, text: str) -> List[WorkflowStep]:
        steps = []
        lines = text.split('\n')
        current_step = None
        
        for i, line in enumerate(lines):
            clean = line.strip()
            if not clean:
                continue
                
            # 1. Skip structural "noise" words from SOPs
            if clean.lower().rstrip(':') in ["procedure", "decision", "special note", "next step", "purpose", "sop"]:
                continue
                
            # 2. Handle Decision Branches (e.g., "- If yes:")
            branch_match = re.match(r'^[-*•]?\s*(If\s+|Yes[:\s]|No[:\s]|True[:\s]|False[:\s])(.*)', clean, re.IGNORECASE)
            if branch_match and current_step and current_step.is_decision:
                if current_step.branches is None:
                    current_step.branches = []
                # Clean the branch text and add to the decision node
                branch_text = re.sub(r'^[-*•]\s*', '', clean).strip()
                current_step.branches.append(branch_text)
                continue

            # 3. Handle Data Bullet Points (e.g., "- Client name")
            if re.match(r'^[-*•]\s+', clean) and current_step:
                # Use standard newline instead of <br>
                current_step.text += f"\n{clean}"
                continue

            # 4. Standard step processing
            # Remove leading numbers like "1. ", "2) "
            clean_step = re.sub(r'^\d+[\.\)]\s*', '', clean)
            if not clean_step:
                continue

            node_type, conf, alternatives = self.mapper.map_from_text(clean_step)
            action = clean_step.split()[0] if clean_step.split() else "Process"
            
            # Override node type if it's a decision
            is_decision = WorkflowPatterns.is_decision(clean_step)
            if is_decision:
                node_type = NodeType.DECISION

            step = WorkflowStep(
                step_number=len(steps)+1,
                text=clean_step,
                action=action,
                node_type=node_type,
                is_decision=is_decision,
                confidence=conf * 0.8,
                alternatives=alternatives or []
            )
            steps.append(step)
            current_step = step
            
        return steps
