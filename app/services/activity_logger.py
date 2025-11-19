"""
Activity Logger Service
Logs user activities to SharePoint list for auditing and tracking
"""

import os
import requests
from datetime import datetime
from flask import session


class ActivityLogger:
    """Service for logging user activities to SharePoint"""
    
    def __init__(self):
        self.site_url = os.getenv('SP_SITE_URL')
        self.log_list_id = os.getenv('SP_LOG_LIST_ID')
        self.tenant_id = os.getenv('TENANT_ID')
    
    def _get_headers(self):
        """Get authorization headers for SharePoint API"""
        try:
            # Get access token from session (same pattern as other services)
            access_token = session.get('access_token')
            print(f"[ActivityLogger] DEBUG: Session keys: {list(session.keys())}")
            print(f"[ActivityLogger] DEBUG: Has access_token: {bool(access_token)}")
            if access_token:
                print(f"[ActivityLogger] DEBUG: Token length: {len(access_token)}")
                print(f"[ActivityLogger] DEBUG: Token prefix: {access_token[:20]}...")
            
            if not access_token:
                print(f"[ActivityLogger] ERROR: No access token in session")
                return None
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
            print(f"[ActivityLogger] DEBUG: Headers created successfully")
            return headers
        except Exception as e:
            print(f"[ActivityLogger] ERROR: Exception getting headers: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def log_analysis(self, contract_name, status='Success', user_email=None, user_display_name=None):
        """
        Log a contract analysis activity to SharePoint
        
        Args:
            contract_name: Name of the contract analyzed
            status: 'Success' or 'Fail'
            user_email: User's email (defaults to session user)
            user_display_name: User's display name (defaults to session user)
        
        Returns:
            bool: True if logged successfully, False otherwise
        """
        print(f"\n{'='*60}")
        print(f"[ActivityLogger] START LOGGING ATTEMPT")
        print(f"{'='*60}")
        
        try:
            # Get user info from session if not provided
            print(f"[ActivityLogger] DEBUG: Getting user info...")
            print(f"[ActivityLogger] DEBUG: Provided user_email: {user_email}")
            print(f"[ActivityLogger] DEBUG: Provided user_display_name: {user_display_name}")
            
            if not user_email:
                user = session.get('user', {})
                user_email = user.get('email') or session.get('user_email', 'unknown@unknown.com')
                print(f"[ActivityLogger] DEBUG: Extracted user_email from session: {user_email}")
            
            if not user_display_name:
                user = session.get('user', {})
                user_display_name = user.get('name') or session.get('user_name', 'Unknown User')
                print(f"[ActivityLogger] DEBUG: Extracted user_display_name from session: {user_display_name}")
            
            # Prepare the log entry data using Graph API format
            # IMPORTANT: Must use INTERNAL field names from SharePoint, not display names
            # See check_log_list_fields.py output for mapping
            timestamp = datetime.utcnow().isoformat() + 'Z'
            log_data = {
                'fields': {
                    'Title': contract_name,  # Title is the default required field
                    'UserEmail': user_email,  # Internal name: UserEmail
                    'UserDisplayName': user_display_name,  # Internal name: UserDisplayName
                    'Contractname': contract_name,  # Internal name: Contractname (no space!)
                    'TimeofAnalysis': timestamp,  # Internal name: TimeofAnalysis
                    'AnalysisSuccessorFail': status  # Internal name: AnalysisSuccessorFail
                }
            }
            
            print(f"[ActivityLogger] DEBUG: Log data prepared:")
            print(f"[ActivityLogger]   - Title: {contract_name}")
            print(f"[ActivityLogger]   - UserEmail: {user_email}")
            print(f"[ActivityLogger]   - UserDisplayName: {user_display_name}")
            print(f"[ActivityLogger]   - Contractname: {contract_name}")
            print(f"[ActivityLogger]   - TimeofAnalysis: {timestamp}")
            print(f"[ActivityLogger]   - AnalysisSuccessorFail: {status}")
            
            # Get authorization headers
            print(f"[ActivityLogger] DEBUG: Getting authorization headers...")
            headers = self._get_headers()
            if not headers:
                print("[ActivityLogger] ERROR: Failed to get authorization headers")
                return False
            
            # Get site ID from environment
            print(f"[ActivityLogger] DEBUG: Getting site ID from environment...")
            site_id = os.getenv('O365_SITE_ID')
            print(f"[ActivityLogger] DEBUG: Site ID: {site_id}")
            print(f"[ActivityLogger] DEBUG: Log List ID: {self.log_list_id}")
            
            if not site_id:
                print("[ActivityLogger] ERROR: O365_SITE_ID not found in environment")
                return False
            
            # Use Microsoft Graph API endpoint for list items (compatible with Graph API token)
            endpoint = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{self.log_list_id}/items"
            
            print(f"[ActivityLogger] DEBUG: Endpoint URL: {endpoint}")
            print(f"[ActivityLogger] DEBUG: Sending POST request...")
            
            # Send POST request to create log entry
            response = requests.post(endpoint, json=log_data, headers=headers, timeout=10)
            
            print(f"[ActivityLogger] DEBUG: Response status: {response.status_code}")
            print(f"[ActivityLogger] DEBUG: Response headers: {dict(response.headers)}")
            print(f"[ActivityLogger] DEBUG: Response body: {response.text[:500]}")
            
            if response.status_code in [200, 201]:
                print(f"[ActivityLogger] ✓✓✓ SUCCESS! Logged analysis for: {contract_name}")
                print(f"{'='*60}\n")
                return True
            else:
                print(f"[ActivityLogger] ✗✗✗ FAILED! Status: {response.status_code}")
                print(f"[ActivityLogger] Full response: {response.text}")
                print(f"{'='*60}\n")
                return False
                
        except Exception as e:
            print(f"[ActivityLogger] ✗✗✗ EXCEPTION: {e}")
            import traceback
            traceback.print_exc()
            print(f"{'='*60}\n")
            return False
    
    def log_analysis_start(self, contract_name, user_email=None, user_display_name=None):
        """Log when an analysis starts (can be used for tracking in-progress analyses)"""
        return self.log_analysis(contract_name, status='In Progress', user_email=user_email, user_display_name=user_display_name)
    
    def log_analysis_success(self, contract_name, user_email=None, user_display_name=None):
        """Log when an analysis completes successfully"""
        return self.log_analysis(contract_name, status='Success', user_email=user_email, user_display_name=user_display_name)
    
    def log_analysis_failure(self, contract_name, user_email=None, user_display_name=None):
        """Log when an analysis fails"""
        return self.log_analysis(contract_name, status='Fail', user_email=user_email, user_display_name=user_display_name)


# Create a singleton instance
logger = ActivityLogger()
