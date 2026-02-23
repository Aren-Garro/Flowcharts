"""Multi-format document parser for extracting text from various file types."""

import io
import re
from pathlib import Path
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class DocumentParser:
    """Parse various document formats to extract raw text."""
    
    def __init__(self):
        """Initialize the document parser."""
        self.supported_formats = [".txt", ".md", ".pdf", ".docx", ".doc"]
        self._check_dependencies()
    
    def _check_dependencies(self):
        """Check which optional dependencies are available."""
        self.has_pdf = False
        self.has_docx = False
        
        # Check for PDF support
        try:
            import PyPDF2
            self.has_pdf = True
            logger.info("PDF support enabled (PyPDF2)")
        except ImportError:
            try:
                import pdfplumber
                self.has_pdf = True
                logger.info("PDF support enabled (pdfplumber)")
            except ImportError:
                logger.warning("PDF support not available. Install PyPDF2 or pdfplumber.")
        
        # Check for DOCX support
        try:
            import docx
            self.has_docx = True
            logger.info("DOCX support enabled (python-docx)")
        except ImportError:
            logger.warning("DOCX support not available. Install python-docx.")
    
    def parse(self, file_path: Path, encoding: str = "utf-8") -> Dict[str, Any]:
        """Parse document and extract text.
        
        Args:
            file_path: Path to the document
            encoding: Text encoding (for text files)
        
        Returns:
            Dictionary with:
                - text: Extracted text content
                - metadata: Document metadata
                - format: File format
                - success: Whether parsing succeeded
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            return {
                "text": "",
                "metadata": {},
                "format": None,
                "success": False,
                "error": f"File not found: {file_path}"
            }
        
        suffix = file_path.suffix.lower()
        
        if suffix not in self.supported_formats:
            return {
                "text": "",
                "metadata": {},
                "format": suffix,
                "success": False,
                "error": f"Unsupported format: {suffix}"
            }
        
        try:
            if suffix in [".txt", ".md"]:
                return self._parse_text(file_path, encoding)
            elif suffix == ".pdf":
                return self._parse_pdf(file_path)
            elif suffix in [".docx", ".doc"]:
                return self._parse_docx(file_path)
            else:
                return {
                    "text": "",
                    "metadata": {},
                    "format": suffix,
                    "success": False,
                    "error": f"Format not yet implemented: {suffix}"
                }
        except Exception as e:
            logger.error(f"Error parsing {file_path}: {e}")
            return {
                "text": "",
                "metadata": {},
                "format": suffix,
                "success": False,
                "error": str(e)
            }
    
    def _parse_text(self, file_path: Path, encoding: str) -> Dict[str, Any]:
        """Parse plain text or markdown files."""
        try:
            with open(file_path, "r", encoding=encoding) as f:
                text = f.read()
            
            return {
                "text": text,
                "metadata": {
                    "filename": file_path.name,
                    "size": file_path.stat().st_size,
                },
                "format": file_path.suffix,
                "success": True
            }
        except UnicodeDecodeError:
            # Try different encoding
            with open(file_path, "r", encoding="latin-1") as f:
                text = f.read()
            
            return {
                "text": text,
                "metadata": {
                    "filename": file_path.name,
                    "size": file_path.stat().st_size,
                    "encoding": "latin-1"
                },
                "format": file_path.suffix,
                "success": True
            }
    
    def _parse_pdf(self, file_path: Path) -> Dict[str, Any]:
        """Parse PDF files using available library."""
        if not self.has_pdf:
            return {
                "text": "",
                "metadata": {},
                "format": ".pdf",
                "success": False,
                "error": "PDF support not available. Install: pip install PyPDF2 pdfplumber"
            }
        
        # Try pdfplumber first (better text extraction)
        try:
            import pdfplumber
            return self._parse_pdf_pdfplumber(file_path)
        except ImportError:
            pass
        
        # Fallback to PyPDF2
        try:
            import PyPDF2
            return self._parse_pdf_pypdf2(file_path)
        except ImportError:
            return {
                "text": "",
                "metadata": {},
                "format": ".pdf",
                "success": False,
                "error": "No PDF library available"
            }
    
    def _parse_pdf_pdfplumber(self, file_path: Path) -> Dict[str, Any]:
        """Parse PDF using pdfplumber."""
        import pdfplumber
        
        text_parts = []
        metadata = {}
        
        with pdfplumber.open(file_path) as pdf:
            metadata["pages"] = len(pdf.pages)
            metadata["filename"] = file_path.name
            
            # Extract metadata if available
            if pdf.metadata:
                metadata["title"] = pdf.metadata.get("Title", "")
                metadata["author"] = pdf.metadata.get("Author", "")
            
            # Extract text from all pages
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        
        text = "\n\n".join(text_parts)
        
        return {
            "text": text,
            "metadata": metadata,
            "format": ".pdf",
            "success": True
        }
    
    def _parse_pdf_pypdf2(self, file_path: Path) -> Dict[str, Any]:
        """Parse PDF using PyPDF2."""
        import PyPDF2
        
        text_parts = []
        metadata = {}
        
        with open(file_path, "rb") as f:
            pdf_reader = PyPDF2.PdfReader(f)
            
            metadata["pages"] = len(pdf_reader.pages)
            metadata["filename"] = file_path.name
            
            # Extract metadata
            if pdf_reader.metadata:
                metadata["title"] = pdf_reader.metadata.get("/Title", "")
                metadata["author"] = pdf_reader.metadata.get("/Author", "")
            
            # Extract text from all pages
            for page in pdf_reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        
        text = "\n\n".join(text_parts)
        
        return {
            "text": text,
            "metadata": metadata,
            "format": ".pdf",
            "success": True
        }
    
    def _parse_docx(self, file_path: Path) -> Dict[str, Any]:
        """Parse DOCX files using python-docx."""
        if not self.has_docx:
            return {
                "text": "",
                "metadata": {},
                "format": ".docx",
                "success": False,
                "error": "DOCX support not available. Install: pip install python-docx"
            }
        
        import docx
        
        try:
            doc = docx.Document(file_path)
            
            # Extract text from paragraphs
            text_parts = []
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():
                    text_parts.append(paragraph.text)
            
            # Extract text from tables
            for table in doc.tables:
                for row in table.rows:
                    row_text = " | ".join(cell.text for cell in row.cells)
                    if row_text.strip():
                        text_parts.append(row_text)
            
            text = "\n".join(text_parts)
            
            # Extract metadata
            metadata = {
                "filename": file_path.name,
                "paragraphs": len(doc.paragraphs),
                "tables": len(doc.tables),
            }
            
            # Core properties if available
            if hasattr(doc, "core_properties"):
                core_props = doc.core_properties
                if core_props.title:
                    metadata["title"] = core_props.title
                if core_props.author:
                    metadata["author"] = core_props.author
            
            return {
                "text": text,
                "metadata": metadata,
                "format": ".docx",
                "success": True
            }
        except Exception as e:
            return {
                "text": "",
                "metadata": {},
                "format": ".docx",
                "success": False,
                "error": f"Error parsing DOCX: {str(e)}"
            }
    
    def parse_clipboard(self) -> Dict[str, Any]:
        """Parse text from clipboard."""
        try:
            import pyperclip
            text = pyperclip.paste()
            
            return {
                "text": text,
                "metadata": {"source": "clipboard"},
                "format": "clipboard",
                "success": True
            }
        except ImportError:
            return {
                "text": "",
                "metadata": {},
                "format": "clipboard",
                "success": False,
                "error": "Clipboard support not available. Install: pip install pyperclip"
            }
        except Exception as e:
            return {
                "text": "",
                "metadata": {},
                "format": "clipboard",
                "success": False,
                "error": str(e)
            }
    
    def get_supported_formats(self) -> list:
        """Get list of currently supported formats based on available dependencies."""
        formats = [".txt", ".md"]
        
        if self.has_pdf:
            formats.append(".pdf")
        
        if self.has_docx:
            formats.extend([".docx", ".doc"])
        
        return formats
