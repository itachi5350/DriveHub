import os
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from dotenv import load_dotenv
from datetime import datetime
from .drive_service import get_drive_service, get_or_create_root_folder,create_repository_folder,upload_file_to_repo,list_files_in_repo
# Import the database helper we created in app/database.py
from .database import get_user_collection
from pydantic import BaseModel
class RepoCreateRequest(BaseModel):
    email: str
    repo_name: str
class FileUploadRequest(BaseModel):
    email: str
    repo_id: str  # The ID of the folder we created in the last step
    file_name: str
    content: str
class CommitRecord(BaseModel):
    email: str
    repo_id: str
    message: str
    file_id: str
load_dotenv()

app = FastAPI(title="DriveHub API")

# Allow insecure transport for local development (OAuth requirement)
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# 1. Configure Google OAuth Flow
# This uses the credentials from your .env file
flow = Flow.from_client_config(
    {
        "web": {
            "client_id": os.getenv("GOOGLE_CLIENT_ID"),
            "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    },
    scopes=[
        "https://www.googleapis.com/auth/userinfo.profile",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/drive.file" # Permission to manage DriveHub files
    ],
    redirect_uri=os.getenv("GOOGLE_REDIRECT_URI")
)

@app.get("/login")
def login():
    """Step 1: Send user to Google Login Page"""
    auth_url, _ = flow.authorization_url(prompt='consent', access_type='offline')
    return RedirectResponse(auth_url)

@app.get("/api/auth/google/callback")
async def callback(code: str):
    try:
        print("--- DEBUG: Starting Callback ---")
        os.environ['OAUTHLIB_RELAX_TOKEN_SCOPE'] = '1'
        # 1. Fetch Token
        flow.fetch_token(code=code)
        creds = flow.credentials
        print("--- DEBUG: Tokens fetched successfully ---")

        # 2. Get User Info
        user_service = build('oauth2', 'v2', credentials=creds)
        user_info = user_service.userinfo().get().execute()
        print(f"--- DEBUG: User Info received for {user_info['email']} ---")

        # 3. Connect to DB
        users = get_user_collection()
        print("--- DEBUG: Collection accessed ---")

        # 4. Save to DB
        await users.update_one(
            {"google_id": user_info['id']},
            {
                "$set": {
                    "email": user_info['email'],
                    "name": user_info.get('name'),
                    "access_token": creds.token,
                    "refresh_token": creds.refresh_token,
                    "last_login": datetime.utcnow()
                }
            },
            upsert=True 
        )
        print("--- DEBUG: Initializing Drive Service ---")
        drive_service = get_drive_service({
            "access_token": creds.token,
            "refresh_token": creds.refresh_token
        })
        
        root_id = await get_or_create_root_folder(drive_service)
        await users.update_one(
            {"google_id": user_info['id']},
            {"$set": {"root_folder_id": root_id}}
        )
        print("--- DEBUG: Database update complete! ---")

        return {"status": "User Authenticated & Saved to DB!", "user": user_info['email'],"root_id": root_id}

    except Exception as e:
        print(f"!!! CRITICAL ERROR: {str(e)}")
        return {"error": "Internal Server Error", "details": str(e)}

@app.post("/api/repositories/create")
async def create_repository(request: RepoCreateRequest):
    try:
        # 1. Find the user in the database
        users = get_user_collection()
        user = await users.find_one({"email": request.email})
        
        if not user:
            return {"error": "User not found"}
        
        if "root_folder_id" not in user:
            return {"error": "Root folder not setup for this user. Please log in again."}

        # 2. Re-initialize the Drive Service using their saved tokens
        drive_service = get_drive_service({
            "access_token": user["access_token"],
            "refresh_token": user["refresh_token"]
        })
        
        # 3. Create the folder inside their Root Folder
        new_repo_id = await create_repository_folder(
            service=drive_service, 
            folder_name=request.repo_name, 
            parent_id=user["root_folder_id"]
        )
        
        return {
            "status": "Repository Created Successfully!",
            "repo_name": request.repo_name,
            "drive_folder_id": new_repo_id
        }

    except Exception as e:
        return {"error": "Failed to create repository", "details": str(e)}
@app.post("/api/files/upload")
async def upload_file(request: FileUploadRequest,commit_message: str = "Initial upload"):
    try:
        users = get_user_collection()
        user = await users.find_one({"email": request.email})
        
        if not user:
            return {"error": "User not found"}

        drive_service = get_drive_service({
            "access_token": user["access_token"],
            "refresh_token": user["refresh_token"]
        })
        
        file_id = await upload_file_to_repo(
            service=drive_service,
            repo_id=request.repo_id,
            file_name=request.file_name,
            content=request.content
        )
        db = get_user_collection().database # Get the database object
        commits_col = db["commits"]
        
        new_commit = {
            "email": request.email,
            "repo_id": request.repo_id,
            "file_name": request.file_name,
            "file_id": file_id,
            "message": commit_message,
            "timestamp": datetime.utcnow()
        }
        await commits_col.insert_one(new_commit)

        
        return {
            "status": "File Uploaded and commit recorded Successfully!",
            "file_name": request.file_name,
            "drive_file_id": file_id,
            "commit_msg": commit_message
        }

    except Exception as e:
        return {"error": "Upload failed", "details": str(e)}
    
@app.get("/api/repositories/{repo_id}/files")
async def get_repo_files(repo_id: str, email: str):
    try:
        users = get_user_collection()
        user = await users.find_one({"email": email})
        
        if not user:
            return {"error": "User not found"}

        drive_service = get_drive_service({
            "access_token": user["access_token"],
            "refresh_token": user["refresh_token"]
        })
        
        files = await list_files_in_repo(drive_service, repo_id)
        return {"repository_id": repo_id, "files": files}

    except Exception as e:
        return {"error": "Failed to list files", "details": str(e)}
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)