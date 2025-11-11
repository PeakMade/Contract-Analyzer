"""
QUICK REFERENCE - OpenAI LLM Client
====================================

FILE: app/services/llm_client.py (200 lines)

KEY CONSTANTS (Lines 18-32):
----------------------------
SYSTEM_PROMPT = "You are a legal contract analyst. Return ONLY valid JSON matching the schema."

USER_PROMPT_TEMPLATE = Template with {standard} and {contract_text} placeholders

KEY FUNCTION:
-------------
analyze_standard(text: str, standard: str) -> dict

Returns:
{
    "found": bool,
    "excerpt": str | None,
    "location": str | None,
    "suggestion": str | None
}

FLOW:
-----
1. Format prompt: USER_PROMPT_TEMPLATE.format(standard=..., contract_text=...)
2. Call: _call_openai(SYSTEM_PROMPT, user_prompt, model)
3. Validate: _validate_json_response(response_text)
4. On failure: Retry with "\n\nReturn ONLY valid JSON." suffix
5. Return: validated dict or raise RuntimeError

FEATURES:
---------
✅ Strict JSON response (response_format={"type": "json_object"})
✅ Embedded prompt templates as constants
✅ JSON validation with required keys check
✅ Retry once on parse failure with explicit instruction
✅ Auto-retry on API errors (rate limits) via @retry decorator
✅ 50k character contract text limit
✅ 30 second timeout, 600 max tokens

USAGE:
------
from app.services.llm_client import analyze_standard

result = analyze_standard(contract_text, "Indemnification")
# Returns: {"found": true/false, "excerpt": "...", "location": "...", "suggestion": "..."}

CONSTRAINTS (per prompt):
-------------------------
If found=true:
  - excerpt: exact clause snippet
  - location: "Section 5.2" or similar
  - suggestion: null

If found=false:
  - excerpt: null
  - location: null
  - suggestion: concise, legally neutral clause (no names, no dates)

STATUS: ✅ COMPLETE
"""

print(__doc__)
