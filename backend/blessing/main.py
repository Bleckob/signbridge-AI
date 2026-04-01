from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from blessing.redis_client import test_redis_connection, get_redis
from blessing.websocket_manager import manager
import os
import json
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

# Create the FastAPI app
app = FastAPI(
    title="SignBridge AI",
    description="Real-Time Speech-to-Sign Language Avatar API",
    version="1.0.0"
)

# CORS Middleware — allows David's frontend to talk to your server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # We'll restrict to David's Vercel URL in Week 3
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root endpoint — confirms server is running
@app.get("/")
async def root():
    return {
        "status": "running",
        "project": "SignBridge AI",
        "message": "Server is live!"
    }

# Health check endpoint — tests Redis connection
@app.get("/health")
async def health_check():
    redis_status = test_redis_connection()
    return {
        "status": "healthy" if redis_status else "degraded",
        "redis": "connected ✅" if redis_status else "disconnected ❌",
        "supabase": "not yet connected",
        "active_connections": len(manager.active_connections)
    }

# WebSocket endpoint — this is what David's frontend connects to
# session_id is a unique ID for each user's session
# Example URL: ws://localhost:8000/ws/session_abc123
@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    # Step 1: Accept and store the connection
    await manager.connect(websocket, session_id)

    try:
        # Step 2: Get Redis client ready
        redis = get_redis()

        # Step 3: Send a welcome message to confirm connection
        await manager.send_message(session_id, {
            "type": "connection_established",
            "session_id": session_id,
            "message": "Connected to SignBridge AI ✅"
        })

        # Step 4: Keep listening for incoming messages
        # This loop runs forever until the user disconnects
        while True:
            # Wait for data from David's frontend
            data = await websocket.receive_text()

            # Convert the received text into a Python dictionary
            payload = json.loads(data)

            # Push the audio data onto Redis stream for Confidence/Ife to pick up
            redis.xadd("audio-chunks", {
                "session_id": session_id,
                "data": json.dumps(payload)
            })

            # Confirm receipt back to David's frontend
            await manager.send_message(session_id, {
                "type": "received",
                "session_id": session_id,
                "message": "Audio chunk received and queued ✅"
            })

    except WebSocketDisconnect:
        # Step 5: Clean up when user disconnects
        manager.disconnect(session_id)
        print(f"Session {session_id} disconnected cleanly")

    except Exception as e:
        # Step 6: Handle any unexpected errors
        print(f"Error in session {session_id}: {e}")
        manager.disconnect(session_id)