import redis
import os
from dotenv import load_dotenv

# Load the .env file so we can read REDIS_URL, REDIS_HOST etc.
load_dotenv()

# Read Redis credentials from your .env file
REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")
REDIS_USERNAME = os.getenv("REDIS_USERNAME", "default")

# Create the Redis connection
# decode_responses=True means data comes back as normal text, not raw bytes
redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    username=REDIS_USERNAME,
    password=REDIS_PASSWORD,
    decode_responses=True,
    ssl=False  # Upstash requires secure connection
)

def get_redis():
    """
    Returns the Redis client.
    Every part of the app that needs Redis will call this function.
    """
    return redis_client

def test_redis_connection():
    """
    Tests if Redis is reachable.
    Returns True if connected, False if something is wrong.
    """
    try:
        redis_client.ping()
        return True
    except Exception as e:
        print(f"Redis connection failed: {e}")
        return False


print(f"HOST: {REDIS_HOST}")
print(f"PORT: {REDIS_PORT}")
print(f"USERNAME: {REDIS_USERNAME}")
print(f"PASSWORD: {REDIS_PASSWORD}")