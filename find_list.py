"""
Quick script to find the SharePoint list ID for "Preferred Contract Terms"
"""
import os
import requests
from dotenv import load_dotenv
from flask import Flask, session

# Load environment variables
load_dotenv()

def find_preferred_terms_list():
    """Find the list ID for 'Preferred Contract Terms'"""
    
    # You'll need to get a token from your session
    # For now, let's just construct the URL to query all lists
    site_id = os.getenv('O365_SITE_ID')
    
    print(f"Site ID: {site_id}")
    print(f"\nTo find your list ID, you need an access token.")
    print(f"Please run this in your browser console while logged into the app:\n")
    print(f"1. Open browser developer tools (F12)")
    print(f"2. Go to Application/Storage > Cookies")
    print(f"3. Find the session cookie")
    print(f"\nOR use the Graph Explorer:")
    print(f"https://developer.microsoft.com/en-us/graph/graph-explorer")
    print(f"\nQuery to run:")
    print(f"GET https://graph.microsoft.com/v1.0/sites/{site_id}/lists")
    print(f"\nLook for a list with displayName = 'Preferred Contract Terms'")
    print(f"Copy its 'id' field and update your .env file:")
    print(f"PREFERRED_STANDARDS_LIST_ID=<the-id-you-found>")

if __name__ == '__main__':
    find_preferred_terms_list()
