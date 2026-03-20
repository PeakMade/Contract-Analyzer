"""
Word COM API-based spelling checker.
Uses Microsoft Word's built-in spell checker via pywin32.

Note: This module handles SPELLING ONLY. Grammar checking is done by GPT with legal context.
"""
import os
import logging
from pathlib import Path
from typing import Dict, List
import tempfile

logger = logging.getLogger(__name__)


def check_spelling_with_word(file_path: str) -> dict:
    """
    Check a Word document for SPELLING errors only using Word COM API.
    
    Grammar checking is handled separately by GPT with legal expertise.
    
    Args:
        file_path: Path to the .docx file to check
        
    Returns:
        Dictionary with:
        - issues_found (bool): Whether any spelling errors were found
        - error_count (int): Total number of spelling errors
        - errors (list): List of error dictionaries with type='spelling', error_text, location, suggestion, explanation
        - method (str): 'word_com' to identify the checking method
    """
    try:
        import win32com.client
        import pythoncom
        
        # Initialize COM for this thread
        pythoncom.CoInitialize()
        
        print(f"\n[WORD SPELLING CHECK] Analyzing document with Word COM API for spelling errors only...")
        print(f"[WORD SPELLING CHECK] File: {file_path}")
        
        # Verify file exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Document not found: {file_path}")
        
        # Create Word application instance
        word = None
        doc = None
        errors_list = []
        
        try:
            # Start Word application (invisible)
            word = win32com.client.Dispatch("Word.Application")
            word.Visible = False
            word.DisplayAlerts = 0  # Don't show alerts
            
            # Open document (read-only to avoid locks)
            abs_path = str(Path(file_path).resolve())
            print(f"[WORD SPELLING CHECK] Opening document: {abs_path}")
            doc = word.Documents.Open(abs_path, ReadOnly=True)
            
            # Get spelling errors only (NO GRAMMAR)
            spelling_errors = doc.SpellingErrors
            spelling_count = spelling_errors.Count
            print(f"[WORD SPELLING CHECK] Found {spelling_count} spelling errors")
            
            # Process spelling errors (limit to 50 for spelling-only)
            for i, error in enumerate(spelling_errors):
                if i >= 50:  # More generous limit for spelling-only
                    break
                    
                try:
                    error_text = error.Text
                    
                    # Get context around the error (up to 150 chars)
                    try:
                        # Get the range and expand to show context
                        error_range = error
                        start_pos = max(0, error_range.Start - 75)
                        end_pos = min(doc.Characters.Count, error_range.End + 75)
                        context_range = doc.Range(start_pos, end_pos)
                        location = context_range.Text.replace('\r', ' ').replace('\n', ' ')[:150]
                    except:
                        location = f"...{error_text}..."
                    
                    # Get suggestion from Word
                    suggestions = error.GetSpellingSuggestions()
                    suggestion = suggestions[0].Name if suggestions.Count > 0 else error_text
                    
                    errors_list.append({
                        'type': 'spelling',
                        'error_text': error_text[:100],
                        'location': location,
                        'suggestion': suggestion[:100],
                        'explanation': f'Spelling error detected by Microsoft Word'
                    })
                except Exception as e:
                    logger.warning(f"Error processing spelling error {i}: {e}")
                    continue
            
            total_errors = len(errors_list)
            print(f"[WORD SPELLING CHECK] Processed {total_errors} spelling errors (max 50)")
            
            # Return results in same format as GPT checker
            result = {
                'issues_found': total_errors > 0,
                'error_count': total_errors,
                'errors': errors_list,
                'method': 'word_com',  # Identifier for debugging
                'raw_counts': {
                    'spelling': spelling_count,
                    'processed': total_errors
                }
            }
            
            return result
            
        finally:
            # Clean up COM objects
            if doc:
                try:
                    doc.Close(SaveChanges=False)
                except:
                    pass
            
            if word:
                try:
                    word.Quit()
                except:
                    pass
            
            # Uninitialize COM
            pythoncom.CoUninitialize()
    
    except ImportError as e:
        logger.warning(f"Word COM API not available: {e}")
        print(f"[WORD SPELLING CHECK] pywin32 not installed or Word not available")
        return {
            'issues_found': False,
            'error_count': 0,
            'errors': [],
            'error_message': 'Word COM API not available (pywin32 not installed or Word not found)',
            'method': 'word_com_failed'
        }
    
    except Exception as e:
        logger.warning(f"Word spelling check failed: {e}")
        print(f"[WORD SPELLING CHECK] Error: {e}")
        import traceback
        traceback.print_exc()
        return {
            'issues_found': False,
            'error_count': 0,
            'errors': [],
            'error_message': f'Word COM error: {str(e)}',
            'method': 'word_com_failed'
        }


def is_word_com_available() -> bool:
    """
    Check if Word COM API is available on this system.
    
    Returns:
        True if Word COM API can be used, False otherwise
    """
    try:
        import win32com.client
        import pythoncom
        
        print("[WORD COM CHECK] Checking Word COM availability...")
        
        # Try to create Word application
        pythoncom.CoInitialize()
        try:
            word = win32com.client.Dispatch("Word.Application")
            word.Quit()
            print("[WORD COM CHECK] ✓ Word COM is available")
            return True
        except Exception as e:
            print(f"[WORD COM CHECK] ✗ Word COM dispatch failed: {e}")
            return False
        finally:
            pythoncom.CoUninitialize()
    except ImportError as e:
        print(f"[WORD COM CHECK] ✗ Import failed: {e}")
        return False
    except  Exception as e:
        print(f"[WORD COM CHECK] ✗ Unexpected error: {e}")
        return False
