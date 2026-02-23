"""NLP-driven workflow detection for any document format."""

import re
from typing import List, Dict, Any
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
    """Multi-strategy workflow detection using semantic analysis."""
    
    ACTION_VERBS = [
        'click', 'select', 'choose', 'enter', 'type', 'press', 'open', 'close',
        'navigate', 'go', 'visit', 'access', 'launch', 'start', 'run', 'execute',
        'install', 'download', 'upload', 'save', 'delete', 'remove', 'add',
        'create', 'update', 'modify', 'change', 'edit', 'configure', 'set',
        'enable', 'disable', 'activate', 'connect', 'restart', 'reboot',
        'verify', 'check', 'confirm', 'ensure', 'wait', 'review', 'test',
        'insert', 'eject', 'mount', 'boot', 'shutdown'
    ]
    
    def __init__(self):
        self.action_pattern = re.compile(r'\b(' + '|'.join(self.ACTION_VERBS) + r')\b', re.IGNORECASE)
        
    def detect_workflows(self, text: str) -> List[WorkflowSection]:
        """Cascade: headers → semantic chunking → single workflow."""
        lines = text.split('\n')
        
        # Try header-based
        sections = self._try_header_detection(lines)
        if sections and len(sections) > 1:
            logger.info(f"Header strategy: {len(sections)} sections")
            return self._analyze_and_filter(sections)
        
        # Try semantic chunking
        sections = self._try_semantic_chunking(lines)
        if sections and len(sections) > 1:
            logger.info(f"Semantic strategy: {len(sections)} sections")
            return self._analyze_and_filter(sections)
        
        # Fallback: single workflow
        logger.info("Single workflow mode")
        return [self._create_section("\n".join(lines), 0, len(lines), "Workflow")]
    
    def _try_header_detection(self, lines: List[str]) -> List[WorkflowSection]:
        """Flexible header detection (any format)."""
        headers = []
        patterns = [
            (r'^(#{1,3})\s+(.{5,})$', 'md'),
            (r'^(\d+(?:\.\d+)*)\.?\s+([A-Z].{5,})$', 'num'),
            (r'^([A-Z][A-Z\s]{10,}[A-Z])$', 'caps'),
        ]
        
        for i, line in enumerate(lines):
            s = line.strip()
            if len(s) < 5 or '|' in s or '→' in s:
                continue
            
            for pat, tag in patterns:
                m = re.match(pat, s)
                if m:
                    title = m.group(2) if tag != 'caps' else m.group(1)
                    level = len(m.group(1)) if tag == 'md' else (m.group(1).count('.') + 1 if tag == 'num' else 1)
                    headers.append({'line': i, 'level': level, 'title': title.strip()})
                    break
            
            # Underlined headers
            if i + 1 < len(lines) and re.match(r'^[=\-]{5,}$', lines[i + 1].strip()):
                headers.append({'line': i, 'level': 1, 'title': s})
        
        return self._build_from_headers(headers, lines) if headers else []
    
    def _try_semantic_chunking(self, lines: List[str]) -> List[WorkflowSection]:
        """Chunk by action verb density and topic shifts."""
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
        """Build sections from headers."""
        sections = []
        parent = None
        
        for i, h in enumerate(headers):
            end = headers[i + 1]['line'] if i + 1 < len(headers) else len(lines)
            content = "\n".join(lines[h['line'] + 1:end]).strip()
            
            if h['level'] == 1:
                if parent:
                    sections.append(parent)
                parent = WorkflowSection(
                    id=f"s{len(sections)}", title=h['title'], content=content,
                    level=1, start_line=h['line'], end_line=end, subsections=[]
                )
            elif parent:
                sub = WorkflowSection(
                    id=f"{parent.id}_sub{len(parent.subsections)}", title=h['title'],
                    content=content, level=h['level'], start_line=h['line'],
                    end_line=end, subsections=[]
                )
                parent.subsections.append(sub)
                parent.content += "\n\n" + content
        
        if parent:
            sections.append(parent)
        
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
        """Analyze section metrics."""
        text = section.content
        for sub in section.subsections:
            text += "\n" + sub.content
        
        # Count steps
        step_patterns = [
            r'^\s*\*\*\d+\*\*',
            r'^\s*\d+[\.\)]\s+',
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
    
    def _analyze_and_filter(self, sections: List[WorkflowSection]) -> List[WorkflowSection]:
        """Analyze and filter sections."""
        for s in sections:
            self._analyze(s)
        
        filtered = [s for s in sections if s.confidence > 0.2 and len(s.content) > 50]
        
        for s in filtered:
            logger.info(f"  {s.title[:40]}: {s.step_count} steps, conf={s.confidence:.2f}")
        
        return filtered if filtered else [max(sections, key=lambda x: x.confidence)] if sections else []
    
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
