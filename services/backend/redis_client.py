import redis
import os
from dotenv import load_dotenv
from pathlib import Path

# Load the .env file
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)


# Use the REDIS_URL directly — it handles SSL/TLS automatically
REDIS_URL = os.getenv("REDIS_URL")

# Lazy connection — only connect when actually needed, not at import time
redis_client = None

def _init_redis():
    """Initialize Redis connection on first use (lazy loading)"""
    global redis_client
    if redis_client is None:
        redis_client = redis.from_url(
            REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5
        )
    return redis_client

def get_redis():
    """
    Returns the Redis client (initializes on first call).
    Every part of the app that needs Redis will call this function.
    """
    return _init_redis()

def test_redis_connection():
    """
    Tests if Redis is reachable.
    Returns True if connected, False if something is wrong.
    """
    try:
        client = _init_redis()
        client.ping()
        return True
    except Exception as e:
        print(f"Redis connection failed: {e}")
        return False


print("Redis client module loaded (connection will be initialized on first use)")
