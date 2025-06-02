"""
WebSocket manager for real-time proctoring communication.

This module handles WebSocket connections for proctoring sessions,
enabling real-time event streaming and bidirectional communication.
"""

import json
import logging
import asyncio
from typing import Dict, Set, Optional, Any, List
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
from dataclasses import dataclass

from ai_interviewer.models.proctoring import (
    ProctoringEventType,
    AnomalySeverity,
    LogProctoringEventRequest
)

logger = logging.getLogger(__name__)


@dataclass
class ProctoringConnection:
    """Represents a WebSocket connection for a proctoring session."""
    websocket: WebSocket
    session_id: str
    user_id: str
    connected_at: datetime
    last_heartbeat: datetime


class ProctoringWebSocketManager:
    """Manager for WebSocket connections in proctoring sessions."""
    
    def __init__(self):
        """Initialize the WebSocket manager."""
        # Active connections: session_id -> ProctoringConnection
        self.connections: Dict[str, ProctoringConnection] = {}
        
        # Connection pools for broadcasting
        self.session_connections: Dict[str, Set[str]] = {}  # session_id -> set of connection_ids
        self.user_connections: Dict[str, Set[str]] = {}     # user_id -> set of connection_ids
        
        # Heartbeat tracking
        self.heartbeat_interval = 30  # seconds
        self.heartbeat_task: Optional[asyncio.Task] = None
        self._heartbeat_started = False
        
        # Message handlers
        self.message_handlers = {
            "heartbeat": self._handle_heartbeat,
            "event": self._handle_event,
            "status_update": self._handle_status_update,
            "face_data": self._handle_face_data,
            "screen_activity": self._handle_screen_activity,
        }
        
        # Don't start heartbeat monitor here - will be started when first connection is made
    
    def _start_heartbeat_monitor(self):
        """Start the heartbeat monitoring task."""
        if not self._heartbeat_started and (self.heartbeat_task is None or self.heartbeat_task.done()):
            try:
                self.heartbeat_task = asyncio.create_task(self._heartbeat_monitor())
                self._heartbeat_started = True
            except RuntimeError:
                # No event loop running yet, will start when first connection is made
                pass
    
    async def _heartbeat_monitor(self):
        """Monitor heartbeats and disconnect stale connections."""
        while True:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                current_time = datetime.utcnow()
                stale_connections = []
                
                for connection_id, connection in self.connections.items():
                    time_since_heartbeat = (current_time - connection.last_heartbeat).total_seconds()
                    if time_since_heartbeat > self.heartbeat_interval * 2:  # 2x timeout
                        stale_connections.append(connection_id)
                
                # Disconnect stale connections
                for connection_id in stale_connections:
                    await self._disconnect_stale(connection_id)
                
            except Exception as e:
                logger.error(f"Error in heartbeat monitor: {e}")
    
    async def _disconnect_stale(self, connection_id: str):
        """Disconnect a stale connection."""
        if connection_id in self.connections:
            connection = self.connections[connection_id]
            logger.warning(f"Disconnecting stale proctoring connection for session {connection.session_id}")
            try:
                await connection.websocket.close()
            except Exception:
                pass  # Connection might already be closed
            finally:
                await self.disconnect(connection_id)
    
    async def connect(self, websocket: WebSocket, session_id: str, user_id: str) -> str:
        """Accept a new WebSocket connection for proctoring."""
        await websocket.accept()
        
        connection_id = f"{session_id}_{user_id}_{datetime.utcnow().timestamp()}"
        current_time = datetime.utcnow()
        
        connection = ProctoringConnection(
            websocket=websocket,
            session_id=session_id,
            user_id=user_id,
            connected_at=current_time,
            last_heartbeat=current_time
        )
        
        # Store connection
        self.connections[connection_id] = connection
        
        # Add to pools
        if session_id not in self.session_connections:
            self.session_connections[session_id] = set()
        self.session_connections[session_id].add(connection_id)
        
        if user_id not in self.user_connections:
            self.user_connections[user_id] = set()
        self.user_connections[user_id].add(connection_id)
        
        logger.info(f"Proctoring WebSocket connected: session={session_id}, user={user_id}, connection={connection_id}")
        
        # Send connection confirmation
        await self._send_to_connection(connection_id, {
            "type": "connection_confirmed",
            "connection_id": connection_id,
            "session_id": session_id,
            "timestamp": current_time.isoformat()
        })
        
        # Start heartbeat monitoring if not already started
        self._start_heartbeat_monitor()
        
        return connection_id
    
    async def disconnect(self, connection_id: str):
        """Disconnect a WebSocket connection."""
        if connection_id not in self.connections:
            return
        
        connection = self.connections[connection_id]
        session_id = connection.session_id
        user_id = connection.user_id
        
        # Remove from pools
        if session_id in self.session_connections:
            self.session_connections[session_id].discard(connection_id)
            if not self.session_connections[session_id]:
                del self.session_connections[session_id]
        
        if user_id in self.user_connections:
            self.user_connections[user_id].discard(connection_id)
            if not self.user_connections[user_id]:
                del self.user_connections[user_id]
        
        # Remove connection
        del self.connections[connection_id]
        
        logger.info(f"Proctoring WebSocket disconnected: session={session_id}, user={user_id}, connection={connection_id}")
    
    async def handle_message(self, connection_id: str, message: str) -> bool:
        """Handle incoming WebSocket message."""
        if connection_id not in self.connections:
            logger.warning(f"Received message from unknown connection: {connection_id}")
            return False
        
        try:
            data = json.loads(message)
            message_type = data.get("type")
            
            if message_type in self.message_handlers:
                await self.message_handlers[message_type](connection_id, data)
                return True
            else:
                logger.warning(f"Unknown message type: {message_type}")
                await self._send_error(connection_id, f"Unknown message type: {message_type}")
                return False
                
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in WebSocket message: {e}")
            await self._send_error(connection_id, "Invalid JSON format")
            return False
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}")
            await self._send_error(connection_id, "Internal error processing message")
            return False
    
    async def _handle_heartbeat(self, connection_id: str, data: Dict[str, Any]):
        """Handle heartbeat message."""
        if connection_id in self.connections:
            self.connections[connection_id].last_heartbeat = datetime.utcnow()
            await self._send_to_connection(connection_id, {
                "type": "heartbeat_ack",
                "timestamp": datetime.utcnow().isoformat()
            })
    
    async def _handle_event(self, connection_id: str, data: Dict[str, Any]):
        """Handle proctoring event message."""
        connection = self.connections.get(connection_id)
        if not connection:
            return
        
        # Extract event data
        event_type = data.get("event_type")
        severity = data.get("severity", "low")
        confidence = data.get("confidence", 1.0)
        event_data = data.get("data", {})
        evidence_data = data.get("evidence_data")
        
        if not event_type:
            await self._send_error(connection_id, "Missing event_type")
            return
        
        # Validate event type
        try:
            ProctoringEventType(event_type)
            AnomalySeverity(severity)
        except ValueError as e:
            await self._send_error(connection_id, f"Invalid event type or severity: {e}")
            return
        
        # Create event request (this would typically be processed by the proctoring service)
        event_request = LogProctoringEventRequest(
            session_id=connection.session_id,
            event_type=event_type,
            severity=severity,
            confidence=confidence,
            data=event_data,
            evidence_data=evidence_data
        )
        
        # Broadcast event to other connections in the session (e.g., monitoring dashboard)
        await self.broadcast_to_session(connection.session_id, {
            "type": "event_notification",
            "event": {
                "event_type": event_type,
                "severity": severity,
                "confidence": confidence,
                "timestamp": datetime.utcnow().isoformat(),
                "session_id": connection.session_id,
                "user_id": connection.user_id
            }
        }, exclude_connection=connection_id)
        
        # Send acknowledgment
        await self._send_to_connection(connection_id, {
            "type": "event_logged",
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    async def _handle_status_update(self, connection_id: str, data: Dict[str, Any]):
        """Handle status update message."""
        connection = self.connections.get(connection_id)
        if not connection:
            return
        
        status_data = {
            "type": "status_update",
            "session_id": connection.session_id,
            "user_id": connection.user_id,
            "status": data.get("status"),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Broadcast status to session
        await self.broadcast_to_session(connection.session_id, status_data, exclude_connection=connection_id)
    
    async def _handle_face_data(self, connection_id: str, data: Dict[str, Any]):
        """Handle face detection data."""
        connection = self.connections.get(connection_id)
        if not connection:
            return
        
        face_count = data.get("face_count", 0)
        confidence = data.get("confidence", 0.0)
        gaze_state = data.get("gaze_state", "unknown")
        
        # Determine if this is an anomaly
        event_type = None
        severity = AnomalySeverity.LOW
        
        if face_count == 0:
            event_type = ProctoringEventType.NO_FACE_DETECTED
            severity = AnomalySeverity.MEDIUM
        elif face_count > 1:
            event_type = ProctoringEventType.MULTIPLE_FACES
            severity = AnomalySeverity.HIGH
        elif gaze_state == "away":
            event_type = ProctoringEventType.GAZE_AWAY
            severity = AnomalySeverity.MEDIUM
        
        # Log significant events
        if event_type:
            await self._handle_event(connection_id, {
                "event_type": event_type,
                "severity": severity,
                "confidence": confidence,
                "data": {
                    "face_count": face_count,
                    "gaze_state": gaze_state,
                    "detection_confidence": confidence
                }
            })
    
    async def _handle_screen_activity(self, connection_id: str, data: Dict[str, Any]):
        """Handle screen activity monitoring data."""
        connection = self.connections.get(connection_id)
        if not connection:
            return
        
        activity_type = data.get("activity_type")
        
        # Map activity types to proctoring events
        event_mapping = {
            "tab_switch": ProctoringEventType.TAB_SWITCH,
            "copy": ProctoringEventType.COPY_PASTE,
            "paste": ProctoringEventType.COPY_PASTE,
            "focus_lost": ProctoringEventType.FOCUS_LOST,
            "focus_gained": ProctoringEventType.FOCUS_GAINED,
            "new_window": ProctoringEventType.NEW_WINDOW
        }
        
        if activity_type in event_mapping:
            severity = AnomalySeverity.MEDIUM
            if activity_type in ["copy", "paste", "tab_switch"]:
                severity = AnomalySeverity.HIGH
            
            await self._handle_event(connection_id, {
                "event_type": event_mapping[activity_type],
                "severity": severity,
                "confidence": 1.0,
                "data": {
                    "activity_type": activity_type,
                    "timestamp": data.get("timestamp", datetime.utcnow().isoformat())
                }
            })
    
    async def _send_to_connection(self, connection_id: str, message: Dict[str, Any]):
        """Send a message to a specific connection."""
        if connection_id not in self.connections:
            return False
        
        try:
            await self.connections[connection_id].websocket.send_text(json.dumps(message))
            return True
        except Exception as e:
            logger.error(f"Error sending to connection {connection_id}: {e}")
            await self.disconnect(connection_id)
            return False
    
    async def _send_error(self, connection_id: str, error_message: str):
        """Send an error message to a connection."""
        await self._send_to_connection(connection_id, {
            "type": "error",
            "message": error_message,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    async def broadcast_to_session(self, session_id: str, message: Dict[str, Any], exclude_connection: Optional[str] = None):
        """Broadcast a message to all connections in a session."""
        if session_id not in self.session_connections:
            return
        
        connections = self.session_connections[session_id].copy()
        if exclude_connection:
            connections.discard(exclude_connection)
        
        failed_connections = []
        for connection_id in connections:
            success = await self._send_to_connection(connection_id, message)
            if not success:
                failed_connections.append(connection_id)
        
        # Clean up failed connections
        for connection_id in failed_connections:
            await self.disconnect(connection_id)
    
    async def broadcast_to_user(self, user_id: str, message: Dict[str, Any]):
        """Broadcast a message to all connections for a user."""
        if user_id not in self.user_connections:
            return
        
        connections = self.user_connections[user_id].copy()
        failed_connections = []
        
        for connection_id in connections:
            success = await self._send_to_connection(connection_id, message)
            if not success:
                failed_connections.append(connection_id)
        
        # Clean up failed connections
        for connection_id in failed_connections:
            await self.disconnect(connection_id)
    
    async def send_alert(self, session_id: str, alert_type: str, severity: str, data: Dict[str, Any]):
        """Send an alert to all connections monitoring a session."""
        alert_message = {
            "type": "alert",
            "alert_type": alert_type,
            "severity": severity,
            "session_id": session_id,
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self.broadcast_to_session(session_id, alert_message)
    
    async def send_command(self, connection_id: str, command: str, parameters: Dict[str, Any] = None):
        """Send a command to a specific connection."""
        command_message = {
            "type": "command",
            "command": command,
            "parameters": parameters or {},
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return await self._send_to_connection(connection_id, command_message)
    
    def get_session_connections(self, session_id: str) -> List[str]:
        """Get all connection IDs for a session."""
        return list(self.session_connections.get(session_id, set()))
    
    def get_connection_info(self, connection_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a connection."""
        if connection_id not in self.connections:
            return None
        
        connection = self.connections[connection_id]
        return {
            "connection_id": connection_id,
            "session_id": connection.session_id,
            "user_id": connection.user_id,
            "connected_at": connection.connected_at.isoformat(),
            "last_heartbeat": connection.last_heartbeat.isoformat()
        }
    
    def get_active_sessions(self) -> List[str]:
        """Get list of all active session IDs."""
        return list(self.session_connections.keys())
    
    def get_stats(self) -> Dict[str, Any]:
        """Get WebSocket manager statistics."""
        return {
            "total_connections": len(self.connections),
            "active_sessions": len(self.session_connections),
            "active_users": len(self.user_connections),
            "heartbeat_interval": self.heartbeat_interval
        }
    
    async def shutdown(self):
        """Shutdown the WebSocket manager and close all connections."""
        logger.info("Shutting down proctoring WebSocket manager")
        
        # Cancel heartbeat task
        if self.heartbeat_task and not self.heartbeat_task.done():
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass
        
        # Close all connections
        connection_ids = list(self.connections.keys())
        for connection_id in connection_ids:
            connection = self.connections[connection_id]
            try:
                await connection.websocket.close()
            except Exception:
                pass
            await self.disconnect(connection_id)
        
        logger.info("Proctoring WebSocket manager shutdown complete")


# Global instance
proctoring_ws_manager = ProctoringWebSocketManager() 