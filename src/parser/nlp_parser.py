"""NLP-based workflow text parser using spaCy."""

import re
from typing import List, Dict, Any, Optional, Tuple, Union
from src.models import WorkflowStep, NodeType
from src.parser.patterns import WorkflowPatterns

try:
    import spacy
    from spacy.language import Language
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    spacy = None
    Language = None


class NLPParser:
    """Parse natural language workflow descriptions into structured steps."""
    
    def __init__(self, use_spacy: bool = True):
        """
        Initialize NLP parser.
        
        Args:
            use_spacy: Whether to use spaCy for advanced NLP (requires model installation)
        """
        self.use_spacy = use_spacy and SPACY_AVAILABLE
        self.nlp = None
        
        if self.use_spacy:
            try:
                # Try to load English model
                self.nlp = spacy.load("en_core_web_sm")
            except OSError:
                print("Warning: spaCy model 'en_core_web_sm' not found.")
                print("Install with: python -m spacy download en_core_web_sm")
                print("Falling back to pattern-based parsing.")
                self.use_spacy = False
    
    def parse(self, text: str) -> List[WorkflowStep]:
        """
        Parse workflow text into structured steps.
        
        Args:
            text: Raw workflow description text
            
        Returns:
            List of parsed workflow steps
        """
        if not text or not text.strip():
            return []
        
        # Split into lines and clean
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        if not lines:
            return []
        
        steps = []
        current_decision = None
        
        for line in lines:
            # Skip empty lines
            if not line:
                continue
            
            # Skip title lines (all caps, no numbers)
            if line.isupper() and not any(c.isdigit() for c in line):
                continue
            
            # Handle sub-bullets (decision branches)
            if line.startswith('-') or line.startswith('•') or line.strip().startswith('a.') or line.strip().startswith('b.'):
                if current_decision:
                    # This is a branch of the previous decision
                    branch_text = re.sub(r'^[-•]\s*', '', line).strip()
                    branch_text = re.sub(r'^[a-z]\.\s*', '', branch_text).strip()
                    if current_decision.branches is None:
                        current_decision.branches = []
                    current_decision.branches.append(branch_text)
                continue
            
            # Parse main step
            try:
                step = self._parse_line(line)
                if step:
                    steps.append(step)
                    
                    # Track if this is a decision for next iteration
                    if step.is_decision:
                        current_decision = step
                    else:
                        current_decision = None
            except Exception as e:
                print(f"Warning: Failed to parse line '{line[:50]}...': {e}")
                continue
        
        return steps
    
    def _parse_line(self, line: str) -> Optional[WorkflowStep]:
        """
        Parse a single line of workflow text.
        
        Args:
            line: Single workflow step text
            
        Returns:
            Parsed WorkflowStep or None if invalid
        """
        if not line or not line.strip():
            return None
        
        # Extract step number
        step_number = WorkflowPatterns.extract_step_number(line)
        
        # Normalize text
        normalized_text = WorkflowPatterns.normalize_step_text(line)
        
        if not normalized_text:
            return None
        
        # Detect node type
        node_type = WorkflowPatterns.detect_node_type(normalized_text)
        
        # Check for decision
        is_decision = WorkflowPatterns.is_decision(normalized_text)
        
        # Check for loop
        is_loop = WorkflowPatterns.is_loop(normalized_text)
        
        # Extract decision branches if applicable
        branches = None
        if is_decision:
            branches = WorkflowPatterns.extract_decision_branches(normalized_text)
        
        # Extract action and components using spaCy if available
        action, subject, obj = self._extract_components(normalized_text)
        
        return WorkflowStep(
            step_number=step_number,
            text=normalized_text,
            action=action,
            subject=subject,
            object=obj,
            is_decision=is_decision,
            is_loop=is_loop,
            branches=branches,
            node_type=node_type
        )
    
    def _extract_components(self, text: str) -> Tuple[str, Optional[str], Optional[str]]:
        """
        Extract action verb, subject, and object from text.
        
        Args:
            text: Normalized step text
            
        Returns:
            Tuple of (action, subject, object)
        """
        if self.use_spacy and self.nlp:
            return self._extract_with_spacy(text)
        else:
            return self._extract_with_patterns(text)
    
    def _extract_with_spacy(self, text: str) -> Tuple[str, Optional[str], Optional[str]]:
        """
        Extract components using spaCy dependency parsing.
        
        Args:
            text: Normalized step text
            
        Returns:
            Tuple of (action, subject, object)
        """
        try:
            doc = self.nlp(text)
            
            action = None
            subject = None
            obj = None
            
            # Find main verb (action)
            for token in doc:
                if token.pos_ == "VERB":
                    action = token.lemma_
                    break
            
            # Find subject and object
            for token in doc:
                if token.dep_ in ["nsubj", "nsubjpass"]:
                    subject = token.text
                elif token.dep_ in ["dobj", "pobj"]:
                    obj = token.text
            
            if not action:
                action = text.split()[0] if text else "Process"
            
            return action, subject, obj
        except Exception as e:
            print(f"Warning: spaCy parsing failed, falling back to patterns: {e}")
            return self._extract_with_patterns(text)
    
    def _extract_with_patterns(self, text: str) -> Tuple[str, Optional[str], Optional[str]]:
        """
        Extract components using simple pattern matching.
        
        Args:
            text: Normalized step text
            
        Returns:
            Tuple of (action, subject, object)
        """
        words = text.split()
        
        if not words:
            return "Process", None, None
        
        # First word is typically the action
        action = words[0]
        
        # Simple subject/object extraction
        subject = None
        obj = None
        
        # Look for common patterns
        if len(words) > 1:
            # "System validates input" -> subject="System", action="validates", object="input"
            if len(words) >= 3:
                subject = words[0]
                action = words[1]
                obj = ' '.join(words[2:])
            else:
                obj = words[1]
        
        return action, subject, obj
