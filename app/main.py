import os
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="DriveHub API")

# Allow insecure transport for local development (OAuth requirement)
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# Configure Google OAuth Flow
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
        "https://www.googleapis.com/auth/drive.file"
    ],
    redirect_uri=os.getenv("GOOGLE_REDIRECT_URI")
)

@app.get("/login")
def login():
    auth_url, _ = flow.authorization_url(prompt='consent', access_type='offline')
    return RedirectResponse(auth_url)

@app.get("/api/auth/google/callback")
async def callback(code: str):
    flow.fetch_token(code=code)
    credentials = flow.credentials
    
    # For now, let's just return the token to see it works
    return {
        "access_token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "expires_at": credentials.expiry
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)