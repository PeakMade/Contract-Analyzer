"""
Check SharePoint Log List Fields
This script queries the SharePoint list to see all available fields and their internal names
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

import requests

def get_access_token():
    """Get access token from Microsoft"""
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
    
    response = requests.post(token_url, data=token_data)
    if response.status_code == 200:
        return response.json().get('access_token')
    else:
        print(f"Failed to get token: {response.status_code}")
        print(response.text)
        return None

def check_list_fields():
    """Check all fields in the log list"""
    print("\n" + "="*80)
    print("SHAREPOINT LOG LIST - FIELD INSPECTION")
    print("="*80)
    
    # Get configuration
    site_id = os.getenv('O365_SITE_ID')
    log_list_id = os.getenv('SP_LOG_LIST_ID')
    
    print(f"\nSite ID: {site_id}")
    print(f"List ID: {log_list_id}")
    
    # Get access token
    print("\nGetting access token...")
    access_token = get_access_token()
    
    if not access_token:
        print("Failed to get access token")
        return False
    
    print(f"✓ Token acquired (length: {len(access_token)})")
    
    # Query the list columns
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/json'
    }
    
    # Get list columns
    columns_url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{log_list_id}/columns"
    
    print(f"\nQuerying list columns...")
    print(f"URL: {columns_url}")
    
    response = requests.get(columns_url, headers=headers)
    
    print(f"Response status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        columns = data.get('value', [])
        
        print(f"\n{'='*80}")
        print(f"FOUND {len(columns)} COLUMNS IN THE LIST")
        print(f"{'='*80}")
        
        # Sort by display name
        columns_sorted = sorted(columns, key=lambda x: x.get('displayName', ''))
        
        print(f"\n{'Display Name':<30} {'Internal Name':<40} {'Type':<20}")
        print(f"{'-'*30} {'-'*40} {'-'*20}")
        
        for col in columns_sorted:
            display_name = col.get('displayName', 'N/A')
            internal_name = col.get('name', 'N/A')
            col_type = col.get('columnGroup', 'N/A')
            
            print(f"{display_name:<30} {internal_name:<40} {col_type:<20}")
        
        print(f"\n{'='*80}")
        print("FIELDS YOU NEED TO USE IN CODE:")
        print(f"{'='*80}")
        
        # Find the specific fields we care about
        target_fields = ['UserEmail', 'UserDisplayName', 'Contract name', 'Contract Name', 
                        'TimeofAnalysis', 'AnalysisSuccessorFail', 'Title']
        
        for target in target_fields:
            for col in columns:
                display = col.get('displayName', '')
                internal = col.get('name', '')
                if display.lower() == target.lower() or internal.lower() == target.lower():
                    print(f"✓ '{display}' -> Use: '{internal}'")
        
        return True
    else:
        print(f"Failed to get columns: {response.status_code}")
        print(response.text)
        return False

if __name__ == '__main__':
    try:
        check_list_fields()
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
