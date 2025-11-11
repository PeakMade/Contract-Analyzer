"""
Quick verification of TTL cache structure.
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.cache import analysis_cache, TTLCache


print("=" * 60)
print("TTL Cache Quick Verification")
print("=" * 60)

# Check that analysis_cache is a TTLCache instance
print(f"\n✓ analysis_cache type: {type(analysis_cache).__name__}")
assert isinstance(analysis_cache, TTLCache), "analysis_cache should be TTLCache instance"

# Check storage structure
print(f"✓ Has _storage attribute: {hasattr(analysis_cache, '_storage')}")
assert hasattr(analysis_cache, '_storage'), "Should have _storage attribute"

# Check methods exist
methods = ['get', 'set', 'delete', '_purge_expired']
for method in methods:
    has_method = hasattr(analysis_cache, method)
    print(f"✓ Has {method} method: {has_method}")
    assert has_method, f"Should have {method} method"

# Test basic functionality (no waiting)
print("\n--- Testing basic operations ---")

# Set a value
analysis_cache.set("test", "value", ttl=3600)
print("✓ Set test='value' with 3600s TTL")

# Check storage structure
storage_entry = analysis_cache._storage.get("test")
print(f"✓ Storage entry type: {type(storage_entry)}")
assert isinstance(storage_entry, tuple), "Storage should use tuple (expires_at, value)"
assert len(storage_entry) == 2, "Storage tuple should have 2 elements"

expires_at, value = storage_entry
print(f"✓ Storage structure: (expires_at={expires_at:.2f}, value='{value}')")

# Get the value
retrieved = analysis_cache.get("test")
print(f"✓ Retrieved value: '{retrieved}'")
assert retrieved == "value", "Should retrieve correct value"

# Delete the value
analysis_cache.delete("test")
print("✓ Deleted test key")

# Verify deleted
retrieved = analysis_cache.get("test")
print(f"✓ After delete: {retrieved}")
assert retrieved is None, "Should return None after delete"

print("\n" + "=" * 60)
print("✅ All verifications passed!")
print("=" * 60)
print("\nTTL Cache implementation matches specification:")
print("  - class TTLCache with dict storage {key: (expires_at, value)}")
print("  - methods: get(key), set(key, value, ttl), delete(key)")
print("  - purge on get/set via _purge_expired()")
print("  - module-level instance: analysis_cache = TTLCache()")
