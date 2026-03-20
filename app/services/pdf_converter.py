"""
PDF to DOCX converter using Microsoft Word COM API.
Converts PDFs to editable Word documents at upload time.
"""
import os
import tempfile
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def convert_pdf_to_docx(pdf_path: str) -> str:
    """
    Convert a PDF file to DOCX format using Microsoft Word COM API.
    
    Args:
        pdf_path (str): Path to the PDF file to convert
        
    Returns:
        str: Path to the converted DOCX file
        
    Raises:
        RuntimeError: If conversion fails
        FileNotFoundError: If PDF file doesn't exist
    """
    try:
        import win32com.client
        import pythoncom
        
        # Initialize COM for this thread
        pythoncom.CoInitialize()
        
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")
        
        # Generate output DOCX path (same location, .docx extension)
        docx_path = pdf_path.with_suffix('.docx')
        
        print(f"\n[PDF CONVERTER] Converting PDF to DOCX")
        print(f"[PDF CONVERTER] Input:  {pdf_path}")
        print(f"[PDF CONVERTER] Output: {docx_path}")
        
        word = None
        doc = None
        
        try:
            # Start Word application (invisible, no alerts)
            word = win32com.client.Dispatch("Word.Application")
            word.Visible = False
            word.DisplayAlerts = 0  # wdAlertsNone
            
            # Open PDF (Word will convert it)
            abs_pdf_path = str(pdf_path.resolve())
            print(f"[PDF CONVERTER] Opening PDF in Word...")
            doc = word.Documents.Open(abs_pdf_path, ConfirmConversions=False)
            
            # Save as DOCX format
            # wdFormatXMLDocument = 12 (DOCX format)
            abs_docx_path = str(docx_path.resolve())
            print(f"[PDF CONVERTER] Saving as DOCX...")
            doc.SaveAs2(abs_docx_path, FileFormat=12)
            
            print(f"[PDF CONVERTER] ✓ Conversion successful")
            logger.info(f"Converted PDF to DOCX: {pdf_path.name} -> {docx_path.name}")
            
            return str(docx_path)
            
        finally:
            # Clean up COM objects
            if doc:
                try:
                    doc.Close(SaveChanges=False)
                except Exception as e:
                    logger.warning(f"Error closing Word document: {e}")
            
            if word:
                try:
                    word.Quit()
                except Exception as e:
                    logger.warning(f"Error quitting Word: {e}")
            
            # Uninitialize COM
            try:
                pythoncom.CoUninitialize()
            except Exception as e:
                logger.warning(f"Error uninitializing COM: {e}")
                
    except ImportError as e:
        error_msg = "Word COM API not available (pywin32 required)"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e
    except Exception as e:
        error_msg = f"PDF to DOCX conversion failed: {str(e)}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e


def is_word_com_available() -> bool:
    """
    Check if Microsoft Word COM API is available.
    
    Returns:
        bool: True if Word COM is available, False otherwise
    """
    try:
        import win32com.client
        import pythoncom
        
        pythoncom.CoInitialize()
        
        try:
            word = win32com.client.Dispatch("Word.Application")
            word.Quit()
            pythoncom.CoUninitialize()
            return True
        except:
            pythoncom.CoUninitialize()
            return False
    except ImportError:
        return False
