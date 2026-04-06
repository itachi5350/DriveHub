from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import os
import io
from googleapiclient.http import MediaIoBaseUpload
def get_drive_service(user_data):
    """
    Creates a Google Drive API client using the user's stored tokens.
    """
    creds = Credentials(
        token=user_data['access_token'],
        refresh_token=user_data['refresh_token'],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        scopes=["https://www.googleapis.com/auth/drive.file"]
    )
    return build('drive', 'v3', credentials=creds)

async def get_or_create_root_folder(service):
    """
    Checks if 'DriveHub_Root' exists. If not, creates it.
    Returns the Folder ID.
    """
    folder_name = "DriveHub_Root"
    
    # 1. Search for an existing folder with this name
    query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get('files', [])

    if files:
        print(f"--- DEBUG: Found existing {folder_name} ---")
        return files[0]['id']
    else:
        # 2. Create the folder if it doesn't exist
        print(f"--- DEBUG: Creating new {folder_name} ---")
        folder_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        file = service.files().create(body=folder_metadata, fields='id').execute()
        return file.get('id')
async def create_repository_folder(service, folder_name, parent_id):
    """
    Creates a new folder inside the DriveHub_Root directory.
    """
    print(f"--- DEBUG: Creating repo '{folder_name}' inside parent '{parent_id}' ---")
    
    file_metadata = {
        'name': folder_name,
        'parents': [parent_id], # This is the magic line that puts it INSIDE the root folder
        'mimeType': 'application/vnd.google-apps.folder'
    }
    
    try:
        file = service.files().create(body=file_metadata, fields='id').execute()
        return file.get('id')
    except Exception as e:
        print(f"!!! ERROR creating repository: {str(e)}")
        raise e
async def upload_file_to_repo(service, repo_id, file_name, content):
    """
    Uploads a file to a specific repository folder on Google Drive.
    """
    print(f"--- DEBUG: Uploading '{file_name}' to repo '{repo_id}' ---")
    
    file_metadata = {
        'name': file_name,
        'parents': [repo_id]
    }
    
    # Convert string content to a byte stream that Google Drive API understands
    media = MediaIoBaseUpload(
        io.BytesIO(content.encode('utf-8')), 
        mimetype='text/plain', 
        resumable=True
    )

    try:
        file = service.files().create(
            body=file_metadata, 
            media_body=media, 
            fields='id'
        ).execute()
        return file.get('id')
    except Exception as e:
        print(f"!!! ERROR uploading file: {str(e)}")
        raise e
async def list_files_in_repo(service, repo_id):
    """
    Lists all files inside a specific repository folder.
    """
    query = f"'{repo_id}' in parents and trashed = false"
    results = service.files().list(
        q=query, 
        fields="files(id, name, mimeType, modifiedTime)"
    ).execute()
    return results.get('files', [])