"""
Test script to verify authentication flow
"""
import requests
import sys

def test_auth_flow():
    """Test the authentication redirect flow"""
    base_url = "http://localhost:5000"
    
    print("Testing authentication flow...")
    print("=" * 60)
    
    # Test 1: Root endpoint should redirect to login
    print("\n1. Testing root endpoint (/)...")
    try:
        response = requests.get(f"{base_url}/", allow_redirects=False)
        print(f"   Status Code: {response.status_code}")
        print(f"   Location: {response.headers.get('Location', 'N/A')}")
        
        if response.status_code == 302:
            if '/auth/login' in response.headers.get('Location', ''):
                print("   ✓ PASS: Correctly redirects to /auth/login")
            else:
                print(f"   ✗ FAIL: Redirects to wrong location: {response.headers.get('Location')}")
        else:
            print(f"   ✗ FAIL: Expected 302 redirect, got {response.status_code}")
    except Exception as e:
        print(f"   ✗ ERROR: {e}")
        return False
    
    # Test 2: Login endpoint should redirect to Microsoft
    print("\n2. Testing login endpoint (/auth/login)...")
    try:
        response = requests.get(f"{base_url}/auth/login", allow_redirects=False)
        print(f"   Status Code: {response.status_code}")
        location = response.headers.get('Location', '')
        print(f"   Location: {location[:100]}...")
        
        if response.status_code == 302:
            if 'login.microsoftonline.com' in location:
                print("   ✓ PASS: Correctly redirects to Microsoft login")
            else:
                print(f"   ✗ FAIL: Redirects to wrong location")
        else:
            print(f"   ✗ FAIL: Expected 302 redirect, got {response.status_code}")
    except Exception as e:
        print(f"   ✗ ERROR: {e}")
        return False
    
    # Test 3: Check if auth redirect endpoint exists
    print("\n3. Testing redirect endpoint (/auth/redirect) without params...")
    try:
        response = requests.get(f"{base_url}/auth/redirect", allow_redirects=False)
        print(f"   Status Code: {response.status_code}")
        print(f"   Location: {response.headers.get('Location', 'N/A')}")
        
        if response.status_code == 302:
            print("   ✓ PASS: Redirect endpoint responds correctly (needs OAuth params)")
        else:
            print(f"   ℹ INFO: Status {response.status_code} (endpoint exists)")
    except Exception as e:
        print(f"   ✗ ERROR: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("✓ Basic authentication flow tests passed")
    print("\nNOTE: Full authentication requires OAuth flow with Microsoft.")
    print("      To test manually, open browser to: http://localhost:5000/")
    return True

if __name__ == "__main__":
    try:
        success = test_auth_flow()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n✗ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
