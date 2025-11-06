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
                return result["access_token"]
            else:
                raise Exception(f"Failed to get access token: {result}")
                
        except Exception as e:
            print(f"Error getting access token: {str(e)}")
            raise
    
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
            # Generate unique contract ID and filename
            contract_id = str(uuid.uuid4())[:8].upper()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_extension = os.path.splitext(file_name)[1]
            safe_contract_name = "".join(c for c in contract_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            unique_filename = f"{contract_id}_{safe_contract_name}_{timestamp}{file_extension}"
            
            # Upload file to ContractFiles library (root, not in Contracts subfolder)
            upload_url = f"{self.graph_url}/drives/{self.drive_id}/root:/{unique_filename}:/content"
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/octet-stream'
            }
            
            # Upload the file
            response = requests.put(upload_url, headers=headers, data=file_content)
            
            if response.status_code in [200, 201]:
                file_info = response.json()
                
                # Get the SharePoint URL for the document
                document_url = file_info.get('webUrl', '')
                
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
                print(error_msg)
                return {
                    'success': False,
                    'error': error_msg,
                    'message': 'Failed to upload contract to SharePoint'
                }
                
        except Exception as e:
            error_msg = f"Error uploading file to SharePoint: {str(e)}"
            print(error_msg)
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
            # Use the specific list ID from environment variable
            uploaded_contracts_list_id = os.getenv('SP_LIST_ID')  # 916e17ce-131a-4866-91c5-46cd36433ed2
            
            if not uploaded_contracts_list_id:
                raise Exception("SP_LIST_ID not found in environment variables")
            
            # Prepare the metadata
            current_datetime = datetime.now().isoformat() + 'Z'
            business_terms_str = ', '.join(business_terms) if business_terms else ''
            
            # Create list item data matching the SharePoint list structure
            list_item_data = {
                'fields': {
                    'Title': contract_name,
                    'ContractName': contract_name,
                    'Submitter': submitter_name,
                    'DateSubmitted': current_datetime,
                    'DateRequested': date_requested + 'T00:00:00Z' if date_requested else current_datetime,
                    'AdditionalNotes': additional_notes or '',
                    'BusinessApproverEmail': business_approver_email,
                    'BusinessTerms': business_terms_str,
                    'RiskAssignee': '',  # Empty initially
                    'Status': 'SUBMITTED',  # Set to SUBMITTED when contract is first uploaded
                    'EstimatedReview': '',  # Empty initially
                    'ContractID': contract_id,
                    'DocumentLink': document_url,
                    'FileName': file_name
                }
            }
            
            # Create the list item
            create_item_url = f"{self.graph_url}/sites/{self.site_id}/lists/{uploaded_contracts_list_id}/items"
            
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            response = requests.post(create_item_url, headers=headers, json=list_item_data)
            
            if response.status_code == 201:
                list_item = response.json()
                print(f"Successfully created metadata record with ID: {list_item['id']}")
                return {
                    'success': True,
                    'list_item_id': list_item['id'],
                    'message': 'Metadata created successfully'
                }
            else:
                error_msg = f"Failed to create list item: {response.status_code} - {response.text}"
                print(error_msg)
                return {
                    'success': False,
                    'error': error_msg,
                    'message': 'Failed to create metadata record'
                }
                
        except Exception as e:
            error_msg = f"Error creating contract metadata: {str(e)}"
            print(error_msg)
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
    
    def get_contract_files(self, limit=50):
        """
        Retrieve list of contract records from the specific SharePoint list
        
        Args:
            limit (int): Maximum number of records to retrieve
            
        Returns:
            list: List of contract information from SharePoint list
        """
        try:
            # Use the specific list ID from environment variable
            uploaded_contracts_list_id = os.getenv('SP_LIST_ID')  # 916e17ce-131a-4866-91c5-46cd36433ed2
            
            if not uploaded_contracts_list_id:
                print("SP_LIST_ID not found in environment variables")
                return []
            
            headers = {
                'Authorization': f'Bearer {self.access_token}'
            }
            
            # Get list items with expanded fields
            items_url = f"{self.graph_url}/sites/{self.site_id}/lists/{uploaded_contracts_list_id}/items?$expand=fields&$top={limit}&$orderby=fields/DateSubmitted desc"
            
            response = requests.get(items_url, headers=headers)
            
            if response.status_code == 200:
                items_data = response.json()
                contract_list = []
                
                for item in items_data.get('value', []):
                    fields = item.get('fields', {})
                    
                    contract_info = {
                        'id': item['id'],
                        'contract_id': fields.get('ContractID', 'N/A'),
                        'name': fields.get('ContractName', fields.get('Title', 'Unknown')),
                        'submitter_name': fields.get('Submitter', 'Unknown'),
                        'submitter_email': fields.get('SubmitterEmail', ''),
                        'business_approver_email': fields.get('BusinessApproverEmail', ''),
                        'date_submitted': fields.get('DateSubmitted', '')[:10] if fields.get('DateSubmitted') else 'Unknown',
                        'date_requested': fields.get('DateRequested', '')[:10] if fields.get('DateRequested') else 'Unknown',
                        'status': fields.get('Status', 'SUBMITTED'),
                        'business_terms': fields.get('BusinessTerms', ''),
                        'additional_notes': fields.get('AdditionalNotes', ''),
                        'risk_assignee': fields.get('RiskAssignee', ''),
                        'estimated_review': fields.get('EstimatedReview', ''),
                        'document_url': fields.get('DocumentLink', ''),
                        'file_name': fields.get('FileName', 'Unknown')
                    }
                    contract_list.append(contract_info)
                
                return contract_list
            else:
                print(f"Error retrieving contract records: {response.status_code} - {response.text}")
                return []
                
        except Exception as e:
            print(f"Error retrieving contract records: {str(e)}")
            return []

# Initialize SharePoint service instance
sharepoint_service = SharePointService()