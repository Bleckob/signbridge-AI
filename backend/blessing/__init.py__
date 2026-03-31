from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # We'll restrict this to David's Vercel URL later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Basic health check route — confirms server is running
@app.get("/")
async def root():
    return {
        "status": "running",
        "project": "SignBridge AI",
        "message": "Server is live!"
    }

# Health check endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "redis": "not yet connected",
        "supabase": "not yet connected"
    }