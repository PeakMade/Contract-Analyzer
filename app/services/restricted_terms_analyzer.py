"""
Restricted terms analyzer using GPT-4o-mini.
Scans contract text for problematic verbiage based on SharePoint rules.
"""
import logging
from typing import List, Dict
import re

logger = logging.getLogger(__name__)


def analyze_restricted_terms(text: str, restricted_terms: List[Dict], llm_client_func) -> dict:
    """
    Analyze contract text for restricted verbiage.
    
    Args:
        text: Full contract text
        restricted_terms: List of restricted term rules from SharePoint
        llm_client_func: LLM analysis function
        
    Returns:
        {
            'issues_found': bool,
            'issue_count': int,
            'issues': [
                {
                    'term': 'Unlimited Liability',
                    'excerpt': 'shall be liable without limit for any damages',
                    'location': 'Section 5, Paragraph 2',
                    'intent': 'Avoid unlimited liability exposure',
                    'explanation': 'Company should limit liability to contract value',
                    'severity': 'high'  # high, medium, low
                },
                ...
            ]
        }
    """
    if not restricted_terms:
        print(f"[RESTRICTED TERMS] No restricted terms configured - skipping check")
        return {'issues_found': False, 'issue_count': 0, 'issues': []}
    
    print(f"\n[RESTRICTED TERMS] Analyzing contract for {len(restricted_terms)} restricted terms...")
    
    issues = []
    
    for term_rule in restricted_terms:
        term_name = term_rule.get('term', '')
        intent = term_rule.get('intent', '')
        verbiage_pattern = term_rule.get('verbiage', '')
        explanation = term_rule.get('explanation', '')
        
        print(f"[RESTRICTED TERMS] Checking for: {term_name}")
        
        # First, do a quick regex check to see if any of the verbiage patterns exist
        # This is a fast pre-filter before calling GPT
        patterns = [p.strip() for p in verbiage_pattern.split('|') if p.strip()]
        found_pattern = False
        
        for pattern in patterns:
            # Case-insensitive search
            if re.search(re.escape(pattern), text, re.IGNORECASE):
                found_pattern = True
                print(f"[RESTRICTED TERMS]   ✗ Pattern match found: '{pattern[:50]}...'")
                break
        
        if not found_pattern:
            print(f"[RESTRICTED TERMS]   ✓ No pattern match")
            continue
        
        # Pattern found - use GPT to get context and confirm
        try:
            # Ask GPT to find and extract instances of this restricted verbiage
            prompt = f"""Analyze the following contract text for instances of restricted verbiage.

RESTRICTED TERM: {term_name}
INTENT: {intent}
VERBIAGE TO LOOK FOR: {verbiage_pattern}

Find all instances where the contract contains language matching the restricted verbiage pattern. Consider:
1. Exact matches of the verbiage
2. Semantically similar language with the same intent
3. Variations in wording that express the same problematic concept

For each instance found, extract:
- The exact text excerpt (50-100 words of context)
- The location/section where it appears

If no instances are found, respond with "NOT FOUND".

CONTRACT TEXT:
{text[:10000]}  

Respond in this format:
FOUND: [yes/no]
EXCERPT: [exact quote from contract]
LOCATION: [section/paragraph identifier]
"""
            
            result = llm_client_func(prompt)
            
            # Parse GPT response
            if 'NOT FOUND' in result.upper() or 'FOUND: NO' in result.upper():
                print(f"[RESTRICTED TERMS]   ✓ GPT confirmed no match")
                continue
            
            # Extract excerpt and location from GPT response
            excerpt_match = re.search(r'EXCERPT:\s*(.+?)(?=LOCATION:|$)', result, re.DOTALL | re.IGNORECASE)
            location_match = re.search(r'LOCATION:\s*(.+?)$', result, re.DOTALL | re.IGNORECASE)
            
            excerpt = excerpt_match.group(1).strip() if excerpt_match else verbiage_pattern[:100]
            location = location_match.group(1).strip() if location_match else 'See contract text'
            
            # Truncate if needed
            if len(excerpt) > 200:
                excerpt = excerpt[:200] + '...'
            if len(location) > 100:
                location = location[:100]
            
            issues.append({
                'term': term_name,
                'excerpt': excerpt,
                'location': location,
                'intent': intent,
                'explanation': explanation,
                'severity': 'high',  # All restricted terms are high severity
                'verbiage_pattern': verbiage_pattern  # Store for text highlighting
            })
            
            print(f"[RESTRICTED TERMS]   ✗ RESTRICTED TERM FOUND: {term_name}")
            
        except Exception as e:
            logger.warning(f"Error analyzing restricted term '{term_name}': {e}")
            print(f"[RESTRICTED TERMS]   ⚠ Error analyzing: {e}")
            continue
    
    print(f"[RESTRICTED TERMS] Analysis complete: {len(issues)} restricted terms found")
    
    return {
        'issues_found': len(issues) > 0,
        'issue_count': len(issues),
        'issues': issues
    }
