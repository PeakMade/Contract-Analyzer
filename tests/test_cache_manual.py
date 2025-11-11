"""
Simple manual test for TTL cache functionality.
"""
import time
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.cache import analysis_cache


def test_basic_get_set():
    """Test basic get and set operations."""
    print("\n=== Test 1: Basic Get/Set ===")
    
    # Set a value with 5 second TTL
    analysis_cache.set("test_key", "test_value", ttl=5)
    print("✓ Set test_key = 'test_value' with 5s TTL")
    
    # Get the value immediately
    value = analysis_cache.get("test_key")
    assert value == "test_value", f"Expected 'test_value', got {value}"
    print(f"✓ Got value: {value}")


def test_expiration():
    """Test that entries expire after TTL."""
    print("\n=== Test 2: Expiration ===")
    
    # Set a value with 2 second TTL
    analysis_cache.set("short_lived", "expires_soon", ttl=2)
    print("✓ Set short_lived = 'expires_soon' with 2s TTL")
    
    # Get immediately - should exist
    value = analysis_cache.get("short_lived")
    assert value == "expires_soon", f"Expected value, got {value}"
    print(f"✓ Value exists: {value}")
    
    # Wait for expiration
    print("⏳ Waiting 3 seconds for expiration...")
    time.sleep(3)
    
    # Get again - should be None
    value = analysis_cache.get("short_lived")
    assert value is None, f"Expected None (expired), got {value}"
    print("✓ Value expired as expected")


def test_delete():
    """Test delete operation."""
    print("\n=== Test 3: Delete ===")
    
    # Set a value
    analysis_cache.set("to_delete", "delete_me", ttl=60)
    print("✓ Set to_delete = 'delete_me' with 60s TTL")
    
    # Verify it exists
    value = analysis_cache.get("to_delete")
    assert value == "delete_me", f"Expected value, got {value}"
    print(f"✓ Value exists: {value}")
    
    # Delete it
    analysis_cache.delete("to_delete")
    print("✓ Deleted to_delete")
    
    # Verify it's gone
    value = analysis_cache.get("to_delete")
    assert value is None, f"Expected None (deleted), got {value}"
    print("✓ Value deleted successfully")


def test_multiple_keys():
    """Test multiple keys with different TTLs."""
    print("\n=== Test 4: Multiple Keys ===")
    
    # Set multiple keys
    analysis_cache.set("key1", {"data": 1}, ttl=10)
    analysis_cache.set("key2", {"data": 2}, ttl=10)
    analysis_cache.set("key3", {"data": 3}, ttl=10)
    print("✓ Set 3 keys with different values")
    
    # Get all keys
    val1 = analysis_cache.get("key1")
    val2 = analysis_cache.get("key2")
    val3 = analysis_cache.get("key3")
    
    assert val1 == {"data": 1}, f"key1 mismatch"
    assert val2 == {"data": 2}, f"key2 mismatch"
    assert val3 == {"data": 3}, f"key3 mismatch"
    print(f"✓ Retrieved all 3 keys correctly")
    
    # Delete one
    analysis_cache.delete("key2")
    print("✓ Deleted key2")
    
    # Verify others still exist
    val1 = analysis_cache.get("key1")
    val2 = analysis_cache.get("key2")
    val3 = analysis_cache.get("key3")
    
    assert val1 == {"data": 1}, f"key1 should still exist"
    assert val2 is None, f"key2 should be deleted"
    assert val3 == {"data": 3}, f"key3 should still exist"
    print("✓ Other keys unaffected by deletion")


def test_purge_on_operations():
    """Test that expired entries are purged during get/set."""
    print("\n=== Test 5: Auto-purge on Get/Set ===")
    
    # Set several keys with short TTL
    analysis_cache.set("purge1", "v1", ttl=1)
    analysis_cache.set("purge2", "v2", ttl=1)
    analysis_cache.set("purge3", "v3", ttl=1)
    print("✓ Set 3 keys with 1s TTL")
    
    # Wait for expiration
    print("⏳ Waiting 2 seconds for expiration...")
    time.sleep(2)
    
    # Set a new key - should trigger purge
    analysis_cache.set("new_key", "new_value", ttl=60)
    print("✓ Set new_key (should trigger purge)")
    
    # Try to get old keys - should be None
    val1 = analysis_cache.get("purge1")
    val2 = analysis_cache.get("purge2")
    val3 = analysis_cache.get("purge3")
    
    assert val1 is None, "purge1 should be purged"
    assert val2 is None, "purge2 should be purged"
    assert val3 is None, "purge3 should be purged"
    print("✓ Expired entries purged automatically")
    
    # New key should still exist
    new_val = analysis_cache.get("new_key")
    assert new_val == "new_value", "new_key should exist"
    print("✓ New key preserved")


if __name__ == '__main__':
    print("=" * 60)
    print("TTL Cache Manual Test Suite")
    print("=" * 60)
    
    try:
        test_basic_get_set()
        test_expiration()
        test_delete()
        test_multiple_keys()
        test_purge_on_operations()
        
        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
