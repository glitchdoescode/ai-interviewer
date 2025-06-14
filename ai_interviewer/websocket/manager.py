"""
WebSocket connection manager for the AI Interviewer platform.
"""
from typing import Dict, Set
from fastapi import WebSocket

class WebSocketManager:
    """Manages WebSocket connections for real-time communication."""
    
    def __init__(self):
        """Initialize the WebSocket manager."""
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        
    async def connect(self, websocket: WebSocket, client_id: str):
        """Connect a new WebSocket client."""
        await websocket.accept()
        if client_id not in self.active_connections:
            self.active_connections[client_id] = set()
        self.active_connections[client_id].add(websocket)
        
    def disconnect(self, websocket: WebSocket, client_id: str):
        """Disconnect a WebSocket client."""
        if client_id in self.active_connections:
            self.active_connections[client_id].discard(websocket)
            if not self.active_connections[client_id]:
                del self.active_connections[client_id]
                
    async def broadcast_to_client(self, client_id: str, message: str):
        """Broadcast a message to all connections for a specific client."""
        if client_id not in self.active_connections:
            return
            
        # Create a list of failed websockets to remove
        failed_websockets = set()
        
        for websocket in self.active_connections[client_id]:
            try:
                await websocket.send_text(message)
            except Exception:
                failed_websockets.add(websocket)
                
        # Remove failed websockets
        self.active_connections[client_id] -= failed_websockets
        
        # Clean up empty client entries
        if not self.active_connections[client_id]:
            del self.active_connections[client_id]
            
    async def broadcast_to_all(self, message: str):
        """Broadcast a message to all connected clients."""
        # Create a list of clients to remove (if all their connections failed)
        clients_to_remove = set()
        
        for client_id in self.active_connections:
            failed_websockets = set()
            
            for websocket in self.active_connections[client_id]:
                try:
                    await websocket.send_text(message)
                except Exception:
                    failed_websockets.add(websocket)
                    
            # Remove failed websockets
            self.active_connections[client_id] -= failed_websockets
            
            # If no connections left for this client, mark for removal
            if not self.active_connections[client_id]:
                clients_to_remove.add(client_id)
                
        # Remove empty client entries
        for client_id in clients_to_remove:
            del self.active_connections[client_id]
            
    def close(self):
        """Close all active connections."""
        self.active_connections.clear() 