# this script reads directly from the bone_names.py, and executes the
# the insert programmatically.
# populates config table from bone_names.py 

import json
from dotenv import load_dotenv
from supabase import create_client
import os
from bone_names import BONE_NAMES

load_dotenv()

# create supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_SERVICE_KEY")

client = create_client(supabase_url, supabase_key)

def setup_config():
    client.table("config").upsert({
        "key": "bone_names",
        "value": BONE_NAMES
    }).execute()
    print("Bone names saved to config table.")

if __name__ == "__main__":
    setup_config()