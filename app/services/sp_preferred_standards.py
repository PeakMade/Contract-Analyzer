"""
SharePoint preferred standards service.
Loads gold standard clauses from a SharePoint list.
"""
import os
import logging
import requests
from flask import session
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)


def _get_bearer_token() -> str:
    """
    Retrieve bearer token from Flask session.
    
    Returns:
        Bearer token string.
        
    Note:
        Returns empty string if token unavailable (non-fatal for this service).
    """
    token = session.get('access_token')
    if not token:
        logger.warning("No access token found in session for preferred standards lookup")
    return token or ""


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((requests.HTTPError,)),
    reraise=True
)
def _fetch_preferred_standards_list(token: str, list_id: str) -> dict:
    """
    Fetch preferred standards from SharePoint list via Microsoft Graph.
    
    Args:
        token: Bearer token for authentication.
        list_id: SharePoint list ID containing preferred standards.
    
    Returns:
        API response JSON.
    
    Raises:
        requests.HTTPError: On HTTP errors (will be retried by tenacity).
    """
    site_id = os.getenv('O365_SITE_ID', '')
    if not site_id:
        raise ValueError("O365_SITE_ID environment variable not configured")
    
    url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/items"
    params = {
        '$expand': 'fields',
        '$select': 'id,fields',
        '$top': 500  # Adjust if you have more than 500 standards
    }
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json'
    }
    
    response = requests.get(
        url,
        headers=headers,
        params=params,
        timeout=(5, 30)
    )
    
    # Check for token expiration (401 Unauthorized)
    if response.status_code == 401:
        logger.error("Token expired when fetching preferred standards - session invalid")
        raise PermissionError("SESSION_EXPIRED: Token expired, user must log in again")
    
    # Retry on 429/503
    if response.status_code in (429, 503):
        logger.warning(f"Received {response.status_code} from SharePoint, will retry")
        response.raise_for_status()
    
    response.raise_for_status()
    return response.json()


def get_preferred_standards() -> list[dict]:
    """
    Load preferred (gold standard) clauses from SharePoint list.
    
    Returns a list of dictionaries with standard names and their clause text.
    On failure, returns empty list and logs a warning (non-fatal).
    
    Returns:
        List like [
            {"standard": "Indemnification", "clause": "INDEMNIFICATION. ..."},
            {"standard": "Limitation of Liability", "clause": "..."}
        ]
    """
    try:
        # Get configuration
        list_id = os.getenv('PREFERRED_STANDARDS_LIST_ID')
        if not list_id:
            logger.warning("PREFERRED_STANDARDS_LIST_ID not configured, skipping preferred standards lookup")
            return []
        
        # Get token
        token = _get_bearer_token()
        if not token:
            logger.warning("No bearer token available, skipping preferred standards lookup")
            return []
        
        # Fetch from SharePoint
        logger.info(f"Fetching preferred standards from SharePoint list 'Preferred Contract Terms': {list_id}")
        print(f"DEBUG sp_preferred_standards: Fetching from list_id={list_id}")
        response_data = _fetch_preferred_standards_list(token, list_id)
        
        # Parse response
        standards_list = []
        items = response_data.get('value', [])
        print(f"DEBUG sp_preferred_standards: Received {len(items)} items from SharePoint")
        
        for item in items:
            fields = item.get('fields', {})
            print(f"DEBUG sp_preferred_standards: Item fields keys: {list(fields.keys())}")
            
            # Extract standard name and clause text
            # SharePoint columns: "Standard" and "Clause"
            standard_name = fields.get('Standard') or fields.get('Title')
            clause_text = fields.get('Clause') or fields.get('ClauseText')
            # Extract Security column (Yes/No field)
            is_security = fields.get('Security', False)
            
            print(f"DEBUG sp_preferred_standards: standard_name={standard_name}, clause_length={len(clause_text) if clause_text else 0}, is_security={is_security}")
            
            if standard_name and clause_text:
                standards_list.append({
                    'standard': standard_name,
                    'clause': clause_text,
                    'is_security': is_security
                })
                logger.debug(f"Loaded preferred standard: {standard_name} (security={is_security})")
            else:
                print(f"DEBUG sp_preferred_standards: SKIPPED - Missing data. Standard={bool(standard_name)}, Clause={bool(clause_text)}")
        
        logger.info(f"Loaded {len(standards_list)} preferred standards from SharePoint")
        print(f"DEBUG sp_preferred_standards: Returning {len(standards_list)} standards")
        return standards_list
        
    except PermissionError as e:
        # Token expired - DO NOT use fallback, force user to re-authenticate
        logger.error(f"Token expired fetching preferred standards: {e}")
        print(f"DEBUG sp_preferred_standards: PermissionError (token expired) - Re-raising to force login")
        raise  # Re-raise to propagate to calling code
    except ValueError as e:
        logger.warning(f"Configuration error for preferred standards: {e}")
        print(f"DEBUG sp_preferred_standards: ValueError - {e}")
        print(f"DEBUG sp_preferred_standards: Returning fallback standards")
        return _get_fallback_standards()
    except requests.RequestException as e:
        logger.warning(f"Failed to fetch preferred standards from SharePoint: {type(e).__name__}")
        print(f"DEBUG sp_preferred_standards: RequestException - {type(e).__name__}: {e}")
        print(f"DEBUG sp_preferred_standards: Returning fallback standards")
        return _get_fallback_standards()
    except Exception as e:
        logger.warning(f"Unexpected error loading preferred standards: {type(e).__name__}")
        print(f"DEBUG sp_preferred_standards: Exception - {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        print(f"DEBUG sp_preferred_standards: Returning fallback standards")
        return _get_fallback_standards()


def _get_fallback_standards() -> list[dict]:
    """
    Temporary fallback standards when SharePoint list is unavailable.
    Returns hardcoded standards with generic clause text.
    """
    print("WARNING: Using fallback standards. Please configure correct PREFERRED_STANDARDS_LIST_ID in .env")
    
    fallback = [
        "Indemnification",
        "Limitation of Liability", 
        "Term and Termination",
        "Confidentiality",
        "Intellectual Property",
        "Warranties",
        "Payment Terms",
        "Dispute Resolution",
        "Governing Law",
        "Force Majeure",
        "Assignment",
        "Notices",
        "Entire Agreement",
        "Severability",
        "Waiver",
        "Insurance Requirements",
        "Compliance with Laws",
        "Data Protection",
        "Audit Rights"
    ]
    
    return [
        {
            'standard': name,
            'clause': f"[PLACEHOLDER: Please configure SharePoint 'Preferred Contract Terms' list to load actual clause text for {name}]",
            'is_security': False
        }
        for name in fallback
    ]


def get_preferred_standards_dict() -> dict[str, str]:
    """
    Load preferred standards as a dictionary (for backward compatibility).
    
    Returns:
        Dictionary mapping standard names to clause text.
    """
    standards_list = get_preferred_standards()
    return {item['standard']: item['clause'] for item in standards_list}


def get_preferred_standards_by_category() -> dict:
    """
    Load preferred standards categorized by security flag.
    
    Returns:
        Dictionary with 'default' and 'security' lists.
    """
    all_standards = get_preferred_standards()
    
    categorized = {
        'default': [],
        'security': []
    }
    
    for standard in all_standards:
        if standard.get('is_security', False):
            categorized['security'].append(standard)
        else:
            categorized['default'].append(standard)
    
    return categorized
