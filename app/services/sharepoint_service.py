"""
SharePoint service for uploading contracts using Microsoft Graph API
"""
import os
import requests
import base64
from datetime import datetime
import msal
import uuid

class SharePointService:
    def __init__(self):
        self.client_id = os.getenv('O365_CLIENT_ID')
        self.client_secret = os.getenv('O365_CLIENT_SECRET')
        self.tenant_id = os.getenv('O365_TENANT_ID')
        self.site_id = None
        self.drive_id = os.getenv('DRIVE_ID')  # ContractFiles library drive ID
        
        # Token management
        self.access_token = None
        self.token_expires_at = None  # Track when token expires
        
        # Microsoft Graph API base URL
        self.graph_url = "https://graph.microsoft.com/v1.0"
        
        # SharePoint site details
        self.site_url = "https://peakcampus.sharepoint.com/sites/BaseCampApps"
        
        # Get access token
        self.access_token = self._get_access_token()
        
        # Get site ID for list operations
        self.site_id = self._get_site_id()
    
    def _get_access_token(self):
        """Get access token using client credentials flow"""
        try:
            from datetime import datetime, timedelta
            
            authority = f"https://login.microsoftonline.com/{self.tenant_id}"
            app = msal.ConfidentialClientApplication(
                self.client_id,
                authority=authority,
                client_credential=self.client_secret
            )
            
            # Get token for Microsoft Graph
            scopes = ["https://graph.microsoft.com/.default"]
            result = app.acquire_token_for_client(scopes=scopes)
            
            if "access_token" in result:
                # Store token and expiration time in UTC
                self.access_token = result["access_token"]
                # Token expires in 'expires_in' seconds (usually 3599 = ~1 hour)
                expires_in = result.get("expires_in", 3599)
                # Use UTC time to match Microsoft's token expiration
                self.token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in - 300)  # Refresh 5 min early
                
                print(f"Token acquired, expires at: {self.token_expires_at} UTC")
                return result["access_token"]
            else:
                raise Exception(f"Failed to get access token: {result}")
                
        except Exception as e:
            print(f"Error getting access token: {str(e)}")
            raise
    
    def _ensure_valid_token(self):
        """Check if token is valid and refresh if needed (using UTC time)"""
        from datetime import datetime
        
        # If token doesn't exist or is expired, get a new one (compare in UTC)
        if self.token_expires_at is None or datetime.utcnow() >= self.token_expires_at:
            print("Token expired or missing, refreshing...")
            self.access_token = self._get_access_token()
            # Site ID might also need refresh after token refresh
            if self.site_id is None:
                self.site_id = self._get_site_id()
        else:
            time_left = (self.token_expires_at - datetime.utcnow()).total_seconds() / 60
            print(f"Token still valid, {time_left:.1f} minutes remaining")
    
    def _get_site_id(self):
        """Get the SharePoint site ID"""
        try:
            site_url = f"{self.graph_url}/sites/peakcampus.sharepoint.com:/sites/BaseCampApps"
            
            headers = {
                'Authorization': f'Bearer {self.access_token}'
            }
            
            response = requests.get(site_url, headers=headers)
            
            if response.status_code == 200:
                site_data = response.json()
                return site_data['id']
            else:
                raise Exception(f"Failed to get site ID: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"Error getting site ID: {str(e)}")
            raise
    
    def upload_contract(self, file_content, file_name, submitter_name, contract_name, submitter_email, business_approver_email, date_requested, business_terms, additional_notes):
        """
        Upload a contract file to SharePoint ContractFiles library and create metadata record
        
        Args:
            file_content (bytes): The file content to upload
            file_name (str): Original filename
            submitter_name (str): Name of the person submitting
            contract_name (str): Name/title of the contract
            submitter_email (str): Email of submitter
            business_approver_email (str): Business approver email
            date_requested (str): Date requested
            business_terms (list): List of selected business terms
            additional_notes (str): Additional notes
            
        Returns:
            dict: Upload result with success status and file URL
        """
        try:
            # Ensure token is valid before making API calls
            self._ensure_valid_token()
            
            print(f"\n=== DEBUG upload_contract ===")
            print(f"Contract Name: {contract_name}")
            print(f"File Name: {file_name}")
            print(f"Submitter: {submitter_name} ({submitter_email})")
            
            # Generate unique contract ID
            contract_id = str(uuid.uuid4())[:8].upper()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Use original uploaded filename (without extension) for naming
            # Extract base name without extension
            import re
            base_filename = file_name.rsplit('.', 1)[0] if '.' in file_name else file_name
            
            # Sanitize filename (remove invalid characters)
            # Invalid characters for Windows/SharePoint: < > : " / \ | ? *
            safe_filename = re.sub(r'[<>:"/\\|?*]', '_', base_filename)
            safe_filename = safe_filename.strip()
            
            # Replace spaces with underscores for cleaner filenames
            safe_filename = safe_filename.replace(' ', '_')
            
            # Calculate max length: 100 total - "_uploaded.docx" (14 chars)
            max_basename_length = 100 - 14  # 86 characters max
            
            # Truncate if necessary
            if len(safe_filename) > max_basename_length:
                safe_filename = safe_filename[:max_basename_length].rstrip('_')
                print(f"Filename truncated to fit 100 character limit")
            
            # Generate filename: OriginalFilename_uploaded.docx
            unique_filename = f"{safe_filename}_uploaded.docx"
            
            print(f"Contract ID: {contract_id}")
            print(f"Unique Filename: {unique_filename} ({len(unique_filename)} chars)")
            
            # Upload file to ContractFiles library (root, not in Contracts subfolder)
            upload_url = f"{self.graph_url}/drives/{self.drive_id}/root:/{unique_filename}:/content"
            
            print(f"Upload URL: {upload_url}")
            
            # Use delegated user token from session so file shows correct creator
            from flask import session
            delegated_token = session.get('access_token')
            upload_token = delegated_token if delegated_token else self.access_token
            
            if delegated_token:
                print(f"✓ Using delegated user token for upload (will show {submitter_email} as creator)")
            else:
                print(f"⚠ No delegated token, using app token (will show 'SharePoint App')")
            
            headers = {
                'Authorization': f'Bearer {upload_token}',
                'Content-Type': 'application/octet-stream'
            }
            
            # Upload the file
            print(f"Uploading file to SharePoint...")
            response = requests.put(upload_url, headers=headers, data=file_content)
            
            print(f"Upload response status: {response.status_code}")
            
            if response.status_code in [200, 201]:
                file_info = response.json()
                
                # Get the SharePoint URL for the document
                document_url = file_info.get('webUrl', '')
                file_id = file_info.get('id')
                
                print(f"✓ File uploaded successfully!")
                print(f"Document URL: {document_url}")
                print(f"File ID: {file_id}")
                print(f"✓ File uploaded with delegated token - {submitter_email} will be shown as creator")
                
                print(f"Now creating metadata record in Uploaded Contracts list...")
                
                # Create metadata record in "Uploaded Contracts" list
                metadata_result = self._create_contract_metadata(
                    contract_id=contract_id,
                    contract_name=contract_name,
                    submitter_name=submitter_name,
                    submitter_email=submitter_email,
                    business_approver_email=business_approver_email,
                    date_requested=date_requested,
                    business_terms=business_terms,
                    additional_notes=additional_notes,
                    document_url=document_url,
                    file_name=unique_filename
                )
                
                print(f"Metadata creation result: {metadata_result['success']}")
                if not metadata_result['success']:
                    print(f"Metadata error: {metadata_result.get('error', 'Unknown error')}")
                
                return {
                    'success': True,
                    'file_url': document_url,
                    'file_name': unique_filename,
                    'file_id': file_info['id'],
                    'contract_id': contract_id,
                    'metadata_created': metadata_result['success'],
                    'message': 'Contract uploaded successfully to SharePoint'
                }
            else:
                error_msg = f"Upload failed with status {response.status_code}: {response.text}"
                print(f"✗ {error_msg}")
                return {
                    'success': False,
                    'error': error_msg,
                    'message': 'Failed to upload contract to SharePoint'
                }
                
        except Exception as e:
            error_msg = f"Error uploading file to SharePoint: {str(e)}"
            print(f"✗ EXCEPTION in upload_contract: {error_msg}")
            import traceback
            print(f"Traceback:\n{traceback.format_exc()}")
            return {
                'success': False,
                'error': error_msg,
                'message': 'Failed to upload contract to SharePoint'
            }
    
    def _update_file_creator(self, file_id, user_email):
        """
        Update the file's Modified By field to show the actual user instead of SharePoint App.
        
        Args:
            file_id: The DriveItem ID from the file upload response
            user_email: Email of the user to set as creator/modifier
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            from flask import session
            
            print(f"\n=== DEBUG _update_file_creator ===")
            print(f"File ID: {file_id}")
            print(f"User Email: {user_email}")
            
            # Use delegated user token from session instead of app token
            # App tokens don't have permission to update file metadata
            delegated_token = session.get('access_token')
            if not delegated_token:
                print(f"✗ No delegated token in session, cannot update file creator")
                return False
            
            print(f"✓ Using delegated user token from session")
            
            # First, get the user's ID from their email
            user_lookup_url = f"{self.graph_url}/users/{user_email}"
            headers = {
                'Authorization': f'Bearer {delegated_token}',
                'Content-Type': 'application/json'
            }
            
            user_response = requests.get(user_lookup_url, headers=headers)
            
            if user_response.status_code != 200:
                print(f"✗ Failed to lookup user: {user_response.status_code} - {user_response.text}")
                return False
            
            user_data = user_response.json()
            user_id = user_data.get('id')
            user_display_name = user_data.get('displayName')
            print(f"✓ Found user: {user_display_name} (ID: {user_id})")
            
            # Get the list item associated with this drive item
            # Files in document libraries have associated list items
            list_item_url = f"{self.graph_url}/drives/{self.drive_id}/items/{file_id}/listItem"
            list_item_response = requests.get(list_item_url, headers=headers)
            
            if list_item_response.status_code != 200:
                print(f"✗ Failed to get list item: {list_item_response.status_code} - {list_item_response.text}")
                return False
            
            list_item_data = list_item_response.json()
            list_item_id = list_item_data.get('id')
            parent_ref = list_item_data.get('parentReference', {})
            list_id = parent_ref.get('id')  # Get the actual list ID from parent reference
            
            print(f"✓ Found list item ID: {list_item_id}")
            print(f"✓ Found list ID: {list_id}")
            
            # For "Modified By" to show correctly, we need to update the file metadata
            # using the delegated user token. Simply making any update with the user's token
            # will set them as the modifier. We'll update a harmless custom property.
            
            # Update approach: Patch the list item fields with the user's token
            # This will automatically set the user as "Modified By"
            update_url = f"{self.graph_url}/drives/{self.drive_id}/items/{file_id}/listItem/fields"
            
            # Make a minimal update - add or update a custom field
            # This triggers SharePoint to record the user as modifier
            update_data = {
                '_ModifiedByUser': user_email  # Custom tracking field
            }
            
            print(f"Updating file metadata with user token to set Modified By...")
            update_response = requests.patch(update_url, headers=headers, json=update_data)
            
            if update_response.status_code == 200:
                print(f"✓ Successfully updated file - Modified By should now show {user_display_name}")
                return True
            else:
                print(f"✗ Failed to update: {update_response.status_code} - {update_response.text}")
                # This is not a critical failure - file is uploaded, just attribution is wrong
                # So we'll log but not fail the upload
                return False
                
        except Exception as e:
            print(f"✗ Exception updating file creator: {e}")
            import traceback
            traceback.print_exc()
            # Non-critical - don't fail the upload
            return False
    
    def _create_contract_metadata(self, contract_id, contract_name, submitter_name, submitter_email, 
                                business_approver_email, date_requested, business_terms, 
                                additional_notes, document_url, file_name):
        """Create a record in the 'Uploaded Contracts' SharePoint list"""
        try:
            # Ensure token is valid before making API calls
            self._ensure_valid_token()
            
            print(f"\n=== DEBUG _create_contract_metadata ===")
            print(f"Contract Name: {contract_name}")
            print(f"Submitter: {submitter_name} ({submitter_email})")
            print(f"Business Approver: {business_approver_email}")
            print(f"Document URL: {document_url}")
            
            # Use the specific list ID from environment variable
            uploaded_contracts_list_id = os.getenv('SP_LIST_ID')  # 916e17ce-131a-4866-91c5-46cd36433ed2
            
            print(f"List ID: {uploaded_contracts_list_id}")
            
            if not uploaded_contracts_list_id:
                raise Exception("SP_LIST_ID not found in environment variables")
            
            # Prepare the metadata
            current_datetime = datetime.now().isoformat() + 'Z'
            
            # Map business terms from form values to SharePoint choice values
            business_terms_mapping = {
                'compensation': 'Compensation',
                'scope_of_services': 'Scope of Services',
                'term_duration': 'Term (duration)'
            }
            
            # Convert business terms list to properly formatted SharePoint choice values
            business_terms_array = [business_terms_mapping.get(term.lower(), term) for term in business_terms] if business_terms else []
            
            print(f"Current DateTime: {current_datetime}")
            print(f"Date Requested: {date_requested}")
            print(f"Business Terms Array: {business_terms_array}")
            
            # Truncate document URL to 255 characters (SharePoint hyperlink field limit)
            truncated_doc_url = document_url[:255] if len(document_url) > 255 else document_url
            if len(document_url) > 255:
                print(f"⚠️ Document URL truncated from {len(document_url)} to 255 characters")
            
            # Create list item data matching the SharePoint list structure
            # Field names must match SharePoint internal column names exactly
            list_item_data = {
                'fields': {
                    'Title': contract_name,  # Use Title as the contract name (SharePoint default column)
                    'SubmitterName': submitter_name,
                    'SubmitterEmail': submitter_email,
                    'DateSubmitted': current_datetime,
                    'DateRequested': date_requested + 'T00:00:00Z' if date_requested else current_datetime,
                    'AdditionalNotes': additional_notes or None,  # Use None instead of empty string
                    'BusinessApproverEmail': business_approver_email,
                    'BusinessTerms': business_terms_array,  # Array for multi-select choice field
                    'BusinessTerms@odata.type': 'Collection(Edm.String)',  # Critical: Specify the OData type for multi-select
                    'RiskAssignee': None,  # None (null) for optional text field
                    'Status': 'Submitted',  # Changed from 'SUBMITTED' to 'Submitted' (title case)
                    'EstimatedReviewCompletion': None,  # None (null) for optional date field
                    'ContractID': contract_id,
                    'Document_x0020_Link': truncated_doc_url,  # "Document Link" column with space encoded as _x0020_ (255 char limit)
                    'filename': file_name  # lowercase 'filename' as shown in SharePoint screenshot
                }
            }
            
            print(f"List item data fields: {list(list_item_data['fields'].keys())}")
            print(f"Site ID being used: {self.site_id}")
            print(f"Full payload: {list_item_data}")
            
            # Create the list item
            create_item_url = f"{self.graph_url}/sites/{self.site_id}/lists/{uploaded_contracts_list_id}/items"
            
            print(f"POST URL: {create_item_url}")
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            print(f"Sending POST request to SharePoint...")
            response = requests.post(create_item_url, headers=headers, json=list_item_data)
            
            print(f"Response Status: {response.status_code}")
            print(f"Response Body: {response.text}")
            
            if response.status_code == 201:
                list_item = response.json()
                print(f"✓ Successfully created metadata record with ID: {list_item['id']}")
                return {
                    'success': True,
                    'list_item_id': list_item['id'],
                    'message': 'Metadata created successfully'
                }
            else:
                error_msg = f"Failed to create list item: {response.status_code} - {response.text}"
                print(f"✗ {error_msg}")
                return {
                    'success': False,
                    'error': error_msg,
                    'message': 'Failed to create metadata record'
                }
                
        except Exception as e:
            error_msg = f"Error creating contract metadata: {str(e)}"
            print(f"✗ EXCEPTION: {error_msg}")
            import traceback
            print(f"Traceback:\n{traceback.format_exc()}")
            return {
                'success': False,
                'error': error_msg,
                'message': 'Failed to create metadata record'
            }
    
    def create_contract_folder_if_not_exists(self):
        """Test connection to SharePoint - no longer needed for folder creation"""
        try:
            # Just test the connection by getting drive info
            drive_url = f"{self.graph_url}/drives/{self.drive_id}"
            
            headers = {
                'Authorization': f'Bearer {self.access_token}'
            }
            
            response = requests.get(drive_url, headers=headers)
            
            if response.status_code == 200:
                drive_info = response.json()
                print(f"Successfully connected to SharePoint drive: {drive_info.get('name', 'ContractFiles')}")
                return True
            else:
                print(f"Error connecting to SharePoint: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"Error testing SharePoint connection: {str(e)}")
            return False
    
    def upload_to_contract_files(self, file, filename, user_email=None):
        """
        Upload a completed contract document to the ContractFiles library
        
        Args:
            file: FileStorage object from Flask request
            filename: Name for the file in SharePoint
            user_email: Email of the user uploading (for attribution)
            
        Returns:
            dict: {'success': bool, 'file_name': str, 'file_url': str} or error dict
        """
        try:
            # Ensure token is valid
            self._ensure_valid_token()
            
            # Sanitize filename - remove special characters, replace spaces with underscores
            safe_filename = "".join(c if c.isalnum() or c in (' ', '-', '_', '.') else '-' for c in filename)
            safe_filename = safe_filename.replace(' ', '_')
            safe_filename = safe_filename.replace(':', '-')  # Replace colons specifically
            
            print(f"\n=== DEBUG upload_to_contract_files ===")
            print(f"Original Filename: {filename}")
            print(f"Sanitized Filename: {safe_filename}")
            
            # Upload file to ContractFiles library root
            upload_url = f"{self.graph_url}/drives/{self.drive_id}/root:/{safe_filename}:/content"
            
            print(f"Upload URL: {upload_url}")
            
            # Use delegated user token from session so file shows correct creator
            from flask import session
            delegated_token = session.get('access_token')
            upload_token = delegated_token if delegated_token else self.access_token
            
            if delegated_token and user_email:
                print(f"✓ Using delegated user token for upload (will show {user_email} as creator)")
            else:
                print(f"⚠ Using app token (will show 'SharePoint App')")
            
            headers = {
                'Authorization': f'Bearer {upload_token}',
                'Content-Type': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            }
            
            # Read file content
            file_content = file.read()
            print(f"File size: {len(file_content)} bytes")
            
            # Upload file
            response = requests.put(upload_url, headers=headers, data=file_content)
            
            print(f"Upload Response Status: {response.status_code}")
            
            if response.status_code in [200, 201]:
                file_info = response.json()
                document_url = file_info.get('webUrl', '')
                file_id = file_info.get('id')
                
                print(f"✓ File uploaded successfully!")
                print(f"Document URL: {document_url}")
                print(f"File ID: {file_id}")
                
                if user_email:
                    print(f"✓ File uploaded with delegated token - {user_email} will be shown as creator")
                else:
                    print(f"⚠ No user_email provided, file may show as 'SharePoint App'")
                
                return {
                    'success': True,
                    'file_name': safe_filename,
                    'file_url': document_url,
                    'file_id': file_id,
                    'drive_item': file_info,  # Full Graph API response for update_enhanced_document_link
                    'message': 'File uploaded successfully to ContractFiles'
                }
            else:
                error_msg = f"Upload failed with status {response.status_code}: {response.text}"
                print(f"✗ {error_msg}")
                return {
                    'success': False,
                    'error': error_msg,
                    'message': 'Failed to upload file to ContractFiles'
                }
                
        except Exception as e:
            error_msg = f"Error uploading file to ContractFiles: {str(e)}"
            print(f"✗ EXCEPTION: {error_msg}")
            import traceback
            print(f"Traceback:\n{traceback.format_exc()}")
            return {
                'success': False,
                'error': error_msg,
                'message': 'Failed to upload file to ContractFiles'
            }
    
    def get_completed_document_url(self, filename):
        """
        Check if a completed version of the document exists in ContractFiles library
        
        Args:
            filename: Original filename (e.g., "ContractName_uploaded.docx")
            
        Returns:
            str: URL to completed document if found, empty string otherwise
        """
        try:
            # Ensure token is valid
            self._ensure_valid_token()
            
            # Construct expected completed filename
            base_name = filename.rsplit('.', 1)[0] if '.' in filename else filename
            
            # Remove _uploaded, _edited, or _completed suffix if present
            import re
            base_name = re.sub(r'_(uploaded|edited|completed)$', '', base_name)
            
            completed_filename = f"{base_name}_completed.docx"
            
            # Sanitize filename
            safe_filename = "".join(c if c.isalnum() or c in (' ', '-', '_', '.') else '-' for c in completed_filename)
            safe_filename = safe_filename.replace(' ', '_')
            safe_filename = safe_filename.replace(':', '-')
            
            # Try to get file info from ContractFiles
            file_url = f"{self.graph_url}/drives/{self.drive_id}/root:/{safe_filename}"
            
            headers = {
                'Authorization': f'Bearer {self.access_token}'
            }
            
            response = requests.get(file_url, headers=headers)
            
            if response.status_code == 200:
                file_info = response.json()
                return file_info.get('webUrl', '')
            else:
                return ''
                
        except Exception as e:
            print(f"Error checking for completed document: {str(e)}")
            return ''
    
    def get_contract_files(self, limit=50, user_email=None, is_admin=False):
        """
        Retrieve list of contract records from the specific SharePoint list
        
        Args:
            limit (int): Maximum number of records to retrieve
            user_email (str): User's email for filtering (optional)
            is_admin (bool): Whether user is admin (admins see all contracts)
            
        Returns:
            list: List of contract information from SharePoint list
        """
        try:
            # Ensure token is valid before making API calls
            self._ensure_valid_token()
            
            # Use the specific list ID from environment variable
            uploaded_contracts_list_id = os.getenv('SP_LIST_ID')  # 916e17ce-131a-4866-91c5-46cd36433ed2
            
            if not uploaded_contracts_list_id:
                print("SP_LIST_ID not found in environment variables")
                return []
            
            print(f"\n=== DEBUG get_contract_files ===")
            print(f"User Email: {user_email}")
            print(f"Is Admin: {is_admin}")
            
            headers = {
                'Authorization': f'Bearer {self.access_token}'
            }
            
            # Get list items with expanded fields
            # Note: Removed orderby on DateSubmitted as it's not indexed in SharePoint
            # Items will be sorted client-side if needed
            items_url = f"{self.graph_url}/sites/{self.site_id}/lists/{uploaded_contracts_list_id}/items?$expand=fields&$top={limit}"
            
            response = requests.get(items_url, headers=headers)
            
            print(f"SharePoint API response: {response.status_code}")
            
            if response.status_code == 200:
                items_data = response.json()
                contract_list = []
                
                for item in items_data.get('value', []):
                    fields = item.get('fields', {})
                    
                    # Filter by user email if not admin
                    if not is_admin and user_email:
                        item_submitter = fields.get('SubmitterEmail', '').lower()
                        if item_submitter != user_email.lower():
                            continue  # Skip this item
                    
                    filename = fields.get('filename', 'Unknown')
                    
                    # Get completed document URL from EnhancedDocumentLink field
                    # Fall back to constructed URL if field is empty (for backwards compatibility)
                    completed_doc_url = fields.get('EnhancedDocumentLink', '')
                    if not completed_doc_url and fields.get('Status') == 'Completed':
                        completed_doc_url = self.get_completed_document_url(filename)
                    
                    contract_info = {
                        'id': item['id'],
                        'contract_id': fields.get('ContractID', 'N/A'),
                        'name': fields.get('Title', 'Unknown'),  # Use Title field
                        'submitter_name': fields.get('SubmitterName', 'Unknown'),  # Corrected field name
                        'submitter_email': fields.get('SubmitterEmail', ''),
                        'business_approver_email': fields.get('BusinessApproverEmail', ''),
                        'date_submitted': fields.get('DateSubmitted', '')[:10] if fields.get('DateSubmitted') else 'Unknown',
                        'date_requested': fields.get('DateRequested', '')[:10] if fields.get('DateRequested') else 'Unknown',
                        'status': fields.get('Status', 'SUBMITTED'),
                        'business_terms': fields.get('BusinessTerms', ''),
                        'additional_notes': fields.get('AdditionalNotes', ''),
                        'risk_assignee': fields.get('RiskAssignee', ''),
                        'estimated_review_completion': fields.get('EstimatedReviewCompletion', ''),
                        'document_url': fields.get('Document_x0020_Link', ''),  # Corrected field name
                        'file_name': filename,  # Corrected to lowercase
                        'completed_document_url': completed_doc_url
                    }
                    contract_list.append(contract_info)
                
                # Sort by DateSubmitted (most recent first) - client-side since field is not indexed
                contract_list.sort(key=lambda x: x['date_submitted'], reverse=True)
                
                print(f"Returning {len(contract_list)} contracts")
                return contract_list
            else:
                print(f"Error retrieving contract records: {response.status_code} - {response.text}")
                return []
                
        except Exception as e:
            print(f"Error retrieving contract records: {str(e)}")
            import traceback
            traceback.print_exc()
            return []
    
    def get_contract_by_id(self, contract_id):
        """
        Retrieve a single contract by its ContractID field value.
        
        Args:
            contract_id (str): The ContractID field value (e.g., 'CAAE5D84')
            
        Returns:
            dict: Contract information with 'fields' key containing SharePoint fields,
                  or None if not found
        """
        try:
            # Ensure token is valid before making API calls
            self._ensure_valid_token()
            
            uploaded_contracts_list_id = os.getenv('SP_LIST_ID')
            
            if not uploaded_contracts_list_id:
                print("SP_LIST_ID not found in environment variables")
                return None
            
            print(f"\n=== DEBUG get_contract_by_id ===")
            print(f"Contract ID: {contract_id}")
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Prefer': 'HonorNonIndexedQueriesWarningMayFailRandomly'
            }
            
            # Query SharePoint list filtering by ContractID field
            # Use $filter to find the specific contract
            # Note: ContractID is not indexed, so we need the Prefer header
            items_url = f"{self.graph_url}/sites/{self.site_id}/lists/{uploaded_contracts_list_id}/items"
            params = {
                '$expand': 'fields',
                '$filter': f"fields/ContractID eq '{contract_id}'"
            }
            
            response = requests.get(items_url, headers=headers, params=params)
            
            print(f"SharePoint API response: {response.status_code}")
            
            if response.status_code == 200:
                items_data = response.json()
                items = items_data.get('value', [])
                
                if items:
                    # Return the first matching item (should be unique)
                    item = items[0]
                    fields = item.get('fields', {})
                    
                    # Return structured contract info
                    contract = {
                        'id': item['id'],
                        'contract_id': fields.get('ContractID', contract_id),
                        'name': fields.get('Title', 'Unknown'),
                        'submitter_name': fields.get('SubmitterName', 'Unknown'),
                        'submitter_email': fields.get('SubmitterEmail', ''),
                        'business_approver_email': fields.get('BusinessApproverEmail', ''),
                        'date_submitted': fields.get('DateSubmitted', ''),
                        'date_requested': fields.get('DateRequested', ''),
                        'status': fields.get('Status', 'SUBMITTED'),
                        'business_terms': fields.get('BusinessTerms', ''),
                        'additional_notes': fields.get('AdditionalNotes', ''),
                        'estimated_review_completion': fields.get('EstimatedReviewCompletion', ''),
                        'document_url': fields.get('Document_x0020_Link', ''),
                        'file_name': fields.get('filename', 'Unknown'),
                        'fields': fields  # Include raw fields for download service
                    }
                    
                    print(f"Contract found: {contract['name']}")
                    return contract
                else:
                    print(f"No contract found with ContractID: {contract_id}")
                    return None
            else:
                print(f"Error retrieving contract: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"Error retrieving contract by ID: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_field_choices(self, field_name):
        """
        Get the choice options for a specific field in the SharePoint list
        
        Args:
            field_name (str): The internal name of the field (e.g., 'RiskAssignee', 'Status')
            
        Returns:
            list: List of choice values, or empty list if not found
        """
        try:
            # Ensure token is valid before making API calls
            self._ensure_valid_token()
            
            uploaded_contracts_list_id = os.getenv('SP_LIST_ID')
            
            if not uploaded_contracts_list_id:
                print("SP_LIST_ID not found in environment variables")
                return []
            
            print(f"\n=== DEBUG get_field_choices ===")
            print(f"Field: {field_name}")
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Accept': 'application/json'
            }
            
            # Get all columns for the list
            columns_url = f"{self.graph_url}/sites/{self.site_id}/lists/{uploaded_contracts_list_id}/columns"
            
            response = requests.get(columns_url, headers=headers)
            
            if response.status_code == 200:
                columns = response.json().get('value', [])
                
                # Find the specific field
                for column in columns:
                    if column.get('name') == field_name or column.get('displayName') == field_name:
                        # Check if it's a choice field
                        if 'choice' in column:
                            choices = column['choice'].get('choices', [])
                            print(f"✓ Found {len(choices)} choices for {field_name}: {choices}")
                            return choices
                        else:
                            print(f"⚠ Field {field_name} is not a choice field")
                            return []
                
                print(f"⚠ Field {field_name} not found in list")
                return []
            else:
                print(f"✗ Error fetching columns: {response.status_code} - {response.text}")
                return []
                
        except Exception as e:
            print(f"Error fetching field choices: {str(e)}")
            import traceback
            traceback.print_exc()
            return []
    
    def update_contract_field(self, item_id, field_name, value):
        """
        Update a specific field in a SharePoint list item.
        
        Args:
            item_id (str): The SharePoint list item ID
            field_name (str): The field name to update (e.g., 'Status', 'RiskAssignee')
            value: The new value for the field
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Ensure token is valid before making API calls
            self._ensure_valid_token()
            
            uploaded_contracts_list_id = os.getenv('SP_LIST_ID')
            
            if not uploaded_contracts_list_id:
                print("SP_LIST_ID not found in environment variables")
                return False
            
            print(f"\n=== DEBUG update_contract_field ===")
            print(f"Item ID: {item_id}")
            print(f"Field: {field_name}")
            print(f"Value: {value}")
            print(f"Value type: {type(value)}")
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            # Update the item
            update_url = f"{self.graph_url}/sites/{self.site_id}/lists/{uploaded_contracts_list_id}/items/{item_id}/fields"
            
            # Build payload - for multi-choice fields like BusinessTerms, we need to specify the OData type
            payload = {
                field_name: value
            }
            
            # If the value is an array (multi-choice field), add the OData type annotation
            if isinstance(value, list) and field_name == 'BusinessTerms':
                payload[f'{field_name}@odata.type'] = 'Collection(Edm.String)'
            
            print(f"Payload: {payload}")
            
            response = requests.patch(update_url, headers=headers, json=payload)
            
            print(f"Update response: {response.status_code}")
            
            if response.status_code == 200:
                print(f"✓ Successfully updated {field_name} to '{value}'")
                return True
            else:
                print(f"✗ Error updating field: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"Error updating contract field: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    def update_enhanced_document_link(self, item_id, drive_item):
        """
        Update the EnhancedDocumentLink field (Single line of text, max 255 chars) in SharePoint list.
        
        Args:
            item_id (str): The SharePoint list item ID
            drive_item (dict): The Graph API response for the uploaded enhanced file
            
        Returns:
            None
            
        Raises:
            ValueError: If URL exceeds 255 character limit
            PermissionError: If session expired (401) or access denied (403)
            FileNotFoundError: If item not found (404)
            RuntimeError: For other errors
        """
        try:
            # Ensure token is valid before making API calls
            self._ensure_valid_token()
            
            uploaded_contracts_list_id = os.getenv('SP_LIST_ID')
            site_id = os.getenv('O365_SITE_ID')
            
            if not uploaded_contracts_list_id:
                raise RuntimeError("SP_LIST_ID not configured")
            
            if not site_id:
                raise RuntimeError("O365_SITE_ID not configured")
            
            # Extract file info from drive_item
            file_id = drive_item.get("id")
            file_name = drive_item.get("name", "")
            web_url = drive_item.get("webUrl", "")
            
            if not file_id or not file_name:
                raise ValueError("drive_item missing 'id' or 'name' property")
            
            print(f"\n=== DEBUG update_enhanced_document_link ===")
            print(f"Item ID: {item_id}")
            print(f"File ID: {file_id}")
            print(f"File Name: {file_name}")
            print(f"Original webUrl length: {len(web_url)} chars")
            
            # Construct a shorter direct link using the drive and file ID
            # Format: https://{tenant}.sharepoint.com/sites/{site}/ContractFiles/{filename}
            site_url = os.getenv('SP_SITE_URL', '')
            if not site_url:
                raise RuntimeError("SP_SITE_URL not configured")
            
            # Build shorter URL: {site_url}/ContractFiles/{filename}
            enhanced_url = f"{site_url}/ContractFiles/{file_name}"
            
            print(f"Constructed shorter URL: {enhanced_url}")
            print(f"Shorter URL length: {len(enhanced_url)} characters")
            
            # One-time debug: Show why previous attempts with Doc.aspx URLs failed
            print(f"\n⚠ URL Length Check:")
            print(f"  Original webUrl length: {len(web_url)} chars (Doc.aspx viewer)")
            print(f"  Constructed URL length: {len(enhanced_url)} chars (direct link)")
            print(f"  SharePoint limit: 255 chars (Single line of text)")
            print(f"  Status: {'✓ PASS' if len(enhanced_url) <= 255 else '✗ FAIL - URL TOO LONG'}")
            
            # Check 255 character limit for "Single line of text" field type
            if len(enhanced_url) > 255:
                error_msg = (
                    f"Enhanced Document Link URL exceeds SharePoint 255 character limit. "
                    f"URL length: {len(enhanced_url)} chars. "
                    f"This field is 'Single line of text' and cannot store URLs longer than 255 characters. "
                    f"The direct link format is shorter than Doc.aspx viewer, but still too long. "
                    f"Consider changing the SharePoint field type to 'Hyperlink' instead of 'Single line of text'."
                )
                print(f"✗ {error_msg}")
                raise ValueError(error_msg)
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            # PATCH to update the fields
            update_url = f"{self.graph_url}/sites/{site_id}/lists/{uploaded_contracts_list_id}/items/{item_id}/fields"
            
            # EnhancedDocumentLink is "Single line of text" - send plain string
            payload = {
                "EnhancedDocumentLink": enhanced_url
            }
            
            print(f"PATCH URL: {update_url}")
            print(f"Payload keys: {list(payload.keys())}")
            
            response = requests.patch(update_url, headers=headers, json=payload)
            
            print(f"Response status: {response.status_code}")
            
            # Log short response snippet (without sensitive data)
            if response.status_code not in (200, 204):
                response_preview = response.text[:200] if response.text else "(empty)"
                print(f"Response preview: {response_preview}")
            
            # Map status codes per requirements
            if response.status_code in (200, 204):
                print(f"✓ Successfully updated EnhancedDocumentLink")
                return
            elif response.status_code == 401:
                print(f"✗ 401 Unauthorized - Session expired")
                raise PermissionError("SESSION_EXPIRED")
            elif response.status_code == 403:
                print(f"✗ 403 Forbidden - Access denied")
                raise PermissionError("ACCESS_DENIED")
            elif response.status_code == 404:
                print(f"✗ 404 Not Found - Item not found")
                raise FileNotFoundError(f"List item {item_id} not found")
            else:
                error_msg = f"Failed to update EnhancedDocumentLink: HTTP {response.status_code}"
                print(f"✗ {error_msg}")
                raise RuntimeError(error_msg)
                
        except (ValueError, PermissionError, FileNotFoundError, RuntimeError):
            # Re-raise expected exceptions
            raise
        except Exception as e:
            print(f"Error updating enhanced document link: {str(e)}")
            import traceback
            traceback.print_exc()
            raise RuntimeError(f"Unexpected error: {str(e)}")

# Initialize SharePoint service instance
sharepoint_service = SharePointService()