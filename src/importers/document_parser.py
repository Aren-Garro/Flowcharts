"""Multi-format document parser for extracting text from various file types."""

import logging
import re
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)


class DocumentParser:
    """Parse various document formats to extract raw text."""

    def __init__(self):
        self.supported_formats = [".txt", ".md", ".pdf", ".docx", ".doc"]
        self._check_dependencies()

    def _check_dependencies(self):
        self.has_pdf = False
        self.has_docx = False

        try:
            __import__("PyPDF2")
            self.has_pdf = True
            logger.info("PDF support enabled (PyPDF2)")
        except ImportError:
            try:
                __import__("pdfplumber")
                self.has_pdf = True
                logger.info("PDF support enabled (pdfplumber)")
            except ImportError:
                logger.warning("PDF support not available. Install PyPDF2 or pdfplumber.")

        try:
            __import__("docx")
            self.has_docx = True
            logger.info("DOCX support enabled (python-docx)")
        except ImportError:
            logger.warning("DOCX support not available. Install python-docx.")

    def parse(self, file_path: Path, encoding: str = "utf-8") -> Dict[str, Any]:
        file_path = Path(file_path)

        if not file_path.exists():
            return {"text": "", "metadata": {}, "format": None, "success": False,
                    "error": f"File not found: {file_path}"}

        suffix = file_path.suffix.lower()
        if suffix not in self.supported_formats:
            return {"text": "", "metadata": {}, "format": suffix, "success": False,
                    "error": f"Unsupported format: {suffix}"}

        try:
            if suffix in [".txt", ".md"]:
                return self._parse_text(file_path, encoding)
            elif suffix == ".pdf":
                return self._parse_pdf(file_path)
            elif suffix in [".docx", ".doc"]:
                return self._parse_docx(file_path)
            else:
                return {"text": "", "metadata": {}, "format": suffix, "success": False,
                        "error": f"Format not yet implemented: {suffix}"}
        except Exception as e:
            logger.error(f"Error parsing {file_path}: {e}")
            return {"text": "", "metadata": {}, "format": suffix, "success": False,
                    "error": str(e)}

    def _parse_text(self, file_path: Path, encoding: str) -> Dict[str, Any]:
        try:
            with open(file_path, "r", encoding=encoding) as f:
                text = f.read()
            return {"text": text, "metadata": {"filename": file_path.name,
                    "size": file_path.stat().st_size}, "format": file_path.suffix, "success": True}
        except UnicodeDecodeError:
            with open(file_path, "r", encoding="latin-1") as f:
                text = f.read()
            return {"text": text, "metadata": {"filename": file_path.name,
                    "size": file_path.stat().st_size, "encoding": "latin-1"},
                    "format": file_path.suffix, "success": True}

    def _parse_pdf(self, file_path: Path) -> Dict[str, Any]:
        if not self.has_pdf:
            return {"text": "", "metadata": {}, "format": ".pdf", "success": False,
                    "error": "PDF support not available. Install: pip install PyPDF2 pdfplumber"}
        try:
            __import__("pdfplumber")
            return self._parse_pdf_pdfplumber(file_path)
        except ImportError:
            pass
        try:
            __import__("PyPDF2")
            return self._parse_pdf_pypdf2(file_path)
        except ImportError:
            return {"text": "", "metadata": {}, "format": ".pdf", "success": False,
                    "error": "No PDF library available"}

    def _parse_pdf_pdfplumber(self, file_path: Path) -> Dict[str, Any]:
        import pdfplumber
        text_parts = []
        metadata = {}
        with pdfplumber.open(file_path) as pdf:
            metadata["pages"] = len(pdf.pages)
            metadata["filename"] = file_path.name
            if pdf.metadata:
                metadata["title"] = pdf.metadata.get("Title", "")
                metadata["author"] = pdf.metadata.get("Author", "")
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return {"text": "\n\n".join(text_parts), "metadata": metadata,
                "format": ".pdf", "success": True}

    def _parse_pdf_pypdf2(self, file_path: Path) -> Dict[str, Any]:
        import PyPDF2
        text_parts = []
        metadata = {}
        with open(file_path, "rb") as f:
            pdf_reader = PyPDF2.PdfReader(f)
            metadata["pages"] = len(pdf_reader.pages)
            metadata["filename"] = file_path.name
            if pdf_reader.metadata:
                metadata["title"] = pdf_reader.metadata.get("/Title", "")
                metadata["author"] = pdf_reader.metadata.get("/Author", "")
            for page in pdf_reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return {"text": "\n\n".join(text_parts), "metadata": metadata,
                "format": ".pdf", "success": True}

    def _get_heading_level(self, paragraph) -> int:
        """Detect heading level from paragraph style.

        Returns 0 for body text, 1-3 for heading levels.
        """
        style_name = (paragraph.style.name or '').lower()

        # Explicit heading styles
        if 'heading 1' in style_name or style_name == 'title':
            return 1
        if 'heading 2' in style_name or style_name == 'subtitle':
            return 2
        if 'heading 3' in style_name or 'heading 4' in style_name:
            return 3

        # Check for TOC styles (not headings)
        if 'toc' in style_name:
            return 0

        # Detect bold-only short paragraphs as implicit headings
        text = paragraph.text.strip()
        if text and len(text) < 80 and len(text) > 3:
            all_bold = all(
                run.bold for run in paragraph.runs
                if run.text.strip()
            ) if paragraph.runs else False
            if all_bold and not re.match(r'^\d+\.?\s', text):
                # Bold, short, and not a numbered step → likely a heading
                return 2

        return 0

    def _format_table_row(self, cells_text, row_idx: int) -> str:
        """Format a table row, detecting Step/Action tables."""
        cells = [c.strip() for c in cells_text]

        # Skip empty rows
        if not any(cells):
            return ''

        # Skip header rows (Step | Action, etc.)
        if cells[0].lower() in ('step', '#', 'no', 'no.', 'number'):
            return ''

        # If first cell is a number, format as a numbered step
        if cells[0].isdigit() and len(cells) >= 2:
            step_num = cells[0]
            action = ' '.join(cells[1:]).strip()
            if action:
                return f"{step_num}. {action}"

        # Otherwise join with pipes
        return ' | '.join(cells)

    def _parse_docx(self, file_path: Path) -> Dict[str, Any]:
        """Parse DOCX preserving heading hierarchy and table structure."""
        if not self.has_docx:
            return {"text": "", "metadata": {}, "format": ".docx", "success": False,
                    "error": "DOCX support not available. Install: pip install python-docx"}

        import docx

        try:
            doc = docx.Document(file_path)
            text_parts = []

            # Build an ordered list of document elements (paragraphs + tables)
            # python-docx body.iter_inner_content() gives us order
            try:
                elements = list(doc.element.body)
            except Exception:
                elements = None

            if elements is not None:
                # Process in document order
                para_idx = 0
                table_idx = 0

                from docx.oxml.ns import qn

                for elem in elements:
                    if elem.tag == qn('w:p'):
                        # It's a paragraph
                        if para_idx < len(doc.paragraphs):
                            para = doc.paragraphs[para_idx]
                            para_idx += 1

                            text = para.text.strip()
                            if not text:
                                continue

                            heading_level = self._get_heading_level(para)
                            if heading_level > 0:
                                prefix = '#' * heading_level
                                text_parts.append(f"\n{prefix} {text}\n")
                            else:
                                text_parts.append(text)
                        else:
                            para_idx += 1

                    elif elem.tag == qn('w:tbl'):
                        # It's a table
                        if table_idx < len(doc.tables):
                            table = doc.tables[table_idx]
                            table_idx += 1

                            text_parts.append('')  # blank line before table
                            for row_i, row in enumerate(table.rows):
                                cells = [cell.text for cell in row.cells]
                                formatted = self._format_table_row(cells, row_i)
                                if formatted:
                                    text_parts.append(formatted)
                            text_parts.append('')  # blank line after table
            else:
                # Fallback: process paragraphs then tables (loses ordering)
                for para in doc.paragraphs:
                    text = para.text.strip()
                    if not text:
                        continue
                    heading_level = self._get_heading_level(para)
                    if heading_level > 0:
                        prefix = '#' * heading_level
                        text_parts.append(f"\n{prefix} {text}\n")
                    else:
                        text_parts.append(text)

                for table in doc.tables:
                    text_parts.append('')
                    for row_i, row in enumerate(table.rows):
                        cells = [cell.text for cell in row.cells]
                        formatted = self._format_table_row(cells, row_i)
                        if formatted:
                            text_parts.append(formatted)
                    text_parts.append('')

            text = "\n".join(text_parts)

            # Clean up excessive blank lines
            text = re.sub(r'\n{4,}', '\n\n\n', text)

            metadata = {
                "filename": file_path.name,
                "paragraphs": len(doc.paragraphs),
                "tables": len(doc.tables),
            }
            if hasattr(doc, "core_properties"):
                core_props = doc.core_properties
                if core_props.title:
                    metadata["title"] = core_props.title
                if core_props.author:
                    metadata["author"] = core_props.author

            return {"text": text, "metadata": metadata, "format": ".docx", "success": True}

        except Exception as e:
            return {"text": "", "metadata": {}, "format": ".docx", "success": False,
                    "error": f"Error parsing DOCX: {str(e)}"}

    def parse_clipboard(self) -> Dict[str, Any]:
        try:
            import pyperclip
            text = pyperclip.paste()
            return {"text": text, "metadata": {"source": "clipboard"},
                    "format": "clipboard", "success": True}
        except ImportError:
            return {"text": "", "metadata": {}, "format": "clipboard", "success": False,
                    "error": "Clipboard support not available. Install: pip install pyperclip"}
        except Exception as e:
            return {"text": "", "metadata": {}, "format": "clipboard", "success": False,
                    "error": str(e)}

    def get_supported_formats(self) -> list:
        formats = [".txt", ".md"]
        if self.has_pdf:
            formats.append(".pdf")
        if self.has_docx:
            formats.extend([".docx", ".doc"])
        return formats
