"""
SharePoint restricted terms service.
Loads restricted verbiage rules from a SharePoint list.
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
        logger.warning("No access token found in session for restricted terms lookup")
    return token or ""


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((requests.HTTPError,)),
    reraise=True
)
def _fetch_restricted_terms_list(token: str, list_id: str) -> dict:
    """
    Fetch restricted terms from SharePoint list via Microsoft Graph.
    
    Args:
        token: Bearer token for authentication.
        list_id: SharePoint list ID containing restricted terms.
    
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
        '$top': 500  # Adjust if you have more than 500 restricted terms
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
        logger.error("Token expired when fetching restricted terms - session invalid")
        raise PermissionError("SESSION_EXPIRED: Token expired, user must log in again")
    
    # Retry on 429/503
    if response.status_code in (429, 503):
        logger.warning(f"Received {response.status_code} from SharePoint, will retry")
        response.raise_for_status()
    
    response.raise_for_status()
    return response.json()


def get_restricted_terms() -> list[dict]:
    """
    Load restricted terms/verbiage rules from SharePoint list.
    
    Returns a list of dictionaries with term, intent, and verbiage patterns.
    On failure, returns empty list and logs a warning (non-fatal).
    
    Returns:
        List like [
            {
                "term": "Unlimited Liability",
                "intent": "Avoid unlimited liability exposure",
                "verbiage": "shall be liable without limit|unlimited liability|no cap on liability",
                "explanation": "Company should limit liability to contract value"
            },
            ...
        ]
    """
    try:
        list_id = os.getenv('RESTRICTED_TERMS_LIST_ID')
        if not list_id:
            logger.warning("RESTRICTED_TERMS_LIST_ID not configured in environment")
            return []
        
        token = _get_bearer_token()
        if not token:
            logger.warning("No access token available - skipping restricted terms check")
            return []
        
        print(f"\n[RESTRICTED TERMS] Fetching from SharePoint list...")
        data = _fetch_restricted_terms_list(token, list_id)
        
        items = data.get('value', [])
        restricted_terms = []
        
        for item in items:
            fields = item.get('fields', {})
            
            # Extract fields from SharePoint
            # Adjust field names based on your actual SharePoint column names
            term = fields.get('Title')  # Assuming Title is the term name
            intent = fields.get('Intent', '')  # Intent/reason for restriction
            verbiage = fields.get('Verbiage', '')  # Exact/pattern verbiage to match
            explanation = fields.get('Explanation', '')  # What to do instead
            
            if term and verbiage:
                restricted_terms.append({
                    'term': term,
                    'intent': intent,
                    'verbiage': verbiage,
                    'explanation': explanation
                })
        
        print(f"[RESTRICTED TERMS] Loaded {len(restricted_terms)} restricted terms from SharePoint")
        logger.info(f"Loaded {len(restricted_terms)} restricted terms")
        
        return restricted_terms
        
    except PermissionError as e:
        if "SESSION_EXPIRED" in str(e):
            logger.error("Session expired - cannot fetch restricted terms")
            return []
        raise
    except Exception as e:
        logger.warning(f"Failed to load restricted terms from SharePoint: {e}")
        print(f"[RESTRICTED TERMS] Warning: Could not load from SharePoint - {e}")
        return []


def get_restricted_terms_dict() -> dict:
    """
    Get restricted terms as a dictionary keyed by term name.
    
    Returns:
        Dict like {
            "Unlimited Liability": {
                "intent": "...",
                "verbiage": "...",
                "explanation": "..."
            }
        }
    """
    terms_list = get_restricted_terms()
    return {
        term['term']: {
            'intent': term['intent'],
            'verbiage': term['verbiage'],
            'explanation': term['explanation']
        }
        for term in terms_list
    }
