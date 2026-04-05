import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

# We look for MONGODB_URI in .env, otherwise we use local
MONGO_URL = os.getenv("MONGODB_URI", "mongodb://localhost:27017")

client = AsyncIOMotorClient(MONGO_URL)
db = client.drivehub_db

# Helper to get the user collection
def get_user_collection():
    return db.users