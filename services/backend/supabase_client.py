import os
from supabase import create_client, Client
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Read Supabase credentials from .env file
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

# Create Supabase client
# We use SERVICE_KEY here because this is the backend
# SERVICE_KEY has full access — never use it on frontend
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def get_supabase() -> Client:
    """
    Returns the Supabase client.
    Every part of the app that needs Supabase will call this.
    """
    return supabase


def test_supabase_connection() -> bool:
    """
    Tests if Supabase is reachable.
    Returns True if connected, False if something is wrong.
    """
    try:
        # We just try to read from a table
        # Even if table doesn't exist, a response means we're connected
        supabase.table("sign_poses").select("id").limit(1).execute()
        return True
    except Exception as e:
        print(f"Supabase connection failed: {e}")
        return False


def get_sign_pose(gloss: str) -> dict:
    """
    Looks up a sign pose from Supabase by its gloss name.
    
    gloss: the sign language word to look up
           Example: "HELLO", "DOCTOR", "MEDICINE"
    
    Returns the pose data if found, or a placeholder if not found yet.
    This placeholder will be replaced when Isaac finishes his table.
    """
    try:
        response = supabase.table("sign_poses")\
            .select("*")\
            .eq("gloss", gloss)\
            .limit(1)\
            .execute()

        if response.data and len(response.data) > 0:
            return response.data[0]
        else:
            # Isaac's table not ready yet — return placeholder
            # This keeps your pipeline working even without real pose data
            print(f"Pose not found for gloss: {gloss} — using placeholder")
            return {
                "gloss": gloss,
                "keyframes": [],
                "duration_ms": 500,
                "placeholder": True
            }
    except Exception as e:
        print(f"Error fetching pose for {gloss}: {e}")
        # Return placeholder so pipeline doesn't crash
        return {
            "gloss": gloss,
            "keyframes": [],
            "duration_ms": 500,
            "placeholder": True
        }