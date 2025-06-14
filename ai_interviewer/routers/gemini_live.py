"""
WebSocket router for Gemini Live API real-time audio streaming.

This module provides WebSocket endpoints for connecting the frontend 
useGeminiLiveAudio hook to the backend GeminiLiveAudioAdapter service.
"""

import asyncio
import logging
import json
import base64
import os
from typing import Dict, Any, Optional
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.routing import APIRouter

from ai_interviewer.services.gemini_live_adapter import GeminiLiveAudioAdapter
from ai_interviewer.services.context_injection_service import ContextInjectionService  
from ai_interviewer.services.langgraph_integration_adapter import LangGraphIntegrationAdapter
from ai_interviewer.auth.security import get_current_active_user
from ai_interviewer.utils.session_manager import SessionManager
from ai_interviewer.core.ai_interviewer import AIInterviewer

logger = logging.getLogger(__name__)

router = APIRouter()

# Global connection manager for active Gemini Live sessions
class GeminiLiveConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Dict[str, Any]] = {}
        
    async def connect(self, websocket: WebSocket, session_id: str, user_id: str):
        """Establish WebSocket connection and initialize Gemini Live session."""
        try:
            await websocket.accept()
            logger.info(f"WebSocket connection accepted for session {session_id}")
            
            # Store basic connection info first
            self.active_connections[session_id] = {
                'websocket': websocket,
                'user_id': user_id,
                'session_id': session_id,
                'connected_at': datetime.now().isoformat()
            }
            
            logger.info(f"Basic connection established for session {session_id}")
            
            # Try to initialize services but don't fail the connection if they fail
            try:
                # Initialize Gemini Live adapter and context service
                gemini_adapter = GeminiLiveAudioAdapter()
                
                # Get session metadata for context
                session_manager = SessionManager(
                    connection_uri=os.getenv("MONGODB_URI"),
                    database_name=os.getenv("MONGODB_DATABASE"),
                    collection_name=os.getenv("MONGODB_METADATA_COLLECTION")
                )
                
                session_data = session_manager.get_session(session_id)
                session_metadata = session_data.get('metadata', {}) if session_data else {}
                
                # Build initial prompt
                initial_prompt = self._build_initial_prompt(session_metadata)
                
                # Start Gemini Live session
                success = await gemini_adapter.start_session(initial_prompt)
                if success:
                    logger.info(f"Gemini Live session started for {session_id}")
                    # Update connection with adapter
                    self.active_connections[session_id]['gemini_adapter'] = gemini_adapter
                    self.active_connections[session_id]['session_metadata'] = session_metadata
                else:
                    logger.warning(f"Gemini Live session failed to start for {session_id}, proceeding with basic connection")
                    
            except Exception as service_error:
                logger.warning(f"Service initialization failed for session {session_id}: {service_error}")
                # Continue with basic connection even if services fail
            
            logger.info(f"Connection established for session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error establishing connection: {e}", exc_info=True)
            try:
                await websocket.close(code=1008, reason=f"Connection error: {str(e)}")
            except:
                pass
            return False
        
    async def disconnect(self, session_id: str):
        """Disconnect and cleanup a Gemini Live session."""
        if session_id in self.active_connections:
            connection = self.active_connections[session_id]
            
            # Stop Gemini Live session
            if 'gemini_adapter' in connection:
                await connection['gemini_adapter'].stop_session()
            
            # Close WebSocket if still open
            try:
                await connection['websocket'].close()
            except Exception as e:
                logger.warning(f"Error closing WebSocket for {session_id}: {e}")
            
            # Remove from active connections
            del self.active_connections[session_id]
            logger.info(f"Gemini Live connection closed for session {session_id}")
    
    async def send_to_session(self, session_id: str, message: Dict[str, Any]):
        """Send a message to a specific session WebSocket."""
        if session_id in self.active_connections:
            websocket = self.active_connections[session_id]['websocket']
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error sending message to session {session_id}: {e}")
                await self.disconnect(session_id)
    
    async def handle_audio_data(self, session_id: str, audio_data: bytes):
        """Process incoming audio data from frontend."""
        if session_id not in self.active_connections:
            logger.warning(f"No active connection for session {session_id}")
            return
            
        connection = self.active_connections[session_id]
        gemini_adapter = connection['gemini_adapter']
        
        try:
            # Send audio to Gemini Live API
            # This would integrate with the gemini_adapter's audio input queue
            # For now, we'll simulate processing
            await gemini_adapter.audio_in_queue.put(audio_data)
            
        except Exception as e:
            logger.error(f"Error processing audio for session {session_id}: {e}")
    
    async def handle_context_injection(self, session_id: str, context: Dict[str, Any]):
        """Inject context into the Gemini Live conversation."""
        if session_id not in self.active_connections:
            logger.warning(f"No active connection for session {session_id}")
            return
            
        connection = self.active_connections[session_id]
        context_injector = connection['context_injector']
        
        try:
            await context_injector.inject_context(context)
            
        except Exception as e:
            logger.error(f"Error injecting context for session {session_id}: {e}")
    
    def _build_initial_prompt(self, session_metadata: Dict[str, Any]) -> str:
        """Build initial prompt from session metadata."""
        job_role = session_metadata.get('job_role', 'Software Developer')
        seniority = session_metadata.get('seniority_level', 'Mid-level')
        skills = session_metadata.get('required_skills', [])
        
        prompt = f"""You are Alex, an AI interviewer conducting a technical interview for a {seniority} {job_role} position.

Required skills: {', '.join(skills) if skills else 'General software development'}

This is a real-time audio conversation. Maintain a natural, conversational tone and be ready to:
- Ask technical questions appropriate for the role
- Evaluate responses and provide follow-up questions
- Guide the interview through different stages
- Be professional but friendly

The interview is just beginning. Greet the candidate and start with introductory questions."""
        
        return prompt

# Global connection manager instance
gemini_manager = GeminiLiveConnectionManager()

@router.websocket("/ws/gemini-live/{session_id}")
async def gemini_live_websocket(websocket: WebSocket, session_id: str, user_id: str):
    """
    WebSocket endpoint for Gemini Live API real-time audio streaming.
    
    Args:
        websocket: WebSocket connection
        session_id: Interview session ID
        user_id: User ID for authentication
    """
    try:
        # Establish connection
        success = await gemini_manager.connect(websocket, session_id, user_id)
        if not success:
            return
        
        # Send connection confirmation
        await gemini_manager.send_to_session(session_id, {
            "type": "connection_established",
            "session_id": session_id,
            "status": "ready"
        })
        
        # Main message loop
        while True:
            try:
                # Receive message from frontend
                data = await websocket.receive_text()
                message = json.loads(data)
                
                message_type = message.get("type")
                
                if message_type == "audio_data":
                    # Process audio data
                    audio_base64 = message.get("data")
                    if audio_base64:
                        audio_data = base64.b64decode(audio_base64)
                        await gemini_manager.handle_audio_data(session_id, audio_data)
                
                elif message_type == "context_injection":
                    # Handle context injection
                    context = message.get("context", {})
                    await gemini_manager.handle_context_injection(session_id, context)
                
                elif message_type == "start_listening":
                    # Notify that user started speaking
                    await gemini_manager.send_to_session(session_id, {
                        "type": "listening_started",
                        "timestamp": message.get("timestamp")
                    })
                
                elif message_type == "stop_listening":
                    # Notify that user stopped speaking
                    await gemini_manager.send_to_session(session_id, {
                        "type": "listening_stopped",
                        "timestamp": message.get("timestamp")
                    })
                
                elif message_type == "ping":
                    # Health check
                    await gemini_manager.send_to_session(session_id, {
                        "type": "pong",
                        "timestamp": message.get("timestamp")
                    })
                
                else:
                    logger.warning(f"Unknown message type: {message_type}")
                    
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON received: {e}")
                await gemini_manager.send_to_session(session_id, {
                    "type": "error",
                    "message": "Invalid JSON format"
                })
            
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                await gemini_manager.send_to_session(session_id, {
                    "type": "error", 
                    "message": "Message processing error"
                })
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}")
    finally:
        # Always cleanup on exit
        await gemini_manager.disconnect(session_id)

@router.get("/status/{session_id}")
async def get_gemini_live_status(session_id: str):
    """Get the status of a Gemini Live session."""
    is_active = session_id in gemini_manager.active_connections
    return {
        "session_id": session_id,
        "active": is_active,
        "connection_count": len(gemini_manager.active_connections)
    } 