"""NLP-based workflow text parser using spaCy dependency trees."""

import re
from typing import List, Optional, Tuple
from src.models import WorkflowStep, NodeType
from src.parser.patterns import WorkflowPatterns
from src.parser.iso_mapper import ISO5807Mapper

try:
    import spacy
    SPACY_AVAILABLE = True
except (ImportError, Exception) as e:
    SPACY_AVAILABLE = False
    spacy = None
    import warnings
    warnings.warn(f"spaCy not available: {e}. Using fallback parser.")


class NLPParser:
    """Parse natural language workflow descriptions into structured steps."""

    def __init__(self, use_spacy: bool = True):
        self.use_spacy = use_spacy and SPACY_AVAILABLE
        self.nlp = None
        self.iso_mapper = ISO5807Mapper()

        if self.use_spacy:
            try:
                self.nlp = spacy.load("en_core_web_sm")
            except OSError:
                print("Warning: spaCy model not found. Install: python -m spacy download en_core_web_sm")
                self.use_spacy = False
            except Exception as e:
                print(f"Warning: spaCy init failed: {e}")
                self.use_spacy = False

    def parse(self, text: str) -> List[WorkflowStep]:
        """Parse workflow text into structured steps.
        
        Branch handling (enhanced):
        - Supports multiple formats:
          1. Dashed sub-bullets: "   - If yes: action"
          2. Indented without dash: "   If yes: action"
          3. Inline branches: "4. Check condition (yes: do this, no: do that)"
        - Sub-bullets (lines starting with - or bullet or significant indent) become branches
        - Parenthetical lines like '(Example: ...)' are annotations — skipped
        - After all lines processed, decisions without branches get default Yes/No
        """
        if not text or not text.strip():
            return []

        lines = [line for line in text.split('\n') if line.strip()]
        if not lines:
            return []

        steps = []
        current_step = None

        for i, line in enumerate(lines):
            if not line.strip():
                continue
            
            # Skip all-caps headers without numbers
            if line.strip().isupper() and not any(c.isdigit() for c in line):
                continue

            # Detect if this is a branch line (indented or starts with bullet)
            is_branch_line = self._is_branch_line(line, i, lines)
            
            if is_branch_line:
                if current_step and current_step.is_decision:
                    branch_text = self._extract_branch_text(line)
                    if branch_text:
                        if current_step.branches is None:
                            current_step.branches = []
                        current_step.branches.append(branch_text)
                continue

            # Skip parenthetical annotation lines: (Example: ...)
            if line.strip().startswith('('):
                continue

            try:
                step = self._parse_line(line)
                if step:
                    steps.append(step)
                    current_step = step
            except Exception as e:
                print(f"Warning: Failed to parse '{line[:50]}...': {e}")
                continue

        # Post-processing: ensure decisions without sub-bullets get default branches
        for step in steps:
            if step.is_decision and not step.branches:
                step.branches = ['Yes', 'No']

        return steps

    def _is_branch_line(self, line: str, index: int, all_lines: List[str]) -> bool:
        """Detect if line is a decision branch.
        
        Recognizes:
        - Lines starting with -, •, *, or letter bullets (a., b.)
        - Lines with significant indentation (4+ spaces) that contain branch keywords
        - Lines that start with "If yes:", "If no:", "Yes:", "No:" regardless of indent
        """
        stripped = line.strip()
        
        # Classic bullet formats
        if stripped.startswith('-') or stripped.startswith('\u2022') or stripped.startswith('*'):
            return True
        if re.match(r'^[a-z]\.\s', stripped):
            return True
        
        # Check for branch keywords at start
        branch_patterns = [
            r'^If\s+(yes|no|true|false)',
            r'^(Yes|No|True|False)\s*:',
            r'^(Valid|Invalid)\s*:',
            r'^(Success|Failure)\s*:',
            r'^(Pass|Fail)\s*:',
        ]
        for pattern in branch_patterns:
            if re.search(pattern, stripped, re.IGNORECASE):
                return True
        
        # Check indentation: if indented 4+ spaces and no step number, likely a branch
        leading_spaces = len(line) - len(line.lstrip())
        if leading_spaces >= 4:
            # Not a numbered step
            if not re.match(r'^\d+[\.\)]\s', stripped):
                # Contains branch-like keywords
                if any(keyword in stripped.lower() for keyword in ['if yes', 'if no', 'yes:', 'no:', 'otherwise']):
                    return True
        
        return False

    def _extract_branch_text(self, line: str) -> Optional[str]:
        """Extract clean branch text from various formats.
        
        Handles:
        - "   - If yes: Start process" → "If yes: Start process"
        - "   If yes: Start process" → "If yes: Start process"
        - "   - Yes: Continue" → "Yes: Continue"
        """
        text = line.strip()
        
        # Remove leading bullets/markers
        text = re.sub(r'^[-\u2022\*]\s*', '', text)
        text = re.sub(r'^[a-z]\.\s*', '', text, flags=re.IGNORECASE)
        
        return text.strip() if text else None

    def _parse_line(self, line: str) -> Optional[WorkflowStep]:
        """Parse a single line into a WorkflowStep.
        
        IMPORTANT: branches is ALWAYS set to None here.
        Branches are populated ONLY from sub-bullets/indented lines in parse().
        """
        if not line or not line.strip():
            return None

        step_number = WorkflowPatterns.extract_step_number(line)
        normalized_text = WorkflowPatterns.normalize_step_text(line)

        if not normalized_text:
            return None

        # Use spaCy dep parse for better extraction
        action, subject, obj = self._extract_components(normalized_text)

        # Use ISO mapper for smart node type detection
        objects = [obj] if obj else []
        node_type, confidence, alternatives = self.iso_mapper.map(action, objects, normalized_text)

        # Override: check decision patterns
        is_decision = WorkflowPatterns.is_decision(normalized_text)
        if is_decision:
            node_type = NodeType.DECISION
            confidence = max(confidence, 0.85)

        is_loop = WorkflowPatterns.is_loop(normalized_text)

        # NEVER set branches here. Sub-bullets/indented lines in parse() are the only source.
        step = WorkflowStep(
            step_number=step_number,
            text=normalized_text,
            action=action,
            subject=subject,
            object=obj,
            is_decision=is_decision,
            is_loop=is_loop,
            branches=None,
            node_type=node_type,
            confidence=confidence,
            alternatives=alternatives
        )
        return step

    def _extract_components(self, text: str) -> Tuple[str, Optional[str], Optional[str]]:
        """Extract action, subject, object from text."""
        if self.use_spacy and self.nlp:
            return self._extract_with_spacy(text)
        return self._extract_with_patterns(text)

    def _extract_with_spacy(self, text: str) -> Tuple[str, Optional[str], Optional[str]]:
        """Extract using spaCy dependency tree."""
        try:
            doc = self.nlp(text)

            action = None
            subject = None
            obj = None

            roots = [t for t in doc if t.dep_ == 'ROOT']
            if roots:
                root = roots[0]
                if root.pos_ == 'VERB':
                    action = root.lemma_
                else:
                    for token in doc:
                        if token.pos_ == 'VERB':
                            action = token.lemma_
                            break

                for child in root.children:
                    if child.dep_ in ('nsubj', 'nsubjpass') and not subject:
                        subject = ' '.join(t.text for t in child.subtree)
                    elif child.dep_ in ('dobj', 'attr') and not obj:
                        obj = ' '.join(t.text for t in child.subtree)
                    elif child.dep_ == 'prep' and not obj:
                        for grandchild in child.children:
                            if grandchild.dep_ == 'pobj':
                                obj = ' '.join(t.text for t in grandchild.subtree)
                                break

            if not action:
                action = text.split()[0] if text else 'Process'

            return action, subject, obj
        except Exception:
            return self._extract_with_patterns(text)

    def _extract_with_patterns(self, text: str) -> Tuple[str, Optional[str], Optional[str]]:
        """Fallback pattern-based extraction."""
        words = text.split()
        if not words:
            return 'Process', None, None

        action = words[0]
        subject = None
        obj = None

        if len(words) >= 3:
            subject = words[0]
            action = words[1]
            obj = ' '.join(words[2:])
        elif len(words) > 1:
            obj = words[1]

        return action, subject, obj
