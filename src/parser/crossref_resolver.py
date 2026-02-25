"""Cross-reference resolver for multi-workflow documents.

Resolves "See Section X" and "refer to procedure Y" references
between workflows detected in the same document.

Enhancement 4: Maps section references to workflow IDs for
navigation and link generation.
"""

import re
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class CrossReference:
    """A resolved cross-reference between workflows."""
    source_workflow_id: str
    target_workflow_id: Optional[str]
    source_text: str
    target_section: str
    resolved: bool = False


class CrossReferenceResolver:
    """Resolve cross-references between workflows in multi-workflow documents."""

    CROSSREF_PATTERNS = [
        re.compile(r'(?:see|refer\s+to)\s+section\s+(\d+(?:\.\d+)?)', re.IGNORECASE),
        re.compile(r'(?:see|refer\s+to)\s+(?:step|procedure)\s+(\d+(?:\.\d+)?)', re.IGNORECASE),
        re.compile(r'(?:as\s+described\s+in|per|follow)\s+section\s+(\d+(?:\.\d+)?)', re.IGNORECASE),
        re.compile(r'(?:detailed\s+(?:in|steps?\s+in))\s+section\s+(\d+(?:\.\d+)?)', re.IGNORECASE),
    ]

    def __init__(self, workflows=None):
        self.section_map: Dict[str, str] = {}
        self.references: List[CrossReference] = []
        if workflows:
            self.build_section_map(workflows)

    def build_section_map(self, workflows) -> Dict[str, str]:
        """Map section identifiers to workflow IDs.
        
        Handles:
        - "Section 7: Network Configuration" -> {"7": workflow_id}
        - "7.1 Adapter Settings" -> {"7.1": workflow_id}
        - "Sierra Wave Setup" -> {"sierra wave setup": workflow_id}
        """
        self.section_map = {}

        for wf in workflows:
            match = re.search(r'(?:section\s+)?(\d+(?:\.\d+)*)', wf.title, re.IGNORECASE)
            if match:
                self.section_map[match.group(1)] = wf.id

            clean_title = re.sub(
                r'^(?:section\s+)?\d+(?:\.\d+)*[:\.\s]*', '', wf.title, flags=re.IGNORECASE
            ).strip().lower()
            if clean_title:
                self.section_map[clean_title] = wf.id

            if hasattr(wf, 'subsections'):
                for sub in wf.subsections:
                    sub_match = re.search(r'(\d+\.\d+)', sub.title)
                    if sub_match:
                        self.section_map[sub_match.group(1)] = sub.id
                    sub_clean = re.sub(
                        r'^(?:section\s+)?\d+(?:\.\d+)*[:\.\s]*', '', sub.title, flags=re.IGNORECASE
                    ).strip().lower()
                    if sub_clean:
                        self.section_map[sub_clean] = sub.id

        return self.section_map

    def resolve(self, text: str, source_workflow_id: str = '') -> Optional[str]:
        """Find the target workflow ID for a cross-reference in text."""
        for pattern in self.CROSSREF_PATTERNS:
            match = pattern.search(text)
            if match:
                section_ref = match.group(1)
                target_id = self.section_map.get(section_ref)

                self.references.append(CrossReference(
                    source_workflow_id=source_workflow_id,
                    target_workflow_id=target_id,
                    source_text=text,
                    target_section=section_ref,
                    resolved=target_id is not None,
                ))

                return target_id

        return None

    def resolve_all_in_text(self, text: str, source_workflow_id: str = '') -> List[Tuple[str, str]]:
        """Find all cross-references in text."""
        results = []
        for pattern in self.CROSSREF_PATTERNS:
            for match in pattern.finditer(text):
                section_ref = match.group(1)
                target_id = self.section_map.get(section_ref)
                if target_id:
                    results.append((section_ref, target_id))
        return results

    def get_unresolved(self) -> List[CrossReference]:
        """Return all unresolved cross-references."""
        return [ref for ref in self.references if not ref.resolved]

    def get_resolution_summary(self) -> Dict:
        """Summary of cross-reference resolution."""
        total = len(self.references)
        resolved = sum(1 for r in self.references if r.resolved)
        return {
            'total_references': total,
            'resolved': resolved,
            'unresolved': total - resolved,
            'section_map_size': len(self.section_map),
            'unresolved_refs': [
                {'text': r.source_text[:80], 'target': r.target_section}
                for r in self.get_unresolved()
            ],
        }
