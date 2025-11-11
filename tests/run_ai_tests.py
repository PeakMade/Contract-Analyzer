"""
Test runner for AI analysis tests - shows output clearly.
"""
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
os.chdir(project_root)

print("=" * 60)
print("AI Analysis Unit Tests")
print("=" * 60)

# Try importing the test module
try:
    print("\n1. Importing test module...")
    import tests.test_ai_analysis as test_module
    print("   ✓ Test module imported successfully")
except Exception as e:
    print(f"   ✗ Failed to import test module: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Try importing pytest
try:
    print("\n2. Importing pytest...")
    import pytest
    print(f"   ✓ pytest {pytest.__version__} available")
except Exception as e:
    print(f"   ✗ pytest not available: {e}")
    sys.exit(1)

# List test classes
print("\n3. Test classes found:")
print(f"   - TestAnalyzeContract: {len([m for m in dir(test_module.TestAnalyzeContract) if m.startswith('test_')])} tests")
print(f"   - TestApplySuggestionsNew: {len([m for m in dir(test_module.TestApplySuggestionsNew) if m.startswith('test_')])} tests")
print(f"   - TestCustomStandardsParsing: {len([m for m in dir(test_module.TestCustomStandardsParsing) if m.startswith('test_')])} tests")
print(f"   - TestErrorHandling: {len([m for m in dir(test_module.TestErrorHandling) if m.startswith('test_')])} tests")
print(f"   - TestCacheIntegration: {len([m for m in dir(test_module.TestCacheIntegration) if m.startswith('test_')])} tests")

# Run pytest
print("\n4. Running pytest...")
print("=" * 60)
sys.exit(pytest.main([
    'tests/test_ai_analysis.py',
    '-v',
    '--tb=short',
    '--color=yes'
]))
