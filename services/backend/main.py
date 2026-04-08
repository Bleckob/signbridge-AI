from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from backend.redis_client import test_redis_connection, get_redis
from backend.redis_streams import create_all_streams, get_stream_info
from backend.websocket_manager import manager
from backend.session_manager import (
    create_session,
    close_session,
    update_session_activity,
    get_all_sessions,
    get_session_count
)
from backend.supabase_client import test_supabase_connection
from backend.pipeline import run_pipeline_listener
from backend.latency import get_latency_stats
import asyncio
import json
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- STARTUP ---
    print("Starting SignBridge AI server...")

    # 1. Ensure Redis/Streams are ready
    try:
        create_all_streams()
        print("All Redis streams ready ✅")
    except Exception as e:
        print(f"❌ Failed to initialize streams: {e}")

    # 2. Start pipeline listener as a background task
    # We store it in app.state so the shutdown block can see it
    app.state.pipeline_task = asyncio.create_task(run_pipeline_listener())
    print("Pipeline listener started in background ✅")

    yield

    # --- SHUTDOWN ---
    print("SignBridge AI server shutting down...")

    # Cancel the background task we stored earlier
    app.state.pipeline_task.cancel()
    try:
        await app.state.pipeline_task
    except asyncio.CancelledError:
        print("Pipeline listener stopped cleanly ✅")
    except Exception as e:
        print(f"Error during shutdown: {e}")

# Create the FastAPI app
app = FastAPI(
    title="SignBridge AI",
    description="Real-Time Speech-to-Sign Language Avatar API",
    version="1.0.0",
    lifespan=lifespan
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
    supabase_status = test_supabase_connection()
    return {
        "status": "healthy" if redis_status and supabase_status else "degraded",
        "redis": "connected ✅" if redis_status else "disconnected ❌",
        "supabase": "connected ✅" if supabase_status else "disconnected ❌",
        "active_connections": len(manager.active_connections),
        "active_sessions": get_session_count()
    }

@app.get("/streams")
async def stream_status():
    """
    Shows the status of all Redis streams.
    Useful for confirming everything is working.
    """
    return {
        "streams": get_stream_info()
    }

@app.get("/sessions")
async def sessions_dashboard():
    """
    Shows all currently active sessions.
    Useful for monitoring who is connected.
    """
    return {
        "total_active_sessions": get_session_count(),
        "sessions": get_all_sessions()
    }

@app.get("/latency-stats")
async def latency_stats():
    """
    Shows p50 and p95 latency for every pipeline stage.
    Share this dashboard with your team at end of Week 2.
    """
    return {
        "latency_budget_ms": 1500,
        "stats": get_latency_stats()
    }

# WebSocket endpoint — this is what David's frontend connects to
# session_id is a unique ID for each user's session
# Example URL: ws://localhost:8000/ws/session_abc123
@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await manager.connect(websocket, session_id)
    create_session(session_id)

    try:
        redis = get_redis()

        await manager.send_message(session_id, {
            "type": "connection_established",
            "session_id": session_id,
            "message": "Connected to SignBridge AI ✅"
        })

        while True:
            try:
                # Wait for data but with a timeout of 30 seconds
                # If no data comes in 30 seconds, send a ping
                # This keeps the connection alive during silent gaps
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0
                )

                payload = json.loads(data)

                # Handle ping messages from Confidence's client
                if payload.get("type") == "ping":
                    await manager.send_message(session_id, {
                        "type": "pong",
                        "session_id": session_id
                    })
                    continue

                update_session_activity(session_id)

                redis.xadd("audio-chunks", {
                    "session_id": session_id,
                    "data": json.dumps(payload)
                })

                await manager.send_message(session_id, {
                    "type": "received",
                    "session_id": session_id,
                    "message": "Audio chunk received and queued ✅"
                })

            except asyncio.TimeoutError:
                # No data received in 30 seconds
                # Send a ping to check if client is still there
                try:
                    await manager.send_message(session_id, {
                        "type": "ping",
                        "session_id": session_id
                    })
                    print(f"Ping sent to session {session_id} — keeping alive")
                except Exception:
                    # Client didn't respond — connection is truly dead
                    print(f"Session {session_id} — no response to ping, closing")
                    break

    except WebSocketDisconnect:
        manager.disconnect(session_id)
        close_session(session_id)
        print(f"Session {session_id} disconnected cleanly")

    except Exception as e:
        print(f"Error in session {session_id}: {e}")
        manager.disconnect(session_id)
        close_session(session_id)
