from fastapi import WebSocket
from typing import Dict
import json

class WebSocketManager:
    """
    Manages all active WebSocket connections.
    Each user gets their own session identified by session_id.
    Think of this as the telephone exchange — it knows who is 
    connected and routes messages to the right person.
    """

    def __init__(self):
        # Dictionary to store all active connections
        # Key: session_id, Value: WebSocket connection
        # Example: {"session_abc123": <WebSocket object>}
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        """
        Accepts a new WebSocket connection and stores it.
        Called when David's frontend first connects.
        """
        await websocket.accept()
        self.active_connections[session_id] = websocket
        print(f"New connection: session {session_id}")
        print(f"Total active connections: {len(self.active_connections)}")

    def disconnect(self, session_id: str):
        """
        Removes a connection when a user disconnects.
        Called when David's frontend closes or loses connection.
        """
        if session_id in self.active_connections:
            del self.active_connections[session_id]
            print(f"Disconnected: session {session_id}")
            print(f"Total active connections: {len(self.active_connections)}")

    async def send_message(self, session_id: str, message: dict):
        """
        Sends a message to a specific session.
        Used to send animation data back to David's frontend.
        """
        if session_id in self.active_connections:
            websocket = self.active_connections[session_id]
            await websocket.send_text(json.dumps(message))

    async def broadcast(self, message: dict):
        """
        Sends a message to ALL connected sessions.
        Useful for system wide announcements.
        """
        for session_id, websocket in self.active_connections.items():
            await websocket.send_text(json.dumps(message))


# Create a single instance that the whole app will use
# This is imported into main.py
manager = WebSocketManager()