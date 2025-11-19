"""
Test Activity Logger
Quick test to verify SharePoint logging is working
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

print("\n" + "="*80)
print("ACTIVITY LOGGER TEST - ENVIRONMENT CHECK")
print("="*80)

# Check all required environment variables
required_vars = {
    'SP_SITE_URL': os.getenv('SP_SITE_URL'),
    'SP_LOG_LIST_ID': os.getenv('SP_LOG_LIST_ID'),
    'O365_SITE_ID': os.getenv('O365_SITE_ID'),
    'O365_CLIENT_ID': os.getenv('O365_CLIENT_ID'),
    'O365_CLIENT_SECRET': os.getenv('O365_CLIENT_SECRET'),
    'TENANT_ID': os.getenv('TENANT_ID')
}

print("\nEnvironment Variables:")
for key, value in required_vars.items():
    if value:
        if 'SECRET' in key:
            print(f"  ✓ {key}: ***hidden***")
        elif 'ID' in key or 'URL' in key:
            print(f"  ✓ {key}: {value[:30]}..." if len(value) > 30 else f"  ✓ {key}: {value}")
        else:
            print(f"  ✓ {key}: Set")
    else:
        print(f"  ✗ {key}: NOT SET")

# Now test with app context
print("\n" + "="*80)
print("TESTING WITH FLASK APP CONTEXT")
print("="*80)

from main import app

def test_logging():
    """Test the activity logger with real Flask app context"""
    
    with app.test_request_context():
        from flask import session
        
        # Get a real access token
        print("\n[TEST] Step 1: Getting access token...")
        
        # We need to get a token from Microsoft
        import requests
        
        tenant_id = os.getenv('TENANT_ID')
        client_id = os.getenv('O365_CLIENT_ID')
        client_secret = os.getenv('O365_CLIENT_SECRET')
        
        token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        token_data = {
            'grant_type': 'client_credentials',
            'client_id': client_id,
            'client_secret': client_secret,
            'scope': 'https://graph.microsoft.com/.default'
        }
        
        print(f"[TEST] Requesting token from: {token_url}")
        token_response = requests.post(token_url, data=token_data)
        
        if token_response.status_code == 200:
            token_result = token_response.json()
            access_token = token_result.get('access_token')
            print(f"[TEST] ✓ Token acquired! Length: {len(access_token)}")
            
            # Set up session with token
            session['access_token'] = access_token
            session['user_email'] = 'pbatson@peakmade.com'
            session['user_name'] = 'Patrick Batson'
            
            print(f"[TEST] ✓ Session configured")
            
            # Now test the logger
            print("\n[TEST] Step 2: Testing logger...")
            
            from app.services.activity_logger import logger
            
            contract_name = "TEST - Sample Contract.pdf"
            
            result = logger.log_analysis_success(
                contract_name=contract_name,
                user_email='pbatson@peakmade.com',
                user_display_name='Patrick Batson'
            )
            
            if result:
                print("\n" + "="*80)
                print("✅✅✅ SUCCESS! Log entry created in SharePoint!")
                print("="*80)
                print(f"Contract: {contract_name}")
                print(f"Status: Success")
                print(f"User: Patrick Batson (pbatson@peakmade.com)")
                print(f"\nCheck your SharePoint list to verify:")
                print(f"List ID: {os.getenv('SP_LOG_LIST_ID')}")
                print("="*80)
            else:
                print("\n" + "="*80)
                print("❌❌❌ FAILED - Could not create log entry")
                print("="*80)
                print("Check the debug output above for details")
                print("="*80)
            
            return result
        else:
            print(f"[TEST] ✗ Failed to get token. Status: {token_response.status_code}")
            print(f"[TEST] Response: {token_response.text}")
            return False

if __name__ == '__main__':
    try:
        success = test_logging()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[TEST] ✗✗✗ Exception during test: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
