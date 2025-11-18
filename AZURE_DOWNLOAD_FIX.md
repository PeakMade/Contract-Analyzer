# Azure Download Fix - Implementation Summary

## Changes Made (Fix for Absolute URL/Proxy Issues)

### Root Cause
Downloads were failing in Azure production because:
1. Flask wasn't aware of Azure's reverse proxy
2. `url_for(_external=True)` generated HTTP URLs instead of HTTPS
3. Absolute URLs caused mixed content and session issues
4. SESSION_COOKIE_SECURE misconfiguration

### Solution Components

#### 1. ProxyFix Middleware (main.py)
- **Added**: Werkzeug ProxyFix to trust Azure proxy headers
- **Configuration**: 
  - `x_for=1`: Trust X-Forwarded-For (client IP)
  - `x_proto=1`: Trust X-Forwarded-Proto (http/https)
  - `x_host=1`: Trust X-Forwarded-Host (original host)
  - `x_prefix=1`: Trust X-Forwarded-Prefix (path prefix)
- **Impact**: Flask now generates correct HTTPS URLs

#### 2. Cookie Configuration (main.py)
- **Changed**:
  - `PREFERRED_URL_SCHEME='https'`
  - `SESSION_COOKIE_SECURE=True` (HTTPS only)
  - `SESSION_COOKIE_SAMESITE='Lax'` (same-origin iframe compatible)
- **Impact**: Sessions work reliably in Azure HTTPS environment

#### 3. Signed URLs (app/utils/signed_url.py)
- **Created**: HMAC-SHA256 signed download URLs with expiration
- **Functions**:
  - `make_signed_path(contract_id, ttl_sec=300)`: Generate signed URL (5-min TTL)
  - `verify_signed(contract_id, exp, sig)`: Verify signature and expiration
- **Benefit**: Downloads work even if session expires within TTL window
- **Security**: Uses DOWNLOAD_URL_SECRET environment variable

#### 4. Download Route Updates (main.py)
- **Changed**: Dual authentication support
  - **Method 1**: Signed URL (HMAC verification)
  - **Method 2**: Session (fallback for logged-in users)
- **Removed**: `@login_required` decorator (now conditional)
- **Impact**: Downloads work with or without active session

#### 5. Backend URL Generation (main.py - apply_suggestions_action)
- **Changed**: Return relative path instead of absolute URL
  - **Old**: `url_for(..., _external=True)` → `http://...` (broken)
  - **New**: `make_signed_path(contract_id, ttl_sec=300)` → `/contracts/ABC/download_edited?exp=...&sig=...` (works)
- **JSON Response**: Changed from `download_url` to `download_path`

#### 6. Frontend Updates (app/templates/apply_suggestions.html)
- **Changed**: Use relative path instead of absolute URL
  - **Parameter**: `downloadUrl` → `downloadPath`
  - **iframe.src**: Uses relative path (same-origin, no mixed content)
- **Already Present**: `credentials: 'same-origin'` in fetch request

### Testing Checklist

#### Local Testing (Before Push)
- [x] Flask app imports successfully
- [x] ProxyFix middleware configured
- [x] Signed URL verification logic works
- [ ] Full workflow test (manual):
  1. Start Flask: `python main.py`
  2. Log in to application
  3. Upload contract
  4. Analyze contract
  5. Apply suggestions (check console logs)
  6. Click download button
  7. Verify file downloads

#### Azure Testing (After Deploy)
- [ ] Apply suggestions completes successfully
- [ ] **CRITICAL**: Download request appears in logs (was missing before!)
- [ ] Download route shows authentication method (signed_url or session)
- [ ] File downloads successfully to browser

### Azure Environment Variables Required

Add to Azure App Service Configuration:
```
DOWNLOAD_URL_SECRET=<generate-random-secret-string>
```

Generate secret with:
```powershell
# PowerShell
[Convert]::ToBase64String([System.Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
```

### Deployment Steps

1. **Commit changes**:
   ```bash
   git add .
   git commit -m "Fix Azure downloads: Add ProxyFix, relative URLs, signed URLs"
   git push origin main
   ```

2. **Set Azure environment variable**:
   - Go to Azure Portal → App Service → Configuration
   - Add new application setting: `DOWNLOAD_URL_SECRET`
   - Value: (generated secret from above)
   - Click "Save"

3. **Deploy to Azure** (automatic if GitHub Actions configured)

4. **Verify in Azure logs**:
   - Check Application Insights or Log Stream
   - Look for: "DOWNLOAD EDITED: Contract ..." after clicking download
   - Should see: "✓ Authenticated via signed_url (expires: ...)"

### Rollback Plan

If deployment fails:
```bash
git revert HEAD
git push origin main
```

Previous working commit: `209a1c9` (session-independent iframe download)

### Key Differences from Previous Fixes

| Fix Attempt | Method | Issue |
|-------------|--------|-------|
| Fix #1 | window.location.href | Blocked by browser |
| Fix #2 | Fetch API + Blob | Session cookie issues |
| Fix #3 | iframe + session-independent | Absolute URL proxy issues |
| **Fix #4 (THIS)** | **ProxyFix + relative URL + signed URL** | **Comprehensive solution** |

### Success Indicators

✅ No more "downloads not reaching server" in logs  
✅ Download request appears in Azure logs  
✅ File downloads to browser's Downloads folder  
✅ Works in both Chrome and Edge  
✅ ProxyFix doesn't break local development  

### Expected Azure Log Output (Success)

```
======================================================================
DOWNLOAD EDITED: Contract 30BD7419-1234-5678-90AB-CDEF12345678
======================================================================
✓ Authenticated via signed_url (expires: 1234567890)
Auth method: signed_url

Fetching contract metadata from SharePoint...
Original uploaded filename: Partner_Agreement_uploaded.docx
Looking for edited file: Partner_Agreement_edited.docx
Drive ID: b!abc123...

Downloading edited file from SharePoint...
✓ Downloaded 45,678 bytes
✓ Sending file to user: Partner_Agreement_edited.docx
======================================================================
```

### Files Modified

1. `main.py` - ProxyFix, cookie config, download route, apply_suggestions_action
2. `app/utils/signed_url.py` - NEW FILE (signed URL utilities)
3. `app/templates/apply_suggestions.html` - Relative path usage
