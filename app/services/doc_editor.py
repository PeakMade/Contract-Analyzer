"""
Document editor service for appending suggested standards to DOCX files.
Detects existing styles and applies them to new content.
"""

from pathlib import Path
from typing import List, Dict, Optional
import tempfile
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_BREAK


class StyleDetector:
    """Detects heading and body styles used for standards in a document."""
    
    def __init__(self, doc: Document, known_standards: List[str]):
        """
        Args:
            doc: python-docx Document object
            known_standards: List of standard names to search for (e.g., ["Payment Terms", "Termination"])
        """
        self.doc = doc
        self.known_standards = known_standards
        self._heading_style = None
        self._body_style = None
    
    def detect_heading_style(self) -> str:
        """
        Scan document paragraphs to find the style used for standard headings.
        
        Returns:
            Style name (e.g., 'Heading 2') or 'Heading 2' as fallback
        """
        if self._heading_style:
            return self._heading_style
        
        for para in self.doc.paragraphs:
            text = para.text.strip()
            # Check if paragraph text matches any known standard
            for standard in self.known_standards:
                if standard.lower() in text.lower():
                    # Found a match - use this paragraph's style
                    style_name = para.style.name if para.style else 'Heading 2'
                    self._heading_style = style_name
                    return style_name
        
        # No match found, use default
        self._heading_style = 'Heading 2'
        return self._heading_style
    
    def detect_body_style(self) -> str:
        """
        Scan document to find the body style used after standard headings.
        
        Returns:
            Style name (e.g., 'Normal', 'Body Text') or 'Normal' as fallback
        """
        if self._body_style:
            return self._body_style
        
        # Find a standard heading, then get the style of the next paragraph
        for i, para in enumerate(self.doc.paragraphs):
            text = para.text.strip()
            for standard in self.known_standards:
                if standard.lower() in text.lower():
                    # Found standard - check next paragraph
                    if i + 1 < len(self.doc.paragraphs):
                        next_para = self.doc.paragraphs[i + 1]
                        style_name = next_para.style.name if next_para.style else 'Normal'
                        self._body_style = style_name
                        return style_name
        
        # No match found, use default
        self._body_style = 'Normal'
        return self._body_style


def append_suggested_standards(
    original_docx_path: Path,
    items: List[Dict[str, str]],
    known_standards: Optional[List[str]] = None
) -> Path:
    """
    Append suggested standards to a DOCX document with matched styling.
    
    Args:
        original_docx_path: Path to original DOCX file
        items: List of dicts with keys 'standard' (heading) and 'suggestion' (body text)
        known_standards: Optional list of standard names for style detection
    
    Returns:
        Path to temporary edited DOCX file
    
    Raises:
        FileNotFoundError: If original_docx_path doesn't exist
        ValueError: If items is empty or malformed
    """
    if not original_docx_path.exists():
        raise FileNotFoundError(f"Original document not found: {original_docx_path}")
    
    if not items:
        raise ValueError("No items provided to append")
    
    # Validate items structure
    for item in items:
        if 'standard' not in item or 'suggestion' not in item:
            raise ValueError("Each item must have 'standard' and 'suggestion' keys")
    
    # Load document
    doc = Document(str(original_docx_path))
    
    # Detect styles if we have known standards
    if known_standards is None:
        known_standards = [item['standard'] for item in items]
    
    detector = StyleDetector(doc, known_standards)
    heading_style = detector.detect_heading_style()
    body_style = detector.detect_body_style()
    
    # Add page break to start appendix on new page
    if doc.paragraphs:
        last_para = doc.paragraphs[-1]
        run = last_para.add_run()
        run.add_break(WD_BREAK.PAGE)
    
    # Add appendix heading
    appendix_heading = doc.add_heading('Appendix — Suggested Standards', level=1)
    
    # Add each suggested standard
    for item in items:
        # Add standard heading
        standard_heading = doc.add_paragraph(item['standard'])
        try:
            standard_heading.style = heading_style
        except KeyError:
            # Style doesn't exist, use Heading 2
            standard_heading.style = 'Heading 2'
        
        # Add suggestion body
        suggestion_para = doc.add_paragraph(item['suggestion'])
        try:
            suggestion_para.style = body_style
        except KeyError:
            # Style doesn't exist, use Normal
            suggestion_para.style = 'Normal'
        
        # Add spacing after each standard
        doc.add_paragraph()
    
    # Save to temporary file
    temp_file = tempfile.NamedTemporaryFile(
        delete=False,
        suffix='.docx',
        prefix='contract_edited_'
    )
    temp_path = Path(temp_file.name)
    temp_file.close()
    
    doc.save(str(temp_path))
    
    return temp_path
