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
SYSTEM_PROMPT = "You are a legal contract analyst. Return ONLY valid JSON matching the schema."

USER_PROMPT_TEMPLATE = '''Analyze the contract text for a "{standard}" clause.

Return JSON: {{"found": true|false, "excerpt": string|null, "location": string|null, "suggestion": string|null}}

Constraints:
- If found: excerpt is the exact clause snippet; location like "Section 5.2" if visible, else null; suggestion must be null.
- If not found: excerpt and location are null; suggestion is a concise, legally neutral clause, no party names, no dates.
- Do not include the entire contract in the response.

Contract:
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
        user_prompt = USER_PROMPT_TEMPLATE.format(
            standard=standard,
            contract_text=text[:50000]  # Limit to ~50k chars to avoid token limits
        )
        
        # Call OpenAI with strict JSON response format
        logger.info(f"Analyzing standard: {standard}")
        response_text = _call_openai(SYSTEM_PROMPT, user_prompt, model)
        
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
        logger.info(
            f"Analysis complete: standard={standard}, found={result['found']}, "
            f"duration={duration:.2f}s"
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
