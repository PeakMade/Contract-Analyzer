"""
Analysis orchestrator - coordinates the full contract analysis workflow.
Combines LLM analysis with SharePoint preferred standards.
"""
import logging
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
    preferred: Dict[str, str]
) -> Dict[str, dict]:
    """
    Analyze a contract against multiple standards.
    
    Combines AI analysis with SharePoint preferred standards:
    - For each standard, calls LLM to analyze contract text
    - If standard not found and preferred clause exists in SharePoint, uses it
    - Returns comprehensive results for all standards
    
    Args:
        text: The contract text to analyze.
        standards: List of standard names to check.
        preferred: Dictionary of preferred (gold standard) clauses from SharePoint.
    
    Returns:
        Dictionary keyed by standard name, with values containing:
        - found (bool): Whether standard is present
        - excerpt (str|None): Relevant excerpt if found
        - location (str|None): Location in contract
        - suggestion (str|None): Suggested clause text
        - source (str): "ai" or "sharepoint" indicating suggestion source
    
    Raises:
        ValueError: If standards is empty or text is blank.
    """
    # Validate inputs
    if not standards:
        raise ValueError("Standards list cannot be empty")
    
    if not text or not text.strip():
        raise ValueError("Contract text cannot be blank")
    
    logger.info(f"Starting contract analysis: {len(standards)} standards, {len(text)} chars")
    
    # Import here to avoid circular dependency
    from app.services.llm_client import analyze_standard
    
    results = {}
    
    for i, standard in enumerate(standards, 1):
        logger.info(f"Analyzing standard {i}/{len(standards)}: {standard}")
        
        try:
            # Analyze with LLM (handles chunking internally)
            result = _analyze_standard_with_chunks(text, standard, analyze_standard)
            
            # If not found and we have a preferred clause from SharePoint, use it
            if not result['found'] and standard in preferred:
                logger.info(f"Using SharePoint preferred clause for: {standard}")
                result['suggestion'] = preferred[standard]
                result['source'] = 'sharepoint'
            else:
                result['source'] = 'ai'
            
            results[standard] = result
            
        except Exception as e:
            logger.error(f"Failed to analyze standard '{standard}': {e}")
            
            # Use preferred clause if available, otherwise provide generic error
            if standard in preferred:
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
    
    return results
