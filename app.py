from flask import Flask, render_template, session, request, jsonify, flash, redirect, url_for
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__, static_folder='app/static', template_folder='app/templates')
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key')

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

# Import authentication utilities
from app.utils.auth_utils import login_required

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
        'is_authenticated': bool(session.get('access_token'))
    }

@app.route('/')
@login_required
def index():
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
        
        # Get contracts from SharePoint list
        contracts = sharepoint_service.get_contract_files()
        
        return jsonify({
            'success': True,
            'contracts': contracts,
            'count': len(contracts)
        })
        
    except Exception as e:
        print(f"Error getting contracts: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)