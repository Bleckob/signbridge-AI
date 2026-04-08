import json
from backend.redis_client import get_redis
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# ============================================
# STREAM NAMES — These are the conveyor belts
# Share these exact names with your teammates
# ============================================
STREAM_AUDIO_CHUNKS = "audio-chunks"      # Confidence → Ife
STREAM_ASR_OUTPUT = "asr-output"          # Ife → Amos
STREAM_NLP_OUTPUT = "nlp-output"          # Amos → You
STREAM_SESSION_RESULT = "session-result"  # You → David


def create_all_streams():
    """
    Creates all Redis streams if they don't already exist.
    This runs once when the server starts up.
    Think of it as setting up all the conveyor belts
    before the factory opens.
    """
    redis = get_redis()
    streams = [
        STREAM_AUDIO_CHUNKS,
        STREAM_ASR_OUTPUT,
        STREAM_NLP_OUTPUT,
        STREAM_SESSION_RESULT
    ]

    for stream in streams:
        try:
            # Check if stream already exists
            redis.xlen(stream)
            print(f"Stream already exists: {stream} ✅")
        except Exception:
            # Stream doesn't exist — create it with a placeholder message
            # The * means Redis auto-generates the message ID
            redis.xadd(stream, {"init": "stream_created"})
            print(f"Stream created: {stream} ✅")


def push_to_stream(stream_name: str, session_id: str, data: dict):
    """
    Pushes data onto a Redis stream.
    Used by your server to send data to the next stage.

    stream_name: which conveyor belt to use
    session_id: which user this data belongs to
    data: the actual content being sent
    """
    redis = get_redis()
    payload = {
        "session_id": session_id,
        "data": json.dumps(data)
    }
    # xadd adds a new message to the stream
    # * means Redis auto-generates a unique message ID
    message_id = redis.xadd(stream_name, payload)
    print(f"Pushed to {stream_name}: message_id={message_id}")
    return message_id


def read_from_stream(stream_name: str, last_id: str = "0"):
    """
    Reads messages from a Redis stream.

    stream_name: which conveyor belt to read from
    last_id: read messages after this ID (0 means read from beginning)
    """
    redis = get_redis()
    # xread reads messages from the stream
    # count=10 means read maximum 10 messages at a time
    # block=1000 means wait up to 1000ms for new messages
    messages = redis.xread(
        {stream_name: last_id},
        count=10,
        block=1000
    )
    return messages


def get_stream_info():
    """
    Returns info about all streams.
    Used by your latency dashboard in Week 2.
    """
    redis = get_redis()
    info = {}
    streams = [
        STREAM_AUDIO_CHUNKS,
        STREAM_ASR_OUTPUT,
        STREAM_NLP_OUTPUT,
        STREAM_SESSION_RESULT
    ]
    for stream in streams:
        try:
            length = redis.xlen(stream)
            info[stream] = {
                "length": length,
                "status": "active ✅"
            }
        except Exception:
            info[stream] = {
                "length": 0,
                "status": "not created ❌"
            }
    return info
