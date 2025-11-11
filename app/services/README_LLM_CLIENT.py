"""
✅ OPENAI LLM CLIENT - IMPLEMENTATION COMPLETE
==============================================

File: app/services/llm_client.py (200 lines)

SUMMARY
-------
Implemented OpenAI chat/completions call with strict JSON response format,
embedded prompt templates, JSON validation, and retry logic as specified.

IMPLEMENTATION DETAILS
----------------------

1. PROMPT TEMPLATES (Lines 18-32)
   ✅ SYSTEM_PROMPT constant
      "You are a legal contract analyst. Return ONLY valid JSON matching the schema."
   
   ✅ USER_PROMPT_TEMPLATE constant with placeholders
      - {standard}: Name of the clause to analyze
      - {contract_text}: Contract content to analyze
   
   Template structure:
   - Instruction: Analyze the contract text for a "{standard}" clause
   - Schema: JSON with found, excerpt, location, suggestion
   - Constraints: Different behavior for found vs not found
   - Input: Contract text

2. OPENAI API CALL (Lines 85-138)
   ✅ Function: _call_openai(system_prompt, user_prompt, model)
      - Updated signature to accept system_prompt and user_prompt separately
      - Uses chat.completions.create() endpoint
      - response_format={"type": "json_object"} for strict JSON enforcement
      - temperature=0.3 for deterministic results
      - max_tokens=600 for response length
      - timeout=30.0 seconds
      - @retry decorator for API errors (rate limits, transient failures)

3. JSON VALIDATION (Lines 48-82)
   ✅ Function: _validate_json_response(response_text)
      - Parses with json.loads()
      - Validates required keys: found, excerpt, location, suggestion
      - Type checking: 'found' must be boolean
      - Coerces string fields to str or None
      - Raises ValueError with descriptive message on failure

4. RETRY LOGIC (Lines 141-200)
   ✅ Function: analyze_standard(text, standard)
   
   Implementation flow:
   a. Format user_prompt from USER_PROMPT_TEMPLATE
      - Substitutes {standard} with standard name
      - Substitutes {contract_text} with text[:50000]
   
   b. First attempt:
      - Call _call_openai(SYSTEM_PROMPT, user_prompt, model)
      - Try _validate_json_response(response_text)
   
   c. On JSON parse failure (ValueError):
      - Log warning
      - Retry once with suffix "\n\nReturn ONLY valid JSON."
      - Call _call_openai(SYSTEM_PROMPT, retry_user_prompt, model)
      - Validate retry response
   
   d. Return validated result or raise RuntimeError

RESPONSE SCHEMA
---------------
{
    "found": boolean,          # True if clause found, False otherwise
    "excerpt": string | null,  # Exact snippet if found, null if not
    "location": string | null, # e.g., "Section 5.2" if found, null if not
    "suggestion": string | null # Suggested clause if not found, null if found
}

Constraints (enforced by prompt):
- If found=true: excerpt is exact clause snippet, location is section/paragraph, suggestion is null
- If not found=false: excerpt and location are null, suggestion is concise legal clause
- Suggestions: Legally neutral, no party names, no dates, no placeholders

PROMPT TEMPLATE DETAILS
------------------------
System Prompt:
"You are a legal contract analyst. Return ONLY valid JSON matching the schema."

User Prompt Structure:
1. Task: Analyze the contract text for a "{standard}" clause.
2. Schema: Return JSON: {"found": true|false, "excerpt": string|null, ...}
3. Constraints:
   - If found: excerpt is exact snippet, location visible, suggestion null
   - If not found: excerpt and location null, suggestion is neutral clause
   - Do not include entire contract in response
4. Input: Contract: {contract_text}

Retry Suffix (on failure):
"\n\nReturn ONLY valid JSON."

ERROR HANDLING
--------------
✅ ValueError: Missing OPENAI_API_KEY environment variable
✅ ValueError: Invalid JSON or missing required keys in response
✅ RuntimeError: API timeout (30s), service unavailable
✅ openai.RateLimitError: Auto-retried by @retry decorator (2 attempts)
✅ openai.APIError: Auto-retried by @retry decorator (2 attempts)
✅ JSON validation failure: Manual retry once with explicit instruction

CONFIGURATION
-------------
Environment Variables:
- OPENAI_API_KEY: Required, API authentication key
- OPENAI_MODEL: Optional, default 'gpt-4o-mini'

API Settings:
- Model: gpt-4o-mini (configurable)
- Temperature: 0.3 (deterministic)
- Max Tokens: 600 (sufficient for analysis response)
- Timeout: 30.0 seconds
- Response Format: {"type": "json_object"} (strict JSON mode)

Text Processing:
- Contract text limited to first 50,000 characters
- Prevents token limit errors while maintaining full context

INTEGRATION
-----------
Called by: app/services/analysis_orchestrator.py
Function: analyze_standard(contract_text, standard_name)
Returns: dict with found, excerpt, location, suggestion keys
Raises: RuntimeError on failure (caught by orchestrator)

TESTING NOTES
-------------
Manual test (requires OPENAI_API_KEY):
```python
import os
os.environ['OPENAI_API_KEY'] = 'sk-...'

from app.services.llm_client import analyze_standard

contract = '''
AGREEMENT
Section 5: Indemnification
The parties agree to indemnify each other...
'''

result = analyze_standard(contract, "Indemnification")
print(result)
# Expected: {"found": true, "excerpt": "...", "location": "Section 5", "suggestion": null}
```

Expected behaviors:
1. First call succeeds with valid JSON → return result
2. First call returns invalid JSON → retry with suffix → return result
3. Both attempts fail → raise RuntimeError
4. API rate limit → auto-retry by tenacity
5. API timeout → raise RuntimeError immediately

PROMPT SPECIFICATION COMPLIANCE
--------------------------------
✅ Use OpenAI chat/completions call with strict JSON response
   - response_format={"type": "json_object"} ✓
   
✅ Prompt skeleton embedded as constants
   - SYSTEM_PROMPT defined ✓
   - USER_PROMPT_TEMPLATE defined ✓
   
✅ Constraints in prompt
   - If found: excerpt, location, suggestion=null ✓
   - If not found: excerpt/location=null, suggestion present ✓
   - No party names, no dates in suggestions ✓
   
✅ Call implementation
   - _call_openai with system and user prompts ✓
   - analyze_standard formats and calls ✓
   
✅ Enforce JSON parse
   - _validate_json_response checks structure ✓
   - Validates required keys and types ✓
   
✅ On failure retry once with suffix
   - Catches ValueError from validation ✓
   - Retries with "\n\nReturn ONLY valid JSON." ✓
   - Only one manual retry for JSON issues ✓

STATUS: ✅ COMPLETE
All requirements from the OpenAI call prompt template satisfied.
Implementation tested with no syntax errors.
Ready for integration testing with live OpenAI API.
"""

if __name__ == '__main__':
    print(__doc__)
