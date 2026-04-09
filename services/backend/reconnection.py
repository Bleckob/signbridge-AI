from datetime import datetime, timedelta
from typing import Dict
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Stores sessions that disconnected but can still reconnect
# Key: session_id, Value: reconnection data
# Sessions stay here for 60 seconds before being permanently removed
pending_reconnections: Dict[str, dict] = {}

# How long to wait for a reconnection before giving up (seconds)
RECONNECTION_WINDOW = 60


def register_disconnection(session_id: str, last_activity: str):
    """
    Called when a WebSocket disconnects unexpectedly.
    Saves the session so it can be restored if client reconnects.

    session_id: the session that disconnected
    last_activity: timestamp of last activity in this session
    """
    pending_reconnections[session_id] = {
        "session_id": session_id,
        "disconnected_at": datetime.utcnow().isoformat(),
        "last_activity": last_activity,
        "expires_at": (
            datetime.utcnow() + timedelta(seconds=RECONNECTION_WINDOW)
        ).isoformat(),
        "reconnection_count": 0
    }
    print(f"Session {session_id} registered for reconnection ⏳")
    print(f"Reconnection window: {RECONNECTION_WINDOW} seconds")


def attempt_reconnection(session_id: str) -> dict:
    """
    Called when a client tries to reconnect with an existing session_id.
    Returns reconnection data if valid, None if expired or not found.

    session_id: the session trying to reconnect
    """
    if session_id not in pending_reconnections:
        return None

    reconnection_data = pending_reconnections[session_id]

    # Check if reconnection window has expired
    expires_at = datetime.fromisoformat(
        reconnection_data["expires_at"]
    )

    if datetime.utcnow() > expires_at:
        # Window expired — remove and return None
        del pending_reconnections[session_id]
        print(f"Session {session_id} reconnection window expired ❌")
        return None

    # Valid reconnection — update count and return data
    pending_reconnections[session_id]["reconnection_count"] += 1
    print(
        f"Session {session_id} reconnected successfully ✅ "
        f"(attempt {reconnection_data['reconnection_count']})"
    )
    return reconnection_data


def complete_reconnection(session_id: str):
    """
    Called after a successful reconnection.
    Removes the session from pending reconnections.
    """
    if session_id in pending_reconnections:
        del pending_reconnections[session_id]
        print(f"Session {session_id} fully reconnected ✅")


def get_pending_reconnections() -> dict:
    """
    Returns all sessions waiting to reconnect.
    Used for monitoring.
    """
    return pending_reconnections


def cleanup_expired_reconnections():
    """
    Removes all expired reconnection sessions.
    Called periodically to keep memory clean.
    """
    now = datetime.utcnow()
    expired = [
        sid for sid, data in pending_reconnections.items()
        if datetime.fromisoformat(data["expires_at"]) < now
    ]
    for sid in expired:
        del pending_reconnections[sid]
        print(f"Cleaned up expired session: {sid}")

    if expired:
        print(f"Cleaned up {len(expired)} expired reconnections")
