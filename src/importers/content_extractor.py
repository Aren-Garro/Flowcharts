"""Smart content extraction for identifying and extracting workflows from documents."""

import re
from typing import List, Tuple, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class ContentExtractor:
    """Extract and identify workflow content from raw document text."""
    
    def __init__(self):
        """Initialize the content extractor."""
        # Patterns for identifying workflow steps
        self.step_patterns = [
            r'^\s*\d+[\.\)]\s+(.+)$',  # "1. Step" or "1) Step"
            r'^\s*\d+\s+(.+)$',  # "1 Step"
            r'^\s*Step\s+\d+[:\.]?\s*(.+)$',  # "Step 1: Description"
            r'^\s*[\-\*•]\s+(.+)$',  # Bullet points
        ]
        
        # Patterns for decision branches
        self.decision_patterns = [
            r'^\s*[\-\*•]?\s*[Ii]f\s+(.+?)[:,]\s*(.+)$',  # "If condition: action"
            r'^\s*[\-\*•]?\s*[Ii]f\s+(.+)$',  # "If condition"
            r'^\s*[\-\*•]?\s*[Yy]es[:,]\s*(.+)$',  # "Yes: action"
            r'^\s*[\-\*•]?\s*[Nn]o[:,]\s*(.+)$',  # "No: action"
        ]
        
        # Section header patterns
        self.header_patterns = [
            r'^#+\s+(.+)$',  # Markdown headers
            r'^(.+)\n[=\-]+$',  # Underlined headers
            r'^[A-Z][A-Z\s]+$',  # ALL CAPS
        ]
        
        # Workflow indicator keywords
        self.workflow_keywords = [
            'workflow', 'process', 'procedure', 'steps', 'flow',
            'algorithm', 'sequence', 'instructions', 'guide',
            'start', 'begin', 'initialize', 'end', 'finish'
        ]
    
    def extract_workflows(self, text: str) -> List[Dict[str, Any]]:
        """Extract all workflows from text.
        
        Args:
            text: Raw document text
        
        Returns:
            List of dictionaries containing:
                - title: Workflow title
                - content: Workflow text
                - start_line: Starting line number
                - end_line: Ending line number
                - confidence: Confidence score (0-1)
        """
        if not text or not text.strip():
            return []
        
        lines = text.split('\n')
        workflows = []
        
        # Try to identify workflow sections
        sections = self._identify_sections(lines)
        
        if sections:
            # Process each section that looks like a workflow
            for section in sections:
                if section['is_workflow']:
                    workflows.append({
                        'title': section['title'],
                        'content': section['content'],
                        'start_line': section['start_line'],
                        'end_line': section['end_line'],
                        'confidence': section['confidence']
                    })
        
        # If no clear sections found, treat entire document as potential workflow
        if not workflows:
            cleaned = self._clean_text(text)
            if self._looks_like_workflow(cleaned):
                workflows.append({
                    'title': 'Extracted Workflow',
                    'content': cleaned,
                    'start_line': 0,
                    'end_line': len(lines),
                    'confidence': 0.5
                })
        
        return workflows
    
    def extract_best_workflow(self, text: str) -> Optional[str]:
        """Extract the most likely workflow from text.
        
        Args:
            text: Raw document text
        
        Returns:
            Cleaned workflow text or None if no workflow found
        """
        workflows = self.extract_workflows(text)
        
        if not workflows:
            return None
        
        # Return workflow with highest confidence
        best = max(workflows, key=lambda w: w['confidence'])
        return best['content']
    
    def _identify_sections(self, lines: List[str]) -> List[Dict[str, Any]]:
        """Identify distinct sections in the document."""
        sections = []
        current_section = None
        
        for i, line in enumerate(lines):
            # Check if line is a header
            if self._is_header(line):
                # Save previous section if exists
                if current_section:
                    current_section['end_line'] = i - 1
                    current_section['content'] = '\n'.join(
                        lines[current_section['start_line']:current_section['end_line'] + 1]
                    )
                    current_section['is_workflow'] = self._looks_like_workflow(
                        current_section['content']
                    )
                    current_section['confidence'] = self._calculate_confidence(
                        current_section['content']
                    )
                    sections.append(current_section)
                
                # Start new section
                current_section = {
                    'title': line.strip(),
                    'start_line': i + 1,
                    'end_line': None,
                    'content': '',
                    'is_workflow': False,
                    'confidence': 0.0
                }
        
        # Save last section
        if current_section:
            current_section['end_line'] = len(lines) - 1
            current_section['content'] = '\n'.join(
                lines[current_section['start_line']:current_section['end_line'] + 1]
            )
            current_section['is_workflow'] = self._looks_like_workflow(
                current_section['content']
            )
            current_section['confidence'] = self._calculate_confidence(
                current_section['content']
            )
            sections.append(current_section)
        
        return sections
    
    def _is_header(self, line: str) -> bool:
        """Check if line is a section header."""
        line = line.strip()
        
        if not line:
            return False
        
        # Markdown header
        if re.match(r'^#+\s+', line):
            return True
        
        # ALL CAPS (but not too long)
        if line.isupper() and 3 <= len(line) <= 60:
            return True
        
        # Contains workflow keywords
        lower_line = line.lower()
        for keyword in self.workflow_keywords:
            if keyword in lower_line and len(line) < 80:
                return True
        
        return False
    
    def _looks_like_workflow(self, text: str) -> bool:
        """Determine if text looks like a workflow."""
        if not text or len(text.strip()) < 20:
            return False
        
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        
        if len(lines) < 2:
            return False
        
        # Count numbered steps
        numbered_steps = 0
        for line in lines:
            if re.match(r'^\d+[\.\)]\s+', line):
                numbered_steps += 1
        
        # If more than 2 numbered steps, likely a workflow
        if numbered_steps >= 2:
            return True
        
        # Check for workflow keywords
        lower_text = text.lower()
        keyword_count = sum(1 for kw in self.workflow_keywords if kw in lower_text)
        
        if keyword_count >= 2:
            return True
        
        # Check for decision indicators
        decision_count = sum(
            1 for line in lines
            if any(pattern in line.lower() for pattern in ['if', 'then', 'else', 'check'])
        )
        
        if decision_count >= 1 and numbered_steps >= 1:
            return True
        
        return False
    
    def _calculate_confidence(self, text: str) -> float:
        """Calculate confidence score that text is a workflow (0-1)."""
        if not text or len(text.strip()) < 20:
            return 0.0
        
        score = 0.0
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        
        if not lines:
            return 0.0
        
        # Count numbered steps
        numbered_steps = sum(1 for line in lines if re.match(r'^\d+[\.\)]\s+', line))
        if numbered_steps >= 3:
            score += 0.4
        elif numbered_steps >= 2:
            score += 0.2
        
        # Check for workflow keywords
        lower_text = text.lower()
        keyword_count = sum(1 for kw in self.workflow_keywords if kw in lower_text)
        score += min(keyword_count * 0.1, 0.3)
        
        # Check for decision branches
        decision_count = sum(
            1 for line in lines
            if re.search(r'\b(if|then|else|check|validate)\b', line.lower())
        )
        score += min(decision_count * 0.1, 0.2)
        
        # Check for start/end indicators
        if re.search(r'\b(start|begin)\b', text.lower()):
            score += 0.1
        if re.search(r'\b(end|finish|complete)\b', text.lower()):
            score += 0.1
        
        return min(score, 1.0)
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text for workflow processing."""
        # Remove excessive whitespace
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        
        # Remove page numbers
        text = re.sub(r'Page \d+', '', text, flags=re.IGNORECASE)
        
        # Remove common headers/footers
        text = re.sub(r'^\s*(Page|Document|Section)\s+\d+.*$', '', text, flags=re.MULTILINE)
        
        # Normalize line endings
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        
        return text.strip()
    
    def preprocess_for_parser(self, text: str) -> str:
        """Preprocess extracted workflow text for the NLP parser.
        
        Args:
            text: Raw workflow text
        
        Returns:
            Cleaned and formatted text ready for parsing
        """
        # Clean the text
        text = self._clean_text(text)
        
        # Ensure consistent numbering
        lines = text.split('\n')
        processed_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Normalize numbered steps
            match = re.match(r'^(\d+)[\)\.]\s+(.+)$', line)
            if match:
                num, content = match.groups()
                processed_lines.append(f"{num}. {content}")
            else:
                processed_lines.append(line)
        
        return '\n'.join(processed_lines)
    
    def extract_from_clipboard(self) -> Optional[str]:
        """Extract workflow from clipboard.
        
        Returns:
            Cleaned workflow text or None
        """
        try:
            import pyperclip
            text = pyperclip.paste()
            return self.extract_best_workflow(text)
        except ImportError:
            logger.warning("Clipboard support not available. Install: pip install pyperclip")
            return None
        except Exception as e:
            logger.error(f"Error reading clipboard: {e}")
            return None
    
    def get_workflow_summary(self, text: str) -> Dict[str, Any]:
        """Get summary statistics about detected workflow.
        
        Args:
            text: Workflow text
        
        Returns:
            Dictionary with workflow statistics
        """
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        
        # Count different types of steps
        numbered_steps = sum(1 for line in lines if re.match(r'^\d+[\.\)]\s+', line))
        decision_steps = sum(
            1 for line in lines
            if re.search(r'\b(if|check|validate|verify)\b', line.lower())
        )
        bullet_points = sum(1 for line in lines if re.match(r'^[\-\*•]\s+', line))
        
        return {
            'total_lines': len(lines),
            'numbered_steps': numbered_steps,
            'decision_steps': decision_steps,
            'bullet_points': bullet_points,
            'is_workflow': self._looks_like_workflow(text),
            'confidence': self._calculate_confidence(text)
        }
