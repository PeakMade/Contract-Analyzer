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
    
    # Retry on 429/503
    if response.status_code in (429, 503):
        logger.warning(f"Received {response.status_code} from SharePoint, will retry")
        response.raise_for_status()
    
    response.raise_for_status()
    return response.json()


def get_preferred_standards() -> dict[str, str]:
    """
    Load preferred (gold standard) clauses from SharePoint list.
    
    Returns a dictionary mapping standard names to their preferred clause text.
    On failure, returns empty dict and logs a warning (non-fatal).
    
    Returns:
        Dictionary like {"Indemnification": "INDEMNIFICATION. ...", ...}
    """
    try:
        # Get configuration
        list_id = os.getenv('PREFERRED_STANDARDS_LIST_ID')
        if not list_id:
            logger.warning("PREFERRED_STANDARDS_LIST_ID not configured, skipping preferred standards lookup")
            return {}
        
        # Get token
        token = _get_bearer_token()
        if not token:
            logger.warning("No bearer token available, skipping preferred standards lookup")
            return {}
        
        # Fetch from SharePoint
        logger.info(f"Fetching preferred standards from SharePoint list: {list_id}")
        response_data = _fetch_preferred_standards_list(token, list_id)
        
        # Parse response
        standards_dict = {}
        items = response_data.get('value', [])
        
        for item in items:
            fields = item.get('fields', {})
            
            # Extract standard name and clause text
            # Adjust field names based on your SharePoint list schema
            standard_name = fields.get('Title') or fields.get('StandardName')
            clause_text = fields.get('ClauseText') or fields.get('PreferredClause')
            
            if standard_name and clause_text:
                standards_dict[standard_name] = clause_text
                logger.debug(f"Loaded preferred standard: {standard_name}")
        
        logger.info(f"Loaded {len(standards_dict)} preferred standards from SharePoint")
        return standards_dict
        
    except ValueError as e:
        logger.warning(f"Configuration error for preferred standards: {e}")
        return {}
    except requests.RequestException as e:
        logger.warning(f"Failed to fetch preferred standards from SharePoint: {type(e).__name__}")
        return {}
    except Exception as e:
        logger.warning(f"Unexpected error loading preferred standards: {type(e).__name__}")
        return {}
