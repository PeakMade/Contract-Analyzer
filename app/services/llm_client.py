"""
LLM client for contract analysis using OpenAI GPT-4o-mini.
"""
import os
import json
import logging
import time
from typing import Optional
import openai
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

# Initialize OpenAI client
client: Optional[OpenAI] = None

# OpenAI prompt templates
SYSTEM_PROMPT = "You are a legal contract analyst specializing in clause identification and drafting. Return ONLY valid JSON matching the required schema."

USER_PROMPT_TEMPLATE = '''You are given the full text of a contract and a standard name: {standard}.

Your job is to:
1. Find the MOST relevant clause in the contract that addresses the standard.
2. Return the exact clause text word-for-word.
3. Return the exact section/heading line FROM THE CONTRACT that is immediately above that clause.
4. Do NOT infer or invent section numbers or names.

HARD CONSTRAINTS (MUST FOLLOW):
- You MUST only use information that literally appears in the contract text.
- The "location" field MUST be copied from a single, contiguous line in the contract.
- If the contract text does NOT contain "Section 4", "4.", "Article VII", etc., you MUST NOT output those labels.
- Do NOT guess the section number based on counting.
- Do NOT synthesize your own headings like "Confidentiality and Non-Compete section" if that exact text does not exist.

DETECTION ALGORITHM:
1. Search the contract for clauses related to "{standard}".
   - Prefer clauses where the heading line or clause text directly includes the standard term
     or a close legal synonym (e.g., "Confidentiality", "Non-Disclosure" for a confidentiality standard).
2. Once you find the best matching clause:
   - Let CLAUSE_START be the start of that clause in the contract text.
   - Scan UPWARDS from CLAUSE_START to find the NEAREST heading line above it.
     A heading line is typically:
       - A line that starts with a number or number pattern:
         e.g., "4. Confidentiality & Non-Compete", "7.2 Limitation of Liability"
       - OR a line starting with "Section", "Article", "Paragraph", or similar:
         e.g., "Section 12: Confidentiality"
       - OR a line in ALL CAPS or Title Case that clearly looks like a section heading.
3. Copy that heading line EXACTLY as it appears, but STOP at the end of the heading.
   - DO NOT include the first sentence of the clause text itself.
   - The heading is usually SHORT (under 100 characters).
   - Include ONLY the section number and title, NOT the clause content.

CRITICAL RULES FOR LOCATION:
- The "location" must be SHORT and concise - just the section number and title.
- GOOD examples: "4. Confidentiality & Non-Compete", "Section 7: Indemnification", "Article V - Termination"
- BAD examples: "4. Confidentiality & Non-Compete. The Partner may have access to..." (includes clause text)
- The "location" value MUST be an exact substring from the contract text.
- Keep punctuation, capitalization, and numbering exactly as written.
- Do NOT convert numbers between formats (no 4 ↔ "four" ↔ "IV").
- Do NOT rename "Section" to "Paragraph" or vice versa.
- Stop at the first period AFTER the title, before clause content begins.
- If you cannot confidently identify a heading line above the clause, set:
  - "location": "Location unclear in document"

WHEN NO CLAUSE EXISTS:
- If you cannot find any clause that clearly addresses "{standard}":
  - "found": false
  - "excerpt": null
  - "location": null
  - Write a complete, professionally worded suggested clause for the standard in "suggestion".

RESPONSE FORMAT (VALID JSON ONLY):
{{
  "found": boolean,
  "excerpt": string | null,      // exact clause text from the contract or null
  "location": string | null,     // exact heading line from the contract or "Location unclear in document"
  "suggestion": string | null    // null if found=true; if found=false provide a full clause here
}}

BEFORE RESPONDING, VERIFY:
- The "excerpt" is copied word-for-word from the contract.
- The "location" is copied word-for-word from a single line in the contract and exists in the contract text.
- You did not invent or infer any section numbers or headings.
- The final output is valid JSON and nothing else.

CONTRACT TEXT:
{contract_text}'''


def _get_client() -> OpenAI:
    """Get or initialize OpenAI client."""
    global client
    if client is None:
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        
        # Debug logging for API key configuration
        print(f"DEBUG llm_client: Initializing OpenAI client")
        print(f"DEBUG llm_client: API key present: {bool(api_key)}")
        print(f"DEBUG llm_client: API key length: {len(api_key) if api_key else 0}")
        print(f"DEBUG llm_client: API key prefix: {api_key[:20] if api_key else 'N/A'}...")
        
        try:
            client = OpenAI(api_key=api_key)
            print(f"DEBUG llm_client: OpenAI client created successfully")
            logger.info("OpenAI client initialized successfully")
        except Exception as e:
            print(f"DEBUG llm_client: Failed to create OpenAI client: {type(e).__name__} - {str(e)}")
            logger.error(f"Failed to create OpenAI client: {type(e).__name__} - {str(e)}")
            raise
    return client


def _validate_json_response(response_text: str) -> dict:
    """
    Parse and validate JSON response from LLM.
    
    Args:
        response_text: Raw text response from LLM.
    
    Returns:
        Validated dictionary with required keys.
    
    Raises:
        ValueError: If JSON is invalid or missing required keys.
    """
    try:
        data = json.loads(response_text)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response: {e}")
        raise ValueError("Invalid JSON response from LLM")
    
    # Validate required keys
    required_keys = {'found', 'excerpt', 'location', 'suggestion'}
    if not all(key in data for key in required_keys):
        missing = required_keys - set(data.keys())
        logger.error(f"JSON response missing required keys: {missing}")
        raise ValueError(f"JSON response missing required keys: {missing}")
    
    # Validate types
    if not isinstance(data['found'], bool):
        raise ValueError("'found' must be a boolean")
    
    # Ensure string fields are str or None
    for key in ['excerpt', 'location', 'suggestion']:
        if data[key] is not None and not isinstance(data[key], str):
            data[key] = str(data[key])
    
    # Post-process location to ensure it's concise (just section number and title)
    if data['location'] and isinstance(data['location'], str):
        location = data['location'].strip()
        
        # If location is too long (> 150 chars), it likely includes clause text
        if len(location) > 150:
            # Try to extract just the heading part (before the first sentence ends)
            # Look for patterns like "4. Title." or "Section 4: Title" and stop there
            parts = location.split('. ', 1)
            if len(parts) > 1 and len(parts[0]) < 100:
                # Keep just the section number and title
                data['location'] = parts[0] + '.'
            else:
                # Truncate at 150 chars as fallback
                data['location'] = location[:150] + '...'
        
        # Clean up any trailing whitespace
        data['location'] = data['location'].strip()
    
    return data


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    retry=retry_if_exception_type((openai.RateLimitError, openai.APIError)),
    reraise=True
)
def _call_openai(system_prompt: str, user_prompt: str, model: str) -> str:
    """
    Call OpenAI API with retry logic.
    
    Args:
        system_prompt: The system message.
        user_prompt: The user message.
        model: The model to use.
    
    Returns:
        Raw response text.
    
    Raises:
        openai.RateLimitError: On rate limit (will be retried).
        openai.APIError: On API errors (will be retried).
        RuntimeError: On other errors.
    """
    try:
        client = _get_client()
        
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=600,
            timeout=30.0
        )
        
        return response.choices[0].message.content
        
    except (openai.RateLimitError, openai.APIError):
        raise  # Will be retried by tenacity
    except openai.APITimeoutError:
        logger.error("OpenAI API request timed out")
        raise RuntimeError("AI analysis request timed out")
    except Exception as e:
        # Enhanced error logging for debugging
        import traceback
        error_type = type(e).__name__
        error_msg = str(e)
        stack_trace = traceback.format_exc()
        
        logger.error(f"OpenAI API call failed: {error_type}")
        logger.error(f"Error message: {error_msg}")
        logger.error(f"Stack trace:\n{stack_trace}")
        
        print(f"DEBUG llm_client: OpenAI API Error Details:")
        print(f"  Type: {error_type}")
        print(f"  Message: {error_msg}")
        print(f"  Full trace:\n{stack_trace}")
        
        raise RuntimeError(f"AI analysis service error: {error_type} - {error_msg}")


def analyze_standard(text: str, standard: str) -> dict:
    """
    Analyze a contract for a specific standard using OpenAI.
    
    Args:
        text: The contract text to analyze.
        standard: The standard/clause to check for (e.g., "Indemnification").
    
    Returns:
        Dictionary with keys:
        - found (bool): Whether the standard is present
        - excerpt (str|None): Relevant text excerpt if found
        - location (str|None): Location description (e.g., "Section 5.2")
        - suggestion (str|None): Suggested clause if not found or needs improvement
    
    Raises:
        RuntimeError: On analysis failure.
    """
    start_time = time.time()
    
    try:
        model = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
        
        # Construct user prompt from template
        contract_text_sample = text[:50000]  # Limit to ~50k chars to avoid token limits
        user_prompt = USER_PROMPT_TEMPLATE.format(
            standard=standard,
            contract_text=contract_text_sample
        )
        
        # === ENHANCED DEBUGGING ===
        print(f"\n[AI DEBUG] Analyzing standard: {standard}")
        print(f"[AI DEBUG] Contract text length: {len(contract_text_sample)} chars")
        
        # Show first 500 chars of what AI receives
        preview = contract_text_sample[:500].replace('\n', '\\n')
        print(f"[AI DEBUG] First 500 chars sent to AI: {preview}...")
        
        # Check for numbering in the text being sent
        has_numbers = any(f"{i}." in contract_text_sample for i in range(1, 10))
        has_roman = any(roman in contract_text_sample for roman in ["I.", "II.", "III.", "IV.", "V."])
        has_section = "Section" in contract_text_sample
        
        print(f"[AI DEBUG] Numbering in text: decimal={has_numbers}, roman={has_roman}, section={has_section}")
        
        # Call OpenAI with strict JSON response format
        logger.info(f"Analyzing standard: {standard}")
        response_text = _call_openai(SYSTEM_PROMPT, user_prompt, model)
        
        print(f"[AI DEBUG] AI response received: {len(response_text)} chars")
        
        # Parse and validate JSON response
        try:
            result = _validate_json_response(response_text)
        except ValueError as e:
            # Retry once with explicit "Return ONLY valid JSON" suffix
            logger.warning(f"First attempt failed validation: {e}. Retrying with explicit instruction.")
            
            retry_user_prompt = user_prompt + "\n\nReturn ONLY valid JSON."
            response_text = _call_openai(SYSTEM_PROMPT, retry_user_prompt, model)
            result = _validate_json_response(response_text)
        
        duration = time.time() - start_time
        
        # === ENHANCED DEBUGGING ===
        print(f"[AI DEBUG] Analysis result for '{standard}':")
        print(f"[AI DEBUG]   - found: {result['found']}")
        print(f"[AI DEBUG]   - location: {result.get('location', 'None')}")
        if result.get('location'):
            location_preview = result['location'][:100]
            print(f"[AI DEBUG]   - location preview: '{location_preview}'")
        print(f"[AI DEBUG]   - duration: {duration:.2f}s")
        
        logger.info(
            f"Analysis complete: standard={standard}, found={result['found']}, "
            f"location={result.get('location', 'None')}, duration={duration:.2f}s"
        )
        
        return result
        
    except (ValueError, RuntimeError):
        raise
    except Exception as e:
        duration = time.time() - start_time
        logger.error(
            f"Analysis failed: standard={standard}, duration={duration:.2f}s, "
            f"error={type(e).__name__}"
        )
        raise RuntimeError("Failed to analyze standard")
