from flask import Flask, render_template, session, request, jsonify, flash, redirect, url_for
import os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Import analysis services
from app.services.sp_download import download_contract
from app.services.text_extractor import extract_text
from app.services.sp_preferred_standards import get_preferred_standards, get_preferred_standards_dict
from app.services.analysis_orchestrator import analyze_contract as run_analysis
from app.cache import analysis_cache

print("\n=== DEBUG APP INITIALIZATION ===")

# Load environment variables
load_dotenv()
print(f"DEBUG: .env file loaded")

app = Flask(__name__, static_folder='app/static', template_folder='app/templates')
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key')
print(f"DEBUG: Flask app created")
print(f"DEBUG: SECRET_KEY set: {bool(app.secret_key)}")

# Configure session to handle large data
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# MSAL Configuration
app.config['CLIENT_ID'] = os.getenv('O365_CLIENT_ID')
app.config['CLIENT_SECRET'] = os.getenv('O365_CLIENT_SECRET')
app.config['TENANT_ID'] = os.getenv('O365_TENANT_ID')
app.config['AUTHORITY'] = f"https://login.microsoftonline.com/{app.config['TENANT_ID']}"
app.config['SCOPE'] = ["User.Read"]  # Start with basic scope
app.config['REDIRECT_URI'] = os.getenv('REDIRECT_URI', 'http://localhost:5000/auth/redirect')

print(f"DEBUG: CLIENT_ID: {app.config['CLIENT_ID'][:10] + '...' if app.config['CLIENT_ID'] else 'None'}")
print(f"DEBUG: CLIENT_SECRET: {'SET' if app.config['CLIENT_SECRET'] else 'None'}")
print(f"DEBUG: TENANT_ID: {app.config['TENANT_ID'][:10] + '...' if app.config['TENANT_ID'] else 'None'}")
print(f"DEBUG: REDIRECT_URI: {app.config['REDIRECT_URI']}")

# SharePoint Configuration
app.config['SP_SITE_URL'] = os.getenv('SP_SITE_URL')
app.config['SP_CLIENT_ID'] = os.getenv('SP_CLIENT_ID')
app.config['SP_CLIENT_SECRET'] = os.getenv('SP_CLIENT_SECRET')
app.config['SP_ADMIN_LIST_ID'] = os.getenv('SP_ADMIN_LIST_ID')
app.config['SP_ADMIN_EMAIL_COLUMN'] = os.getenv('SP_ADMIN_EMAIL_COLUMN', 'Email')
app.config['SP_ADMIN_ACTIVE_COLUMN'] = os.getenv('SP_ADMIN_ACTIVE_COLUMN', 'Active')

print(f"DEBUG: SP_SITE_URL: {app.config['SP_SITE_URL']}")
print(f"DEBUG: SP_ADMIN_LIST_ID: {app.config['SP_ADMIN_LIST_ID'][:10] + '...' if app.config['SP_ADMIN_LIST_ID'] else 'None'}")

# Import authentication utilities
from app.utils.auth_utils import login_required
from app.utils.admin_utils import admin_required

# Register auth blueprint
from app.routes.auth_routes import auth_bp
app.register_blueprint(auth_bp)

# Template context
@app.context_processor
def inject_auth():
    """Make user info available in all templates"""
    return {
        'user_name': session.get('user_name'),
        'user_email': session.get('user_email'),
        'is_authenticated': bool(session.get('access_token')),
        'is_admin': session.get('is_admin', False)
    }

@app.route('/')
@login_required
def index():
    print(f"\n=== DEBUG index() route called ===")
    return render_template('index.html')

@app.route('/submit-contract', methods=['POST'])
@login_required
def submit_contract():
    """Handle contract submission and upload to SharePoint"""
    try:
        # Get form data
        submitter_name = request.form.get('submitterName')
        submitter_email = request.form.get('submitterEmail')
        contract_name = request.form.get('contractName')
        business_approver_email = request.form.get('businessApproverEmail')
        date_requested = request.form.get('dateRequested')
        business_terms = request.form.getlist('businessTerms')
        additional_notes = request.form.get('additionalNotes', '')
        
        # Validate required fields
        if not all([submitter_name, submitter_email, contract_name, business_approver_email, date_requested]):
            return jsonify({'success': False, 'message': 'All required fields must be filled'}), 400
        
        # Check if file was uploaded
        if 'contractFile' not in request.files:
            return jsonify({'success': False, 'message': 'No file uploaded'}), 400
        
        file = request.files['contractFile']
        if file.filename == '':
            return jsonify({'success': False, 'message': 'No file selected'}), 400
        
        # Validate file type
        if not file.filename.lower().endswith(('.docx', '.doc')):
            return jsonify({'success': False, 'message': 'Only DOCX files are allowed'}), 400
        
        # Read file content
        file_content = file.read()
        
        # Import SharePoint service
        from app.services.sharepoint_service import sharepoint_service
        
        # Upload to SharePoint
        upload_result = sharepoint_service.upload_contract(
            file_content=file_content,
            file_name=file.filename,
            submitter_name=submitter_name,
            contract_name=contract_name,
            submitter_email=submitter_email,
            business_approver_email=business_approver_email,
            date_requested=date_requested,
            business_terms=business_terms,
            additional_notes=additional_notes
        )
        
        if upload_result['success']:
            # Store submission details in session for success message
            session['last_submission'] = {
                'contract_name': contract_name,
                'file_url': upload_result['file_url'],
                'file_name': upload_result['file_name'],
                'submitter_name': submitter_name,
                'business_approver_email': business_approver_email,
                'date_requested': date_requested,
                'business_terms': business_terms,
                'additional_notes': additional_notes
            }
            
            flash(f'Contract "{contract_name}" uploaded successfully to SharePoint!', 'success')
            return jsonify({
                'success': True, 
                'message': f'Contract submitted successfully! Contract ID: {upload_result["contract_id"]}',
                'file_url': upload_result['file_url'],
                'contract_id': upload_result['contract_id'],
                'redirect_url': url_for('index')
            })
        else:
            return jsonify({
                'success': False, 
                'message': f'Failed to upload to SharePoint: {upload_result.get("error", "Unknown error")}'
            }), 500
            
    except Exception as e:
        print(f"Error in submit_contract: {str(e)}")
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'}), 500

@app.route('/test-sharepoint')
def test_sharepoint():
    """Test SharePoint connection"""
    try:
        from app.services.sharepoint_service import sharepoint_service
        
        # Test basic connection
        sharepoint_service.create_contract_folder_if_not_exists()
        
        return jsonify({'success': True, 'message': 'SharePoint connection successful'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/contracts')
@login_required
def get_contracts():
    """Get contracts data from SharePoint list"""
    try:
        from app.services.sharepoint_service import sharepoint_service
        
        # Get user info from session
        user_email = session.get('user_email')
        is_admin = session.get('is_admin', False)
        
        print(f"\n=== DEBUG /api/contracts ===")
        print(f"User: {user_email}")
        print(f"Is Admin: {is_admin}")
        
        # Get contracts from SharePoint list (filtered by user if not admin)
        contracts = sharepoint_service.get_contract_files(
            user_email=user_email,
            is_admin=is_admin
        )
        
        return jsonify({
            'success': True,
            'contracts': contracts,
            'count': len(contracts)
        })
        
    except Exception as e:
        print(f"Error getting contracts: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route('/admin')
@admin_required
def admin_panel():
    """Admin-only route - requires user to be in SharePoint admin list"""
    print(f"\n=== DEBUG admin_panel() route called ===")
    return render_template('admin.html')

@app.route('/debug/lists')
@admin_required
def debug_lists():
    """Debug route to list all SharePoint lists"""
    import requests
    
    try:
        print("\n=== DEBUG /debug/lists route ===")
        token = session.get('access_token')
        site_id = os.getenv('O365_SITE_ID')
        
        print(f"Token present: {bool(token)}")
        print(f"Site ID: {site_id}")
        
        if not token:
            return jsonify({'error': 'No access token in session'}), 401
        
        url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists"
        print(f"URL: {url}")
        
        headers = {'Authorization': f'Bearer {token}'}
        
        print(f"Making request to Graph API...")
        response = requests.get(url, headers=headers, timeout=30)
        print(f"Response status: {response.status_code}")
        
        response.raise_for_status()
        
        lists_data = response.json()
        lists = lists_data.get('value', [])
        print(f"Found {len(lists)} lists")
        
        # Format for display
        result = []
        for lst in lists:
            list_info = {
                'name': lst.get('displayName'),
                'id': lst.get('id'),
                'description': lst.get('description', 'N/A'),
                'webUrl': lst.get('webUrl', 'N/A')
            }
            result.append(list_info)
            print(f"  - {list_info['name']}: {list_info['id']}")
        
        return jsonify({'lists': result, 'count': len(result), 'site_id': site_id})
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"ERROR in debug_lists: {str(e)}")
        print(error_trace)
        return jsonify({'error': str(e), 'trace': error_trace}), 500

# Default standards list (19 standards)
@app.route('/contract/<contract_id>/standards')
@login_required
def contract_standards(contract_id):
    """Display standards selection page for a specific contract"""
    try:
        from app.services.sharepoint_service import sharepoint_service
        
        print(f"\n=== DEBUG contract_standards ===")
        print(f"Contract ID: {contract_id}")
        
        # Get user info
        user_email = session.get('user_email')
        is_admin = session.get('is_admin', False)
        
        # Get all contracts to find this specific one
        contracts = sharepoint_service.get_contract_files(
            user_email=user_email,
            is_admin=is_admin
        )
        
        # Find the specific contract
        contract = next((c for c in contracts if c['contract_id'] == contract_id), None)
        
        if not contract:
            flash('Contract not found', 'error')
            return redirect(url_for('dashboard'))
        
        # Check if user has access to this contract (admins can access all)
        if not is_admin and contract['submitter_email'].lower() != user_email.lower():
            flash('You do not have access to this contract', 'error')
            return redirect(url_for('dashboard'))
        
        # Get preferred standards from SharePoint
        print(f"Loading preferred standards from SharePoint...")
        preferred_standards = get_preferred_standards()
        print(f"Loaded {len(preferred_standards)} preferred standards")
        if preferred_standards:
            print(f"First standard example: {preferred_standards[0]}")
        else:
            print(f"WARNING: No standards loaded! Check SharePoint connection and list configuration.")
        
        return render_template('standards.html',
                             contract_id=contract_id,
                             contract_name=contract['name'],
                             preferred_standards=preferred_standards)
        
    except Exception as e:
        print(f"Error in contract_standards: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f'Error loading contract standards: {str(e)}', 'error')
        return redirect(url_for('dashboard'))

@app.route('/contract/<contract_id>/analyze', methods=['POST'], endpoint='analyze_contract')
@login_required
def analyze_contract_route(contract_id):
    """Run AI analysis on contract with selected standards"""
    temp_file_path = None
    
    try:
        print(f"\n=== DEBUG analyze_contract ===")
        print(f"Contract ID: {contract_id}")
        
        # Get selected standards from form
        selected_standards = request.form.getlist('standards')
        custom_standards_text = request.form.get('custom_standards', '').strip()
        
        # Parse custom standards
        custom_standards = []
        if custom_standards_text:
            custom_standards = [s.strip() for s in custom_standards_text.split(',') if s.strip()]
        
        # Combine all standards
        all_standards = selected_standards + custom_standards
        
        print(f"Selected standards: {len(selected_standards)}")
        print(f"Custom standards: {len(custom_standards)}")
        print(f"Total standards: {len(all_standards)}")
        
        if not all_standards:
            flash('Please select at least one standard to analyze', 'warning')
            return redirect(url_for('contract_standards', contract_id=contract_id))
        
        # Download contract from SharePoint
        print(f"Downloading contract {contract_id} from SharePoint...")
        temp_file_path = download_contract(contract_id)
        print(f"Contract downloaded to: {temp_file_path}")
        
        # Extract text from contract
        print(f"Extracting text from contract...")
        contract_text = extract_text(temp_file_path)
        print(f"Extracted {len(contract_text)} characters")
        
        # Get preferred standards from SharePoint (as dict for analysis)
        print(f"Loading preferred standards from SharePoint...")
        preferred_standards_dict = get_preferred_standards_dict()
        print(f"Loaded {len(preferred_standards_dict)} preferred standards")
        
        # Run AI analysis
        print(f"Running AI analysis for {len(all_standards)} standards...")
        analysis_results = run_analysis(contract_text, all_standards, preferred_standards_dict)
        print(f"Analysis complete: {len(analysis_results)} results")
        
        # Cache the results with 30-minute TTL
        cache_data = {
            'results': analysis_results,
            'selected': all_standards,
            'ts': datetime.utcnow().isoformat()
        }
        analysis_cache.set(contract_id, cache_data, ttl=1800)
        print(f"Results cached for contract {contract_id}")
        
        # Clean up temporary file
        if temp_file_path and Path(temp_file_path).exists():
            Path(temp_file_path).unlink()
            print(f"Cleaned up temporary file: {temp_file_path}")
        
        flash('✅ AI analysis completed successfully!', 'success')
        return redirect(url_for('apply_suggestions_new', contract_id=contract_id))
        
    except PermissionError as e:
        if "SESSION_EXPIRED" in str(e):
            flash('Session expired — please sign in again.', 'warning')
            return redirect(url_for('auth.login'))
        else:
            print(f"Permission error in analyze_contract: {str(e)}")
            import traceback
            traceback.print_exc()
            flash('You do not have permission to access this contract.', 'error')
            return redirect(url_for('contract_standards', contract_id=contract_id))
            
    except FileNotFoundError as e:
        print(f"File not found in analyze_contract: {str(e)}")
        import traceback
        traceback.print_exc()
        flash('Contract file not found in SharePoint.', 'error')
        return redirect(url_for('contract_standards', contract_id=contract_id))
        
    except RuntimeError as e:
        print(f"Runtime error in analyze_contract: {str(e)}")
        import traceback
        traceback.print_exc()
        flash('Could not process the document.', 'error')
        return redirect(url_for('contract_standards', contract_id=contract_id))
        
    except Exception as e:
        print(f"Unexpected error in analyze_contract: {str(e)}")
        import traceback
        traceback.print_exc()
        flash('Analysis failed; please try again.', 'error')
        return redirect(url_for('contract_standards', contract_id=contract_id))
        
    finally:
        # Ensure cleanup of temporary file even if error occurs
        if temp_file_path:
            try:
                if Path(temp_file_path).exists():
                    Path(temp_file_path).unlink()
            except Exception as cleanup_error:
                print(f"Warning: Failed to clean up temporary file: {cleanup_error}")

@app.route('/apply_suggestions_new/<contract_id>')
@login_required
def apply_suggestions_new(contract_id):
    """Display AI analysis results for contract"""
    try:
        print(f"\n=== DEBUG apply_suggestions_new ===")
        print(f"Contract ID: {contract_id}")
        
        # Get analysis from cache
        cached_data = analysis_cache.get(contract_id)
        
        if not cached_data:
            print(f"No cached analysis found for contract {contract_id}")
            flash('No analysis found for this contract.', 'warning')
            return redirect(url_for('contract_standards', contract_id=contract_id))
        
        # Extract cached data
        analysis_results = cached_data.get('results', {})
        selected_standards = cached_data.get('selected', [])
        timestamp = cached_data.get('ts', '')
        
        print(f"Found cached analysis: {len(analysis_results)} results")
        
        # Get contract details from SharePoint
        from app.services.sharepoint_service import SharePointService
        sp_service = SharePointService()
        contract = sp_service.get_contract_by_id(contract_id)
        
        if not contract:
            flash('Contract not found.', 'error')
            return redirect(url_for('dashboard'))
        
        contract_name = contract.get('name', 'Unknown Contract')
        
        # Build summary items list for template
        summary_items = []
        for standard_name in selected_standards:
            result = analysis_results.get(standard_name, {})
            
            summary_items.append({
                'standard': standard_name,
                'present': result.get('found', False),
                'excerpt': result.get('excerpt') or 'N/A',
                'location': result.get('location') or 'N/A',
                'suggestion': result.get('suggestion') or 'N/A',
                'source': result.get('source', 'ai')
            })
        
        print(f"Rendering apply_suggestions with {len(summary_items)} items")
        
        # Render template with analysis_completed flag
        return render_template(
            'apply_suggestions.html',
            analysis_completed=True,
            summary=summary_items,
            contract_id=contract_id,
            contract_name=contract_name,
            timestamp=timestamp
        )
        
    except Exception as e:
        print(f"Error in apply_suggestions_new: {str(e)}")
        import traceback
        traceback.print_exc()
        flash('Error loading analysis results.', 'error')
        return redirect(url_for('dashboard'))

@app.route('/contracts/<contract_id>/apply_suggestions', methods=['POST'])
@login_required
def apply_suggestions_action(contract_id):
    """Apply selected suggestions to contract and return download URL."""
    from app.services.sharepoint_service import sharepoint_service
    from app.services import doc_editor, sp_upload
    import tempfile
    
    try:
        # Parse JSON payload
        data = request.get_json()
        if not data or 'items' not in data:
            return jsonify({'error': 'Invalid payload: missing items'}), 400
        
        items = data['items']
        if not items:
            return jsonify({'error': 'No standards selected'}), 400
        
        # Validate item structure
        for item in items:
            if 'standard' not in item or 'suggestion' not in item:
                return jsonify({'error': 'Invalid item structure'}), 400
        
        print(f"\n{'='*70}")
        print(f"APPLY SUGGESTIONS: Contract {contract_id}")
        print(f"{'='*70}")
        print(f"Applying {len(items)} suggestions to contract {contract_id}")
        for i, item in enumerate(items[:3]):
            print(f"  [{i+1}] {item.get('standard', 'N/A')[:40]}...")
        
        # Get contract metadata
        print(f"\nStep 1: Fetching contract metadata...")
        contract = sharepoint_service.get_contract_by_id(contract_id)
        if not contract:
            print(f"✗ Contract not found: {contract_id}")
            return jsonify({'error': 'Contract not found'}), 404
        
        drive_id = contract.get('DriveId') or os.getenv('DRIVE_ID')
        original_filename = contract.get('FileName', 'contract.docx')
        print(f"✓ Contract metadata retrieved")
        print(f"  Drive ID: {drive_id}")
        print(f"  Filename: {original_filename}")
        
        # Download original document
        print(f"\nStep 2: Downloading original document: {original_filename}")
        try:
            doc_path = download_contract(contract_id)
            doc_size = doc_path.stat().st_size
            print(f"✓ Downloaded to temp file: {doc_path}")
            print(f"  File size: {doc_size:,} bytes")
        except FileNotFoundError:
            print(f"✗ ERROR: Original document not found")
            return jsonify({'error': 'Original document not found'}), 404
        except PermissionError as e:
            if 'SESSION_EXPIRED' in str(e):
                print(f"✗ ERROR: Session expired")
                return jsonify({'error': 'Session expired', 'message': 'Please sign in again'}), 401
            raise
        
        # Use the downloaded temp file directly
        print(f"\nStep 3: Using downloaded temp file for processing...")
        original_path = doc_path
        print(f"✓ Original path ready: {original_path}")
        
        try:
            # Get all standards for style detection
            print(f"\nStep 4: Getting preferred standards for style detection...")
            all_standards = get_preferred_standards()
            known_standard_names = [s['standard'] for s in all_standards if 'standard' in s]
            print(f"✓ Found {len(known_standard_names)} known standards")
            
            # Apply suggestions to document
            print(f"\nStep 5: Appending {len(items)} standards to document...")
            edited_path = doc_editor.append_suggested_standards(
                original_path,
                items,
                known_standards=known_standard_names
            )
            print(f"✓ Document editing complete")
            
            # Read edited content
            print(f"\nStep 6: Reading edited document...")
            with open(edited_path, 'rb') as f:
                edited_content = f.read()
            print(f"✓ Read {len(edited_content):,} bytes")
            
            # Generate edited filename
            edited_filename = sp_upload.generate_edited_filename(original_filename)
            print(f"✓ Generated filename: {edited_filename}")
            
            # Upload to SharePoint
            print(f"\nStep 7: Uploading edited document to SharePoint...")
            try:
                upload_result = sp_upload.upload_file(
                    drive_id=drive_id,
                    folder_path='',  # Same folder as original (root of ContractFiles)
                    filename=edited_filename,
                    content=edited_content
                )
                print(f"✓ Upload successful: {upload_result.get('name')}")
            except PermissionError as e:
                print(f"✗ PermissionError during upload: {e}")
                if 'SESSION_EXPIRED' in str(e):
                    return jsonify({'error': 'Session expired', 'message': 'Please sign in again'}), 401
                raise
            except sp_upload.UploadError as e:
                print(f"✗ UploadError: {str(e)}")
                return jsonify({'error': 'Upload failed', 'message': str(e)}), 502
            
            # Store edited file info in session for download
            print(f"\nStep 8: Storing file info in session...")
            session[f'edited_file_{contract_id}'] = {
                'filename': edited_filename,
                'drive_id': drive_id,
                'uploaded_at': datetime.utcnow().isoformat()
            }
            print(f"✓ Session updated")
            
            # Generate download URL
            download_url = url_for(
                'download_edited_contract',
                contract_id=contract_id,
                _external=True
            )
            
            print(f"\n✓✓✓ SUCCESS ✓✓✓")
            print(f"  Standards applied: {len(items)}")
            print(f"  Download URL: {download_url}")
            print(f"{'='*70}\n")
            
            return jsonify({
                'success': True,
                'download_url': download_url,
                'filename': edited_filename,
                'standards_applied': len(items)
            })
        
        finally:
            # Cleanup temp files
            if original_path.exists():
                original_path.unlink()
            if 'edited_path' in locals() and edited_path.exists():
                edited_path.unlink()
    
    except PermissionError as e:
        if 'SESSION_EXPIRED' in str(e):
            return jsonify({'error': 'Session expired', 'message': 'Please sign in again'}), 401
        raise
    except Exception as e:
        print(f"Error applying suggestions: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Internal server error', 'message': str(e)}), 500


@app.route('/contracts/<contract_id>/download_edited')
@login_required
def download_edited_contract(contract_id):
    """Download the edited contract document."""
    from flask import send_file
    from io import BytesIO
    
    print(f"\n{'='*70}")
    print(f"DOWNLOAD EDITED: Contract {contract_id}")
    print(f"{'='*70}")
    print(f"User: {session.get('user_email', 'Unknown')}")
    
    try:
        # Get edited file info from session
        print(f"\nLooking for session key: edited_file_{contract_id}")
        file_info = session.get(f'edited_file_{contract_id}')
        if not file_info:
            print(f"✗ ERROR: No edited file found in session")
            print(f"Available keys: {[k for k in session.keys() if 'edited' in k]}")
            return jsonify({'error': 'No edited file found'}), 404
        
        filename = file_info['filename']
        drive_id = file_info['drive_id']
        print(f"✓ Found edited file:")
        print(f"  Filename: {filename}")
        print(f"  Drive ID: {drive_id}")
        
        print(f"\nDownloading edited file from SharePoint...")
        
        # Download from SharePoint using the same approach as original
        # We'll use the drive_id and filename to construct the download
        try:
            from app.services.sp_download import download_contract_by_filename
            content = download_contract_by_filename(drive_id, filename)
            print(f"✓ Downloaded {len(content):,} bytes")
        except FileNotFoundError:
            print(f"✗ ERROR: Edited file not found in SharePoint")
            return jsonify({'error': 'Edited file not found in SharePoint'}), 404
        except PermissionError as e:
            print(f"✗ ERROR: Permission denied - {e}")
            if 'SESSION_EXPIRED' in str(e):
                flash('Session expired — please sign in again', 'error')
                return redirect(url_for('login'))
            raise
        
        # Send file as attachment
        print(f"✓ Sending file to user: {filename}")
        print(f"{'='*70}\n")
        return send_file(
            BytesIO(content),
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            as_attachment=True,
            download_name=filename
        )
    
    except Exception as e:
        print(f"Error downloading edited contract: {str(e)}")
        import traceback
        traceback.print_exc()
        flash('Error downloading edited contract.', 'error')
        return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)