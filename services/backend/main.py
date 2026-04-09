from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from backend.redis_client import test_redis_connection, get_redis
from backend.redis_streams import create_all_streams, get_stream_info
from backend.websocket_manager import manager
from datetime import datetime
from backend.session_manager import (
    create_session,
    close_session,
    update_session_activity,
    get_all_sessions,
    get_session_count,
    get_session
)
from backend.reconnection import (
    register_disconnection,
    attempt_reconnection,
    complete_reconnection,
    get_pending_reconnections,
    cleanup_expired_reconnections
)
from backend.supabase_client import test_supabase_connection
from backend.pipeline import run_pipeline_listener
from backend.latency import get_latency_stats
from backend.sentry_config import init_sentry
import asyncio
import json
import httpx
import os
from dotenv import load_dotenv
from pathlib import Path


# Load environment variables from .env file
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

async def keep_alive_ping():
    """
    Pings the server itself every 10 minutes.
    Prevents Render free tier from putting server to sleep.
    Only runs in production — not needed locally.
    """
    # Only run in production
    if os.getenv("APP_ENV") != "production":
        return

    render_url = os.getenv("RENDER_URL")
    if not render_url:
        print("⚠️ RENDER_URL not set — keep alive disabled")
        return

    print("Keep alive started — pinging every 10 minutes ✅")

    while True:
        # Wait 10 minutes
        await asyncio.sleep(600)
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{render_url}/health")
                print(f"Keep alive ping sent ✅ status: {response.status_code}")
        except Exception as e:
            print(f"Keep alive ping failed: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- STARTUP ---
    print("Starting SignBridge AI server...")

    init_sentry()

    try:
        create_all_streams()
        print("All Redis streams ready ✅")
    except Exception as e:
        print(f"❌ Failed to initialize streams: {e}")

    app.state.pipeline_task = asyncio.create_task(run_pipeline_listener())
    print("Pipeline listener started in background ✅")

    async def periodic_cleanup():
        while True:
            await asyncio.sleep(60)
            cleanup_expired_reconnections()

    app.state.cleanup_task = asyncio.create_task(periodic_cleanup())
    print("Reconnection cleanup task started ✅")

    # Start keep alive for Render free tier
    app.state.keep_alive_task = asyncio.create_task(keep_alive_ping())

    yield

    # --- SHUTDOWN ---
    print("SignBridge AI server shutting down...")
    app.state.pipeline_task.cancel()
    app.state.cleanup_task.cancel()
    app.state.keep_alive_task.cancel()
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

@app.get("/reconnections")
async def reconnection_status():
    """
    Shows all sessions currently waiting to reconnect.
    Useful for monitoring dropped connections.
    """
    pending = get_pending_reconnections()
    return {
        "total_pending_reconnections": len(pending),
        "reconnection_window_seconds": 60,
        "pending": pending
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
    # Check if this is a reconnection attempt
    reconnection_data = attempt_reconnection(session_id)

    if reconnection_data:
        # This is a reconnection — restore the session
        print(f"Restoring session: {session_id}")
        await manager.connect(websocket, session_id)
        create_session(session_id)
        complete_reconnection(session_id)

        # Tell client they reconnected successfully
        await manager.send_message(session_id, {
            "type": "reconnection_successful",
            "session_id": session_id,
            "message": "Reconnected to SignBridge AI ✅",
            "previous_disconnection": reconnection_data["disconnected_at"]
        })
    else:
        # This is a brand new connection
        await manager.connect(websocket, session_id)
        create_session(session_id)

        await manager.send_message(session_id, {
            "type": "connection_established",
            "session_id": session_id,
            "message": "Connected to SignBridge AI ✅"
        })

    try:
        redis = get_redis()

        while True:
            try:
                # Wait for data with 30 second timeout
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0
                )

                payload = json.loads(data)

                # Handle ping messages — keepalive from Confidence
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
                # No data for 30 seconds — send ping
                try:
                    await manager.send_message(session_id, {
                        "type": "ping",
                        "session_id": session_id
                    })
                    session_data = get_session(session_id)
                    ping_count = session_data.get("audio_chunks_received", 0) if session_data else 0
                    if ping_count % 5 == 0:
                        print(f"Ping sent to {session_id} — keeping alive")
                    print(f"Ping sent to {session_id} — keeping alive")
                except Exception:
                    print(f"Session {session_id} not responding — closing")
                    break

    except WebSocketDisconnect:
        # Get session data before closing
        session = get_session(session_id)
        last_activity = session["last_activity"] if session else datetime.utcnow().isoformat()

        # Register disconnection for potential reconnection
        register_disconnection(session_id, last_activity)

        # Clean up connection
        manager.disconnect(session_id)
        close_session(session_id)
        print(f"Session {session_id} disconnected — reconnection window open for {60}s")

    except Exception as e:
        print(f"Error in session {session_id}: {e}")
        manager.disconnect(session_id)
        close_session(session_id)
