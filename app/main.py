import os
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from dotenv import load_dotenv
from datetime import datetime

# Import the database helper we created in app/database.py
from .database import get_user_collection

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
        print("--- DEBUG: Database update complete! ---")

        return {"status": "User Authenticated & Saved to DB!", "user": user_info['email']}

    except Exception as e:
        print(f"!!! CRITICAL ERROR: {str(e)}")
        return {"error": "Internal Server Error", "details": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)