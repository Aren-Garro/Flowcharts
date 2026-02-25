"""Multi-workflow detection and splitting.

Detects document structure and splits into multiple workflows based on:
- Sections (top-level headings)
- Subsections (nested headings)
- Procedures (numbered sequences)
- Auto-detection (heuristic analysis)
"""

import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass


@dataclass
class WorkflowSection:
    """Represents a detected workflow section."""
    title: str
    content: str
    level: int  # Heading level (1=section, 2=subsection, etc.)
    start_line: int
    end_line: int
    section_type: str  # 'section', 'subsection', 'procedure'


class WorkflowDetector:
    """Detect and split documents into multiple workflows."""

    SECTION_PATTERNS = [
        re.compile(r'^#{1,2}\s+(.+)$', re.MULTILINE),  # Markdown headers
        re.compile(r'^([A-Z][A-Za-z\s]+)\s*$(?=\n[=-]+)', re.MULTILINE),  # Underlined headers
        re.compile(r'^([\dA-Z]+\.\s+[A-Z][^\n]+)$', re.MULTILINE),  # Numbered sections
    ]

    PROCEDURE_PATTERNS = [
        re.compile(r'^(Procedure|Process|Workflow)\s*[:\-]?\s*(.+)?$', re.IGNORECASE | re.MULTILINE),
        re.compile(r'^(Step-by-Step|Instructions|Setup)\s*[:\-]?\s*(.+)?$', re.IGNORECASE | re.MULTILINE),
    ]

    def __init__(self, split_mode: str = 'auto'):
        """
        Args:
            split_mode: 'auto', 'section', 'subsection', 'procedure', or 'none'
        """
        self.split_mode = split_mode

    def detect_workflows(self, text: str) -> List[WorkflowSection]:
        """Detect multiple workflows in document text."""
        if self.split_mode == 'none':
            return [WorkflowSection(
                title='Workflow',
                content=text,
                level=0,
                start_line=0,
                end_line=len(text.split('\n')),
                section_type='document'
            )]

        if self.split_mode == 'auto':
            return self._auto_detect(text)
        elif self.split_mode == 'section':
            return self._split_by_sections(text, max_level=1)
        elif self.split_mode == 'subsection':
            return self._split_by_sections(text, max_level=2)
        elif self.split_mode == 'procedure':
            return self._split_by_procedures(text)
        else:
            raise ValueError(f"Invalid split_mode: {self.split_mode}")

    def _auto_detect(self, text: str) -> List[WorkflowSection]:
        """Heuristically detect workflow boundaries."""
        # Try procedures first
        procedures = self._split_by_procedures(text)
        if len(procedures) >= 3:  # Multiple clear procedures
            return procedures

        # Try subsections
        subsections = self._split_by_sections(text, max_level=2)
        if len(subsections) >= 5:  # Many subsections
            return subsections

        # Try sections
        sections = self._split_by_sections(text, max_level=1)
        if len(sections) >= 2:  # At least 2 sections
            return sections

        # Fallback: single workflow
        return [WorkflowSection(
            title='Workflow',
            content=text,
            level=0,
            start_line=0,
            end_line=len(text.split('\n')),
            section_type='document'
        )]

    def _split_by_sections(self, text: str, max_level: int = 2) -> List[WorkflowSection]:
        """Split by markdown/heading sections."""
        lines = text.split('\n')
        sections = []
        current_section = None
        current_content = []
        current_start = 0

        for i, line in enumerate(lines):
            # Check for section headers
            header_match = None
            level = 0

            # Markdown headers
            md_match = re.match(r'^(#{1,6})\s+(.+)$', line)
            if md_match:
                level = len(md_match.group(1))
                title = md_match.group(2)
                if level <= max_level:
                    header_match = title

            # Numbered sections like "1. Setup"
            num_match = re.match(r'^([\d.]+)\s+([A-Z][^\n]+)$', line)
            if num_match and not header_match:
                level = 1
                title = f"{num_match.group(1)} {num_match.group(2)}"
                header_match = title

            if header_match and level <= max_level:
                # Save previous section
                if current_section:
                    sections.append(WorkflowSection(
                        title=current_section,
                        content='\n'.join(current_content),
                        level=level,
                        start_line=current_start,
                        end_line=i,
                        section_type='subsection' if level > 1 else 'section'
                    ))

                # Start new section
                current_section = header_match
                current_content = []
                current_start = i + 1
            else:
                current_content.append(line)

        # Save final section
        if current_section and current_content:
            sections.append(WorkflowSection(
                title=current_section,
                content='\n'.join(current_content),
                level=1,
                start_line=current_start,
                end_line=len(lines),
                section_type='section'
            ))

        return sections if sections else [WorkflowSection(
            title='Workflow',
            content=text,
            level=0,
            start_line=0,
            end_line=len(lines),
            section_type='document'
        )]

    def _split_by_procedures(self, text: str) -> List[WorkflowSection]:
        """Split by explicit procedure markers."""
        lines = text.split('\n')
        procedures = []
        current_proc = None
        current_content = []
        current_start = 0

        for i, line in enumerate(lines):
            # Check for procedure headers
            for pattern in self.PROCEDURE_PATTERNS:
                match = pattern.match(line)
                if match:
                    # Save previous procedure
                    if current_proc:
                        procedures.append(WorkflowSection(
                            title=current_proc,
                            content='\n'.join(current_content),
                            level=1,
                            start_line=current_start,
                            end_line=i,
                            section_type='procedure'
                        ))

                    # Start new procedure
                    title = match.group(2) if match.lastindex >= 2 and match.group(2) else match.group(1)
                    current_proc = title.strip()
                    current_content = []
                    current_start = i + 1
                    break
            else:
                current_content.append(line)

        # Save final procedure
        if current_proc and current_content:
            procedures.append(WorkflowSection(
                title=current_proc,
                content='\n'.join(current_content),
                level=1,
                start_line=current_start,
                end_line=len(lines),
                section_type='procedure'
            ))

        return procedures if procedures else []

    def estimate_workflow_count(self, text: str) -> Dict[str, int]:
        """Estimate workflow counts for each split mode."""
        return {
            'none': 1,
            'section': len(self._split_by_sections(text, max_level=1)),
            'subsection': len(self._split_by_sections(text, max_level=2)),
            'procedure': len(self._split_by_procedures(text)),
            'auto': len(self._auto_detect(text))
        }
