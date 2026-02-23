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
        """Parse workflow text into structured steps."""
        if not text or not text.strip():
            return []

        lines = [line.strip() for line in text.split('\n') if line.strip()]
        if not lines:
            return []

        steps = []
        current_decision = None

        for line in lines:
            if not line:
                continue
            if line.isupper() and not any(c.isdigit() for c in line):
                continue

            # Handle sub-bullets (decision branches)
            if line.startswith('-') or line.startswith('\u2022') or line.strip().startswith('a.') or line.strip().startswith('b.'):
                if current_decision:
                    branch_text = re.sub(r'^[-\u2022]\s*', '', line).strip()
                    branch_text = re.sub(r'^[a-z]\.\s*', '', branch_text).strip()
                    if current_decision.branches is None:
                        current_decision.branches = []
                    current_decision.branches.append(branch_text)
                continue

            try:
                step = self._parse_line(line)
                if step:
                    steps.append(step)
                    current_decision = step if step.is_decision else None
            except Exception as e:
                print(f"Warning: Failed to parse '{line[:50]}...': {e}")
                continue

        return steps

    def _parse_line(self, line: str) -> Optional[WorkflowStep]:
        """Parse a single line into a WorkflowStep."""
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
        branches = WorkflowPatterns.extract_decision_branches(normalized_text) if is_decision else None

        return WorkflowStep(
            step_number=step_number,
            text=normalized_text,
            action=action,
            subject=subject,
            object=obj,
            is_decision=is_decision,
            is_loop=is_loop,
            branches=branches,
            node_type=node_type,
            confidence=confidence,
            alternatives=alternatives
        )

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

            # Find ROOT verb via dependency tree
            roots = [t for t in doc if t.dep_ == 'ROOT']
            if roots:
                root = roots[0]
                if root.pos_ == 'VERB':
                    action = root.lemma_
                else:
                    # ROOT isn't a verb — find first verb
                    for token in doc:
                        if token.pos_ == 'VERB':
                            action = token.lemma_
                            break

                # Walk children for subject and direct objects
                for child in root.children:
                    if child.dep_ in ('nsubj', 'nsubjpass') and not subject:
                        subject = ' '.join(t.text for t in child.subtree)
                    elif child.dep_ in ('dobj', 'attr') and not obj:
                        obj = ' '.join(t.text for t in child.subtree)
                    elif child.dep_ == 'prep' and not obj:
                        # Prepositional objects: "save TO database"
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
