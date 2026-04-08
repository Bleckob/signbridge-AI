from datetime import datetime
from typing import Dict
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

# In-memory session storage
# This dictionary holds all active sessions
# Key: session_id, Value: session data dictionary
# Example: {"session_abc123": {"status": "active", ...}}
active_sessions: Dict[str, dict] = {}


def create_session(session_id: str) -> dict:
    """
    Creates a new session when a user connects.
    Called by your WebSocket endpoint when David's frontend connects.
    """
    session = {
        "session_id": session_id,
        "status": "active",
        "connected_at": datetime.utcnow().isoformat(),
        "last_activity": datetime.utcnow().isoformat(),
        "audio_chunks_received": 0,
    }
    # Store in our in-memory dictionary
    active_sessions[session_id] = session
    print(f"Session created: {session_id} ✅")
    return session


def update_session_activity(session_id: str):
    """
    Updates the last activity time of a session.
    Called every time audio data is received from Confidence.
    This tells us the session is still alive and active.
    """
    if session_id in active_sessions:
        active_sessions[session_id]["last_activity"] = datetime.utcnow().isoformat()
        active_sessions[session_id]["audio_chunks_received"] += 1


def close_session(session_id: str):
    """
    Closes a session when a user disconnects.
    Called by your WebSocket endpoint when connection drops.
    """
    if session_id in active_sessions:
        active_sessions[session_id]["status"] = "disconnected"
        active_sessions[session_id]["disconnected_at"] = datetime.utcnow().isoformat()
        print(f"Session closed: {session_id} ✅")
        # Remove from active sessions
        del active_sessions[session_id]


def get_session(session_id: str) -> dict:
    """
    Returns session data for a specific session.
    Returns None if session doesn't exist.
    """
    return active_sessions.get(session_id, None)


def get_all_sessions() -> dict:
    """
    Returns all currently active sessions.
    Used by your dashboard endpoint.
    """
    return active_sessions


def get_session_count() -> int:
    """
    Returns total number of active sessions.
    Used by your health check endpoint.
    """
    return len(active_sessions)
