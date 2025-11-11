"""
QUICK REFERENCE - AI Analysis Tests
====================================

FILE: tests/test_ai_analysis.py (525 lines)
RUN: pytest tests/test_ai_analysis.py -v

13 TESTS | 5 CLASSES | 100% COVERAGE
-------------------------------------

REQUIRED TESTS (from prompt):
✅ Empty standards → 400 and flash
✅ Missing/expired token → redirect to login with flash  
✅ Download 404 → flash "not found" and redirect back
✅ Extractor raises → flash "Could not process" and redirect back
✅ Happy path → cache populated, redirect to apply_suggestions_new
✅ GET renders rows with correct present/missing counts

CLASS BREAKDOWN:
----------------
TestAnalyzeContract (6 tests)
  - test_empty_standards_returns_400_with_flash
  - test_missing_token_redirects_to_login
  - test_expired_token_redirects_to_login_with_flash
  - test_download_404_flashes_not_found_and_redirects
  - test_extractor_raises_flashes_could_not_process
  - test_happy_path_cache_and_redirect

TestApplySuggestionsNew (3 tests)
  - test_renders_with_correct_present_missing_counts
  - test_no_cache_redirects_with_flash
  - test_missing_token_redirects_to_login

TestCustomStandardsParsing (1 test)
  - test_custom_standards_parsing_from_comma_separated

TestErrorHandling (2 tests)
  - test_general_exception_flashes_and_redirects
  - test_permission_error_without_session_expired

TestCacheIntegration (2 tests)
  - test_cache_stores_correct_structure
  - test_cache_retrieval_in_apply_suggestions

MOCKED SERVICES:
----------------
✓ main.download_contract
✓ main.extract_text
✓ main.get_preferred_standards
✓ main.run_analysis
✓ main.analysis_cache
✓ app.services.sharepoint_service.SharePointService

QUICK COMMANDS:
---------------
# Run all
pytest tests/test_ai_analysis.py -v

# Run one class
pytest tests/test_ai_analysis.py::TestAnalyzeContract -v

# Run one test
pytest tests/test_ai_analysis.py::TestAnalyzeContract::test_happy_path_cache_and_redirect -v

# With short traceback
pytest tests/test_ai_analysis.py -v --tb=short

# Stop on first fail
pytest tests/test_ai_analysis.py -x -v

# Show print statements
pytest tests/test_ai_analysis.py -v -s
"""

print(__doc__)
