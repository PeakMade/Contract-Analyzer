"""
Text extraction service for contract documents.
Supports DOCX and PDF formats.
"""
import re
import logging
from pathlib import Path
from typing import Optional
import docx
from pdfminer.high_level import extract_text as pdf_extract_text
from pdfminer.pdfparser import PDFSyntaxError

logger = logging.getLogger(__name__)

# Maximum characters to extract to avoid runaway prompts
MAX_TEXT_LENGTH = 2_000_000


def _normalize_whitespace(text: str) -> str:
    """
    Normalize whitespace and remove control characters.
    
    Args:
        text: Raw extracted text.
    
    Returns:
        Cleaned text with normalized whitespace.
    """
    # Remove control characters except newline, tab, carriage return
    text = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F-\x9F]', '', text)
    
    # Normalize line breaks
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    
    # Replace multiple spaces with single space (but preserve newlines)
    text = re.sub(r' +', ' ', text)
    
    # Replace multiple newlines with maximum of 2
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Strip leading/trailing whitespace from each line
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(lines)
    
    return text.strip()


def _extract_docx_text(path: Path) -> str:
    """
    Extract text from a DOCX file.
    
    Args:
        path: Path to the DOCX file.
    
    Returns:
        Extracted text content.
    
    Raises:
        RuntimeError: On extraction failure.
    """
    try:
        doc = docx.Document(path)
        
        # Extract text from all paragraphs
        paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
        
        # Extract text from tables
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        paragraphs.append(cell.text)
        
        text = '\n\n'.join(paragraphs)
        
        if not text.strip():
            raise RuntimeError("Document appears to be empty")
        
        logger.info(f"Extracted {len(text)} characters from DOCX file")
        return text
        
    except Exception as e:
        logger.error(f"Failed to extract text from DOCX: {type(e).__name__}")
        raise RuntimeError("Failed to extract text from document. The file may be corrupted or in an unsupported format.")


def _extract_pdf_text(path: Path) -> str:
    """
    Extract text from a PDF file.
    
    Args:
        path: Path to the PDF file.
    
    Returns:
        Extracted text content.
    
    Raises:
        RuntimeError: On extraction failure.
    """
    try:
        text = pdf_extract_text(str(path))
        
        if not text or not text.strip():
            raise RuntimeError("PDF appears to be empty or contains only images")
        
        logger.info(f"Extracted {len(text)} characters from PDF file")
        return text
        
    except PDFSyntaxError:
        logger.error("PDF file has syntax errors")
        raise RuntimeError("Failed to extract text from PDF. The file may be corrupted.")
    except Exception as e:
        logger.error(f"Failed to extract text from PDF: {type(e).__name__}")
        raise RuntimeError("Failed to extract text from PDF. The file may be encrypted, corrupted, or in an unsupported format.")


def extract_text(path: Path) -> str:
    """
    Extract text from a contract document (DOCX or PDF).
    
    Args:
        path: Path to the document file.
    
    Returns:
        Normalized text content with whitespace cleaned and control characters removed.
    
    Raises:
        RuntimeError: If extraction fails or file format is unsupported.
    """
    if not path.exists():
        raise RuntimeError("Contract file not found")
    
    # Determine file type by extension
    suffix = path.suffix.lower()
    
    try:
        if suffix == '.docx':
            raw_text = _extract_docx_text(path)
        elif suffix == '.pdf':
            raw_text = _extract_pdf_text(path)
        else:
            logger.error(f"Unsupported file format: {suffix}")
            raise RuntimeError(f"Unsupported file format: {suffix}. Only DOCX and PDF files are supported.")
        
        # Normalize whitespace
        normalized_text = _normalize_whitespace(raw_text)
        
        # Clamp to maximum length
        if len(normalized_text) > MAX_TEXT_LENGTH:
            logger.warning(f"Text length {len(normalized_text)} exceeds maximum {MAX_TEXT_LENGTH}, truncating")
            normalized_text = normalized_text[:MAX_TEXT_LENGTH]
        
        logger.info(f"Text extraction complete: {len(normalized_text)} characters after normalization")
        
        return normalized_text
        
    except RuntimeError:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during text extraction: {type(e).__name__}")
        raise RuntimeError("An unexpected error occurred while extracting text from the document")
