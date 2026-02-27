"""NLP-driven workflow detection for any document format."""

import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class WorkflowSection:
    id: str
    title: str
    content: str
    level: int
    start_line: int
    end_line: int
    step_count: int = 0
    decision_count: int = 0
    confidence: float = 0.0
    subsections: List['WorkflowSection'] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id, 'title': self.title, 'content': self.content,
            'level': self.level, 'start_line': self.start_line, 'end_line': self.end_line,
            'step_count': self.step_count, 'decision_count': self.decision_count,
            'confidence': self.confidence,
            'subsections': [s.to_dict() for s in self.subsections]
        }


class WorkflowDetector:
    """Multi-strategy workflow detection using semantic analysis.
    
    Split modes:
    - auto: Cascade through strategies (headers → numbered → semantic → single)
    - section: Force header-based detection
    - subsection: Detect nested subsections
    - procedure: Look for procedure/process keywords
    - none: Treat entire document as one workflow
    """
    
    ACTION_VERBS = [
        'click', 'select', 'choose', 'enter', 'type', 'press', 'open', 'close',
        'navigate', 'go', 'visit', 'access', 'launch', 'start', 'run', 'execute',
        'install', 'download', 'upload', 'save', 'delete', 'remove', 'add',
        'create', 'update', 'modify', 'change', 'edit', 'configure', 'set',
        'enable', 'disable', 'activate', 'connect', 'restart', 'reboot',
        'verify', 'check', 'confirm', 'ensure', 'wait', 'review', 'test',
        'insert', 'eject', 'mount', 'boot', 'shutdown'
    ]
    
    def __init__(self, split_mode: str = 'auto'):
        """Initialize workflow detector.
        
        Args:
            split_mode: Detection strategy ('auto', 'section', 'subsection', 'procedure', 'none')
        """
        self.split_mode = split_mode.lower()
        self.action_pattern = re.compile(r'\b(' + '|'.join(self.ACTION_VERBS) + r')\b', re.IGNORECASE)
        
    def detect_workflows(self, text: str) -> List[WorkflowSection]:
        """Detect workflows based on split_mode strategy."""
        lines = text.split('\n')
        
        if self.split_mode == 'none':
            # Treat entire document as one workflow
            logger.info("Split mode: none (single workflow)")
            return [self._create_section("\n".join(lines), 0, len(lines), "Workflow")]
        
        if self.split_mode == 'section':
            # Force header-based detection
            logger.info("Split mode: section (headers only)")
            sections = self._try_header_detection(lines)
            if sections:
                return self._analyze_and_filter(sections)
            return [self._create_section("\n".join(lines), 0, len(lines), "Workflow")]
        
        if self.split_mode == 'subsection':
            # Detect nested subsections and flatten into separate workflows
            logger.info("Split mode: subsection (nested headers)")
            sections = self._try_header_detection(lines)
            if sections:
                # Flatten subsections into separate workflows
                all_sections = []
                for section in sections:
                    all_sections.append(section)
                    all_sections.extend(section.subsections)
                return self._analyze_and_filter(all_sections)
            return [self._create_section("\n".join(lines), 0, len(lines), "Workflow")]
        
        if self.split_mode == 'procedure':
            # Look for procedure/process keywords
            logger.info("Split mode: procedure (keyword-based)")
            sections = self._try_procedure_detection(lines)
            if sections:
                return self._analyze_and_filter(sections)
            return [self._create_section("\n".join(lines), 0, len(lines), "Workflow")]
        
        # Default: auto mode (cascade)
        return self._auto_detect(lines)
    
    def _auto_detect(self, lines: List[str]) -> List[WorkflowSection]:
        """Cascade: headers → numbered sequence → semantic chunking → single workflow.
        
        Smart detection: Only try headers if document isn't a single numbered workflow.
        """
        # First, check if this is a single continuous numbered workflow
        # If so, skip header detection to avoid false positives
        numbered_lines = [l for l in lines if re.match(r'^\s*\d+[\.)\:]\s+', l.strip())]
        total_lines = len([l for l in lines if l.strip()])
        
        # If >60% of lines are numbered steps, it's likely a single workflow
        if total_lines > 0 and (len(numbered_lines) / total_lines) > 0.6:
            logger.info(f"Auto mode → High numbered line density ({len(numbered_lines)}/{total_lines}), treating as single workflow")
            numbered_workflow = self._try_numbered_sequence_detection(lines)
            if numbered_workflow:
                return [numbered_workflow]
        
        # Priority 1: Try header-based detection (multi-section documents)
        sections = self._try_header_detection(lines)
        if sections and len(sections) > 1:
            logger.info(f"Auto mode → Headers: {len(sections)} sections")
            return self._analyze_and_filter(sections)
        
        # Priority 2: Check for numbered sequence workflow (single workflow with steps)
        numbered_workflow = self._try_numbered_sequence_detection(lines)
        if numbered_workflow:
            logger.info(f"Auto mode → Numbered sequence: 1 continuous workflow")
            return [numbered_workflow]
        
        # Priority 3: Try semantic chunking
        sections = self._try_semantic_chunking(lines)
        if sections and len(sections) > 1:
            logger.info(f"Auto mode → Semantic: {len(sections)} sections")
            return self._analyze_and_filter(sections)
        
        # Fallback: single workflow
        logger.info("Auto mode → Fallback: single workflow")
        return [self._create_section("\n".join(lines), 0, len(lines), "Workflow")]
    
    def _try_numbered_sequence_detection(self, lines: List[str]) -> Optional[WorkflowSection]:
        """Detect continuous numbered workflow (1. 2. 3. ... N.)"""
        sequence_ranges = []
        current_sequence = []
        last_number = 0
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            # Match numbered steps: "1.", "1)", "Step 1:", "1 -", etc.
            match = re.match(r'^(\d+)[\.)\:\-\s]', stripped)
            
            if match:
                num = int(match.group(1))
                
                # Check if this continues the sequence (allow gaps of 1)
                if num == last_number + 1 or (not current_sequence and num <= 3):
                    current_sequence.append(i)
                    last_number = num
                elif num == 1 and current_sequence:
                    # New sequence starting, save previous
                    if len(current_sequence) >= 3:
                        sequence_ranges.append((current_sequence[0], current_sequence[-1]))
                    current_sequence = [i]
                    last_number = 1
                elif current_sequence:
                    # Gap in sequence, end current
                    if len(current_sequence) >= 3:
                        sequence_ranges.append((current_sequence[0], current_sequence[-1]))
                    current_sequence = []
                    last_number = 0
            elif stripped and current_sequence:
                # Non-numbered line within sequence (could be sub-item, decision branch, etc.)
                # Keep the sequence going if it's indented or starts with dash/bullet
                if re.match(r'^[\s\-\*•]', line) or 'if yes' in stripped.lower() or 'if no' in stripped.lower():
                    continue
        
        # Save final sequence
        if len(current_sequence) >= 3:
            sequence_ranges.append((current_sequence[0], current_sequence[-1]))
        
        # If we found a substantial numbered sequence, treat entire range as one workflow
        if sequence_ranges:
            # Find the largest sequence
            largest = max(sequence_ranges, key=lambda r: r[1] - r[0])
            start_line, end_line = largest
            
            # Expand to include all lines between start and end (captures sub-items)
            content_lines = []
            for i in range(len(lines)):
                if i >= start_line and i <= end_line + 5:  # Include a few lines after for "End"
                    content_lines.append(lines[i])
            
            content = "\n".join(content_lines).strip()
            
            # Count actual numbered steps
            step_count = len([l for l in content_lines if re.match(r'^\d+[\.)\:]', l.strip())])
            
            if step_count >= 3:
                # Extract title from first comment line or first step
                title = "Workflow"
                for line in lines[:start_line]:
                    if line.strip() and not line.strip().startswith('#'):
                        title = line.strip()[:60]
                        break
                
                section = WorkflowSection(
                    id="s0",
                    title=title,
                    content=content,
                    level=1,
                    start_line=start_line,
                    end_line=min(end_line + 5, len(lines)),
                    subsections=[]
                )
                self._analyze(section)
                logger.info(f"Detected numbered sequence: {step_count} steps")
                return section
        
        return None
    
    def _try_header_detection(self, lines: List[str]) -> List[WorkflowSection]:
        """Flexible header detection (any format).
        
        Skip lines that appear to be part of numbered sequences.
        """
        headers = []
        patterns = [
            (r'^(#{1,3})\s+(.{5,})$', 'md'),
            (r'^(\d+(?:\.\d+)*)\s+([A-Z][A-Za-z\s]{5,})$', 'num'),  # Must start with capital
            (r'^([A-Z][A-Z\s]{10,}[A-Z])$', 'caps'),  # All caps, long
            (r'^(Section\s+\d+)[:\s]+(.{5,})$', 'section'),  # "Section 1: Title"
        ]
        
        # First identify numbered step lines to exclude them from header detection
        numbered_step_lines = set()
        for i, line in enumerate(lines):
            if re.match(r'^\d+[\.)\:]\s+', line.strip()):
                numbered_step_lines.add(i)
        
        for i, line in enumerate(lines):
            s = line.strip()
            
            # Skip if part of numbered sequence
            if i in numbered_step_lines:
                continue
            
            if len(s) < 5 or '|' in s or '→' in s:
                continue
            
            for pat, tag in patterns:
                m = re.match(pat, s, re.IGNORECASE if tag == 'section' else 0)
                if m:
                    if tag == 'section':
                        title = m.group(2).strip() if len(m.groups()) > 1 else m.group(1)
                        level = 1
                    elif tag == 'caps':
                        title = m.group(1)
                        level = 1
                    else:
                        title = m.group(2)
                        level = len(m.group(1)) if tag == 'md' else (m.group(1).count('.') + 1 if tag == 'num' else 1)
                    headers.append({'line': i, 'level': level, 'title': title.strip()})
                    break
            
            # Underlined headers
            if i + 1 < len(lines) and re.match(r'^[=\-]{5,}$', lines[i + 1].strip()):
                if i not in numbered_step_lines:
                    headers.append({'line': i, 'level': 1, 'title': s})
        
        return self._build_from_headers(headers, lines) if headers else []
    
    def _try_procedure_detection(self, lines: List[str]) -> List[WorkflowSection]:
        """Detect sections starting with procedure/process keywords."""
        procedure_keywords = [
            'procedure:', 'process:', 'workflow:', 'steps:', 'method:',
            'instructions:', 'how to', 'setup:', 'configuration:', 'installation:'
        ]
        
        sections = []
        current_start = None
        current_title = None
        
        for i, line in enumerate(lines):
            stripped = line.strip().lower()
            
            # Check if line starts with procedure keyword
            for keyword in procedure_keywords:
                if stripped.startswith(keyword):
                    # Save previous section if exists
                    if current_start is not None:
                        content = "\n".join(lines[current_start:i]).strip()
                        sections.append(self._create_section(content, current_start, i, current_title))
                    
                    # Start new section
                    current_start = i
                    current_title = line.strip()[:60]
                    break
        
        # Save final section
        if current_start is not None:
            content = "\n".join(lines[current_start:]).strip()
            sections.append(self._create_section(content, current_start, len(lines), current_title))
        
        return sections
    
    def _try_semantic_chunking(self, lines: List[str]) -> List[WorkflowSection]:
        """Chunk by action verb density and topic shifts - but NOT for numbered sequences."""
        # First check if this looks like a numbered sequence
        numbered_lines = [l for l in lines if re.match(r'^\s*\d+[\.)\:]', l.strip())]
        if len(numbered_lines) >= 5:
            # This is likely a single numbered workflow, don't chunk it
            return []
        
        paragraphs = self._get_paragraphs(lines)
        if len(paragraphs) < 2:
            return []
        
        # Score each paragraph
        for p in paragraphs:
            p['score'] = self._workflow_score(p['text'])
        
        # Merge high-scoring consecutive paragraphs
        chunks = []
        current = []
        
        for p in paragraphs:
            if p['score'] > 0.25:
                current.append(p)
            elif current:
                chunks.append(current)
                current = []
        
        if current:
            chunks.append(current)
        
        # Create sections from chunks
        sections = []
        for chunk in chunks:
            if len(chunk) >= 2 or chunk[0]['score'] > 0.4:
                content = "\n\n".join(p['text'] for p in chunk)
                title = self._gen_title(chunk[0]['text'])
                sections.append(self._create_section(content, chunk[0]['start'], chunk[-1]['end'], title))
        
        return sections
    
    def _get_paragraphs(self, lines: List[str]) -> List[Dict]:
        """Split into paragraphs."""
        paras = []
        curr, start = [], 0
        
        for i, line in enumerate(lines):
            if line.strip():
                if not curr:
                    start = i
                curr.append(line)
            elif curr:
                paras.append({'start': start, 'end': i, 'text': "\n".join(curr)})
                curr = []
        
        if curr:
            paras.append({'start': start, 'end': len(lines), 'text': "\n".join(curr)})
        
        return paras
    
    def _workflow_score(self, text: str) -> float:
        """Score procedural content likelihood (0-1)."""
        if len(text) < 20:
            return 0.0
        
        words = text.lower().split()
        if not words:
            return 0.0
        
        score = 0.0
        
        # Action verb density
        actions = len(self.action_pattern.findall(text.lower()))
        score += min(0.4, (actions / len(words)) * 2.5)
        
        # Numbered/bulleted
        if re.search(r'^\s*[\d\-\*•]', text, re.MULTILINE):
            score += 0.25
        
        # Decision words
        if re.search(r'\b(if|whether|choose|option|select)\b', text.lower()):
            score += 0.15
        
        # Imperative sentences
        sentences = [s.strip() for s in re.split(r'[.!?]', text) if s.strip()]
        imperatives = sum(1 for s in sentences if s.split()[0].lower() in self.ACTION_VERBS if s.split())
        if sentences:
            score += min(0.2, (imperatives / len(sentences)))
        
        return min(1.0, score)
    
    def _gen_title(self, text: str) -> str:
        """Generate title from text."""
        first = re.split(r'[.!?]', text)[0].strip()[:60]
        return first if first else "Workflow"
    
    def _build_from_headers(self, headers: List[Dict], lines: List[str]) -> List[WorkflowSection]:
        """Build sections from headers with proper content isolation.
        
        Key principle: Each section only gets content BETWEEN its header and next same/higher level header.
        Subsections are nested but don't include their content in parent.
        """
        if not headers:
            return []
        
        sections = []
        stack = []  # Stack to track parent sections at each level
        
        for i, h in enumerate(headers):
            # Find where this section's content ends
            next_same_or_higher = None
            for j in range(i + 1, len(headers)):
                if headers[j]['level'] <= h['level']:
                    next_same_or_higher = headers[j]['line']
                    break
            
            content_end = next_same_or_higher if next_same_or_higher else len(lines)
            
            # Find where THIS section's own content ends (before any subsections)
            own_content_end = content_end
            for j in range(i + 1, len(headers)):
                if headers[j]['level'] > h['level']:
                    # Found a subsection - parent content ends here
                    own_content_end = headers[j]['line']
                    break
                elif headers[j]['level'] <= h['level']:
                    # Found same/higher level - stop
                    break
            
            # Extract ONLY this section's content (not including subsections)
            content_start = h['line'] + 1
            content = "\n".join(lines[content_start:own_content_end]).strip()
            
            # Pop stack to appropriate level
            while stack and stack[-1]['level'] >= h['level']:
                stack.pop()
            
            # Create section
            section = WorkflowSection(
                id=f"s{len(sections)}" if not stack else f"{stack[-1]['section'].id}_sub{len(stack[-1]['section'].subsections)}",
                title=h['title'],
                content=content,
                level=h['level'],
                start_line=h['line'],
                end_line=content_end,
                subsections=[]
            )
            
            # Add to parent or root
            if stack:
                stack[-1]['section'].subsections.append(section)
            else:
                sections.append(section)
            
            # Push to stack for potential children
            stack.append({'level': h['level'], 'section': section})
        
        return sections
    
    def _create_section(self, content: str, start: int, end: int, title: str) -> WorkflowSection:
        """Create analyzed section."""
        s = WorkflowSection(
            id=f"s{start}", title=title, content=content,
            level=1, start_line=start, end_line=end, subsections=[]
        )
        self._analyze(s)
        return s
    
    def _analyze(self, section: WorkflowSection):
        """Analyze section metrics.
        
        CRITICAL: Only analyze this section's content, NOT subsections.
        Subsections are analyzed separately.
        """
        text = section.content
        
        # Count steps
        step_patterns = [
            r'^\s*\*\*\d+\*\*',
            r'^\s*\d+[\.)](\s+|$)',
            r'^\s*Step\s+\d+',
            r'^\s*[\-\*•]\s+[A-Z]',
        ]
        section.step_count = sum(1 for line in text.split('\n')
                                 if any(re.match(p, line.strip(), re.I) for p in step_patterns))
        
        # Decisions
        section.decision_count = len(re.findall(r'\b(if|whether|choose|option|select|yes|no)\b', text.lower()))
        
        # Confidence
        section.confidence = self._workflow_score(text)
        if section.step_count >= 3:
            section.confidence = min(1.0, section.confidence + 0.2)
    
    def _is_reference_section(self, section: WorkflowSection) -> bool:
        """Check if section is a reference/overview (not an actionable workflow).
        
        IMPORTANT: Only call this on sections WITHOUT subsections.
        Sections with subsections should be evaluated based on their children.
        """
        text = section.content.lower()
        title = section.title.lower()
        
        # Keywords that indicate reference content
        reference_keywords = [
            'overview', 'introduction', 'summary', 'table of contents', 
            'index', 'glossary'
        ]
        
        # Check title for reference keywords
        if any(keyword in title for keyword in reference_keywords):
            return True
        
        # Check for "See Section X" patterns (common in overview sections)
        if len(re.findall(r'see section \d+', text)) >= 2:
            return True
        
        # Check if content is very short (likely just a header with no workflow)
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        if len(lines) < 3:
            return True
        
        return False
    
    def _analyze_and_filter(self, sections: List[WorkflowSection]) -> List[WorkflowSection]:
        """Analyze sections and intelligently filter to avoid duplication.
        
        CRITICAL FIX: Check for workflow subsections BEFORE marking parent as reference.
        
        Strategy:
        1. Analyze all sections recursively
        2. For each parent: Check if it has workflow subsections FIRST
        3. If yes, export subsections (ignore parent)
        4. If no subsections, check if parent itself is a workflow
        5. Only skip truly empty reference sections
        """
        # Analyze all sections including subsections
        def analyze_recursive(section_list):
            for s in section_list:
                self._analyze(s)
                if s.subsections:
                    analyze_recursive(s.subsections)
        
        analyze_recursive(sections)
        
        # Flatten and filter intelligently
        result = []
        
        for section in sections:
            # CRITICAL: Check for workflow subsections FIRST (before reference check)
            # Use stricter threshold for subsections (3 steps)
            workflow_subsections = [sub for sub in section.subsections 
                                   if sub.step_count >= 3 and sub.confidence > 0.25]
            
            if workflow_subsections:
                # This parent has valid workflow subsections
                # Export the subsections, not the parent
                for sub in workflow_subsections:
                    if not self._is_reference_section(sub):
                        result.append(sub)
                        logger.info(f"  ✓ {sub.title[:40]}: {sub.step_count} steps, conf={sub.confidence:.2f}")
            else:
                # No workflow subsections found
                # Check if parent itself is a reference section
                if self._is_reference_section(section):
                    logger.info(f"  Skipping reference section: {section.title[:40]}")
                    continue
                
                # Parent is not a reference and has workflow content
                # Use more lenient threshold for top-level sections (2 steps)
                if section.step_count >= 2 and section.confidence > 0.25:
                    result.append(section)
                    logger.info(f"  ✓ {section.title[:40]}: {section.step_count} steps, conf={section.confidence:.2f}")
        
        return result if result else [max(sections, key=lambda x: x.confidence)] if sections else []
    
    def get_workflow_summary(self, sections: List[WorkflowSection]) -> Dict[str, Any]:
        return {
            'total_workflows': len(sections),
            'total_steps': sum(s.step_count for s in sections),
            'total_decisions': sum(s.decision_count for s in sections),
            'avg_confidence': round(sum(s.confidence for s in sections) / len(sections), 2) if sections else 0,
            'workflows': [{
                'id': s.id, 'title': s.title, 'step_count': s.step_count,
                'decision_count': s.decision_count, 'confidence': round(s.confidence, 2)
            } for s in sections]
        }
