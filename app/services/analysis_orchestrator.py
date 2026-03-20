"""
Analysis orchestrator - coordinates the full contract analysis workflow.
Combines LLM analysis with SharePoint preferred standards.
"""
import logging
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)

# Chunk size for large contracts (in characters)
CHUNK_SIZE = 14_000  # ~14k chars per chunk to stay well under token limits


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE) -> List[str]:
    """
    Split text into chunks for analysis.
    
    Args:
        text: Full contract text.
        chunk_size: Maximum characters per chunk.
    
    Returns:
        List of text chunks.
    """
    if len(text) <= chunk_size:
        return [text]
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        
        # Try to break at paragraph boundary
        if end < len(text):
            # Look for paragraph break within last 1000 chars
            search_start = max(start, end - 1000)
            last_break = text.rfind('\n\n', search_start, end)
            
            if last_break > start:
                end = last_break
        
        chunks.append(text[start:end])
        start = end
    
    logger.info(f"Split text into {len(chunks)} chunks of ~{chunk_size} chars each")
    return chunks


def _analyze_standard_with_chunks(
    text: str,
    standard: str,
    llm_client_analyze
) -> dict:
    """
    Analyze a single standard, handling large text by chunking.
    
    Args:
        text: Full contract text.
        standard: Standard to analyze.
        llm_client_analyze: Function to call for LLM analysis.
    
    Returns:
        Analysis result dictionary.
    """
    chunks = _chunk_text(text)
    
    if len(chunks) == 1:
        # No chunking needed
        return llm_client_analyze(text, standard)
    
    # Analyze each chunk until we find a positive result
    best_result = None
    
    for i, chunk in enumerate(chunks):
        logger.debug(f"Analyzing chunk {i+1}/{len(chunks)} for standard: {standard}")
        
        try:
            result = llm_client_analyze(chunk, standard)
            
            if result['found']:
                # Found in this chunk - return immediately
                logger.info(f"Standard '{standard}' found in chunk {i+1}")
                return result
            
            # Keep first negative result for suggestion
            if best_result is None:
                best_result = result
                
        except Exception as e:
            logger.warning(f"Chunk {i+1} analysis failed: {e}")
            continue
    
    # Not found in any chunk - return the first negative result
    logger.info(f"Standard '{standard}' not found in any chunk")
    return best_result or {
        'found': False,
        'excerpt': None,
        'location': None,
        'suggestion': "Unable to analyze this standard due to technical issues."
    }


def analyze_contract(
    text: str,
    standards: List[str],
    preferred: Dict[str, str],
    check_grammar: bool = True,
    file_path: Optional[str] = None
) -> Dict[str, dict]:
    """
    Analyze a contract against multiple standards and optionally check spelling/grammar.
    
    Combines AI analysis with SharePoint preferred standards:
    - For SharePoint standards: AI checks presence only, uses SharePoint clause if missing
    - For custom standards: AI checks presence AND generates suggestion if missing
    - Returns comprehensive results for all standards
    - Optionally performs spelling and grammar check
    
    Args:
        text: The contract text to analyze.
        standards: List of standard names to check.
        preferred: Dictionary of preferred (gold standard) clauses from SharePoint.
                   Keys are standard names from "Preferred Contract Terms" list.
        check_grammar: Whether to perform spelling/grammar check (default: True).
        file_path: Optional path to .docx file for Word COM API grammar checking.
    
    Returns:
        Dictionary with two keys:
        - 'standards': Dictionary keyed by standard name, with values containing:
            - found (bool): Whether standard is present
            - excerpt (str|None): Relevant excerpt if found
            - location (str|None): Location in contract
            - suggestion (str|None): Suggested clause text
            - source (str): "sharepoint" (preferred list), "ai" (custom/generated), or "error"
        - 'grammar': Dictionary with grammar check results (if check_grammar=True):
            - issues_found (bool): Whether errors were found
            - error_count (int): Number of errors
            - errors (list): List of error dictionaries
            - method (str): "word_com" or "gpt" to identify checking method
    
    Raises:
    logger.info(f"Grammar check enabled: {check_grammar}")
        ValueError: If standards is empty or text is blank.
    """
    # Validate inputs
    if not standards:
        raise ValueError("Standards list cannot be empty")
    
    if not text or not text.strip():
        raise ValueError("Contract text cannot be blank")
    
    logger.info(f"Starting contract analysis: {len(standards)} standards, {len(text)} chars")
    logger.info(f"SharePoint preferred standards available: {len(preferred)}")
    
    # Import here to avoid circular dependency
    from app.services.llm_client import analyze_standard
    
    results = {}
    
    for i, standard in enumerate(standards, 1):
        logger.info(f"Analyzing standard {i}/{len(standards)}: {standard}")
        
        # Check if this is a SharePoint preferred standard or custom standard
        is_preferred_standard = standard in preferred
        
        try:
            # Analyze with LLM (handles chunking internally)
            result = _analyze_standard_with_chunks(text, standard, analyze_standard)
            
            if not result['found']:
                # Standard not found in contract
                if is_preferred_standard:
                    # Use SharePoint clause directly (don't use AI suggestion)
                    logger.info(f"Using SharePoint preferred clause for: {standard}")
                    result['suggestion'] = preferred[standard]
                    result['source'] = 'sharepoint'
                else:
                    # Custom standard - keep AI-generated suggestion
                    logger.info(f"Using AI-generated suggestion for custom standard: {standard}")
                    result['source'] = 'ai'
            else:
                # Standard found - mark source appropriately
                result['source'] = 'sharepoint' if is_preferred_standard else 'ai'
            
            results[standard] = result
            
        except Exception as e:
            logger.error(f"Failed to analyze standard '{standard}': {e}")
            
            # Use preferred clause if available, otherwise provide error message
            if is_preferred_standard:
                results[standard] = {
                    'found': False,
                    'excerpt': None,
                    'location': None,
                    'suggestion': preferred[standard],
                    'source': 'sharepoint'
                }
            else:
                results[standard] = {
                    'found': False,
                    'excerpt': None,
                    'location': None,
                    'suggestion': "Unable to analyze this standard due to a technical error.",
                    'source': 'error'
                }
    
    logger.info(
        f"Analysis complete: {len(results)} standards analyzed, "
        f"{sum(1 for r in results.values() if r['found'])} found"
    )
    # Grammar and spelling check (optional)
    grammar_results = None
    if check_grammar:
        print("\n" + "="*70)
        print("STARTING GRAMMAR/SPELLING CHECK")
        print("="*70)
        logger.info("Starting grammar/spelling check...")
        
        spelling_errors = []
        grammar_errors = []
        
        try:
            # Step 1: Word COM API for spelling errors (preferred for accuracy)
            print(f"[DEBUG] file_path parameter: {file_path}")
            print(f"[DEBUG] file_path type: {type(file_path)}")
            if file_path:
                file_path_obj = Path(file_path)
                print(f"[DEBUG] Path object created: {file_path_obj}")
                print(f"[DEBUG] Path exists: {file_path_obj.exists()}")
                print(f"[DEBUG] Path is_file: {file_path_obj.is_file()}")
                if file_path_obj.exists():
                    print(f"[DEBUG] File size: {file_path_obj.stat().st_size} bytes")
                    print(f"[DEBUG] File extension: {file_path_obj.suffix}")
            else:
                print(f"[DEBUG] file_path is None or empty")
            
            if file_path and Path(file_path).exists():
                from app.services.word_grammar_checker import check_spelling_with_word
                print(f"[SPELLING CHECK] Using Word COM API for file: {file_path}")
                spelling_result = check_spelling_with_word(str(file_path))
                print(f"[SPELLING CHECK] Word COM API returned: {spelling_result}")
                spelling_errors = spelling_result.get('errors', [])
                print(f"[SPELLING CHECK] Word COM API check complete: {len(spelling_errors)} spelling errors found")
                print(f"[SPELLING CHECK] Raw counts: {spelling_result.get('raw_counts', {})}")
            else:
                print(f"[SPELLING CHECK] No file path provided or file doesn't exist, skipping Word COM check")
                if file_path:
                    print(f"[SPELLING CHECK] file_path was: {file_path}")
            
            # Step 2: AI Grammar Check (for legal contract grammar analysis)
            print(f"\n[GRAMMAR CHECK] Starting AI-powered grammar analysis...")
            try:
                from app.services.llm_client import check_grammar
                
                # Call AI grammar check
                grammar_response = check_grammar(text, max_words=3000)
                print(f"[GRAMMAR CHECK] AI response received: {len(grammar_response)} chars")
                print(f"[GRAMMAR CHECK] AI response preview: {grammar_response[:200]}...")
                
                # Parse AI response
                import json
                import re
                
                # Extract JSON from response (handle markdown code blocks)
                json_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', grammar_response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                    print(f"[GRAMMAR CHECK] Extracted JSON from code block")
                else:
                    # Try to find raw JSON array
                    json_match = re.search(r'(\[.*\])', grammar_response, re.DOTALL)
                    if json_match:
                        json_str = json_match.group(1)
                        print(f"[GRAMMAR CHECK] Extracted raw JSON array")
                    else:
                        json_str = '[]'
                        print(f"[GRAMMAR CHECK] No JSON found, using empty array")
                
                print(f"[GRAMMAR CHECK] Parsing JSON: {json_str[:200]}...")
                ai_grammar_issues = json.loads(json_str)
                print(f"[GRAMMAR CHECK] Parsed {len(ai_grammar_issues)} issues from AI response")
                
                # Convert AI format to our standard format
                for issue in ai_grammar_issues:
                    grammar_errors.append({
                        'type': 'grammar',
                        'error_text': issue.get('error_text', ''),
                        'location': issue.get('location', 'See context'),
                        'suggestion': issue.get('suggestion', ''),
                        'explanation': issue.get('issue', ''),
                        'severity': issue.get('severity', 'medium')
                    })
                
                print(f"[GRAMMAR CHECK] AI analysis complete: {len(grammar_errors)} grammar issues found")
                
            except Exception as ai_error:
                logger.warning(f"AI grammar check failed: {ai_error}")
                print(f"[GRAMMAR CHECK] AI analysis failed: {ai_error}")
                # Continue with spelling results even if AI fails
            
            # Combine results
            all_errors = spelling_errors + grammar_errors
            grammar_results = {
                'issues_found': len(all_errors) > 0,
                'error_count': len(all_errors),
                'spelling_count': len(spelling_errors),
                'grammar_count': len(grammar_errors),
                'errors': all_errors,
                'method': 'word_com_and_ai'
            }
            print(f"[GRAMMAR/SPELLING CHECK] Total: {len(all_errors)} issues ({len(spelling_errors)} spelling, {len(grammar_errors)} grammar)")
            
        except Exception as e:
            logger.error(f"Grammar/spelling check failed: {e}")
            print(f"[GRAMMAR CHECK] ✗ ERROR: {e}")
            import traceback
            traceback.print_exc()
            grammar_results = {
                'issues_found': False,
                'error_count': 0,
                'spelling_count': 0,
                'grammar_count': 0,
                'errors': [],
                'error_message': str(e),
                'method': 'failed'
            }
    
    # Return both standards analysis and grammar results
    return {
        'standards': results,
        'grammar': grammar_results
    }
