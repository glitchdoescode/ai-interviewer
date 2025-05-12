"""
FastAPI server for the AI Interviewer platform.

This module provides a REST API for interacting with the AI Interviewer.
"""
import os
import uuid
import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ai_interviewer.core.ai_interviewer import AIInterviewer

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="AI Interviewer API",
    description="REST API for the AI Technical Interviewer platform",
    version="1.0.0",
)

# Add CORS middleware to allow cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update with specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize AI Interviewer instance
interviewer = AIInterviewer()

# Pydantic models for request/response validation
class MessageRequest(BaseModel):
    message: str = Field(..., description="User's message")
    user_id: Optional[str] = Field(None, description="User ID (generated if not provided)")

class MessageResponse(BaseModel):
    response: str = Field(..., description="AI interviewer's response")
    session_id: str = Field(..., description="Session ID for continuing the conversation")
    interview_stage: Optional[str] = Field(None, description="Current stage of the interview")

class SessionRequest(BaseModel):
    session_id: str = Field(..., description="Session ID to resume")
    user_id: str = Field(..., description="User ID associated with the session")

class SessionResponse(BaseModel):
    session_id: str = Field(..., description="Session ID")
    user_id: str = Field(..., description="User ID")
    created_at: str = Field(..., description="Session creation timestamp")
    last_active: str = Field(..., description="Last activity timestamp")
    interview_stage: Optional[str] = Field(None, description="Current stage of the interview")

# Background task to clean up resources when the server is shutting down
@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources when the server is shutting down."""
    try:
        interviewer.cleanup()
        logger.info("Resources cleaned up on server shutdown")
    except Exception as e:
        logger.error(f"Error cleaning up resources: {e}")

# API endpoints
@app.post("/api/interview", response_model=MessageResponse)
async def start_interview(request: MessageRequest):
    """
    Start a new interview session.
    
    Args:
        request: MessageRequest containing the user's message and optional user ID
        
    Returns:
        MessageResponse with the AI's response and session ID
    """
    try:
        # Generate a user ID if not provided
        user_id = request.user_id or f"api-user-{uuid.uuid4()}"
        
        # Process the user message
        ai_response, session_id = await interviewer.run_interview(
            user_id, request.message
        )
        
        # Get session metadata if available
        metadata = {}
        if interviewer.session_manager:
            session = interviewer.session_manager.get_session(session_id)
            if session and "metadata" in session:
                metadata = session["metadata"]
        
        return MessageResponse(
            response=ai_response,
            session_id=session_id,
            interview_stage=metadata.get("interview_stage")
        )
    except Exception as e:
        logger.error(f"Error starting interview: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/interview/{session_id}", response_model=MessageResponse)
async def continue_interview(session_id: str, request: MessageRequest):
    """
    Continue an existing interview session.
    
    Args:
        session_id: Session ID to continue
        request: MessageRequest containing the user's message and user ID
        
    Returns:
        MessageResponse with the AI's response and session ID
    """
    try:
        # Ensure user ID is provided
        if not request.user_id:
            raise HTTPException(status_code=400, detail="User ID is required")
        
        # Process the user message
        ai_response, new_session_id = await interviewer.run_interview(
            request.user_id, request.message, session_id
        )
        
        # Get session metadata if available
        metadata = {}
        if interviewer.session_manager:
            session = interviewer.session_manager.get_session(new_session_id)
            if session and "metadata" in session:
                metadata = session["metadata"]
        
        return MessageResponse(
            response=ai_response,
            session_id=new_session_id,
            interview_stage=metadata.get("interview_stage")
        )
    except Exception as e:
        logger.error(f"Error continuing interview: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sessions/{user_id}", response_model=List[SessionResponse])
async def get_user_sessions(user_id: str, include_completed: bool = False):
    """
    Get all sessions for a user.
    
    Args:
        user_id: User ID to get sessions for
        include_completed: Whether to include completed sessions
        
    Returns:
        List of SessionResponse objects
    """
    try:
        sessions = interviewer.get_user_sessions(user_id, include_completed)
        
        # Convert sessions to response format
        response = []
        for session in sessions:
            response.append(SessionResponse(
                session_id=session["session_id"],
                user_id=session["user_id"],
                created_at=session["created_at"],
                last_active=session["last_active"],
                interview_stage=session.get("metadata", {}).get("interview_stage")
            ))
        
        return response
    except Exception as e:
        logger.error(f"Error getting user sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health_check():
    """
    Check the health of the server.
    
    Returns:
        JSON response with status "ok"
    """
    return {"status": "ok"}

# Run the server
def start_server(host: str = "0.0.0.0", port: int = 8000):
    """
    Start the FastAPI server.
    
    Args:
        host: Host to bind to
        port: Port to bind to
    """
    import uvicorn
    
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    # Run the server directly if this module is executed
    start_server() 