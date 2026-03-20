"""
Quick script to check grammar checking configuration.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("="*70)
print("GRAMMAR CHECK CONFIGURATION")
print("="*70)

# Check environment variable
grammar_method = os.getenv('GRAMMAR_CHECK_METHOD', 'auto')
print(f"\n1. Environment Variable:")
print(f"   GRAMMAR_CHECK_METHOD = '{grammar_method}'")

# Check Word COM availability
print(f"\n2. Word COM Availability:")
try:
    from app.services.word_grammar_checker import is_word_com_available
    available = is_word_com_available()
    if available:
        print(f"   ✓ Word COM is AVAILABLE")
    else:
        print(f"   ✗ Word COM is NOT available")
except Exception as e:
    print(f"   ✗ Error checking: {e}")
    available = False

# Check pywin32
print(f"\n3. pywin32 Installation:")
try:
    import win32com.client
    print(f"   ✓ win32com.client imported successfully")
except ImportError:
    print(f"   ✗ win32com.client NOT installed")

try:
    import pythoncom
    print(f"   ✓ pythoncom imported successfully")
except ImportError:
    print(f"   ✗ pythoncom NOT installed")

# Expected behavior
print(f"\n4. Expected Behavior:")
if grammar_method == 'auto':
    if available:
        print(f"   → Will use WORD COM (with GPT fallback)")
    else:
        print(f"   → Will use GPT (Word COM not available)")
elif grammar_method == 'word_com':
    if available:
        print(f"   → Will use WORD COM (forced)")
    else:
        print(f"   → Will FAIL (Word COM forced but not available)")
elif grammar_method == 'gpt':
    print(f"   → Will use GPT (forced)")
else:
    print(f"   → Unknown method setting: {grammar_method}")

print("\n" + "="*70)
