"""
Test script to verify Word COM API grammar/spelling check is working
"""
import sys
from pathlib import Path

# Test with a sample contract file
print("="*70)
print("TESTING WORD COM API GRAMMAR/SPELLING CHECK")
print("="*70)

# Get a contract file path from user
if len(sys.argv) > 1:
    test_file = sys.argv[1]
else:
    test_file = input("Enter path to a Word document (.docx) to test: ").strip().strip('"')

test_file_path = Path(test_file)

if not test_file_path.exists():
    print(f"❌ ERROR: File not found: {test_file_path}")
    sys.exit(1)

if test_file_path.suffix.lower() not in ['.docx', '.doc']:
    print(f"❌ ERROR: File must be a Word document (.doc or .docx)")
    print(f"   Got: {test_file_path.suffix}")
    sys.exit(1)

print(f"\n✓ File found: {test_file_path}")
print(f"✓ File size: {test_file_path.stat().st_size:,} bytes")

# Import and test the Word COM function
print("\n" + "="*70)
print("STEP 1: Testing Word COM API Import")
print("="*70)

try:
    from app.services.word_grammar_checker import check_spelling_with_word
    print("✓ Successfully imported check_spelling_with_word")
except ImportError as e:
    print(f"❌ ERROR: Failed to import word_grammar_checker: {e}")
    sys.exit(1)

# Run the check
print("\n" + "="*70)
print("STEP 2: Running Word COM API Check")
print("="*70)

try:
    result = check_spelling_with_word(str(test_file_path))
    
    print("\n" + "="*70)
    print("STEP 3: Results")
    print("="*70)
    
    print(f"\n✓ Check completed successfully!")
    print(f"\nResult structure:")
    print(f"  - issues_found: {result.get('issues_found')}")
    print(f"  - error_count: {result.get('error_count')}")
    print(f"  - method: {result.get('method')}")
    
    raw_counts = result.get('raw_counts', {})
    print(f"\nRaw Word COM counts:")
    print(f"  - Spelling errors (raw): {raw_counts.get('spelling', 0)}")
    print(f"  - Grammar errors (raw): {raw_counts.get('grammar', 0)}")
    print(f"  - Errors processed: {raw_counts.get('processed', 0)}")
    
    errors_list = result.get('errors', [])
    print(f"\nErrors returned: {len(errors_list)}")
    
    if len(errors_list) > 0:
        print(f"\nFirst 5 errors:")
        for i, error in enumerate(errors_list[:5], 1):
            print(f"\n  {i}. Type: {error.get('type')}")
            print(f"     Error: {error.get('error_text')[:50]}")
            print(f"     Suggestion: {error.get('suggestion')[:50]}")
            print(f"     Location: {error.get('location')[:80]}")
    else:
        print("\n⚠ WARNING: No errors found!")
        print("   This could mean:")
        print("   1. The document has no spelling/grammar errors (unlikely for contracts)")
        print("   2. Word COM API is not detecting errors properly")
        print("   3. All errors were filtered as false positives")
        
except Exception as e:
    print(f"\n❌ ERROR: Word COM check failed:")
    print(f"   {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "="*70)
print("TEST COMPLETE")
print("="*70)
