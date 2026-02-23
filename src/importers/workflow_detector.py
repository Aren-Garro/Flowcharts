"""Intelligent workflow boundary detection for multi-section documents."""

import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class WorkflowSection:
    """Represents a detected workflow section in a document."""
    id: str
    title: str
    content: str
    level: int  # Header level (1=top, 2=sub, etc.)
    start_line: int
    end_line: int
    step_count: int
    decision_count: int
    confidence: float
    subsections: List['WorkflowSection']
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'title': self.title,
            'content': self.content,
            'level': self.level,
            'start_line': self.start_line,
            'end_line': self.end_line,
            'step_count': self.step_count,
            'decision_count': self.decision_count,
            'confidence': self.confidence,
            'subsections': [s.to_dict() for s in self.subsections]
        }


class WorkflowDetector:
    """Detect workflow boundaries and section structure in documents."""
    
    # Header patterns for different document styles
    HEADER_PATTERNS = [
        # Markdown headers: # Header, ## Subheader
        r'^#{1,6}\s+(.+)$',
        # Section numbers: 1. Title, 1.1 Subtitle
        r'^(\d+(?:\.\d+)*)[\.\s]+(.+)$',
        # ALL CAPS HEADERS
        r'^([A-Z][A-Z\s\d\.:-]{3,})$',
        # Underlined headers (followed by ===== or -----)
        r'^(.+)\n[=-]{3,}$',
    ]
    
    # Keywords that suggest workflow content
    WORKFLOW_KEYWORDS = [
        'step', 'procedure', 'process', 'method', 'setup', 'installation',
        'configuration', 'instruction', 'guide', 'workflow', 'protocol',
        'operation', 'task', 'action', 'perform', 'execute'
    ]
    
    # Section titles that indicate new workflows
    WORKFLOW_SECTION_INDICATORS = [
        'method', 'setup', 'procedure', 'installation', 'configuration',
        'process', 'workflow', 'guide', 'instructions', 'steps'
    ]
    
    def __init__(self):
        """Initialize the workflow detector."""
        self.compiled_patterns = [re.compile(p, re.MULTILINE) for p in self.HEADER_PATTERNS]
    
    def detect_workflows(self, text: str) -> List[WorkflowSection]:
        """
        Detect all workflow sections in a document.
        
        Args:
            text: Full document text
        
        Returns:
            List of detected workflow sections with hierarchy
        """
        lines = text.split('\n')
        
        # First, detect all headers
        headers = self._detect_headers(lines)
        
        if not headers:
            # No headers found, treat entire document as single workflow
            return [self._create_single_workflow(text, lines)]
        
        # Build hierarchical structure
        sections = self._build_hierarchy(headers, lines)
        
        # Filter for workflow sections (exclude TOC, glossary, etc.)
        workflow_sections = self._filter_workflow_sections(sections)
        
        # Analyze each section
        for section in workflow_sections:
            self._analyze_section(section)
        
        return workflow_sections
    
    def _detect_headers(self, lines: List[str]) -> List[Dict[str, Any]]:
        """
        Detect all headers in the document.
        
        Args:
            lines: Document lines
        
        Returns:
            List of header dictionaries with line number, level, and title
        """
        headers = []
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            # Try each header pattern
            for pattern in self.compiled_patterns:
                match = pattern.match(line)
                if match:
                    title, level = self._extract_header_info(match, line)
                    if title:
                        headers.append({
                            'line': i,
                            'level': level,
                            'title': title,
                            'raw': line
                        })
                        break
        
        return headers
    
    def _extract_header_info(self, match: re.Match, line: str) -> Tuple[str, int]:
        """
        Extract title and level from header match.
        
        Args:
            match: Regex match object
            line: Original line
        
        Returns:
            Tuple of (title, level)
        """
        # Markdown headers: # = level 1, ## = level 2, etc.
        if line.startswith('#'):
            level = len(line) - len(line.lstrip('#'))
            title = match.group(1).strip()
            return title, level
        
        # Numbered sections: 1. = level 1, 1.1 = level 2, etc.
        if match.groups()[0] and match.groups()[0][0].isdigit():
            section_num = match.groups()[0]
            level = section_num.count('.') + 1
            title = match.groups()[1].strip() if len(match.groups()) > 1 else match.group(1).strip()
            return title, level
        
        # ALL CAPS or underlined = level 1
        title = match.group(1).strip()
        return title, 1
    
    def _build_hierarchy(self, headers: List[Dict[str, Any]], lines: List[str]) -> List[WorkflowSection]:
        """
        Build hierarchical section structure from headers.
        
        Args:
            headers: Detected headers
            lines: Document lines
        
        Returns:
            List of top-level workflow sections with nested subsections
        """
        if not headers:
            return []
        
        sections = []
        stack = []  # Stack to track parent sections
        
        for i, header in enumerate(headers):
            # Determine content range
            start_line = header['line']
            end_line = headers[i + 1]['line'] if i + 1 < len(headers) else len(lines)
            
            # Extract section content
            content_lines = lines[start_line + 1:end_line]
            content = '\n'.join(content_lines).strip()
            
            # Create section
            section = WorkflowSection(
                id=f"section_{i}",
                title=header['title'],
                content=content,
                level=header['level'],
                start_line=start_line,
                end_line=end_line,
                step_count=0,
                decision_count=0,
                confidence=0.0,
                subsections=[]
            )
            
            # Build hierarchy using stack
            while stack and stack[-1].level >= section.level:
                stack.pop()
            
            if stack:
                # Add as subsection to parent
                stack[-1].subsections.append(section)
            else:
                # Top-level section
                sections.append(section)
            
            stack.append(section)
        
        return sections
    
    def _filter_workflow_sections(self, sections: List[WorkflowSection]) -> List[WorkflowSection]:
        """
        Filter sections to include only workflow-related content.
        
        Excludes: Table of Contents, Glossary, References, etc.
        
        Args:
            sections: All detected sections
        
        Returns:
            Filtered list of workflow sections
        """
        workflow_sections = []
        
        # Exclusion patterns
        exclude_patterns = [
            r'table of contents',
            r'glossary',
            r'references',
            r'appendix',
            r'index',
            r'bibliography',
            r'^contents$',
        ]
        
        for section in sections:
            title_lower = section.title.lower()
            
            # Check if should be excluded
            is_excluded = any(re.search(pattern, title_lower) for pattern in exclude_patterns)
            
            if not is_excluded:
                # Check if contains workflow indicators
                has_workflow_keywords = any(
                    keyword in title_lower or keyword in section.content.lower()[:500]
                    for keyword in self.WORKFLOW_KEYWORDS
                )
                
                # Include if has workflow keywords or has substantial content
                if has_workflow_keywords or len(section.content) > 200:
                    workflow_sections.append(section)
                    
                    # Recursively filter subsections
                    if section.subsections:
                        section.subsections = self._filter_workflow_sections(section.subsections)
        
        return workflow_sections
    
    def _analyze_section(self, section: WorkflowSection):
        """
        Analyze section to extract workflow metrics.
        
        Updates section in place with step count, decision count, and confidence.
        
        Args:
            section: Workflow section to analyze
        """
        content_lower = section.content.lower()
        
        # Count steps (numbered items, bullet points, action verbs)
        step_patterns = [
            r'^\s*\d+[\.\)]',  # 1. or 1)
            r'^\s*[•\-\*]',    # bullets
            r'^\s*step \d+',   # "Step 1"
        ]
        
        step_count = 0
        for line in section.content.split('\n'):
            if any(re.match(pattern, line, re.IGNORECASE) for pattern in step_patterns):
                step_count += 1
        
        section.step_count = step_count
        
        # Count decisions (if/then, yes/no, choice indicators)
        decision_keywords = ['if', 'whether', 'yes', 'no', 'choose', 'select', 'option', 'either', 'or']
        section.decision_count = sum(content_lower.count(keyword) for keyword in decision_keywords)
        
        # Calculate confidence score
        confidence = 0.0
        
        # Has workflow keywords in title
        if any(indicator in section.title.lower() for indicator in self.WORKFLOW_SECTION_INDICATORS):
            confidence += 0.3
        
        # Has steps
        if section.step_count > 0:
            confidence += min(0.4, section.step_count * 0.05)
        
        # Has workflow keywords in content
        keyword_count = sum(1 for kw in self.WORKFLOW_KEYWORDS if kw in content_lower)
        confidence += min(0.2, keyword_count * 0.05)
        
        # Has reasonable length
        if 100 < len(section.content) < 5000:
            confidence += 0.1
        
        section.confidence = min(1.0, confidence)
        
        # Recursively analyze subsections
        for subsection in section.subsections:
            self._analyze_section(subsection)
    
    def _create_single_workflow(self, text: str, lines: List[str]) -> WorkflowSection:
        """
        Create a single workflow section from entire document.
        
        Args:
            text: Full document text
            lines: Document lines
        
        Returns:
            Single workflow section
        """
        section = WorkflowSection(
            id="section_0",
            title="Workflow",
            content=text,
            level=1,
            start_line=0,
            end_line=len(lines),
            step_count=0,
            decision_count=0,
            confidence=0.5,
            subsections=[]
        )
        
        self._analyze_section(section)
        return section
    
    def get_workflow_summary(self, sections: List[WorkflowSection]) -> Dict[str, Any]:
        """
        Generate summary of detected workflows.
        
        Args:
            sections: Detected workflow sections
        
        Returns:
            Summary dictionary
        """
        total_steps = sum(s.step_count for s in sections)
        total_decisions = sum(s.decision_count for s in sections)
        avg_confidence = sum(s.confidence for s in sections) / len(sections) if sections else 0
        
        return {
            'total_workflows': len(sections),
            'total_steps': total_steps,
            'total_decisions': total_decisions,
            'avg_confidence': round(avg_confidence, 2),
            'workflows': [
                {
                    'id': s.id,
                    'title': s.title,
                    'step_count': s.step_count,
                    'decision_count': s.decision_count,
                    'confidence': round(s.confidence, 2),
                    'has_subsections': len(s.subsections) > 0
                }
                for s in sections
            ]
        }
