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
1. Find the MOST relevant clause in the contract that addresses the standard by analyzing the ACTUAL CLAUSE CONTENT, not just section titles.
2. Return the exact clause text word-for-word.
3. Return the exact section/heading line FROM THE CONTRACT that is immediately above that clause.
4. Do NOT infer or invent section numbers or names.

HARD CONSTRAINTS (MUST FOLLOW):
- You MUST only use information that literally appears in the contract text.
- The "location" field MUST be copied from a single, contiguous line in the contract.
- If the contract text does NOT contain "Section 4", "4.", "Article VII", etc., you MUST NOT output those labels.
- Do NOT guess the section number based on counting.
- Do NOT synthesize your own headings like "Confidentiality and Non-Compete section" if that exact text does not exist.

SECTION IDENTIFICATION RULES (CRITICAL - MUST FOLLOW):
1. SECTION TITLE MATCHING (HIGHEST PRIORITY):
   - ALWAYS scan the entire contract for section headings that match or closely relate to "{standard}"
   - If you find a section explicitly titled with the standard name (e.g., "Independent Contractors", "Indemnification", "Confidentiality"), this should be your FIRST CHOICE
   - Examples of title matches:
     * "Independent Contractor" standard → Section titled "Independent Contractors", "Independent Contractor Status", "No Agency"
     * "Indemnification" standard → Section titled "Indemnification", "Indemnity", "Hold Harmless"
     * "Limitation of Liability" standard → Section titled "Limitation of Liability", "Liability Limits", "Damages Cap"
   - Only choose a differently-titled section if the matching-titled section does NOT actually address the topic
   - This rule applies to ALL standards - prioritize title matches universally

2. Match based on SEMANTIC MEANING of the entire section, not keyword overlap.
   - Keywords like "acknowledges", "agrees", "warrants", "represents" appear in many contexts
   - DO NOT match based on word similarity alone
   - The section's PRIMARY PURPOSE must align with the standard being searched
   - Example: Don't match "Independent Contractor" just because a R&W section mentions "authorized representatives"

3. Structural hierarchy matters:
   - First identify the top-level section (A., B., C., etc. or Section 1, Section 2, etc.)
   - Then identify subsections (a., b., c., etc.)
   - Match at the highest structural level that fully represents the standard
   - A subsection like "H.b" is preferred if it's the dedicated location for that standard

4. Prefer dedicated sections over partial mentions:
   - If a contract has a section explicitly labeled or functioning as the standard (e.g., "Representations and Warranties"), choose that
   - Do NOT choose sections that only contain passing references or tangential mentions
   - If similar wording appears in multiple locations, choose the STRONGEST SEMANTIC MATCH, not the first occurrence

5. Understand the PURPOSE of common sections to avoid false matches:
   - "Representations and Warranties" sections are about parties making factual statements about their authority, status, and capacity at time of signing
   - "Independent Contractor" sections establish the nature of the business relationship between parties
   - "Indemnification" sections create obligations to protect/compensate for losses
   - "Termination" sections describe how and when the agreement can end
   - Don't match standards to sections serving different purposes, even if similar words appear

DETECTION ALGORITHM:
1. STEP 1 - SCAN FOR SECTION TITLE MATCHES FIRST:
   - Before analyzing content, scan through all section headings in the contract
   - Look for any section whose title/heading closely matches "{standard}"
   - If you find a title match (e.g., searching for "Independent Contractor" and finding a section titled "Independent Contractors: No Agency"), START YOUR ANALYSIS THERE
   - This section should be your primary candidate unless it clearly doesn't address the topic

2. STEP 2 - ANALYZE CONTENT IF NO CLEAR TITLE MATCH:
   - If no section title matches, then search based on clause content and semantic purpose
   - Match based on what the section is TRYING TO ACCOMPLISH, not just word overlap
   - A section titled "Miscellaneous" or "General Provisions" may contain many different clause types - look for the one that matches the purpose of "{standard}"
   
   SPECIFIC STANDARD DEFINITIONS AND COMMON FALSE MATCHES:
   
   - "Representations and Warranties": 
     * PURPOSE: Parties making factual statements about their authority, status, and capacity at time of signing
     * Look for affirmative statements where parties declare facts about themselves to be relied upon
     * Common false match: Finding this in warranty disclaimers or limitation of liability language that contains the word "warranty"
     * Common false match: Performance obligations about service quality
   
   - "Independent Contractor": 
     * PURPOSE: Establishing the nature of the business relationship (contractor vs. employee, no agency created)
     * Typically addresses whether parties are independent contractors, not creating employment or agency relationships
     * Common false match: Representations and Warranties sections that mention "authorized representatives" for signing purposes
     * Common false match: Sections that use the word "representative" in other contexts
   
   - "Indemnification": 
     * PURPOSE: One party protecting/compensating the other for losses, claims, or damages
     * Look for obligations to "indemnify", "hold harmless", "defend", or compensate for losses
     * Common false match: Passing mentions of indemnity within termination or other sections - look for the dedicated indemnification provision
   
   - "Standard of Care":
     * PURPOSE: Establishing the level of quality, skill, or professionalism required in performance
     * Look for references to industry standards, professional standards, workmanlike manner, or similar quality benchmarks
     * Common false match: General language about quality that doesn't establish a specific standard of care
   
   - "Limitation of Liability":
     * PURPOSE: Capping or excluding certain types of damages or liability
     * Look for liability caps, exclusions of consequential damages, "shall not be liable" language
     * Common false match: General warranty disclaimers that mention warranties but don't specifically limit liability
   
   - "Confidentiality":
     * PURPOSE: Protecting confidential or proprietary information from disclosure
     * Look for obligations to maintain confidentiality, non-disclosure requirements, handling of proprietary information
     * Common false match: General references to information sharing that don't create confidentiality obligations
   
   - "Limitation of Liability": Look for phrases like "limitation of liability", "shall not be liable", "maximum liability", "in no event shall", "liability cap", "excluding consequential damages".
   
   - "Confidentiality": Look for phrases like "confidential information", "shall not disclose", "maintain confidentiality", "proprietary information", "non-disclosure".
   
   - For ANY standard: Find where the contract PRIMARILY and COMPREHENSIVELY addresses that topic, not just passing mentions in other sections.
2. Once you find the best matching clause BY CONTENT:
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
- GOOD examples: "4. Confidentiality & Non-Compete", "Section 7: Indemnification", "Article V - Termination", "H. Miscellaneous Provisions"
- BAD examples: "4. Confidentiality & Non-Compete. The Partner may have access to..." (includes clause text)
- The "location" value MUST be an exact substring from the contract text.
- Keep punctuation, capitalization, and numbering exactly as written.
- Do NOT convert numbers between formats (no 4 ↔ "four" ↔ "IV").
- Do NOT rename "Section" to "Paragraph" or vice versa.
- Stop at the first period AFTER the title, before clause content begins.
- VERIFY: After identifying the location, re-read the clause content under that heading to confirm it actually contains content about "{standard}". If the heading says "Termination" but the clause content is about "Representations and Warranties", you have the WRONG section - keep searching.
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

BEFORE RESPONDING, VERIFY (MANDATORY CHECKS):
- The "excerpt" is copied word-for-word from the contract.
- The "location" is copied word-for-word from a single line in the contract and exists in the contract text.
- You did not invent or infer any section numbers or headings.

- MOST CRITICAL: Did you find a section whose TITLE/HEADING matches "{standard}"?
  * If YES: Did you analyze that section first? Is there a strong reason to choose a different section instead?
  * If NO: Did you thoroughly scan all section headings before analyzing content?
  * Title-matched sections should almost always be chosen unless they clearly don't address the topic

- CRITICAL: The PRIMARY PURPOSE of the section matches "{standard}" - not just keyword overlap or tangential mentions.
- Ask yourself: "Is this section DEDICATED to {standard}, or does it just happen to mention related words?"
- Ask yourself: "Does this section serve the same PURPOSE as {standard}, or is it doing something else?"

- Examples of common false matches to AVOID:
  * Finding "Independent Contractor" in a Representations and Warranties section just because it mentions "authorized representatives"
  * Finding "Standard of Care" in general quality language that doesn't establish a professional standard
  * Finding "Representations and Warranties" in warranty disclaimers or limitation of liability sections
  * Finding any standard in a section that just happens to use similar vocabulary but serves a different legal purpose

- If multiple sections contain related language, strongly prefer:
  1st: Section with matching title
  2nd: Section whose PRIMARY PURPOSE matches the standard
  3rd: If neither exists, set found=false rather than forcing a weak match

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


# Party Detection Prompt
PARTY_DETECTION_PROMPT = """Analyze the contract text and identify the two main parties.

CONTRACT TEXT (first 5000 characters):
{text}

Identify:
1. Party 1 (typically the contractor/vendor/service provider)
2. Party 2 (typically the customer/client/buyer)

For each party, provide:
- legal_name: The full legal entity name
- defined_as: What they're referred to in the contract (e.g., "Contractor", "Vendor", "Client", "Customer")
- role: Either "contractor" or "customer" (contractor = service provider, customer = service recipient)

Determine roles based on:
- Who is providing the service/product = contractor
- Who is receiving/purchasing the service/product = customer

Return as JSON:
{{
    "party1": {{
        "legal_name": "Full legal name",
        "defined_as": "Contractor or Vendor or similar",
        "role": "contractor"
    }},
    "party2": {{
        "legal_name": "Full legal name", 
        "defined_as": "Client or Customer or similar",
        "role": "customer"
    }},
    "found": true
}}

If parties cannot be clearly identified, return {{"found": false}}"""


def detect_contract_parties(text: str) -> dict:
    """
    Detect the two main parties in a contract (contractor and customer).
    
    Args:
        text: Full contract text
        
    Returns:
        Dictionary with party1, party2, and found status
    """
    try:
        model = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
        
        # Use first 5000 characters where parties are typically defined
        text_sample = text[:5000] if len(text) > 5000 else text
        
        prompt = PARTY_DETECTION_PROMPT.format(text=text_sample)
        response = _call_openai(SYSTEM_PROMPT, prompt, model)
        
        # Parse JSON response
        party_info = json.loads(response)
        
        logger.info(f"Party detection complete: found={party_info.get('found', False)}")
        return party_info
        
    except Exception as e:
        logger.warning(f"Party detection failed: {e}")
        return {
            'party1': {'legal_name': 'Unknown', 'defined_as': 'Unknown', 'role': 'contractor'},
            'party2': {'legal_name': 'Unknown', 'defined_as': 'Unknown', 'role': 'customer'},
            'found': False
        }
