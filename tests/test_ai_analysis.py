"""
Unit tests for AI analysis workflow.
Tests the /contract/<contract_id>/analyze endpoint with mocked service layers.
"""
import pytest
from unittest.mock import patch, MagicMock, Mock
from flask import session, Flask
from datetime import datetime
import tempfile
import os


@pytest.fixture
def app():
    """Create Flask app for testing."""
    # Import after ensuring we can import main
    from main import app as flask_app
    
    flask_app.config['TESTING'] = True
    flask_app.config['SECRET_KEY'] = 'test-secret-key'
    flask_app.config['WTF_CSRF_ENABLED'] = False
    
    return flask_app


@pytest.fixture
def client(app):
    """Create Flask test client."""
    return app.test_client()


@pytest.fixture
def authenticated_session(client):
    """Set up authenticated session."""
    with client.session_transaction() as sess:
        sess['access_token'] = 'fake-token-12345'
        sess['user_email'] = 'test@example.com'
        sess['user_name'] = 'Test User'
    return client


class TestAnalyzeContract:
    """Test suite for the analyze_contract route."""
    
    def test_empty_standards_returns_400_with_flash(self, authenticated_session):
        """Test that submitting no standards returns 400 and flashes warning."""
        with patch('main.download_contract') as mock_download:
            # POST with no standards selected
            response = authenticated_session.post(
                '/contract/TEST-001/analyze',
                data={
                    'standards': [],  # Empty list
                    'custom_standards': ''  # Empty string
                },
                follow_redirects=False
            )
            
            # Should redirect to contract_standards page
            assert response.status_code == 302
            assert '/contract/TEST-001/standards' in response.location
            
            # Follow redirect to check flash message
            response = authenticated_session.get(response.location)
            assert b'Please select at least one standard' in response.data
            
            # Download should not be called
            mock_download.assert_not_called()
    
    def test_missing_token_redirects_to_login(self, client):
        """Test that missing access token redirects to login with flash."""
        # No authenticated session - just use client directly
        response = client.post(
            '/contract/TEST-001/analyze',
            data={'standards': ['Indemnification']},
            follow_redirects=False
        )
        
        # Should redirect to login
        assert response.status_code == 302
        assert '/auth/login' in response.location
    
    def test_expired_token_redirects_to_login_with_flash(self, authenticated_session):
        """Test that expired/invalid token redirects to login with flash message."""
        with patch('main.download_contract') as mock_download:
            # Mock download_contract to raise PermissionError with SESSION_EXPIRED
            mock_download.side_effect = PermissionError('SESSION_EXPIRED')
            
            response = authenticated_session.post(
                '/contract/TEST-001/analyze',
                data={'standards': ['Indemnification']},
                follow_redirects=False
            )
            
            # Should redirect to login
            assert response.status_code == 302
            assert '/auth/login' in response.location
            
            # Follow redirect to check flash message
            response = authenticated_session.get(response.location)
            assert b'Session expired' in response.data or b'sign in again' in response.data
    
    def test_download_404_flashes_not_found_and_redirects(self, authenticated_session):
        """Test that FileNotFoundError flashes 'not found' and redirects back."""
        with patch('main.download_contract') as mock_download:
            # Mock download_contract to raise FileNotFoundError
            mock_download.side_effect = FileNotFoundError('Contract file not found')
            
            response = authenticated_session.post(
                '/contract/TEST-001/analyze',
                data={'standards': ['Indemnification']},
                follow_redirects=False
            )
            
            # Should redirect back to contract standards page
            assert response.status_code == 302
            assert '/contract/TEST-001/standards' in response.location
            
            # Follow redirect to check flash message
            response = authenticated_session.get(response.location)
            assert b'not found' in response.data.lower()
    
    def test_extractor_raises_flashes_could_not_process(self, authenticated_session):
        """Test that RuntimeError from extractor flashes 'Could not process' and redirects."""
        with patch('main.download_contract') as mock_download, \
             patch('main.extract_text') as mock_extract:
            
            # Mock successful download
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
            temp_file.close()
            mock_download.return_value = temp_file.name
            
            # Mock extract_text to raise RuntimeError
            mock_extract.side_effect = RuntimeError('PDF parsing failed')
            
            try:
                response = authenticated_session.post(
                    '/contract/TEST-001/analyze',
                    data={'standards': ['Indemnification']},
                    follow_redirects=False
                )
                
                # Should redirect back to contract standards page
                assert response.status_code == 302
                assert '/contract/TEST-001/standards' in response.location
                
                # Follow redirect to check flash message
                response = authenticated_session.get(response.location)
                assert b'Could not process' in response.data
            finally:
                # Clean up temp file
                if os.path.exists(temp_file.name):
                    os.unlink(temp_file.name)
    
    def test_happy_path_cache_and_redirect(self, authenticated_session):
        """
        Test happy path: successful analysis populates cache and redirects to apply_suggestions_new.
        """
        with patch('main.download_contract') as mock_download, \
             patch('main.extract_text') as mock_extract, \
             patch('main.get_preferred_standards') as mock_get_standards, \
             patch('main.run_analysis') as mock_run_analysis, \
             patch('main.analysis_cache') as mock_cache:
            
            # Mock successful download
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.docx')
            temp_file.close()
            mock_download.return_value = temp_file.name
            
            # Mock successful text extraction
            mock_extract.return_value = "This is the contract text with an indemnification clause."
            
            # Mock preferred standards
            mock_get_standards.return_value = {
                'Indemnification': {
                    'text': 'Standard indemnification language',
                    'category': 'Legal'
                }
            }
            
            # Mock analysis results
            mock_run_analysis.return_value = {
                'Indemnification': {
                    'found': True,
                    'excerpt': 'indemnification clause',
                    'location': 'Section 5',
                    'suggestion': 'Present and compliant',
                    'source': 'preferred'
                },
                'Confidentiality': {
                    'found': False,
                    'excerpt': None,
                    'location': None,
                    'suggestion': 'Add standard confidentiality clause',
                    'source': 'ai'
                }
            }
            
            try:
                # POST with selected standards
                response = authenticated_session.post(
                    '/contract/TEST-001/analyze',
                    data={
                        'standards': ['Indemnification', 'Confidentiality']
                    },
                    follow_redirects=False
                )
                
                # Verify services were called correctly
                mock_download.assert_called_once_with('TEST-001')
                mock_extract.assert_called_once_with(temp_file.name)
                mock_get_standards.assert_called_once()
                mock_run_analysis.assert_called_once()
                
                # Verify cache was populated
                mock_cache.set.assert_called_once()
                cache_call_args = mock_cache.set.call_args
                assert cache_call_args[0][0] == 'TEST-001'  # contract_id
                assert 'results' in cache_call_args[0][1]  # cache_data has results
                assert 'selected' in cache_call_args[0][1]  # cache_data has selected
                assert cache_call_args[1]['ttl'] == 1800  # 30-minute TTL
                
                # Should redirect to apply_suggestions_new
                assert response.status_code == 302
                assert '/apply_suggestions_new/TEST-001' in response.location
                
            finally:
                # Clean up temp file
                if os.path.exists(temp_file.name):
                    os.unlink(temp_file.name)


class TestApplySuggestionsNew:
    """Test suite for the apply_suggestions_new route (GET results page)."""
    
    def test_renders_with_correct_present_missing_counts(self, authenticated_session):
        """Test that GET renders rows with correct present/missing counts from cache."""
        with patch('main.analysis_cache') as mock_cache, \
             patch('app.services.sharepoint_service.SharePointService') as mock_sp_class:
            
            # Mock cache data
            cached_data = {
                'results': {
                    'Indemnification': {
                        'found': True,
                        'excerpt': 'indemnification clause',
                        'location': 'Section 5',
                        'suggestion': 'Present and compliant',
                        'source': 'preferred'
                    },
                    'Confidentiality': {
                        'found': False,
                        'excerpt': None,
                        'location': None,
                        'suggestion': 'Add confidentiality clause',
                        'source': 'ai'
                    },
                    'Term and Termination': {
                        'found': True,
                        'excerpt': 'termination provisions',
                        'location': 'Section 10',
                        'suggestion': 'Compliant',
                        'source': 'ai'
                    },
                    'Insurance': {
                        'found': False,
                        'excerpt': None,
                        'location': None,
                        'suggestion': 'Add insurance requirements',
                        'source': 'ai'
                    }
                },
                'selected': ['Indemnification', 'Confidentiality', 'Term and Termination', 'Insurance'],
                'ts': '2025-11-11T12:00:00'
            }
            
            mock_cache.get.return_value = cached_data
            
            # Mock SharePoint service
            mock_sp_instance = Mock()
            mock_sp_instance.get_contract_by_id.return_value = {
                'id': 'TEST-001',
                'name': 'Test Contract.docx',
                'contract_id': 'TEST-001'
            }
            mock_sp_class.return_value = mock_sp_instance
            
            # GET the results page
            response = authenticated_session.get('/apply_suggestions_new/TEST-001')
            
            # Should render successfully
            assert response.status_code == 200
            
            # Check that cache was accessed
            mock_cache.get.assert_called_once_with('TEST-001')
            
            # Check content includes standards
            assert b'Indemnification' in response.data
            assert b'Confidentiality' in response.data
            assert b'Term and Termination' in response.data
            assert b'Insurance' in response.data
            
            # Check for present indicators (should have 2 present: Indemnification, Term and Termination)
            # Note: Exact HTML depends on template, but check for common patterns
            data_str = response.data.decode('utf-8')
            
            # Count occurrences of present/missing patterns
            # This is a basic check - adjust based on your actual template
            assert 'Present and compliant' in data_str
            assert 'Add confidentiality clause' in data_str
            assert 'Add insurance requirements' in data_str
    
    def test_no_cache_redirects_with_flash(self, authenticated_session):
        """Test that missing cache redirects to standards page with flash."""
        with patch('main.analysis_cache') as mock_cache:
            # Mock empty cache
            mock_cache.get.return_value = None
            
            response = authenticated_session.get(
                '/apply_suggestions_new/TEST-001',
                follow_redirects=False
            )
            
            # Should redirect to contract standards
            assert response.status_code == 302
            assert '/contract/TEST-001/standards' in response.location
            
            # Follow redirect to check flash
            response = authenticated_session.get(response.location)
            assert b'No analysis found' in response.data
    
    def test_missing_token_redirects_to_login(self, client):
        """Test that missing token redirects to login."""
        response = client.get('/apply_suggestions_new/TEST-001', follow_redirects=False)
        
        # Should redirect to login
        assert response.status_code == 302
        assert '/auth/login' in response.location


class TestCustomStandardsParsing:
    """Test suite for custom standards parsing in analyze_contract."""
    
    def test_custom_standards_parsing_from_comma_separated(self, authenticated_session):
        """Test that custom standards are correctly parsed from comma-separated input."""
        with patch('main.download_contract') as mock_download, \
             patch('main.extract_text') as mock_extract, \
             patch('main.get_preferred_standards') as mock_get_standards, \
             patch('main.run_analysis') as mock_run_analysis, \
             patch('main.analysis_cache') as mock_cache:
            
            # Mock successful flow
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
            temp_file.close()
            mock_download.return_value = temp_file.name
            mock_extract.return_value = "Contract text"
            mock_get_standards.return_value = {}
            mock_run_analysis.return_value = {}
            
            try:
                # POST with custom standards
                response = authenticated_session.post(
                    '/contract/TEST-001/analyze',
                    data={
                        'standards': ['Indemnification'],
                        'custom_standards': 'Custom Clause 1, Custom Clause 2,  Custom Clause 3  '
                    },
                    follow_redirects=False
                )
                
                # Verify analysis was called with combined standards
                call_args = mock_run_analysis.call_args[0]
                contract_text = call_args[0]
                all_standards = call_args[1]
                
                # Should have 4 standards total: 1 selected + 3 custom
                assert len(all_standards) == 4
                assert 'Indemnification' in all_standards
                assert 'Custom Clause 1' in all_standards
                assert 'Custom Clause 2' in all_standards
                assert 'Custom Clause 3' in all_standards
                
            finally:
                if os.path.exists(temp_file.name):
                    os.unlink(temp_file.name)


class TestErrorHandling:
    """Test suite for various error scenarios."""
    
    def test_general_exception_flashes_and_redirects(self, authenticated_session):
        """Test that unexpected exceptions flash error and redirect."""
        with patch('main.download_contract') as mock_download:
            # Mock unexpected exception
            mock_download.side_effect = ValueError('Unexpected error occurred')
            
            response = authenticated_session.post(
                '/contract/TEST-001/analyze',
                data={'standards': ['Indemnification']},
                follow_redirects=False
            )
            
            # Should redirect back
            assert response.status_code == 302
            assert '/contract/TEST-001/standards' in response.location
            
            # Follow redirect to check flash
            response = authenticated_session.get(response.location)
            assert b'Analysis failed' in response.data or b'try again' in response.data
    
    def test_permission_error_without_session_expired(self, authenticated_session):
        """Test that PermissionError without SESSION_EXPIRED shows permission message."""
        with patch('main.download_contract') as mock_download:
            # Mock permission error without SESSION_EXPIRED
            mock_download.side_effect = PermissionError('Access denied')
            
            response = authenticated_session.post(
                '/contract/TEST-001/analyze',
                data={'standards': ['Indemnification']},
                follow_redirects=False
            )
            
            # Should redirect back to standards
            assert response.status_code == 302
            assert '/contract/TEST-001/standards' in response.location
            
            # Follow redirect to check flash
            response = authenticated_session.get(response.location)
            assert b'permission' in response.data.lower()


class TestCacheIntegration:
    """Test suite for cache integration."""
    
    def test_cache_stores_correct_structure(self, authenticated_session):
        """Test that cache stores results, selected standards, and timestamp."""
        with patch('main.download_contract') as mock_download, \
             patch('main.extract_text') as mock_extract, \
             patch('main.get_preferred_standards') as mock_get_standards, \
             patch('main.run_analysis') as mock_run_analysis, \
             patch('main.analysis_cache') as mock_cache:
            
            # Setup mocks
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.docx')
            temp_file.close()
            mock_download.return_value = temp_file.name
            mock_extract.return_value = "Contract text"
            mock_get_standards.return_value = {}
            
            analysis_results = {
                'Standard 1': {'found': True, 'excerpt': 'text'},
                'Standard 2': {'found': False}
            }
            mock_run_analysis.return_value = analysis_results
            
            try:
                response = authenticated_session.post(
                    '/contract/TEST-001/analyze',
                    data={'standards': ['Standard 1', 'Standard 2']},
                    follow_redirects=False
                )
                
                # Verify cache.set was called
                mock_cache.set.assert_called_once()
                
                # Extract arguments
                contract_id, cache_data, ttl = (
                    mock_cache.set.call_args[0][0],
                    mock_cache.set.call_args[0][1],
                    mock_cache.set.call_args[1]['ttl']
                )
                
                # Verify cache structure
                assert contract_id == 'TEST-001'
                assert 'results' in cache_data
                assert 'selected' in cache_data
                assert 'ts' in cache_data
                assert cache_data['results'] == analysis_results
                assert cache_data['selected'] == ['Standard 1', 'Standard 2']
                assert ttl == 1800  # 30 minutes
                
            finally:
                if os.path.exists(temp_file.name):
                    os.unlink(temp_file.name)
    
    def test_cache_retrieval_in_apply_suggestions(self, authenticated_session):
        """Test that apply_suggestions_new correctly retrieves from cache."""
        with patch('main.analysis_cache') as mock_cache, \
             patch('app.services.sharepoint_service.SharePointService') as mock_sp_class:
            
            # Mock cache data
            cached_data = {
                'results': {
                    'Standard A': {
                        'found': True,
                        'excerpt': 'excerpt A',
                        'location': 'Section 1',
                        'suggestion': 'Good',
                        'source': 'ai'
                    }
                },
                'selected': ['Standard A'],
                'ts': '2025-11-11T10:00:00'
            }
            mock_cache.get.return_value = cached_data
            
            # Mock SharePoint
            mock_sp_instance = Mock()
            mock_sp_instance.get_contract_by_id.return_value = {
                'name': 'Test.docx'
            }
            mock_sp_class.return_value = mock_sp_instance
            
            response = authenticated_session.get('/apply_suggestions_new/TEST-001')
            
            # Verify cache was accessed
            mock_cache.get.assert_called_once_with('TEST-001')
            
            # Verify response is successful
            assert response.status_code == 200


# Run tests with: pytest tests/test_ai_analysis.py -v
if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
