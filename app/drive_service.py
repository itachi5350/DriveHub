from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import os

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