from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from blessing.redis_client import test_redis_connection
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Create the FastAPI app
app = FastAPI(
    title="SignBridge AI",
    description="Real-Time Speech-to-Sign Language Avatar API",
    version="1.0.0"
)

# CORS Middleware — allows David's frontend to talk to your server
# * means any frontend can connect for now
# We'll restrict this to David's Vercel URL in Week 3
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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

# Health check endpoint — now actually tests Redis connection
@app.get("/health")
async def health_check():
    redis_status = test_redis_connection()
    return {
        "status": "healthy" if redis_status else "degraded",
        "redis": "connected ✅" if redis_status else "disconnected ❌",
        "supabase": "not yet connected"
    }