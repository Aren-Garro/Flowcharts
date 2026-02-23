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
        # Section with colon: "Section 4: Title" or "Section 4.2: Title"
        r'^Section\s+(\d+(?:\.\d+)*)\s*[:\-]\s*(.+)$',
        # Numbered sections: "4. Title" or "4.2 Title"
        r'^(\d+(?:\.\d+)*)[\.\s]\s*([A-Z].+)$',
        # Markdown headers: # Header, ## Subheader
        r'^#{1,3}\s+(.+)$',
        # ALL CAPS HEADERS (min 10 chars)
        r'^([A-Z][A-Z\s]{9,})$',
    ]
    
    # Keywords that suggest workflow content
    WORKFLOW_KEYWORDS = [
        'step', 'procedure', 'process', 'method', 'setup', 'installation',
        'configuration', 'instruction', 'guide', 'workflow', 'protocol',
        'operation', 'task', 'action', 'perform', 'execute', 'prepare',
        'install', 'configure', 'create', 'restore', 'backup', 'upgrade'
    ]
    
    # Section titles that indicate workflows
    WORKFLOW_SECTION_INDICATORS = [
        'method', 'setup', 'procedure', 'installation', 'configuration',
        'process', 'workflow', 'guide', 'instructions', 'steps', 'preparation',
        'backup', 'restore', 'upgrade', 'creating', 'restoring'
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
            List of detected workflow sections
        """
        lines = text.split('\n')
        
        # Detect headers
        headers = self._detect_headers(lines)
        
        logger.info(f"Detected {len(headers)} headers")
        
        if not headers:
            # No headers, treat as single workflow
            single = self._create_single_workflow(text, lines)
            return [single] if single.confidence > 0.3 else []
        
        # Build sections
        sections = self._build_hierarchy(headers, lines)
        logger.info(f"Built {len(sections)} sections")
        
        # Filter for workflows
        workflow_sections = self._filter_workflow_sections(sections)
        logger.info(f"After filtering: {len(workflow_sections)} workflow sections")
        
        # Analyze each
        for section in workflow_sections:
            self._analyze_section(section)
        
        # Apply quality filters
        filtered = self._apply_quality_filters(workflow_sections)
        logger.info(f"After quality filters: {len(filtered)} workflows")
        
        # Fallback: if too strict, return unfiltered
        if not filtered and workflow_sections:
            logger.warning("Quality filters removed all sections, returning unfiltered")
            return workflow_sections
        
        return filtered
    
    def _detect_headers(self, lines: List[str]) -> List[Dict[str, Any]]:
        """Detect all headers in the document."""
        headers = []
        seen_titles = set()
        
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            if not line_stripped or len(line_stripped) < 3:
                continue
            
            for pattern in self.compiled_patterns:
                match = pattern.match(line_stripped)
                if match:
                    title, level = self._extract_header_info(match, line_stripped)
                    if title and title not in seen_titles and len(title) > 3:
                        headers.append({
                            'line': i,
                            'level': level,
                            'title': title,
                            'raw': line_stripped
                        })
                        seen_titles.add(title)
                        logger.debug(f"Header found at line {i}: {title} (level {level})")
                        break
        
        return headers
    
    def _extract_header_info(self, match: re.Match, line: str) -> Tuple[str, int]:
        """Extract title and level from header match."""
        groups = match.groups()
        
        # Section with number: "Section 4: Title" or "4.2 Title"
        if groups and len(groups) >= 2 and groups[0] and groups[0][0].isdigit():
            section_num = groups[0]
            level = section_num.count('.') + 1
            title = groups[1].strip()
            return title, level
        
        # Markdown headers
        if line.startswith('#'):
            level = len(line) - len(line.lstrip('#'))
            title = groups[0].strip() if groups else line.lstrip('#').strip()
            return title, min(level, 3)
        
        # ALL CAPS or single group
        title = groups[0].strip() if groups else line.strip()
        return title, 1
    
    def _build_hierarchy(self, headers: List[Dict[str, Any]], lines: List[str]) -> List[WorkflowSection]:
        """Build sections from headers."""
        sections = []
        
        for i, header in enumerate(headers):
            start_line = header['line']
            end_line = headers[i + 1]['line'] if i + 1 < len(headers) else len(lines)
            
            content_lines = lines[start_line + 1:end_line]
            content = '\n'.join(content_lines).strip()
            
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
            
            sections.append(section)
        
        return sections
    
    def _filter_workflow_sections(self, sections: List[WorkflowSection]) -> List[WorkflowSection]:
        """Filter to workflow-related sections."""
        workflow_sections = []
        
        exclude_patterns = [
            r'table of contents',
            r'^contents$',
            r'glossary',
            r'references',
            r'index',
            r'quick reference$',
        ]
        
        for section in sections:
            title_lower = section.title.lower()
            
            # Exclude non-workflow sections
            if any(re.search(pattern, title_lower) for pattern in exclude_patterns):
                continue
            
            # Must have some content
            if len(section.content) < 100:
                continue
            
            # Check for workflow indicators
            has_workflow_title = any(
                indicator in title_lower
                for indicator in self.WORKFLOW_SECTION_INDICATORS
            )
            
            # Include if: workflow title OR substantial content
            if has_workflow_title or len(section.content) >= 300:
                workflow_sections.append(section)
        
        return workflow_sections
    
    def _analyze_section(self, section: WorkflowSection):
        """Analyze section for workflow metrics."""
        content_lower = section.content.lower()
        
        # Count steps
        step_patterns = [
            r'^\s*\d+[\.\)]\s+',
            r'^\s*\*\*\d+\*\*',
            r'^\s*step\s+\d+',
        ]
        
        step_count = 0
        for line in section.content.split('\n'):
            if any(re.match(p, line.strip(), re.IGNORECASE) for p in step_patterns):
                step_count += 1
        
        section.step_count = step_count
        
        # Count decisions
        decision_keywords = ['if', 'whether', 'yes', 'no', 'choose', 'select']
        section.decision_count = sum(content_lower.count(kw) for kw in decision_keywords)
        
        # Calculate confidence
        confidence = 0.0
        
        # Workflow keywords in title
        title_lower = section.title.lower()
        if any(ind in title_lower for ind in self.WORKFLOW_SECTION_INDICATORS):
            confidence += 0.4
        
        # Has steps
        if section.step_count >= 3:
            confidence += 0.3
        elif section.step_count > 0:
            confidence += 0.2
        
        # Workflow keywords in content
        keyword_count = sum(1 for kw in self.WORKFLOW_KEYWORDS if kw in content_lower)
        confidence += min(0.2, keyword_count * 0.02)
        
        # Content length
        if 300 <= len(section.content) <= 10000:
            confidence += 0.1
        
        section.confidence = min(1.0, confidence)
    
    def _apply_quality_filters(self, sections: List[WorkflowSection]) -> List[WorkflowSection]:
        """Apply quality filters."""
        filtered = []
        
        for section in sections:
            # Minimum confidence
            if section.confidence < 0.25:
                continue
            
            # Must have steps OR good content
            if section.step_count == 0 and len(section.content) < 500:
                continue
            
            # Filter pure tables
            pipe_count = section.content.count('|')
            if pipe_count > len(section.content) / 15:
                continue
            
            filtered.append(section)
        
        return filtered
    
    def _create_single_workflow(self, text: str, lines: List[str]) -> WorkflowSection:
        """Create single workflow from entire document."""
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
        """Generate summary of detected workflows."""
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
