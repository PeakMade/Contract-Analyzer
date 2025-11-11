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
                # Store token and expiration time
                self.access_token = result["access_token"]
                # Token expires in 'expires_in' seconds (usually 3599 = ~1 hour)
                expires_in = result.get("expires_in", 3599)
                self.token_expires_at = datetime.now() + timedelta(seconds=expires_in - 300)  # Refresh 5 min early
                
                print(f"Token acquired, expires at: {self.token_expires_at}")
                return result["access_token"]
            else:
                raise Exception(f"Failed to get access token: {result}")
                
        except Exception as e:
            print(f"Error getting access token: {str(e)}")
            raise
    
    def _ensure_valid_token(self):
        """Check if token is valid and refresh if needed"""
        from datetime import datetime
        
        # If token doesn't exist or is expired, get a new one
        if self.token_expires_at is None or datetime.now() >= self.token_expires_at:
            print("Token expired or missing, refreshing...")
            self.access_token = self._get_access_token()
            # Site ID might also need refresh after token refresh
            if self.site_id is None:
                self.site_id = self._get_site_id()
        else:
            time_left = (self.token_expires_at - datetime.now()).total_seconds() / 60
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
            
            # Generate unique contract ID and filename
            contract_id = str(uuid.uuid4())[:8].upper()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_extension = os.path.splitext(file_name)[1]
            safe_contract_name = "".join(c for c in contract_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            unique_filename = f"{contract_id}_{safe_contract_name}_{timestamp}{file_extension}"
            
            print(f"Contract ID: {contract_id}")
            print(f"Unique Filename: {unique_filename}")
            
            # Upload file to ContractFiles library (root, not in Contracts subfolder)
            upload_url = f"{self.graph_url}/drives/{self.drive_id}/root:/{unique_filename}:/content"
            
            print(f"Upload URL: {upload_url}")
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
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
                
                print(f"✓ File uploaded successfully!")
                print(f"Document URL: {document_url}")
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
                    'Document_x0020_Link': document_url,  # "Document Link" column with space encoded as _x0020_
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
                        'estimated_review': fields.get('EstimatedReviewCompletion', ''),  # Corrected field name
                        'document_url': fields.get('Document_x0020_Link', ''),  # Corrected field name
                        'file_name': fields.get('filename', 'Unknown')  # Corrected to lowercase
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

# Initialize SharePoint service instance
sharepoint_service = SharePointService()