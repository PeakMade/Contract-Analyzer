# Session Management Guide

## Overview

This document describes our custom session management approach for tracking user activity and maintaining session context across web applications. This pattern provides a consistent way to identify and trace user sessions for logging, debugging, and analytics purposes.

## The Problem

When building web applications, we need a reliable way to:
- Track user activities across multiple requests
- Debug issues by correlating actions to specific user sessions
- Log activities with consistent session identifiers
- Maintain session context without relying on complex session frameworks

## Our Solution: Logical Session ID

We implemented a **custom logical session ID** pattern that creates and maintains a unique identifier for each user session. This is a simple, fabricated UUID that we generate and manage ourselves.

### Key Characteristics

- **Custom Generated**: We create our own UUID using `uuid.uuid4()`
- **Stored in Session**: Persisted in the server-side session storage
- **Application Controlled**: We decide when to generate, regenerate, or invalidate
- **Framework Agnostic**: Can work with any session storage mechanism

## Implementation

### Core Function

```python
import uuid
from flask import session

def get_session_id():
    """Get or generate logical session ID for activity tracking"""
    if 'logical_session_id' not in session:
        session['logical_session_id'] = str(uuid.uuid4())
        print(f"=== GENERATED NEW SESSION ID: {session['logical_session_id']} ===")
    else:
        print(f"=== USING EXISTING SESSION ID: {session['logical_session_id']} ===")
    return session['logical_session_id']
```

### Usage Pattern

**Basic Usage:**
```python
@app.route('/analyze')
def analyze():
    session_id = get_session_id()
    print(f"Processing request in session: {session_id}")
    # ... your route logic
    return jsonify({'session_id': session_id})
```

**With Logging:**
```python
@app.route('/upload')
def upload_file():
    session_id = get_session_id()
    logger.info(f"File upload started - Session: {session_id}")
    
    # Process file
    result = process_file(uploaded_file)
    
    logger.info(f"File processed successfully - Session: {session_id}")
    return jsonify({'status': 'success', 'session_id': session_id})
```

**For Database Activity Tracking:**
```python
def log_activity(activity_type, details):
    """Log user activity with session tracking"""
    session_id = get_session_id()
    
    conn = get_database_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO ActivityLog (session_id, activity_type, details, timestamp)
        VALUES (?, ?, ?, ?)
    """, (session_id, activity_type, details, datetime.now()))
    conn.commit()
```

## When to Generate New Session IDs

### Automatic Generation
A new session ID is automatically generated on:
- **First Request**: When user first accesses the application
- **Session Timeout**: When server-side session expires

### Explicit Regeneration
You should explicitly regenerate the session ID when:

**1. User Initiates New Workflow:**
```python
@app.route('/restart')
def restart_session():
    # Clear old session data
    session.clear()
    
    # Generate new session ID
    session['logical_session_id'] = str(uuid.uuid4())
    print(f"=== SESSION RESTART: Generated new session ID: {session['logical_session_id']} ===")
    
    return jsonify({'status': 'session_restarted'})
```

**2. After Major State Changes:**
```python
@app.route('/complete-workflow')
def complete_workflow():
    # Save results
    save_workflow_results(session['logical_session_id'])
    
    # Start fresh for next workflow
    session['logical_session_id'] = str(uuid.uuid4())
    print(f"=== NEW WORKFLOW: Generated session ID: {session['logical_session_id']} ===")
    
    return redirect('/dashboard')
```

**3. Timeout Recovery:**
```python
@app.before_request
def check_session_timeout():
    last_activity = session.get('last_activity')
    
    if last_activity:
        time_elapsed = datetime.now() - last_activity
        if time_elapsed > timedelta(hours=1):
            # Session timeout - regenerate ID
            session['logical_session_id'] = str(uuid.uuid4())
            print(f"=== TIMEOUT RECOVERY: New session ID: {session['logical_session_id']} ===")
    
    session['last_activity'] = datetime.now()
```

## Best Practices

### 1. Always Use get_session_id()
Don't access `session['logical_session_id']` directly. Always use the helper function to ensure the ID exists.

**✅ Good:**
```python
session_id = get_session_id()
```

**❌ Bad:**
```python
session_id = session.get('logical_session_id', 'unknown')
```

### 2. Log Session IDs Consistently
Use a consistent format for logging session IDs to make log searching easier.

```python
print(f"=== SESSION {session_id}: {action} ===")
logger.info(f"Session {session_id}: {message}")
```

### 3. Include Session ID in Error Responses
Help users and support teams by including session IDs in error messages.

```python
@app.errorhandler(500)
def internal_error(error):
    session_id = get_session_id()
    return jsonify({
        'error': 'Internal server error',
        'session_id': session_id,
        'message': 'Please contact support with this session ID'
    }), 500
```

### 4. Track Session Boundaries
Log when sessions are created or regenerated to understand user flows.

```python
if 'logical_session_id' not in session:
    session['logical_session_id'] = str(uuid.uuid4())
    logger.info(f"NEW SESSION CREATED: {session['logical_session_id']}")
    track_session_start(session['logical_session_id'])
```

### 5. Store Session Context
Use the session ID as a key for temporary data storage.

```python
# Store uploaded files by session
upload_dir = os.path.join('uploads', get_session_id())
os.makedirs(upload_dir, exist_ok=True)

# Store processing results by session
redis_client.set(f"results:{get_session_id()}", json.dumps(results))
```

## Integration with Other Systems

### Database Activity Logging
```python
def create_activity_log_table():
    """Create table for tracking activities by session"""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ActivityLog (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            activity_type TEXT NOT NULL,
            details TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_session_id (session_id)
        )
    """)
```

### Analytics and Reporting
```python
def get_session_analytics(session_id):
    """Retrieve all activities for a specific session"""
    cursor.execute("""
        SELECT activity_type, details, timestamp
        FROM ActivityLog
        WHERE session_id = ?
        ORDER BY timestamp
    """, (session_id,))
    return cursor.fetchall()
```

### Debugging and Support
```python
def get_session_debug_info(session_id):
    """Get comprehensive session information for debugging"""
    return {
        'session_id': session_id,
        'activities': get_session_analytics(session_id),
        'files_uploaded': list_session_files(session_id),
        'errors': get_session_errors(session_id),
        'duration': calculate_session_duration(session_id)
    }
```

## Common Patterns

### Pattern 1: Multi-Step Workflow Tracking
```python
@app.route('/step1')
def step1():
    session_id = get_session_id()
    session['workflow_step'] = 1
    log_activity(session_id, 'workflow_step_1', 'User started workflow')
    return render_template('step1.html')

@app.route('/step2')
def step2():
    session_id = get_session_id()
    session['workflow_step'] = 2
    log_activity(session_id, 'workflow_step_2', 'User progressed to step 2')
    return render_template('step2.html')
```

### Pattern 2: Session-Scoped File Management
```python
def save_user_file(file):
    """Save file in session-specific directory"""
    session_id = get_session_id()
    session_dir = os.path.join('uploads', session_id)
    os.makedirs(session_dir, exist_ok=True)
    
    file_path = os.path.join(session_dir, secure_filename(file.filename))
    file.save(file_path)
    
    return file_path

def cleanup_session_files():
    """Clean up files for completed sessions"""
    session_id = get_session_id()
    session_dir = os.path.join('uploads', session_id)
    if os.path.exists(session_dir):
        shutil.rmtree(session_dir)
```

### Pattern 3: Session-Based Caching
```python
def get_cached_result(cache_key):
    """Get cached result for current session"""
    session_id = get_session_id()
    full_key = f"{session_id}:{cache_key}"
    return cache.get(full_key)

def set_cached_result(cache_key, value, ttl=3600):
    """Cache result for current session"""
    session_id = get_session_id()
    full_key = f"{session_id}:{cache_key}"
    cache.set(full_key, value, ttl)
```

## Troubleshooting

### Issue: Session ID Changes Unexpectedly
**Cause:** Server-side session expired or was cleared
**Solution:** Check session timeout settings and ensure session storage is persistent

### Issue: Cannot Track User Across Requests
**Cause:** Session cookies not being sent/stored
**Solution:** Verify cookie configuration and ensure HTTPS in production

### Issue: Multiple Session IDs for Same User
**Cause:** Session regeneration logic triggering too frequently
**Solution:** Review regeneration conditions and add appropriate guards

## Migration Guide

If you're adopting this pattern in an existing application:

1. **Add the helper function** to your main application file
2. **Replace manual session ID access** with calls to `get_session_id()`
3. **Update logging statements** to include session IDs
4. **Add session ID to error responses** for better debugging
5. **Review and standardize** session regeneration points

## Security Considerations

- **Don't expose session IDs in URLs** - Keep them server-side only
- **Use HTTPS in production** - Protect session cookies from interception
- **Implement proper timeout** - Regenerate IDs after inactivity
- **Clear session on logout** - Prevent session hijacking
- **Don't log sensitive data** - Session IDs are safe, but avoid logging tokens or passwords

## Summary

This custom logical session ID pattern provides:
- ✅ Simple, predictable session tracking
- ✅ Framework-agnostic implementation
- ✅ Full control over session lifecycle
- ✅ Easy integration with logging and analytics
- ✅ Improved debugging capabilities

By using this consistent approach across all team projects, we ensure:
- Easier troubleshooting across applications
- Standardized logging and monitoring
- Better collaboration and code sharing
- Reduced learning curve for new team members
