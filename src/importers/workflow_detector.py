"""Intelligent workflow boundary detection for multi-section documents.

Designed to handle real-world documents with free-form formatting including:
- DOCX table extraction (pipe-delimited with **bold** markers)
- Mixed numbered lists and tables
- Markdown headers from DOCX parsing
- Warning callouts and cross-references
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
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
    step_count: int = 0
    decision_count: int = 0
    confidence: float = 0.0
    subsections: List['WorkflowSection'] = field(default_factory=list)
    
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
    """Detect workflow boundaries and section structure in documents.
    
    Handles real-world document formats including:
    - DOCX extracted tables (pipe-delimited with bold markers)
    - Mixed free-form and structured content
    - Markdown-style headers from document parsing
    """
    
    # Header patterns ordered by specificity
    HEADER_PATTERNS = [
        # Markdown "# Section N: Title" (from DOCX extraction)
        (r'^#\s+Section\s+(\d+)\s*[:\-]\s*(.+)$', 'section_md'),
        # Markdown "## N.N Title" (subsection)
        (r'^##\s+(\d+\.\d+)\s+(.+)$', 'subsection_md'),
        # Markdown "### Title" (sub-subsection)
        (r'^###\s+(.+)$', 'subsubsection_md'),
        # Plain "Section N: Title"
        (r'^Section\s+(\d+)\s*[:\-]\s*(.+)$', 'section_plain'),
        # Numbered: "4. Title" or "4.2 Title" (title must be 6+ chars starting uppercase)
        (r'^(\d+(?:\.\d+)*)[.\s]\s*([A-Z][A-Za-z].{5,})$', 'numbered'),
        # ALL CAPS (min 15 chars to avoid short table headers)
        (r'^([A-Z][A-Z\s]{14,})$', 'caps'),
    ]
    
    # Patterns that identify steps in various document formats
    STEP_PATTERNS = [
        r'^\s*\*\*(\d+)\*\*\s+\S',           # **1** Action text (DOCX bold in table)
        r'^\s*\*\*(\d+)\.\*\*\s+',            # **1.** Action text (DOCX bold numbered)
        r'^\s*\*\*(\d+)\*\*\.\s+',            # **1**. Action text
        r'^\s*\|\s*\*\*(\d+)\*\*\s*\|\s*\S',  # | **1** | text (pipe-delimited table)
        r'^\s*(\d+)\.\s+[A-Z]',               # 1. Action (plain numbered)
        r'^\s*(\d+)\)\s+[A-Z]',               # 1) Action
        r'^\s*Step\s+(\d+)',                   # Step 1
        r'^\s*\*\*Step\s+(\d+)\*\*',          # **Step 1**
    ]
    
    # Keywords suggesting workflow/procedural content
    WORKFLOW_KEYWORDS = [
        'step', 'procedure', 'process', 'method', 'setup', 'installation',
        'configuration', 'instruction', 'guide', 'workflow', 'protocol',
        'install', 'configure', 'create', 'restore', 'backup', 'upgrade',
        'connect', 'navigate', 'click', 'select', 'enter', 'run',
        'download', 'insert', 'open', 'boot', 'restart', 'reboot'
    ]
    
    # Title keywords indicating a workflow section
    WORKFLOW_TITLE_INDICATORS = [
        'method', 'setup', 'procedure', 'installation', 'configuration',
        'process', 'workflow', 'guide', 'instructions', 'preparation',
        'backup', 'restore', 'upgrade', 'creating', 'restoring',
        'verification', 'network', 'adapter', 'settings'
    ]
    
    # Sections to exclude
    EXCLUDE_PATTERNS = [
        r'table of contents',
        r'^contents$',
        r'glossary',
        r'^quick reference$',
        r'^hardware requirements$',
        r'^system requirements$',
    ]
    
    def __init__(self):
        """Initialize the workflow detector."""
        self.compiled_headers = [
            (re.compile(p, re.MULTILINE), tag) for p, tag in self.HEADER_PATTERNS
        ]
        self.compiled_steps = [re.compile(p, re.IGNORECASE) for p in self.STEP_PATTERNS]
        self.compiled_excludes = [re.compile(p, re.IGNORECASE) for p in self.EXCLUDE_PATTERNS]
    
    def detect_workflows(self, text: str) -> List[WorkflowSection]:
        """
        Detect all workflow sections in a document.
        
        Strategy:
        1. Find all headers (top-level and sub-level)
        2. Group subsections under their parent top-level section
        3. Analyze each top-level section (with merged subsection content)
        4. Filter by workflow indicators and quality
        5. Fallback to single workflow if nothing detected
        """
        lines = text.split('\n')
        
        # Step 1: Detect all headers
        headers = self._detect_headers(lines)
        logger.info(f"Detected {len(headers)} headers: {[h['title'][:40] for h in headers]}")
        
        if not headers:
            logger.info("No headers found, treating as single workflow")
            return [self._create_single_workflow(text, lines)]
        
        # Step 2: Build top-level sections with merged subsections
        sections = self._build_grouped_sections(headers, lines)
        logger.info(f"Built {len(sections)} top-level sections")
        
        # Step 3: Analyze each section
        for section in sections:
            self._analyze_section(section)
            logger.info(
                f"  {section.title[:40]}: {section.step_count} steps, "
                f"{section.decision_count} decisions, "
                f"confidence={section.confidence:.2f}, "
                f"content_len={len(section.content)}"
            )
        
        # Step 4: Filter for workflow sections
        filtered = self._filter_workflows(sections)
        logger.info(f"After filtering: {len(filtered)} workflows")
        
        # Step 5: Fallback - always return something
        if not filtered:
            logger.warning("No workflows passed filters, returning single workflow")
            single = self._create_single_workflow(text, lines)
            return [single]
        
        return filtered
    
    def _detect_headers(self, lines: List[str]) -> List[Dict[str, Any]]:
        """Detect all headers with their types and levels."""
        headers = []
        seen_titles = set()
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or len(stripped) < 3:
                continue
            
            # Skip lines that look like table borders
            if stripped.startswith('+') and '-' in stripped:
                continue
            if stripped.startswith('|') and stripped.endswith('|'):
                continue
            # Skip lines with too many special chars (table formatting)
            special_count = sum(1 for c in stripped if c in '+-=|')
            if len(stripped) > 0 and special_count / len(stripped) > 0.3:
                continue
            
            for pattern, tag in self.compiled_headers:
                match = pattern.match(stripped)
                if match:
                    title, level = self._parse_header(match, tag, stripped)
                    
                    if title and len(title) > 3 and title not in seen_titles:
                        headers.append({
                            'line': i,
                            'level': level,
                            'title': title,
                            'tag': tag,
                            'raw': stripped
                        })
                        seen_titles.add(title)
                        break
        
        return headers
    
    def _parse_header(self, match: re.Match, tag: str, line: str) -> Tuple[str, int]:
        """Parse header match into title and level."""
        groups = match.groups()
        
        if tag == 'section_md' or tag == 'section_plain':
            return groups[1].strip(), 1
        
        elif tag == 'subsection_md':
            return groups[1].strip(), 2
        
        elif tag == 'subsubsection_md':
            return groups[0].strip(), 3
        
        elif tag == 'numbered':
            section_num = groups[0]
            level = section_num.count('.') + 1
            return groups[1].strip(), level
        
        elif tag == 'caps':
            return groups[0].strip(), 1
        
        return groups[0].strip() if groups else line.strip(), 1
    
    def _build_grouped_sections(self, headers: List[Dict[str, Any]], lines: List[str]) -> List[WorkflowSection]:
        """
        Group headers into top-level sections, merging subsections into parent.
        
        This ensures "Section 4: Sierra Wedge Setup" includes content from
        4.1, 4.2, 4.3, 4.4 as one unified workflow.
        """
        sections = []
        current_parent = None
        current_parent_start = None
        
        for i, header in enumerate(headers):
            next_start = headers[i + 1]['line'] if i + 1 < len(headers) else len(lines)
            
            if header['level'] == 1:
                # Save previous parent section
                if current_parent is not None:
                    content_lines = lines[current_parent_start:header['line']]
                    current_parent.content = '\n'.join(content_lines).strip()
                    current_parent.end_line = header['line']
                    sections.append(current_parent)
                
                # Start new parent section
                current_parent = WorkflowSection(
                    id=f"section_{len(sections)}",
                    title=header['title'],
                    content='',
                    level=1,
                    start_line=header['line'],
                    end_line=next_start,
                    subsections=[]
                )
                current_parent_start = header['line'] + 1
            
            elif header['level'] >= 2 and current_parent is not None:
                # Subsection - add as child, content stays merged in parent
                sub_content_lines = lines[header['line'] + 1:next_start]
                sub = WorkflowSection(
                    id=f"{current_parent.id}_sub_{len(current_parent.subsections)}",
                    title=header['title'],
                    content='\n'.join(sub_content_lines).strip(),
                    level=header['level'],
                    start_line=header['line'],
                    end_line=next_start,
                    subsections=[]
                )
                current_parent.subsections.append(sub)
            
            elif header['level'] >= 2 and current_parent is None:
                # Orphan subsection, create standalone
                content_lines = lines[header['line'] + 1:next_start]
                section = WorkflowSection(
                    id=f"section_{len(sections)}",
                    title=header['title'],
                    content='\n'.join(content_lines).strip(),
                    level=header['level'],
                    start_line=header['line'],
                    end_line=next_start,
                    subsections=[]
                )
                sections.append(section)
        
        # Save the last parent
        if current_parent is not None:
            content_lines = lines[current_parent_start:]
            current_parent.content = '\n'.join(content_lines).strip()
            current_parent.end_line = len(lines)
            sections.append(current_parent)
        
        return sections
    
    def _analyze_section(self, section: WorkflowSection):
        """Analyze section for workflow metrics including subsection content."""
        # Combine parent + subsection content for analysis
        all_content = section.content
        for sub in section.subsections:
            all_content += '\n' + sub.content
        
        content_lower = all_content.lower()
        
        # Count steps using all patterns
        step_count = 0
        for line in all_content.split('\n'):
            stripped = line.strip()
            if not stripped:
                continue
            for pattern in self.compiled_steps:
                if pattern.match(stripped):
                    step_count += 1
                    break
        
        section.step_count = step_count
        
        # Count decision indicators
        decision_patterns = [
            r'\bif\b', r'\bwhether\b', r'\bchoose\b',
            r'\boption\b', r'\balternative\b', r'\bskip if\b'
        ]
        section.decision_count = sum(
            len(re.findall(p, content_lower)) for p in decision_patterns
        )
        
        # Calculate confidence
        confidence = 0.0
        title_lower = section.title.lower()
        
        # Workflow title keywords
        title_matches = sum(1 for ind in self.WORKFLOW_TITLE_INDICATORS if ind in title_lower)
        confidence += min(0.4, title_matches * 0.15)
        
        # Has procedural steps
        if section.step_count >= 5:
            confidence += 0.35
        elif section.step_count >= 3:
            confidence += 0.25
        elif section.step_count >= 1:
            confidence += 0.15
        
        # Workflow action keywords in content
        action_keywords = ['click', 'navigate', 'select', 'enter', 'install',
                          'run', 'open', 'insert', 'connect', 'download',
                          'configure', 'restart', 'reboot', 'boot']
        action_count = sum(1 for kw in action_keywords if kw in content_lower)
        confidence += min(0.2, action_count * 0.02)
        
        # Has subsections (structured document)
        if len(section.subsections) >= 2:
            confidence += 0.1
        
        # Meaningful content length (exclude table borders)
        meaningful = re.sub(r'[+\-=|]', '', all_content)
        meaningful = re.sub(r'\s+', ' ', meaningful).strip()
        if len(meaningful) >= 200:
            confidence += 0.1
        
        section.confidence = min(1.0, confidence)
    
    def _filter_workflows(self, sections: List[WorkflowSection]) -> List[WorkflowSection]:
        """Filter sections to only include actual workflows."""
        filtered = []
        
        for section in sections:
            title_lower = section.title.lower()
            
            # Check exclusions
            if any(p.search(title_lower) for p in self.compiled_excludes):
                logger.debug(f"Excluded: {section.title}")
                continue
            
            # Must have minimum confidence
            if section.confidence < 0.2:
                logger.debug(f"Low confidence ({section.confidence:.2f}): {section.title}")
                continue
            
            # Must have some procedural content
            if section.step_count == 0 and section.decision_count == 0:
                # Check if content has any action words at all
                all_content = section.content.lower()
                for sub in section.subsections:
                    all_content += ' ' + sub.content.lower()
                action_words = ['click', 'install', 'run', 'navigate', 'select', 'enter',
                               'connect', 'configure', 'download', 'insert', 'open']
                action_count = sum(1 for w in action_words if w in all_content)
                if action_count < 3:
                    logger.debug(f"No procedural content: {section.title}")
                    continue
            
            filtered.append(section)
        
        return filtered
    
    def _create_single_workflow(self, text: str, lines: List[str]) -> WorkflowSection:
        """Create a single workflow from entire document."""
        section = WorkflowSection(
            id="section_0",
            title="Complete Workflow",
            content=text,
            level=1,
            start_line=0,
            end_line=len(lines),
            subsections=[]
        )
        self._analyze_section(section)
        # Boost confidence for single-workflow fallback
        section.confidence = max(section.confidence, 0.5)
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
