"""NLP-driven workflow detection for any document format."""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

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
    module_id: Optional[str] = None
    module_title: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id, 'title': self.title, 'content': self.content,
            'level': self.level, 'start_line': self.start_line, 'end_line': self.end_line,
            'step_count': self.step_count, 'decision_count': self.decision_count,
            'confidence': self.confidence,
            'module_id': self.module_id,
            'module_title': self.module_title,
            'subsections': [s.to_dict() for s in self.subsections]
        }


class WorkflowDetector:
    """Multi-strategy workflow detection using semantic analysis.

    Split modes:
    - auto: Cascade through strategies (headers → numbered → semantic → single)
    - merge: Join all detected sections into a single pipeline (SOP mode)
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
        'assign', 'move', 'record', 'document', 'pack', 'ship', 'monitor',
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

        if self.split_mode == 'merge':
            # Detect sections then merge them
            logger.info("Split mode: merge (pipeline mode)")
            sections = self._try_header_detection(lines)
            if sections:
                merged = self._merge_sections(sections)
                return [merged]
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
                # Flatten subsections into separate workflows. _analyze_and_filter
                # also recurses into subsections, so dedupe afterwards by
                # (title, start_line) to avoid each subsection appearing twice.
                all_sections = []
                for section in sections:
                    all_sections.append(section)
                    all_sections.extend(section.subsections)
                analyzed = self._analyze_and_filter(all_sections)
                return self._dedupe_sections(analyzed)
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

    def _count_transition_indicators(self, text: str) -> int:
        lowered = text.lower()
        indicators = [
            "move the ticket to",
            "move the deal to",
            "move the item to",
            "move to '",
            'move to "',
            "change status to",
            "update ticket to",
            "proceed to section",
            "next step:",
        ]
        return sum(lowered.count(phrase) for phrase in indicators)

    def _should_merge_state_sections(self, sections: List[WorkflowSection]) -> bool:
        """Return True when staged SOP sections should become one phased pipeline."""
        if len(sections) < 3:
            return False

        transition_sections = sum(
            1 for section in sections
            if self._count_transition_indicators(section.content) > 0
        )
        procedural_sections = sum(1 for section in sections if section.step_count >= 2)

        return (
            transition_sections >= 3
            and transition_sections / max(1, len(sections)) >= 0.6
            and procedural_sections / max(1, len(sections)) >= 0.7
        )

    def _merge_sections(self, sections: List[WorkflowSection]) -> WorkflowSection:
        """Merge multiple sections into a single continuous pipeline."""
        if not sections:
            return self._create_section("", 0, 0, "Empty")
            
        full_content = []
        for s in sections:
            full_content.append(f"## {s.title}\n{s.content}")
            
        merged_text = "\n\n".join(full_content)
        title = sections[0].title if len(sections) == 1 else f"Pipeline: {sections[0].title} to {sections[-1].title}"
        
        return self._create_section(
            merged_text, 
            sections[0].start_line, 
            sections[-1].end_line, 
            title
        )

    def _auto_detect(self, lines: List[str]) -> List[WorkflowSection]:
        """Cascade: headers → numbered sequence → semantic chunking → single workflow.

        Smart detection: Only try headers if document isn't a single numbered workflow.
        """
        # First, check if this is a single continuous numbered workflow
        numbered_lines = [line for line in lines if re.match(r'^\s*\d+[\.)\:]\s+', line.strip())]
        total_lines = len([line for line in lines if line.strip()])

        sections = self._try_header_detection(lines)
        if sections and len(sections) > 1:
            filtered = self._analyze_and_filter(sections)
            weak_section_split = (
                len(filtered) >= 3
                and sum(1 for section in filtered if section.step_count <= 2) / max(1, len(filtered)) >= 0.6
                and total_lines > 0
                and (len(numbered_lines) / total_lines) >= 0.35
            )
            if weak_section_split:
                numbered_workflow = self._try_numbered_sequence_detection(lines)
                if numbered_workflow:
                    logger.info("Auto mode -> Headers looked fragmented; promoting numbered workflow instead")
                    return [numbered_workflow]
            if self._should_merge_state_sections(filtered):
                logger.info(
                    f"Auto mode -> Headers: {len(filtered)} phased sections, merging into one pipeline"
                )
                return [self._merge_sections(filtered)]

            logger.info(f"Auto mode -> Headers: {len(filtered)} sections")
            return filtered

        # If >60% of lines are numbered steps, it's likely a single workflow
        if total_lines > 0 and (len(numbered_lines) / total_lines) > 0.6:
            logger.info(
                f"Auto mode → High numbered line density ({len(numbered_lines)}/{total_lines}), "
                "treating as single workflow"
            )
            numbered_workflow = self._try_numbered_sequence_detection(lines)
            if numbered_workflow:
                return [numbered_workflow]

        # Prefer explicit section structure before applying any document-wide
        # transition heuristics. This keeps manuals split into legible phases.
        sections = self._try_header_detection(lines)
        if sections and len(sections) > 1:
            filtered = self._analyze_and_filter(sections)
            if self._should_merge_state_sections(filtered):
                logger.info(
                    f"Auto mode -> Headers: {len(filtered)} phased sections, merging into one pipeline"
                )
                return [self._merge_sections(filtered)]

            logger.info(f"Auto mode -> Headers: {len(filtered)} sections")
            return filtered

        # -------------------------------------------------------------
        # Legacy transition shortcut; should be replaced with section-aware merging.
        # -------------------------------------------------------------
        text_lower = "\n".join(lines).lower()
        transition_indicators = [
            "move the ticket to", 
            "move the deal to",
            "move the item to",
            "change status to", 
            "update ticket to",
            "proceed to section"
        ]
        
        # If these phrases appear 2 or more times anywhere in the doc, it's a unified SOP!
        if sum(text_lower.count(phrase) for phrase in transition_indicators) >= 2:
            logger.info("Auto mode -> State transitions detected, treating as unified SOP (legacy)")
            title = lines[0].strip() if lines[0].strip() else "End-to-End Workflow"
            return [self._create_section("\n".join(lines), 0, len(lines), title)]
        # -------------------------------------------------------------

        # Priority 1: Try header-based detection (multi-section documents)
        sections = self._try_header_detection(lines)
        if sections and len(sections) > 1:
            logger.info(f"Auto mode → Headers: {len(sections)} sections")
            return self._analyze_and_filter(sections)

        # Priority 2: Check for numbered sequence workflow (single workflow with steps)
        numbered_workflow = self._try_numbered_sequence_detection(lines)
        if numbered_workflow:
            logger.info("Auto mode → Numbered sequence: 1 continuous workflow")
            return [numbered_workflow]

        # Priority 3: Try semantic chunking
        sections = self._try_semantic_chunking(lines)
        if sections and len(sections) > 1:
            logger.info(f"Auto mode → Semantic: {len(sections)} sections")
            return self._analyze_and_filter(sections)

        # Fallback: single workflow
        logger.info("Auto mode → Fallback: single workflow")
        return [self._create_section("\n".join(lines), 0, len(lines), "Workflow")]

    def _record_sequence_if_valid(
        self,
        current_sequence: List[int],
        sequence_ranges: List[tuple],
    ) -> None:
        if len(current_sequence) >= 3:
            sequence_ranges.append((current_sequence[0], current_sequence[-1]))

    def _is_sequence_context_line(self, line: str, stripped: str) -> bool:
        return bool(
            re.match(r'^[\s\-\*]', line)
            or 'if yes' in stripped.lower()
            or 'if no' in stripped.lower()
        )

    def _build_numbered_sequence_section(
        self,
        lines: List[str],
        start_line: int,
        end_line: int,
    ) -> Optional[WorkflowSection]:
        content_lines = []
        for i in range(len(lines)):
            if i >= start_line and i <= end_line + 5:
                content_lines.append(lines[i])

        step_count = len(
            [line for line in content_lines if re.match(r'^\d+[\.)\:]', line.strip())]
        )
        if step_count < 3:
            return None

        title = "Workflow"
        for line in lines[:start_line]:
            if line.strip() and not line.strip().startswith('#'):
                title = line.strip()[:60]
                break

        section = WorkflowSection(
            id="s0",
            title=title,
            content="\n".join(content_lines).strip(),
            level=1,
            start_line=start_line,
            end_line=min(end_line + 5, len(lines)),
            subsections=[]
        )
        self._analyze(section)
        logger.info(f"Detected numbered sequence: {step_count} steps")
        return section

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
                    self._record_sequence_if_valid(current_sequence, sequence_ranges)
                    current_sequence = [i]
                    last_number = 1
                elif current_sequence:
                    # Gap in sequence, end current
                    self._record_sequence_if_valid(current_sequence, sequence_ranges)
                    current_sequence = []
                    last_number = 0
            elif stripped and current_sequence:
                # Non-numbered line within sequence (could be sub-item, decision branch, etc.)
                # Keep the sequence going if it's indented or starts with dash/bullet
                if self._is_sequence_context_line(line, stripped):
                    continue

        # Save final sequence
        self._record_sequence_if_valid(current_sequence, sequence_ranges)

        # If we found a substantial numbered sequence, treat entire range as one workflow
        if sequence_ranges:
            largest = max(sequence_ranges, key=lambda r: r[1] - r[0])
            start_line, end_line = largest
            return self._build_numbered_sequence_section(lines, start_line, end_line)

        return None

    def _collect_numbered_step_lines(self, lines: List[str]) -> set:
        numbered_step_lines = set()
        for i, line in enumerate(lines):
            if re.match(r'^\d+[\.)\:]\s+', line.strip()):
                numbered_step_lines.add(i)
        return numbered_step_lines

    def _match_header_line(self, line: str, patterns: List[tuple]) -> Optional[Dict[str, Any]]:
        for pat, tag in patterns:
            m = re.match(pat, line, re.IGNORECASE if tag == 'section' else 0)
            if not m:
                continue
            if tag == 'section':
                title = m.group(2).strip() if len(m.groups()) > 1 else m.group(1)
                level = 1
            elif tag == 'caps':
                title = m.group(1)
                level = 1
            else:
                title = m.group(2)
                level = len(m.group(1)) if tag == 'md' else (m.group(1).count('.') + 1 if tag == 'num' else 1)
            return {'level': level, 'title': title.strip()}
        return None

    def _try_header_detection(self, lines: List[str]) -> List[WorkflowSection]:
        """Flexible header detection (any format).

        Skip lines that appear to be part of numbered sequences.
        """
        headers = []
        patterns = [
            (r'^(#{1,3})\s+(.{5,})$', 'md'),
            (r'^(\d+(?:\.\d+)*)\s+([A-Z][A-Za-z\s]{5,})$', 'num'),
            (r'^([A-Z][A-Z\s]{10,}[A-Z])$', 'caps'),
            (r'^(Section\s+\d+)[:\s]+(.{5,})$', 'section'),
        ]

        numbered_step_lines = self._collect_numbered_step_lines(lines)

        for i, line in enumerate(lines):
            s = line.strip()

            if i in numbered_step_lines:
                continue
            if len(s) < 5 or '|' in s:
                continue

            header_match = self._match_header_line(s, patterns)
            if header_match:
                headers.append(
                    {'line': i, 'level': header_match['level'], 'title': header_match['title']}
                )

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

            for keyword in procedure_keywords:
                if stripped.startswith(keyword):
                    if current_start is not None:
                        content = "\n".join(lines[current_start:i]).strip()
                        sections.append(self._create_section(content, current_start, i, current_title))

                    current_start = i
                    current_title = line.strip()[:60]
                    break

        if current_start is not None:
            content = "\n".join(lines[current_start:]).strip()
            sections.append(self._create_section(content, current_start, len(lines), current_title))

        return sections

    def _try_semantic_chunking(self, lines: List[str]) -> List[WorkflowSection]:
        """Chunk by action verb density and topic shifts - but NOT for numbered sequences."""
        # First check if this looks like a numbered sequence
        numbered_lines = [line for line in lines if re.match(r'^\s*\d+[\.)\:]', line.strip())]
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

            module_source = stack[0]['section'] if stack else None

            # Create section
            section = WorkflowSection(
                id=(
                    f"s{len(sections)}"
                    if not stack
                    else f"{stack[-1]['section'].id}_sub{len(stack[-1]['section'].subsections)}"
                ),
                title=h['title'],
                content=content,
                level=h['level'],
                start_line=h['line'],
                end_line=content_end,
                subsections=[],
                module_id=module_source.id if module_source else None,
                module_title=module_source.title if module_source else None,
            )

            # Add to parent or root
            if stack:
                stack[-1]['section'].subsections.append(section)
            else:
                sections.append(section)

            # Push to stack for potential children
            stack.append({'level': h['level'], 'section': section})

        return sections

    def _dedupe_sections(self, sections: List[WorkflowSection]) -> List[WorkflowSection]:
        """Remove duplicate sections that share both title and starting line."""
        seen = set()
        deduped: List[WorkflowSection] = []
        for section in sections:
            key = ((section.title or '').strip().lower(), section.start_line)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(section)
        return deduped

    def _create_section(self, content: str, start: int, end: int, title: str) -> WorkflowSection:
        """Create analyzed section."""
        s = WorkflowSection(
            id=f"s{start}", title=title, content=content,
            level=1, start_line=start, end_line=end, subsections=[]
        )
        self._analyze(s)
        return s

    def _is_actionable_line(self, line: str) -> bool:
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            return False

        if re.match(r'^\s*\*\*\d+\*\*', stripped, re.I):
            return True
        if re.match(r'^\s*\d+[\.)](\s+|$)', stripped):
            return True
        if re.match(r'^\s*Step\s+\d+', stripped, re.I):
            return True
        if re.match(r'^\s*[\-\*â€¢]\s+[A-Z]', stripped):
            return True
        if '->' in stripped:
            return True
        if re.match(r'^(if|when|once|then|otherwise|yes:|no:)', stripped, re.I):
            return True

        first_word = re.split(r'[\s/:()\-]+', stripped.lower())[0]
        return first_word in self.ACTION_VERBS

    def _is_phase_section(self, section: WorkflowSection) -> bool:
        return bool(re.search(r'\b(stage|phase|step)\b', section.title.lower()))

    def _analyze(self, section: WorkflowSection):
        """Analyze section metrics.

        CRITICAL: Only analyze this section's content, NOT subsections.
        Subsections are analyzed separately.
        """
        text = section.content

        # Count steps, including bare imperative lines from SOPs/manuals.
        step_patterns = [
            r'^\s*\*\*\d+\*\*',
            r'^\s*\d+[\.)](\s+|$)',
            r'^\s*Step\s+\d+',
            r'^\s*[\-\*•]\s+[A-Z]',
        ]
        section.step_count = sum(1 for line in text.split('\n')
                                 if any(re.match(p, line.strip(), re.I) for p in step_patterns))
        section.step_count = sum(
            1 for line in text.split('\n')
            if self._is_actionable_line(line)
        )

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
            'index', 'glossary', 'purpose', 'prerequisites',
            'required tools', 'system requirements', 'hardware requirements',
            'supported systems', 'key manufacturers', 'quick reference card',
            'end of training manual'
        ]

        # Check title for reference keywords
        if any(keyword in title for keyword in reference_keywords):
            return True

        # Check for "See Section X" patterns (common in overview sections)
        if len(re.findall(r'see section \d+', text)) >= 2:
            return True

        # Keep concise actionable sections, even when the body is short.
        if section.step_count >= 2 and section.confidence > 0.25:
            return False
        if (
            self._is_phase_section(section)
            and section.step_count >= 1
        ):
            return False

        # Check if content is very short (likely just a header with no workflow)
        lines = [line.strip() for line in text.split('\n') if line.strip()]
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
            workflow_subsections = [
                sub
                for sub in section.subsections
                if (
                    (sub.step_count >= 3 and sub.confidence > 0.25)
                    or (
                        self._is_phase_section(sub)
                        and sub.step_count >= 1
                    )
                )
            ]

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
                if (
                    (section.step_count >= 2 and section.confidence > 0.25)
                    or (
                        self._is_phase_section(section)
                        and section.step_count >= 1
                    )
                ):
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
