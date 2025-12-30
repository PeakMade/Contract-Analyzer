# Authentication & Token Management Architecture

## Overview

This document provides a comprehensive guide to implementing OAuth 2.0 authentication with Microsoft Entra ID (Azure AD) using MSAL for delegated user permissions, automatic token refresh, and server-side session management. This architecture ensures seamless user experience while maintaining enterprise-grade security.

**Last Updated**: December 29, 2025  
**Implementation**: Contract Analyzer (Production)  
**Status**: ✅ Deployed and Tested  
**Framework**: Flask + MSAL + Flask-Session

---

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [OAuth Authentication Flow](#oauth-authentication-flow)
3. [Token Storage & Session Management](#token-storage--session-management)
4. [Automatic Token Refresh](#automatic-token-refresh)
5. [Keep-Alive Mechanism](#keep-alive-mechanism)
6. [Security Best Practices](#security-best-practices)
7. [Azure Deployment Configuration](#azure-deployment-configuration)
8. [Implementation Takeaways](#implementation-takeaways)
9. [Troubleshooting Guide](#troubleshooting-guide)

---

## Architecture Overview

### Authentication Pattern: Server-Side Confidential Client

We implement **OAuth 2.0 Authorization Code Flow** with **delegated permissions**, where users authenticate as themselves (not as a service principal).

### Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Authentication Library** | MSAL 1.25.0 | Microsoft Authentication Library for Python |
| **Session Backend** | Flask-Session 0.6.0 | Server-side session storage (filesystem) |
| **Token Type** | OAuth 2.0 Bearer | Delegated user permissions |
| **Session Strategy** | Sliding sessions | 8-hour lifetime with auto-renewal |
| **Token Refresh** | Automatic | Refreshes when <5 minutes remaining |
| **Cache Backend** | cachelib >=0.9.0 | Flask-Session filesystem support |

### Architecture Diagram

```
┌─────────────┐         ┌──────────────────┐         ┌─────────────────┐         ┌─────────────┐
│   User      │         │  Flask App       │         │  Microsoft      │         │  SharePoint │
│   Browser   │         │  (Confidential)  │         │  Entra ID       │         │  Graph API  │
└──────┬──────┘         └────────┬─────────┘         └────────┬────────┘         └──────┬──────┘
       │                         │                            │                         │
       │  1. Visit / (protected) │                            │                         │
       ├────────────────────────>│                            │                         │
       │                         │                            │                         │
       │  2. Redirect to login   │                            │                         │
       │<────────────────────────┤                            │                         │
       │                         │                            │                         │
       │  3. Redirect to Microsoft (state/PKCE)              │                         │
       ├────────────────────────────────────────────────────>│                         │
       │                         │                            │                         │
       │  4. User authenticates (MFA, Conditional Access)    │                         │
       │<───────────────────────────────────────────────────>│                         │
       │                         │                            │                         │
       │  5. Redirect with authorization code                │                         │
       │<────────────────────────────────────────────────────┤                         │
       │                         │                            │                         │
       │  6. Submit code         │                            │                         │
       ├────────────────────────>│                            │                         │
       │                         │  7. Exchange code + secret │                         │
       │                         ├───────────────────────────>│                         │
       │                         │                            │                         │
       │                         │  8. Return tokens:         │                         │
       │                         │     - Access Token         │                         │
       │                         │     - Refresh Token        │                         │
       │                         │     - ID Token             │                         │
       │                         │<───────────────────────────┤                         │
       │                         │                            │                         │
       │                         │  9. Query admin list       │                         │
       │                         ├─────────────────────────────────────────────────────>│
       │                         │<─────────────────────────────────────────────────────┤
       │                         │                            │                         │
       │  10. Set session cookie │                            │                         │
       │<────────────────────────┤                            │                         │
       │                         │                            │                         │
       │  11. Make API calls     │                            │                         │
       ├────────────────────────>│  12. Use access token     │                         │
       │                         ├─────────────────────────────────────────────────────>│
       │                         │<─────────────────────────────────────────────────────┤
       │  13. Return data        │                            │                         │
       │<────────────────────────┤                            │                         │
```

### Why This Approach?

✅ **Delegated Permissions**: Users authenticate as themselves, preserving audit trails  
✅ **Conditional Access Compatible**: Works with MFA, device compliance, location policies  
✅ **Secure**: Client secret never exposed to browser  
✅ **Automatic Token Refresh**: Long-lived refresh tokens enable seamless renewal  
✅ **Enterprise-Grade**: Same pattern as Microsoft 365, Teams, SharePoint

---

## OAuth Authentication Flow

### Step 1: Initial Login Request
**File**: `app/routes/auth_routes.py` → `/auth/login`

**Process**:
1. User clicks "Login" or visits protected route
2. Application clears any existing session data
3. Generates CSRF state token (32-byte random string)
4. Stores state token in session
5. Redirects to Microsoft login page

**Code Behavior**:
```python
# Line 37: Clear session to prevent conflicts
session.clear()

# Line 41-42: Generate and store CSRF token
state = secrets.token_urlsafe(32)
session["oauth_state"] = state

# Line 48-51: Build authorization URL
auth_url = msal_app.get_authorization_request_url(
    scopes=["User.Read", "Files.ReadWrite.All", "Sites.ReadWrite.All"],
    redirect_uri=REDIRECT_URI,
    state=state,
    prompt="select_account"
)
```

**Scopes Requested**:
- `User.Read`: Get user profile information
- `Files.ReadWrite.All`: Access SharePoint files
- `Sites.ReadWrite.All`: Access SharePoint lists
- `offline_access`: **Automatically added by MSAL** (DO NOT pass explicitly)

**Critical Note**: MSAL automatically includes `offline_access` scope. Passing it explicitly causes a `frozenset` error.

---

### Step 2: OAuth Callback & Token Exchange
**File**: `app/routes/auth_routes.py` → `/auth/redirect`

**Process**:
1. Microsoft redirects back with authorization code
2. Validate CSRF state token (prevents CSRF attacks)
3. Exchange authorization code for tokens
4. Retrieve user profile from Microsoft Graph
5. Check domain restriction (`@peakmade.com` only)
6. Store tokens and user data in session
7. Check admin status via SharePoint list
8. Log user login to SharePoint activity log

**Token Exchange**:
```python
# Line 109-113: Exchange code for tokens
result = msal_app.acquire_token_by_auth_code(
    code,
    scopes=["User.Read", "Files.ReadWrite.All", "Sites.ReadWrite.All"],
    redirect_uri=REDIRECT_URI
)
```

**Response Contains**:
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJ...",  // JWT token, ~2700 chars
  "refresh_token": "1.ARsAnNIM...",          // Refresh token, ~800 chars
  "expires_in": 3599,                         // Seconds until expiration
  "token_type": "Bearer",
  "scope": "User.Read Files.ReadWrite.All Sites.ReadWrite.All",
  "id_token": "eyJ0eXAiOiJKV1QiLCJ..."       // User identity claims
}
```

**Session Data Stored**:
```python
# Lines 155-172: Store in Flask session
session['access_token'] = result['access_token']
session['refresh_token'] = result['refresh_token']
session['token_expires_at'] = token_expires_at.isoformat()  # UTC timestamp
session['user_name'] = user_info.get('displayName')
session['user_email'] = email
session['is_admin'] = admin_status  # Determined via SharePoint list query
```

---

## Token Storage & Session Management

### Flask-Session Configuration
**File**: `main.py` → Lines 33-42

**Storage Backend**: Filesystem (cachelib)

**Configuration**:
```python
session_dir_path = '/home/flask_session' if os.path.exists('/home') else './flask_session'

app.config.update(
    SESSION_TYPE='filesystem',
    SESSION_FILE_DIR=session_dir_path,
    SESSION_PERMANENT=True,
    PERMANENT_SESSION_LIFETIME=timedelta(hours=8),
    SESSION_REFRESH_EACH_REQUEST=True,  # Sliding session
    SESSION_USE_SIGNER=False  # Disabled due to Python 3.14 compatibility
)
```

**Key Settings**:
- **SESSION_TYPE='filesystem'**: Stores sessions as files on server (not in cookies)
- **SESSION_PERMANENT=True**: Sessions persist across browser restarts
- **PERMANENT_SESSION_LIFETIME=8 hours**: Session expires after 8 hours of inactivity
- **SESSION_REFRESH_EACH_REQUEST=True**: Session timeout resets on every request (sliding window)

---

### Session File Structure

**File Location**:
- **Local**: `./flask_session/`
- **Azure**: `/home/flask_session/`

**Filename Generation**:
```python
# Internal Flask-Session logic:
session_id = "UKOI55yQ8hp10Dt6VzgbkqfyHevcWEcIal8MVX22MHE"  # Random base64 string
store_id = "session:" + session_id  # Prepend default prefix
filename = hashlib.md5(store_id.encode()).hexdigest()  # MD5 hash

# Result: flask_session/534b91e6cd82009c854c1beb8a5cf3e6
```

**Session Cookie**:
```
Set-Cookie: session=UKOI55yQ8hp10Dt6VzgbkqfyHevcWEcIal8MVX22MHE; 
            Path=/; 
            HttpOnly; 
            SameSite=Lax
```

**Cookie Properties**:
- **HttpOnly**: Not accessible via JavaScript (prevents XSS)
- **SameSite=Lax**: Allows same-site iframe access, blocks CSRF
- **Secure**: Enabled in Azure (HTTPS only)

---

### Session Isolation & Security

**How Users Access Only Their Own Sessions**:

1. **Unique Session ID**: Cryptographically random (10^77 possible combinations)
2. **Browser Cookie**: Session ID stored in user's browser only
3. **Server-Side Files**: Session data stored on server, not user machine
4. **One-Way Hash**: Session ID → Filename is irreversible (MD5 with prefix)
5. **File System Isolation**: Each instance has own `/home/` directory

**Attack Prevention**:
| Attack Vector | Protection |
|---------------|------------|
| Session ID guessing | 10^77 combinations, random generation |
| Cookie tampering | Cookie integrity (Flask validates) |
| Cross-user access | Filesystem isolation, unique filenames |
| Session fixation | Session ID regenerated after login (not implemented yet) |
| XSS token theft | HttpOnly cookie (JavaScript can't read) |

---

### Session Cleanup Strategy

**File**: `main.py` → Lines 48-74

**Cleanup Logic**:
- **Runs**: On app startup only
- **Criteria**: Deletes files >9 hours old (8h session + 1h safety buffer)
- **Safe for Active Users**: File modification time = last access time
- **Timezone**: Uses UTC to prevent clock skew issues

**Why Files Accumulate**:
- Each `/auth/login` call creates a new session file (even if login not completed)
- `session.clear()` does NOT delete the underlying file
- Abandoned sessions remain until cleanup runs

**Cleanup Code**:
```python
def cleanup_old_sessions():
    session_lifetime_hours = 8
    safety_buffer_hours = 1
    cutoff_time = datetime.now(tz.utc) - timedelta(hours=9)
    
    for session_file in session_dir.glob('*'):
        file_mtime = datetime.fromtimestamp(session_file.stat().st_mtime, tz=tz.utc)
        
        if file_mtime < cutoff_time:
            session_file.unlink()  # Delete old file
```

---

## Token Refresh Strategy

### Overview
**File**: `app/auth/token_utils.py`

**Goal**: Keep users logged in by automatically refreshing access tokens before they expire, using the refresh token.

**Key Functions**:
1. `token_expiring_soon(skew_seconds=300)` - Checks if token expires within 5 minutes
2. `refresh_access_token()` - Exchanges refresh token for new access token
3. `ensure_fresh_access_token()` - Main entry point called before API operations

---

### Token Expiration Detection

**Function**: `token_expiring_soon(skew_seconds=300)`

**Logic**:
```python
# Get token expiration from session
token_expires_at = datetime.fromisoformat(session.get('token_expires_at'))

# Calculate time until expiration
time_until_expiry = token_expires_at - datetime.now(tz.utc)

# Check if within threshold (default 5 minutes)
return time_until_expiry.total_seconds() < skew_seconds
```

**Why 5 Minutes?**
- Network delays can take 1-2 seconds
- Token requests might queue during high load
- Prevents race condition where token expires during API call
- Buffer allows graceful token replacement

---

### Token Refresh Process

**Function**: `refresh_access_token()`

**Process**:
1. Retrieve refresh token from session
2. Call MSAL `acquire_token_by_refresh_token()`
3. Microsoft validates refresh token
4. Microsoft issues new access token + new refresh token (rolling refresh)
5. Update session with new tokens

**Code**:
```python
refresh_token = session.get('refresh_token')

# MSAL handles the OAuth refresh grant
result = msal_app.acquire_token_by_refresh_token(
    refresh_token,
    scopes=["User.Read", "Files.ReadWrite.All", "Sites.ReadWrite.All"]
)

if "access_token" in result:
    # Update session with new tokens
    session['access_token'] = result['access_token']
    session['token_expires_at'] = new_expiry.isoformat()
    
    # Rolling refresh: New refresh token issued
    if 'refresh_token' in result:
        session['refresh_token'] = result['refresh_token']
```

**Rolling Refresh Behavior**:
- Azure AD issues a **new refresh token** with each refresh
- Old refresh token is invalidated
- This allows indefinite login for active users
- Inactive users forced to re-authenticate after refresh token expires

**Refresh Token Lifetime**:
- **Default**: 90 days (configurable in Azure AD)
- **Your Environment**: ~1 hour (unusual, check Azure AD token policies)
- **Effect**: Users must re-login after 1 hour even if active

---

### Error Handling

**Common Errors**:
```python
# Expired refresh token
if "error" in result and result["error"] == "invalid_grant":
    # AADSTS50173: Token expired
    # AADSTS70000: Invalid token
    raise AuthRequired("Please log in again")

# Network errors
except Exception as e:
    logger.error(f"Token refresh failed: {e}")
    raise AuthRequired("Authentication required")
```

---

### Integration Points

**Where Token Refresh is Called**:

1. **Before Every Protected Route** (`main.py` → index, submit_contract, etc.)
   ```python
   @app.route('/')
   @login_required
   def index():
       ensure_fresh_access_token()
       # ... rest of route logic
   ```

2. **Before SharePoint API Calls** (`app/services/sharepoint_service.py`)
   ```python
   def _ensure_valid_token(self):
       ensure_fresh_access_token()
       return session['access_token']
   ```

3. **Keep-Alive Endpoint** (`app/routes/auth_routes.py` → `/auth/ping`)
   ```python
   @auth_bp.route('/ping')
   def ping():
       ensure_fresh_access_token()
       return jsonify({'status': 'ok'}), 200
   ```

**Result**: Tokens are proactively refreshed across all API interactions, preventing mid-request expiration.

---

## Keep-Alive Mechanism

### Frontend JavaScript Implementation
**File**: `app/templates/index.html` → Lines 1205-1244

**Purpose**: Keep user sessions active by pinging the server periodically, preventing session expiration during active use.

**Configuration**:
```javascript
const PING_INTERVAL = 10 * 60 * 1000;      // 10 minutes
const INACTIVITY_TIMEOUT = 15 * 60 * 1000; // 15 minutes
```

**Logic**:
1. Track user activity (mousedown, keydown, scroll, touchstart)
2. Every 10 minutes, check if user was active within last 15 minutes
3. If active, ping `/auth/ping` endpoint
4. Endpoint refreshes token if needed and resets session timeout
5. If ping returns 401, redirect to login (session expired)

**Activity Tracking**:
```javascript
['mousedown', 'keydown', 'scroll', 'touchstart'].forEach(event => {
    document.addEventListener(event, () => {
        lastActivity = Date.now();
    });
});
```

**Ping Logic**:
```javascript
setInterval(() => {
    const timeSinceActivity = Date.now() - lastActivity;
    
    if (timeSinceActivity < INACTIVITY_TIMEOUT) {
        fetch('/auth/ping', { credentials: 'same-origin' })
            .then(response => {
                if (response.status === 401) {
                    window.location.href = '/auth/login';
                }
            });
    }
}, PING_INTERVAL);
```

**Benefits**:
- User never interrupted during active use
- Session extends automatically (sliding window)
- Tokens refresh proactively
- Graceful redirect on expiration

---

## Security Considerations

### Secret Management

**Two Critical Secrets**:

1. **CLIENT_SECRET** (`O365_CLIENT_SECRET` in `.env`)
   - **Purpose**: Authenticates your app to Microsoft Azure AD
   - **Used For**: OAuth token exchange, token refresh
   - **Rotation**: Expires after 24 months (set in Azure Portal)
   - **Storage**: Environment variables (`.env` locally, Azure App Service config in production)

2. **SECRET_KEY** (`SECRET_KEY` in `.env`)
   - **Purpose**: Signs Flask session cookies
   - **Used For**: Session integrity, CSRF protection
   - **Rotation**: No expiration, but should rotate periodically
   - **Effect of Rotation**: Invalidates all active sessions

**Security Best Practices**:
```bash
# Never commit secrets to git
echo ".env" >> .gitignore

# Generate strong secrets (32+ bytes)
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Store in Azure Key Vault for production
```

---

### Token Exposure Prevention

**Where Tokens Are NOT Exposed**:
- ❌ Not in URLs (query parameters)
- ❌ Not in client-side JavaScript variables
- ❌ Not in browser localStorage/sessionStorage
- ❌ Not in HTML source
- ❌ Not in browser console logs (production)

**Where Tokens ARE Stored**:
- ✅ Server-side session files (`/home/flask_session/`)
- ✅ Memory during request processing
- ✅ HTTPS-encrypted transmission only

**Token Lifecycle**:
```
User Login → Tokens stored in session file → Accessed per-request → 
Refreshed automatically → Invalidated on logout or expiration
```

---

### Domain Restriction

**File**: `app/routes/auth_routes.py` → Lines 145-151

**Implementation**:
```python
email = user_info.get('mail', user_info.get('userPrincipalName'))

if not email.lower().endswith('@peakmade.com'):
    logger.warning(f"Domain restriction: {email} not allowed")
    flash('Access denied. Only @peakmade.com email addresses are allowed.', 'error')
    session.clear()
    return redirect('/')
```

**Purpose**: Restrict application access to authorized domain, even though Azure AD allows broader authentication.

---

### Admin Access Control

**File**: `app/utils/admin_utils.py`

**Process**:
1. Query SharePoint admin list via Microsoft Graph
2. Check if user email exists in list
3. Check if `Active` column = True
4. Cache result in session (`session['is_admin']`)

**SharePoint List Structure**:
```
Admin List Columns:
- Email: User's email address
- Active: Boolean (true/false)
```

**Usage**:
```python
from app.utils.admin_utils import admin_required

@app.route('/admin-only-route')
@admin_required
def admin_function():
    # Only admins can access
    ...
```

---

## Azure Deployment Configuration

### Environment Variables Required

**Azure App Service → Configuration → Application Settings**:

```bash
# OAuth Configuration
CLIENT_ID=5a2d3a1b-82e5-4edf-a0e9-00ab39462977
TENANT_ID=ea0cd29c-45e6-4ad1-94ff-2e9f36fb84b5
O365_CLIENT_SECRET=<secret-from-azure-portal>
REDIRECT_URI=https://your-app.azurewebsites.net/auth/redirect

# Flask Configuration
SECRET_KEY=<cryptographically-random-string>

# SharePoint Configuration
SP_SITE_URL=https://peakcampus.sharepoint.com/sites/BaseCampApps
SP_ADMIN_LIST_ID=beea8d68-b6ba-4007-98d8-93f525b5483f
ACTIVITY_LOG_LIST_ID=f3ccd59d-1497-42a0-985f-6faa7fa6e226

# OpenAI Configuration (if using AI features)
OPENAI_API_KEY=<openai-secret>

# Download URL Security (if using signed URLs)
DOWNLOAD_URL_SECRET=<random-secret>
```

---

### ARR Affinity (Session Stickiness)

**Requirement**: **MUST be enabled** for multi-instance deployments

**Configuration**:
```
Azure Portal → App Service → Configuration → General Settings
ARR affinity: ON ✓
```

**Why Required**:
- Flask-Session stores files in instance-local `/home/` directory
- Without sticky sessions, user requests hit different instances
- Different instances = different session files = session not found = forced re-login

**How It Works**:
```
User A → Load Balancer → Instance 1 (ARR cookie set)
User A → Load Balancer → Instance 1 (same instance via ARR cookie)
User B → Load Balancer → Instance 2 (different ARR cookie)
```

---

### Startup Command

**Azure App Service → Configuration → General Settings → Startup Command**:

```bash
gunicorn --bind=0.0.0.0 --timeout 600 --chdir /home/site/wwwroot main:app
```

**No changes needed** for Flask-Session - it's just a Python package.

---

### Session File Persistence

**Azure App Service Filesystem**:
- `/home/` directory persists across app restarts
- Limited to ~1GB storage (shared with logs, uploads)
- Survives deployments
- Instance-local (each instance has own `/home/`)

**Session File Cleanup**:
- Runs on app startup (when Azure recycles instances)
- Deletes files >9 hours old
- Active users protected (file modification time = last access)

---

## Key Takeaways for Implementation

### 1. **Use Server-Side Session Storage**
**Why**: Prevents token exposure in cookies, avoids 4KB cookie limit.

**Implementation**:
- Use Flask-Session with filesystem backend (simple) or Redis (scalable)
- Store tokens in session, not cookies
- Session ID in cookie, data on server

---

### 2. **Implement Token Refresh Proactively**
**Why**: Prevents mid-request token expiration, seamless user experience.

**Implementation**:
- Check token expiration before **every** API call
- Refresh if <5 minutes remaining (skew_seconds=300)
- Use MSAL's `acquire_token_by_refresh_token()` method
- Update session with new tokens

**Critical**: Call `ensure_fresh_access_token()` before:
- Protected route handlers
- SharePoint/Graph API calls
- Any operation requiring authentication

---

### 3. **Enable Sliding Sessions**
**Why**: Active users stay logged in indefinitely without interruption.

**Implementation**:
```python
SESSION_PERMANENT=True
PERMANENT_SESSION_LIFETIME=timedelta(hours=8)
SESSION_REFRESH_EACH_REQUEST=True  # Extends timeout on every request
```

**Result**: Session timeout resets on every page load, API call, or keep-alive ping.

---

### 4. **Add Keep-Alive Mechanism**
**Why**: Prevents session expiration during active use, proactive token refresh.

**Implementation**:
- JavaScript pings server every 10 minutes (if user active within 15 minutes)
- Server endpoint refreshes token and resets session timeout
- Redirect to login on 401 (session expired)

**Key Parameters**:
- `PING_INTERVAL`: 10 minutes (adjust based on token lifetime)
- `INACTIVITY_TIMEOUT`: 15 minutes (tracks user activity)

---

### 5. **Handle Refresh Token Expiration Gracefully**
**Why**: Refresh tokens expire eventually (1 hour to 90 days depending on Azure AD config).

**Implementation**:
- Catch `invalid_grant` errors from MSAL
- Raise `AuthRequired` exception
- Redirect user to `/auth/login`
- Clear session data

**Error Codes**:
- `AADSTS50173`: Refresh token expired
- `AADSTS70000`: Refresh token invalid

---

### 6. **Secure Session Configuration**
**Why**: Prevent session hijacking, CSRF, and token theft.

**Critical Settings**:
```python
# Azure/Production
SESSION_COOKIE_SECURE=True      # HTTPS only
SESSION_COOKIE_HTTPONLY=True    # Not accessible via JavaScript
SESSION_COOKIE_SAMESITE='Lax'   # CSRF protection, allows same-site iframes

# ProxyFix (for Azure reverse proxy)
from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
```

---

### 7. **Manage Secrets Properly**
**Why**: Compromised secrets = compromised application.

**Best Practices**:
- Store in environment variables, never hardcode
- Add `.env` to `.gitignore`
- Use Azure Key Vault in production
- Rotate CLIENT_SECRET before expiration (24 months)
- Use strong SECRET_KEY (32+ bytes, cryptographically random)

---

### 8. **Enable Session Cleanup**
**Why**: Prevent disk space exhaustion from abandoned sessions.

**Implementation**:
- Run cleanup on app startup
- Delete files older than session lifetime + safety buffer (9 hours = 8h + 1h)
- Use UTC timezone to prevent clock skew issues
- Safe for active users (file modification time tracks activity)

---

### 9. **Configure ARR Affinity for Multi-Instance Deployments**
**Why**: Session files are instance-local, users must hit same instance.

**Azure Configuration**:
```
ARR affinity: ON
```

**Alternative**: Use Redis session backend (shared across instances).

---

### 10. **Test Token Refresh Thoroughly**
**Why**: Token refresh failures cause user re-authentication, poor UX.

**Test Scenarios**:
- [ ] Token expires within 5 minutes → Refresh triggered
- [ ] Refresh token expires → User redirected to login
- [ ] Network error during refresh → Graceful fallback
- [ ] Multiple simultaneous refreshes → No race conditions
- [ ] Keep-alive pings → Token stays fresh during activity
- [ ] 1+ hour of inactivity → Session expires correctly

---

### 11. **Monitor Token Lifecycle in Production**
**Why**: Detect issues before they affect users.

**Add Logging**:
```python
logger.info(f"Token expires in {minutes:.1f} minutes")
logger.info("Token refreshed successfully")
logger.warning("Refresh token expired, re-authentication required")
```

**Monitor**:
- Token refresh frequency
- Refresh failures
- Session duration
- User re-authentication rate

---

## Summary: The Complete Flow

```
1. User visits app
   ↓
2. Redirect to Microsoft login (OAuth)
   ↓
3. User authenticates with Microsoft
   ↓
4. Microsoft redirects back with authorization code
   ↓
5. Exchange code for access_token + refresh_token
   ↓
6. Store tokens in Flask-Session (filesystem)
   ↓
7. Browser receives session cookie (ID only, no tokens)
   ↓
8. User makes API calls (token sent from server-side session)
   ↓
9. Before each call: Check if token expires soon (<5 min)
   ↓
10. If expiring: Use refresh_token to get new access_token
   ↓
11. Update session with new tokens (rolling refresh)
   ↓
12. API call succeeds with fresh token
   ↓
13. JavaScript keep-alive pings every 10 minutes (if active)
   ↓
14. Session extends automatically (sliding window)
   ↓
15. After 8 hours inactivity OR refresh token expiration:
   ↓
16. User redirected to login, process repeats
```

---

## Implementation Checklist

### Phase 1: Basic OAuth
- [ ] Install MSAL and Flask-Session
- [ ] Configure Azure AD app registration
- [ ] Implement `/auth/login` and `/auth/redirect` routes
- [ ] Store tokens in session (server-side)
- [ ] Test login/logout flow

### Phase 2: Token Refresh
- [ ] Create `token_utils.py` with refresh logic
- [ ] Implement `ensure_fresh_access_token()`
- [ ] Call before all protected routes
- [ ] Call before all API operations
- [ ] Test token refresh when <5 min remaining

### Phase 3: Keep-Alive
- [ ] Add JavaScript keep-alive to frontend
- [ ] Implement `/auth/ping` endpoint
- [ ] Track user activity
- [ ] Test session extension during active use

### Phase 4: Session Cleanup
- [ ] Implement cleanup function (UTC, 9-hour threshold)
- [ ] Run on app startup
- [ ] Test with abandoned sessions

### Phase 5: Security Hardening
- [ ] Enable `SESSION_COOKIE_SECURE` in production
- [ ] Add ProxyFix middleware for Azure
- [ ] Rotate CLIENT_SECRET before expiration
- [ ] Add domain restriction
- [ ] Implement admin access control

### Phase 6: Deployment
- [ ] Set environment variables in Azure
- [ ] Enable ARR Affinity
- [ ] Deploy and test in production
- [ ] Monitor logs for token refresh activity

---

## Reference Files

| File | Purpose |
|------|---------|
| `main.py` | Flask-Session config, cleanup logic, ProxyFix |
| `app/routes/auth_routes.py` | OAuth login/callback, logout, keep-alive |
| `app/auth/token_utils.py` | Token refresh logic |
| `app/services/sharepoint_service.py` | API calls with token refresh |
| `app/templates/index.html` | Keep-alive JavaScript |
| `app/utils/admin_utils.py` | Admin access control |
| `.env` | Environment variables (local) |
| `requirements.txt` | Flask-Session, MSAL dependencies |

---

**Document Version**: 1.0  
**Last Updated**: December 29, 2025  
**Author**: AI Assistant (based on Contract Analyzer implementation)
