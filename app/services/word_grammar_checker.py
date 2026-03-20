"""
Word COM API-based spelling checker.
Uses Microsoft Word's built-in spell checker via pywin32.

Note: This module handles SPELLING ONLY. Grammar checking is done by GPT with legal context.

IMPORTANT: Word COM can hang if dialogs appear. We use timeouts to prevent indefinite hangs.
"""
import os
import logging
from pathlib import Path
from typing import Dict, List
import tempfile
import threading

logger = logging.getLogger(__name__)


def _is_false_positive_spelling_error(error_text: str, suggestion: str, context: str) -> bool:
    """
    Detect common false positive spelling errors from Word COM API.
    
    Args:
        error_text: The text Word flagged as incorrect
        suggestion: Word's suggested correction
        context: Surrounding text for context
        
    Returns:
        True if this appears to be a false positive, False otherwise
    """
    # Skip empty or whitespace-only errors
    if not error_text or not error_text.strip():
        return True
    
    # Common false positive: standalone 'i' → 'I' when it's actually part of a word
    # This happens when PDF conversion creates hidden characters/spaces
    if error_text.strip().lower() == 'i' and suggestion.strip() == 'I':
        # Check if 'i' appears to be in the middle of a word in context
        # Look for patterns like: "...someth i ng..." or "...appl i cation..."
        import re
        
        # Clean context for analysis
        clean_context = context.replace('\r', ' ').replace('\n', ' ').strip()
        
        # Find where the 'i' appears in the context
        i_pattern = r'\b\w*\s*i\s*\w+\b|\b\w+\s*i\s*\w*\b'
        if re.search(i_pattern, clean_context, re.IGNORECASE):
            # The 'i' appears to be part of a larger word
            print(f"[FILTER] Skipping false positive: 'i' appears to be part of word in: '{clean_context[:50]}...'")
            return True
    
    # Filter out single-character "errors" that are likely noise
    if len(error_text.strip()) == 1 and error_text.strip() in 'abcdefghjklmnopqrstuvwxyz':
        # Single letters flagged (except 'a' and 'I' which are valid words)
        if error_text.strip().lower() not in ['a', 'i']:
            print(f"[FILTER] Skipping single character: '{error_text}' (likely formatting artifact)")
            return True
    
    # Filter out errors where suggestion is just capitalization of the same text
    # and it appears mid-sentence (likely autocorrect being overzealous)
    if error_text.lower() == suggestion.lower() and error_text != suggestion:
        # Check if this is mid-sentence (not after period)
        if context and not context.strip().endswith('.'):
            # Likely mid-sentence capitalization suggestion - could be false
            # Allow it for actual standalone words but block for partial words
            if len(error_text) <= 2:
                print(f"[FILTER] Skipping capitalization suggestion mid-sentence: '{error_text}' → '{suggestion}'")
                return True
    
    return False


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
            # Start Word application (invisible) with aggressive dialog suppression
            print(f"[WORD GRAMMAR CHECK] Starting Word application in automation mode...")
            word = win32com.client.Dispatch("Word.Application")
            word.Visible = False
            word.DisplayAlerts = 0  # wdAlertsNone - suppress all alerts
            word.ScreenUpdating = False  # Disable screen updates for performance
            
            # Set automation security to allow all macros without prompting
            # This prevents macro security dialogs
            try:
                word.AutomationSecurity = 1  # msoAutomationSecurityLow - no security prompts
            except:
                print(f"[WORD GRAMMAR CHECK] ⚠ Could not set AutomationSecurity")
            
            # Disable features that might trigger dialogs
            try:
                word.Options.CheckGrammarAsYouType = False
                word.Options.CheckGrammarWithSpelling = False
                word.Options.CheckSpellingAsYouType = False
                word.Options.SuggestSpellingCorrections = False
                word.Options.IgnoreInternetAndFileAddresses = True
                word.Options.IgnoreMixedDigits = True
                word.Options.IgnoreUppercase = False
                word.Options.UpdateLinksAtOpen = False  # Don't update links
                word.Options.ConfirmConversions = False  # Don't confirm conversions
            except Exception as opt_err:
                # Some Word versions may not support all options
                print(f"[WORD GRAMMAR CHECK] ⚠ Could not set some Word options: {opt_err}")
            
            # Disable AutoRecover to prevent recovery dialogs
            try:
                word.Options.SaveInterval = 0  # Disable AutoRecover
            except:
                pass
            
            print(f"[WORD GRAMMAR CHECK] ✓ Word configured for automation")
            
            # Open document with maximum dialog suppression
            abs_path = str(Path(file_path).resolve())
            print(f"[WORD GRAMMAR CHECK] Opening document: {abs_path}")
            
            # Use explicit parameters to ensure proper COM binding and suppress all prompts
            doc = word.Documents.Open(
                FileName=abs_path,
                ConfirmConversions=False,  # Don't ask about file conversion
                ReadOnly=True,  # Open read-only to avoid save prompts
                AddToRecentFiles=False,  # Don't add to recent files
                Visible=False,  # Keep invisible
                NoEncodingDialog=True,  # Suppress encoding dialog
                Revert=False,  # Don't revert to saved version
                Format=0  # wdOpenFormatAuto - let Word determine format
            )
            
            # Verify we got a valid document object
            if not doc or not hasattr(doc, 'SpellingErrors'):
                raise RuntimeError(f"Failed to open document properly - invalid document object returned")
            
            print(f"[WORD GRAMMAR CHECK] ✓ Document opened successfully")
            
            # Get spelling errors
            spelling_errors = doc.SpellingErrors
            spelling_count = spelling_errors.Count
            print(f"[WORD GRAMMAR CHECK] Found {spelling_count} spelling errors")
            
            # Track filtered false positives
            filtered_count = 0
            
            # Process spelling errors (limit to 25)
            for i, error in enumerate(spelling_errors):
                if i >= 25:  # Limit to avoid performance issues
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
                    
                    # Filter out false positives (e.g., 'i' in middle of words from PDF artifacts)
                    if _is_false_positive_spelling_error(error_text, suggestion, location):
                        filtered_count += 1
                        print(f"[FILTER] Excluded false positive #{filtered_count}: '{error_text}' → '{suggestion}'")
                        continue
                    
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
            
            # Log filtering results
            if filtered_count > 0:
                print(f"[WORD GRAMMAR CHECK] ✓ Filtered out {filtered_count} false positive spelling errors")
                logger.info(f"Filtered {filtered_count} false positive spelling errors from PDF artifacts")
            
            # Get grammar errors
            grammar_errors = doc.GrammaticalErrors
            grammar_count = grammar_errors.Count
            print(f"[WORD GRAMMAR CHECK] Found {grammar_count} grammar errors")
            
            # Process grammar errors (limit to 25)
            for i, error in enumerate(grammar_errors):
                if i >= 25:  # Limit to avoid performance issues
                    break
                    
                try:
                    error_text = error.Text
                    
                    # Get context around the error
                    try:
                        error_range = error
                        start_pos = max(0, error_range.Start - 75)
                        end_pos = min(doc.Characters.Count, error_range.End + 75)
                        context_range = doc.Range(start_pos, end_pos)
                        location = context_range.Text.replace('\r', ' ').replace('\n', ' ')[:150]
                    except:
                        location = f"...{error_text}..."
                    
                    # Note: Word COM API doesn't provide direct grammar suggestions
                    # We'll use the error text as-is and let the user decide
                    suggestion = error_text  # No automatic suggestion for grammar
                    
                    errors_list.append({
                        'type': 'grammar',
                        'error_text': error_text[:100],
                        'location': location,
                        'suggestion': suggestion[:100],
                        'explanation': f'Grammar issue detected by Microsoft Word'
                    })
                except Exception as e:
                    logger.warning(f"Error processing grammar error {i}: {e}")
                    continue
            
            total_errors = len(errors_list)
            print(f"[WORD GRAMMAR CHECK] Processed {total_errors} errors total (max 50)")
            
            # Return results in same format as GPT checker
            result = {
                'issues_found': total_errors > 0,
                'error_count': total_errors,
                'errors': errors_list,
                'method': 'word_com',  # Identifier for debugging
                'raw_counts': {
                    'spelling': spelling_count,
                    'grammar': grammar_count,
                    'processed': total_errors
                }
            }
            
            return result
            
        finally:
            # Clean up COM objects (CRITICAL: Must close Word or files stay locked)
            # First, try to close any dialogs that might be open
            if word:
                try:
                    # Try to close any open dialogs by sending ESC key commands
                    # This helps if Word has a dialog box blocking closure
                    import win32api
                    import win32con
                    # SendKeys is unreliable in background mode, so we'll just try aggressive quit
                except:
                    pass
            
            if doc:
                try:
                    # Close without saving - use explicit parameter
                    doc.Close(SaveChanges=False)
                    print(f"[WORD GRAMMAR CHECK] ✓ Document closed")
                except Exception as close_err:
                    print(f"[WORD GRAMMAR CHECK] ⚠ Failed to close document: {close_err}")
                    # Try to release the document reference anyway
                    try:
                        del doc
                    except:
                        pass
            
            if word:
                try:
                    # Set alerts to suppress any last-minute dialogs
                    word.DisplayAlerts = 0
                    
                    # Force quit Word application to release ALL file handles
                    # Use wdDoNotSaveChanges constant (0) explicitly
                    word.Quit(SaveChanges=0)
                    print(f"[WORD GRAMMAR CHECK] ✓ Word application quit")
                except Exception as quit_err:
                    print(f"[WORD GRAMMAR CHECK] ⚠ Failed to quit Word gracefully: {quit_err}")
                    # Try harder - kill the Word process if needed
                    try:
                        # Note: os is imported at top of file
                        import signal
                        # Get Word's process ID if possible
                        try:
                            # This is a last resort - forcefully terminate
                            print(f"[WORD GRAMMAR CHECK] Attempting force quit...")
                        except:
                            pass
                    except:
                        pass
                finally:
                    # Release COM reference explicitly
                    try:
                        del word
                    except:
                        pass
            
            # Longer delay to allow Word to fully release file handles
            import time
            time.sleep(0.3)  # Increased from 0.1 to give Word more time
            
            # Uninitialize COM
            try:
                pythoncom.CoUninitialize()
            except Exception as uninit_err:
                print(f"[WORD GRAMMAR CHECK] ⚠ COM uninit error: {uninit_err}")
    
    except ImportError as e:
        logger.warning(f"Word COM API not available: {e}")
        print(f"[WORD GRAMMAR CHECK] pywin32 not installed or Word not available")
        return {
            'issues_found': False,
            'error_count': 0,
            'errors': [],
            'error_message': 'Word COM API not available (pywin32 not installed or Word not found)',
            'method': 'word_com_failed'
        }
    
    except Exception as e:
        logger.warning(f"Word grammar check failed: {e}")
        print(f"[WORD GRAMMAR CHECK] Error: {e}")
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
    except Exception as e:
        print(f"[WORD COM CHECK] ✗ Unexpected error: {e}")
        return False
