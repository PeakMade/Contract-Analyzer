"""
TTL Cache Implementation Summary
================================

Implementation matches specification exactly:

✅ class TTLCache with dict storage of {key: (expires_at, value)}
✅ methods: get(key) -> Any|None, set(key, value, ttl:int), delete(key)
✅ background cleanup not required; purge on get/set
✅ module-level instance: analysis_cache = TTLCache()

Key Features:
- Storage: dict with tuple values (expires_at, value)
- Auto-purge: _purge_expired() called in get() and set()
- Simple: No threading, no logging, no default TTL
- Direct: Module exports `analysis_cache` instance ready to use

Example Usage:
    from app.cache import analysis_cache
    
    # Store value with 30 minute TTL
    analysis_cache.set("key", {"data": "value"}, ttl=1800)
    
    # Retrieve value (None if expired or missing)
    value = analysis_cache.get("key")
    
    # Delete value
    analysis_cache.delete("key")

Integration Points:
- main.py line 12: imports analysis_cache
- main.py line 340: analysis_cache.set(contract_id, cache_data, ttl=1800)
- main.py line 401: cached_data = analysis_cache.get(contract_id)
"""

if __name__ == '__main__':
    import sys
    from pathlib import Path
    
    # Add project root
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))
    
    from app.cache import analysis_cache, TTLCache
    import time
    
    print(__doc__)
    
    print("\n" + "=" * 60)
    print("Quick Functionality Test")
    print("=" * 60)
    
    # Test 1: Basic set/get
    print("\n1. Set and get value:")
    analysis_cache.set("demo", {"result": "success"}, ttl=5)
    value = analysis_cache.get("demo")
    print(f"   analysis_cache.get('demo') = {value}")
    assert value == {"result": "success"}
    
    # Test 2: Delete
    print("\n2. Delete value:")
    analysis_cache.delete("demo")
    value = analysis_cache.get("demo")
    print(f"   After delete: {value}")
    assert value is None
    
    # Test 3: Expiration (quick version)
    print("\n3. Expiration test (2 second TTL):")
    analysis_cache.set("expires", "soon", ttl=2)
    print(f"   Immediately: {analysis_cache.get('expires')}")
    print("   Waiting 3 seconds...")
    time.sleep(3)
    result = analysis_cache.get("expires")
    print(f"   After 3 seconds: {result}")
    assert result is None
    
    print("\n" + "=" * 60)
    print("✅ All tests passed! Cache is working correctly.")
    print("=" * 60)
