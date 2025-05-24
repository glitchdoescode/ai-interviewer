"""
FastAPI server for the AI Interviewer platform.

This module provides a REST API for interacting with the AI Interviewer.
"""
import os
import uuid
import asyncio
import logging
import base64
import re
from typing import Dict, Any, Optional, List, Literal, Union
from datetime import datetime

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.status import HTTP_429_TOO_MANY_REQUESTS

from ai_interviewer.core.ai_interviewer import AIInterviewer
from ai_interviewer.utils.speech_utils import VoiceHandler
from ai_interviewer.utils.config import get_llm_config, get_db_config
from ai_interviewer.utils.transcript import extract_messages_from_transcript, safe_extract_content
from ai_interviewer.utils.memory_manager import InterviewMemoryManager
from langgraph.types import interrupt, Command
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from ai_interviewer.tools.question_tools import generate_interview_question, analyze_candidate_response

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Setup rate limiter
limiter = Limiter(key_func=get_remote_address)

# Initialize FastAPI app with enhanced metadata for OpenAPI docs
app = FastAPI(
    title="AI Interviewer API",
    description="""
    REST API for the AI Technical Interviewer platform.
    
    This API provides endpoints for conducting technical interviews with AI,
    managing interview sessions, and processing audio for voice-based interviews.
    
    ## Features
    
    * Text-based interview sessions
    * Voice-based interview with STT/TTS
    * Session management for resuming interviews
    * User session history
    * Cross-session memory persistence
    
    ## Authentication
    
    Authentication will be added in a future update.
    """,
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
)

# Add rate limiter exception handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add CORS middleware to allow cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update with specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize AI Interviewer instance
# Apply a patch to make sure the interview instance has access to the summarization model
try:
    # Initialize memory manager first
    db_config = get_db_config()
    
    # Create a proper async setup function
    async def setup_memory_manager():
        # Create the memory manager
        memory_manager = InterviewMemoryManager(
            connection_uri=db_config["uri"],
            db_name=db_config["database"],
            checkpoint_collection=db_config["sessions_collection"],
            store_collection="interview_memory_store",
            use_async=True  # Explicitly use async mode
        )
        
        # Initialize the AsyncMongoDBSaver in an async context
        await memory_manager.async_setup()
        return memory_manager
    
    # Use asyncio.run() to properly create and run the event loop
    try:
        # Check if we already have a running event loop
        try:
            loop = asyncio.get_running_loop()
            # If we're in a running event loop, create a new task
            memory_manager_task = loop.create_task(setup_memory_manager())
            memory_manager = loop.run_until_complete(memory_manager_task)
        except RuntimeError:
            # No running event loop, use asyncio.run() instead
            memory_manager = asyncio.run(setup_memory_manager())
        
        logger.info("Memory manager initialized and setup successfully")
    except Exception as e:
        logger.error(f"Error setting up memory manager: {e}")
        raise
    
    # Initialize AIInterviewer with MongoDB persistence
    interviewer = AIInterviewer(use_mongodb=True)
    
    # Make sure the summarization model is initialized
    if not hasattr(interviewer, 'summarization_model'):
        llm_config = get_llm_config()
        interviewer.summarization_model = ChatGoogleGenerativeAI(
            model=llm_config["model"],
            temperature=0.1
        )
        logger.info("Added summarization model to interviewer instance")
    
    logger.info("AI Interviewer initialized successfully with async memory management")
except Exception as e:
    logger.critical(f"Failed to initialize AI Interviewer: {e}")
    # In a production environment, you might want to exit the application
    # sys.exit(1)
    raise

# Initialize VoiceHandler for speech processing
try:
    from ai_interviewer.utils.config import get_speech_config
    speech_config = get_speech_config()
    voice_handler = VoiceHandler(api_key=speech_config.get("api_key"))
    voice_enabled = True
    logger.info("Voice processing enabled")
except Exception as e:
    logger.warning(f"Voice processing disabled: {e}")
    voice_handler = None
    voice_enabled = False

# <custom_code>
# Ensure VoiceHandler is initialized if speech_utils was updated and not re-imported
if voice_enabled and not voice_handler:
    try:
        from ai_interviewer.utils.config import get_speech_config
        speech_config = get_speech_config()
        # This assumes VoiceHandler can be re-initialized or its state is managed externally
        # If VoiceHandler has significant internal state, this might not be ideal
        from ai_interviewer.utils.speech_utils import VoiceHandler
        voice_handler = VoiceHandler(api_key=speech_config.get("api_key")) # api_key is for Deepgram fallback
        logger.info("VoiceHandler re-initialized in server.py")
    except Exception as e:
        logger.error(f"Failed to re-initialize VoiceHandler: {e}")
        voice_enabled = False
# </custom_code>

# Custom OpenAPI documentation
@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title=app.title + " - API Documentation",
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
    )

@app.get("/openapi.json", include_in_schema=False)
async def get_open_api_endpoint():
    return get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

# Pydantic models for request/response validation
class JobRole(BaseModel):
    """Model for job role configuration."""
    role_name: str = Field(..., description="Name of the job role (e.g., 'Frontend Developer')")
    seniority_level: str = Field("Mid-level", description="Seniority level (e.g., 'Junior', 'Mid-level', 'Senior')")
    required_skills: List[str] = Field(default_factory=list, description="List of required skills for the role")
    description: str = Field("", description="Detailed job description")
    requires_coding: bool = Field(True, description="Whether this role requires coding challenges during the interview")
    
    class Config:
        schema_extra = {
            "example": {
                "role_name": "Frontend Developer",
                "seniority_level": "Mid-level",
                "required_skills": ["JavaScript", "React", "HTML/CSS", "UI/UX"],
                "description": "We're looking for a Frontend Developer with strong React skills to join our team.",
                "requires_coding": True
            }
        }

class MessageRequest(BaseModel):
    message: str = Field(..., description="User's message")
    user_id: Optional[str] = Field(None, description="User ID (generated if not provided)")
    job_role: Optional[str] = Field(None, description="Job role for the interview (e.g., 'Frontend Developer')")
    seniority_level: Optional[str] = Field(None, description="Seniority level (e.g., 'Junior', 'Mid-level', 'Senior')")
    required_skills: Optional[List[str]] = Field(None, description="List of required skills for the role")
    job_description: Optional[str] = Field(None, description="Detailed job description")
    requires_coding: Optional[bool] = Field(None, description="Whether this role requires coding challenges")
    
    class Config:
        schema_extra = {
            "example": {
                "message": "Hello, I'm here for the interview.",
                "user_id": "user-123",
                "job_role": "Frontend Developer",
                "seniority_level": "Mid-level",
                "required_skills": ["JavaScript", "React", "HTML/CSS"],
                "job_description": "Looking for a developer with strong React skills.",
                "requires_coding": True
            }
        }

class MessageResponse(BaseModel):
    response: str = Field(..., description="AI interviewer's response")
    session_id: str = Field(..., description="Session ID for continuing the conversation")
    interview_stage: Optional[str] = Field(None, description="Current stage of the interview")
    job_role: Optional[str] = Field(None, description="Job role for the interview")
    requires_coding: Optional[bool] = Field(None, description="Whether this role requires coding challenges")
    
    class Config:
        schema_extra = {
            "example": {
                "response": "Hello! Welcome to your technical interview for the Frontend Developer position. Could you please introduce yourself?",
                "session_id": "sess-abc123",
                "interview_stage": "introduction",
                "job_role": "Frontend Developer",
                "requires_coding": True
            }
        }

class SessionRequest(BaseModel):
    session_id: str = Field(..., description="Session ID to resume")
    user_id: str = Field(..., description="User ID associated with the session")
    
    class Config:
        schema_extra = {
            "example": {
                "session_id": "sess-abc123",
                "user_id": "user-123"
            }
        }

class SessionResponse(BaseModel):
    session_id: str = Field(..., description="Session ID")
    user_id: str = Field(..., description="User ID")
    created_at: str = Field(..., description="Session creation timestamp")
    last_active: str = Field(..., description="Last activity timestamp")
    interview_stage: Optional[str] = Field(None, description="Current stage of the interview")
    job_role: Optional[str] = Field(None, description="Job role for the interview")
    requires_coding: Optional[bool] = Field(None, description="Whether this role requires coding challenges")
    
    class Config:
        schema_extra = {
            "example": {
                "session_id": "sess-abc123",
                "user_id": "user-123",
                "created_at": "2023-07-15T14:30:00.000Z",
                "last_active": "2023-07-15T14:35:00.000Z",
                "interview_stage": "technical_questions",
                "job_role": "Frontend Developer",
                "requires_coding": True
            }
        }

class AudioTranscriptionRequest(BaseModel):
    user_id: Optional[str] = Field(None, description="User ID (generated if not provided)")
    session_id: Optional[str] = Field(None, description="Session ID (if continuing a session)")
    audio_data: str = Field(..., description="Base64-encoded audio data with data URI format")
    sample_rate: int = Field(16000, description="Audio sample rate in Hz")
    channels: int = Field(1, description="Number of audio channels")
    job_role: Optional[str] = Field(None, description="Job role for the interview")
    seniority_level: Optional[str] = Field(None, description="Seniority level")
    required_skills: Optional[List[str]] = Field(None, description="List of required skills")
    job_description: Optional[str] = Field(None, description="Detailed job description")
    requires_coding: Optional[bool] = Field(None, description="Whether this role requires coding challenges")

class AudioTranscriptionResponse(BaseModel):
    transcription: str = Field(..., description="Transcribed text from audio")
    response: str = Field(..., description="AI interviewer's response")
    session_id: str = Field(..., description="Session ID for continuing the conversation")
    interview_stage: Optional[str] = Field(None, description="Current stage of the interview")
    audio_response_url: Optional[str] = Field(None, description="URL to audio response file")
    job_role: Optional[str] = Field(None, description="Job role for the interview")
    requires_coding: Optional[bool] = Field(None, description="Whether this role requires coding challenges")

class ErrorResponse(BaseModel):
    detail: str = Field(..., description="Error details")
    
    class Config:
        schema_extra = {
            "example": {
                "detail": "Session not found or invalid user ID"
            }
        }

# Exception handler for general exceptions
@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred. Please try again later."}
    )

# Background task to clean up resources when the server is shutting down
@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources when the server shuts down."""
    logger.info("Server shutting down, cleaning up resources")
    
    # Clean up AI Interviewer resources
    if 'interviewer' in globals():
        try:
            interviewer.cleanup()
            logger.info("AI Interviewer resources cleaned up")
        except Exception as e:
            logger.error(f"Error cleaning up AI Interviewer: {e}")
    
    # Properly close the memory manager
    if 'memory_manager' in globals():
        try:
            if hasattr(memory_manager, 'use_async') and memory_manager.use_async:
                await memory_manager.aclose()
                logger.info("Async memory manager closed during shutdown")
            else:
                memory_manager.close()
                logger.info("Sync memory manager closed during shutdown")
        except Exception as e:
            logger.error(f"Error closing memory manager: {e}")
    
    # Clean up voice handler resources
    if 'voice_handler' in globals() and voice_handler:
        try:
            if hasattr(voice_handler, 'close'):
                voice_handler.close()
                logger.info("Voice handler resources cleaned up")
        except Exception as e:
            logger.error(f"Error cleaning up voice handler: {e}")
    
    logger.info("Server shutdown complete")

# Dependency for monitoring request timing
async def log_request_time(request: Request):
    request.state.start_time = datetime.now()
    yield
    process_time = (datetime.now() - request.state.start_time).total_seconds() * 1000
    logger.info(f"Request to {request.url.path} took {process_time:.2f}ms")

# Define some default job roles
DEFAULT_JOB_ROLES = [
    JobRole(
        role_name="Frontend Developer",
        seniority_level="Mid-level",
        required_skills=["JavaScript", "React", "HTML/CSS", "UI/UX", "Responsive Design"],
        description="We're looking for a Frontend Developer with strong React skills to build responsive and interactive web applications.",
        requires_coding=True
    ),
    JobRole(
        role_name="Backend Developer",
        seniority_level="Mid-level",
        required_skills=["Python", "Node.js", "Databases", "API Design", "Server Architecture"],
        description="Backend Developer responsible for server-side application logic, database management, and API development.",
        requires_coding=True
    ),
    JobRole(
        role_name="Full Stack Developer",
        seniority_level="Senior",
        required_skills=["JavaScript", "React", "Node.js", "Python", "Databases", "DevOps"],
        description="Senior Full Stack Developer with experience across the entire web stack from frontend to backend.",
        requires_coding=True
    ),
    JobRole(
        role_name="Data Scientist",
        seniority_level="Mid-level",
        required_skills=["Python", "Statistics", "Machine Learning", "Data Analysis", "SQL"],
        description="Data Scientist with strong analytical skills to develop machine learning models and extract insights from data.",
        requires_coding=True
    ),
    JobRole(
        role_name="DevOps Engineer",
        seniority_level="Mid-level",
        required_skills=["CI/CD", "Docker", "Kubernetes", "Cloud Platforms", "Linux", "Scripting"],
        description="DevOps Engineer to build and maintain CI/CD pipelines and cloud infrastructure.",
        requires_coding=True
    ),
    JobRole(
        role_name="Product Manager",
        seniority_level="Senior",
        required_skills=["Product Strategy", "User Research", "Agile Methodologies", "Roadmapping", "Stakeholder Management"],
        description="Product Manager to lead product development, define requirements, and coordinate with engineering teams.",
        requires_coding=False
    ),
    JobRole(
        role_name="UX/UI Designer",
        seniority_level="Mid-level",
        required_skills=["User Experience Design", "Wireframing", "Prototyping", "User Research", "Visual Design"],
        description="UX/UI Designer to create engaging and intuitive user interfaces and experiences for web and mobile applications.",
        requires_coding=False
    ),
    JobRole(
        role_name="Technical Project Manager",
        seniority_level="Senior",
        required_skills=["Project Management", "Agile Methodologies", "Technical Knowledge", "Risk Management", "Communication"],
        description="Technical Project Manager to oversee software development projects, manage resources, and ensure timely delivery.",
        requires_coding=False
    )
]

# API endpoints
@app.get(
    "/api/job-roles",
    response_model=List[JobRole],
    responses={
        200: {"description": "Successfully retrieved job roles"},
        429: {"description": "Rate limit exceeded", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    },
    dependencies=[Depends(log_request_time)]
)
@limiter.limit("30/minute")
async def get_job_roles(request: Request):
    """
    Get available job roles for interviews.
    
    This endpoint returns a list of predefined job roles that can be used
    to customize the interview experience.
    
    Returns:
        List of JobRole objects
    """
    try:
        # In a real implementation, these would come from a database
        return DEFAULT_JOB_ROLES
    except Exception as e:
        logger.error(f"Error getting job roles: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post(
    "/api/interview", 
    response_model=MessageResponse,
    responses={
        200: {"description": "Successfully started interview"},
        429: {"description": "Rate limit exceeded", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    },
    dependencies=[Depends(log_request_time)]
)
@limiter.limit("10/minute")
async def start_interview(request: Request, request_data: MessageRequest):
    """
    Start a new interview session.
    
    This endpoint initiates a new AI interview session with the provided message.
    If no user_id is provided, a random one will be generated.
    
    Args:
        request_data: MessageRequest containing the user's message and optional user ID
        
    Returns:
        MessageResponse with the AI's response and session ID
    """
    try:
        # Generate a user ID if not provided
        user_id = request_data.user_id or f"api-user-{uuid.uuid4()}"
        
        # Process the user message with job role parameters
        ai_response, session_id = await interviewer.run_interview(
            user_id, 
            request_data.message,
            job_role=request_data.job_role,
            seniority_level=request_data.seniority_level,
            required_skills=request_data.required_skills,
            job_description=request_data.job_description,
            requires_coding=request_data.requires_coding
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
            interview_stage=metadata.get("interview_stage"),
            job_role=metadata.get("job_role"),
            requires_coding=metadata.get("requires_coding")
        )
    except Exception as e:
        logger.error(f"Error starting interview: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post(
    "/api/interview/{session_id}", 
    response_model=MessageResponse,
    responses={
        200: {"description": "Successfully continued interview"},
        400: {"description": "Bad request - missing user ID", "model": ErrorResponse},
        404: {"description": "Session not found", "model": ErrorResponse},
        429: {"description": "Rate limit exceeded", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    },
    dependencies=[Depends(log_request_time)]
)
@limiter.limit("15/minute")
async def continue_interview(request: Request, session_id: str, request_data: MessageRequest):
    """
    Continue an existing interview session.
    
    This endpoint continues an existing interview session using the provided session ID.
    The user_id must match the one associated with the session.
    
    Args:
        session_id: Session ID to continue
        request_data: MessageRequest containing the user's message and user ID
        
    Returns:
        MessageResponse with the AI's response and session ID
    """
    try:
        # Ensure user ID is provided
        if not request_data.user_id:
            raise HTTPException(status_code=400, detail="User ID is required")
        
        # Process the user message with job role parameters (will only apply if session is new)
        ai_response, new_session_id = await interviewer.run_interview(
            request_data.user_id, 
            request_data.message, 
            session_id,
            job_role=request_data.job_role,
            seniority_level=request_data.seniority_level,
            required_skills=request_data.required_skills,
            job_description=request_data.job_description,
            requires_coding=request_data.requires_coding
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
            interview_stage=metadata.get("interview_stage"),
            job_role=metadata.get("job_role"),
            requires_coding=metadata.get("requires_coding")
        )
    except ValueError as e:
        if "session" in str(e).lower():
            raise HTTPException(status_code=404, detail=f"Session not found: {str(e)}")
        else:
            raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error continuing interview: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get(
    "/api/sessions/{user_id}", 
    response_model=List[SessionResponse],
    responses={
        200: {"description": "Successfully retrieved sessions"},
        404: {"description": "No sessions found for user", "model": ErrorResponse},
        429: {"description": "Rate limit exceeded", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    },
    dependencies=[Depends(log_request_time)]
)
@limiter.limit("30/minute")
async def get_user_sessions(request: Request, user_id: str, include_completed: bool = False):
    """
    Get all sessions for a user.
    
    This endpoint retrieves all interview sessions associated with the provided user ID.
    
    Args:
        user_id: User ID to get sessions for
        include_completed: Whether to include completed sessions (default: false)
        
    Returns:
        List of SessionResponse objects containing session details
    """
    try:
        sessions = interviewer.get_user_sessions(user_id, include_completed)
        
        if not sessions:
            return []
        
        # Convert sessions to response format
        response = []
        for session in sessions:
            # Ensure datetime objects are converted to strings
            created_at_str = session["created_at"]
            if isinstance(created_at_str, datetime):
                created_at_str = created_at_str.isoformat()
                
            last_active_str = session["last_active"]
            if isinstance(last_active_str, datetime):
                last_active_str = last_active_str.isoformat()
                
            # Get metadata from session if available
            metadata = session.get("metadata", {})

            response.append(SessionResponse(
                session_id=session["session_id"],
                user_id=session["user_id"],
                created_at=created_at_str,
                last_active=last_active_str,
                interview_stage=metadata.get("interview_stage"),
                job_role=metadata.get("job_role"),
                requires_coding=metadata.get("requires_coding", True)  # Default to True if not specified
            ))
        
        return response
    except Exception as e:
        logger.error(f"Error getting user sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post(
    "/api/audio/transcribe", 
    response_model=AudioTranscriptionResponse,
    responses={
        200: {"description": "Successfully transcribed audio and got response"},
        422: {"description": "Failed to transcribe audio or no speech detected", "model": ErrorResponse},
        429: {"description": "Rate limit exceeded", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse},
        501: {"description": "Voice processing not available", "model": ErrorResponse}
    },
    dependencies=[Depends(log_request_time)]
)
@limiter.limit("5/minute")
async def transcribe_and_respond(request: Request, request_data: AudioTranscriptionRequest):
    """
    Transcribe audio and get AI interviewer response.
    
    This endpoint transcribes the provided audio data and sends the transcription
    to the AI interviewer for a response.
    
    Args:
        request_data: AudioTranscriptionRequest containing audio data and optional session info
        
    Returns:
        AudioTranscriptionResponse with transcription, AI response, and session ID
    """
    if not voice_enabled or not voice_handler:
        raise HTTPException(status_code=501, detail="Voice processing not available")
    
    try:
        # Generate a user ID if not provided
        user_id = request_data.user_id or f"api-user-{uuid.uuid4()}"
        
        # Enhanced logging for audio data debugging
        logger.info(f"Processing audio transcription request from user: {user_id}")
        logger.info(f"Audio data received, length: {len(request_data.audio_data)}")
        
        # Check if we have an existing session with candidate information
        session_data = {}
        candidate_name_before = None
        if request_data.session_id and interviewer.session_manager:
            existing_session = interviewer.session_manager.get_session(request_data.session_id)
            if existing_session and "metadata" in existing_session:
                session_data = existing_session["metadata"]
                candidate_name_before = session_data.get('candidate_name')
                logger.info(f"Restored session data with candidate: {candidate_name_before or 'Unknown'}")
        
        # Extract base64 data from data URI format
        # Expected format: data:audio/wav;base64,BASE64_DATA
        audio_data = request_data.audio_data
        has_data_uri = "data:audio/" in audio_data
        logger.info(f"Audio has data URI format: {has_data_uri}")
        
        if "base64," in audio_data:
            parts = audio_data.split("base64,")
            mime_type = parts[0].split("data:")[1].split(";")[0] if len(parts) > 1 and "data:" in parts[0] else "unknown"
            audio_data = parts[1]
            logger.info(f"Extracted base64 data, MIME type: {mime_type}, length: {len(audio_data)}")
        
        # Decode base64 audio
        try:
            audio_bytes = base64.b64decode(audio_data)
            logger.info(f"Decoded audio bytes, size: {len(audio_bytes)} bytes")
            
            # Validate audio data is substantial enough
            if len(audio_bytes) < 1000:
                logger.warning(f"Audio data too small: {len(audio_bytes)} bytes, likely silent or corrupt")
                raise HTTPException(status_code=422, detail="Audio data too small or empty")
            
            # Log audio format detection
            if len(audio_bytes) >= 16:
                header_hex = audio_bytes[:16].hex()
                logger.info(f"Audio header (hex): {header_hex}")
                
                # Detect common audio formats
                is_wav = header_hex.startswith("52494646")  # "RIFF"
                is_webm = header_hex.startswith("1a45dfa3")
                is_mp3 = header_hex.startswith("494433") or header_hex.startswith("fffb")
                
                logger.info(f"Audio format detection - WAV: {is_wav}, WebM: {is_webm}, MP3: {is_mp3}")
            
            # Save a sample for debugging
            debug_sample_path = "/tmp/audio_debug_sample.raw"
            with open(debug_sample_path, "wb") as f:
                f.write(audio_bytes[:min(8000, len(audio_bytes))])
            logger.info(f"Debug audio sample saved to {debug_sample_path}")
            
        except Exception as e:
            logger.error(f"Error decoding base64 audio data: {e}")
            raise HTTPException(status_code=422, detail=f"Invalid base64 audio data: {str(e)}")
        
        # Log transcription parameters
        logger.info(f"Transcribing with sample_rate={request_data.sample_rate}, channels={request_data.channels}")
        
        # Transcribe the audio with error handling
        try:
            transcription_result = await voice_handler.transcribe_audio_bytes(
                audio_bytes,
                sample_rate=request_data.sample_rate,
                channels=request_data.channels
            )
            
            # Log detailed transcription results
            logger.info(f"Transcription result type: {type(transcription_result)}")
            if isinstance(transcription_result, dict):
                logger.info(f"Transcription result dict: {transcription_result}")
            else:
                logger.info(f"Transcription result: '{transcription_result}'")
        except Exception as e:
            logger.error(f"Transcription service error: {e}")
            raise HTTPException(status_code=500, detail=f"Transcription service failed: {str(e)}")
        
        # Handle different return types from transcribe_audio_bytes
        if isinstance(transcription_result, str):
            # If it's a string, use it directly as the transcript
            transcription = transcription_result
        elif isinstance(transcription_result, dict):
            # If it's a dict, extract the transcript
            if transcription_result.get("success", False):
                transcription = transcription_result.get("transcript", "")
                # <custom_code>
                provider = transcription_result.get("provider", "unknown")
                logger.info(f"Transcription successful via {provider}.")
                # </custom_code>
            else:
                # Failed transcription
                error_msg = transcription_result.get("error", "Unknown transcription error")
                logger.error(f"Transcription failed: {error_msg}")
                raise HTTPException(status_code=422, detail=f"Failed to transcribe audio: {error_msg}")
        else:
            # Unexpected return type
            logger.error(f"Unexpected transcription result type: {type(transcription_result)}")
            raise HTTPException(status_code=500, detail="Internal transcription error")
        
        # Check if we have a valid transcription
        if not transcription or not isinstance(transcription, str) or transcription.strip() == "":
            # Use a default message instead of returning an error
            logger.info("Empty transcription detected, using default message")
            transcription = "Hello, I'd like to continue our interview."
        
        # Check transcription for name pattern before invoking the interviewer
        name_pattern = re.search(r"(?i)my name is ([A-Za-z][a-z]+)", transcription)
        if name_pattern:
            potential_name = name_pattern.group(1).strip()
            logger.info(f"Potential name detected in transcription: {potential_name}")

        # Process the transcribed message with job role parameters
        ai_response, session_id = await interviewer.run_interview(
            user_id, 
            transcription, 
            request_data.session_id,
            job_role=request_data.job_role,
            seniority_level=request_data.seniority_level,
            required_skills=request_data.required_skills,
            job_description=request_data.job_description,
            requires_coding=request_data.requires_coding
        )
        
        # Get session metadata if available
        metadata = {}
        if interviewer.session_manager:
            # Verify session exists
            session = interviewer.session_manager.get_session(session_id)
            if not session:
                logger.error(f"Session {session_id} not found after run_interview. Creating backup session.")
                # Create emergency backup session
                try:
                    interviewer.session_manager.create_session(
                        user_id, 
                        {
                            "interview_stage": "introduction",
                            "created_at": datetime.now().isoformat(),
                            "last_active": datetime.now().isoformat(),
                            "backup_created": True
                        }
                    )
                    # Try to get session again
                    session = interviewer.session_manager.get_session(session_id)
                except Exception as e:
                    logger.error(f"Error creating backup session: {e}")
            
            if session and "metadata" in session:
                metadata = session["metadata"]
                candidate_name_after = metadata.get('candidate_name')
                
                # Log candidate name for debugging
                logger.info(f"Session metadata has candidate_name: {candidate_name_after or 'No name found'}")
                
                # Check if candidate name changed
                if candidate_name_before != candidate_name_after and candidate_name_after:
                    logger.info(f"Candidate name changed from '{candidate_name_before or 'Unknown'}' to '{candidate_name_after}'")
        
        # Optional: Generate audio response
        audio_response_url = None
        try:
            if voice_handler:
                # Create a unique filename for the audio response
                audio_filename = f"{session_id}_{int(datetime.now().timestamp())}.wav"
                
                # Use a path relative to the application directory
                app_dir = os.path.dirname(os.path.abspath(__file__))
                audio_responses_dir = os.path.join(app_dir, "audio_responses")
                
                # Ensure directory exists
                os.makedirs(audio_responses_dir, exist_ok=True)
                
                audio_path = os.path.join(audio_responses_dir, audio_filename)
                
                # Generate audio
                # <custom_code>
                # Use the updated speak method which handles Gemini/Deepgram logic
                # The `voice` parameter in `speak` will be used by Deepgram if it falls back.
                # Gemini voice is configured within `synthesize_speech_gemini` or via gemini_live_config.
                success = await voice_handler.speak(
                    text=ai_response,
                    # voice parameter here is for Deepgram if used as fallback.
                    # Gemini voice is handled internally by speak -> synthesize_speech_gemini
                    voice=speech_config.get("tts_voice", "nova"),
                    output_file=audio_path,
                    play_audio=False
                )
                # </custom_code>
                
                if success:
                    logger.info(f"Generated audio response at {audio_path}")
                    audio_response_url = f"/api/audio/response/{audio_filename}"
                else:
                    logger.warning(f"Failed to generate audio response")
        except Exception as e:
            logger.warning(f"Error generating audio response: {e}")
            # Continue without audio response
        
        return AudioTranscriptionResponse(
            transcription=transcription,
            response=ai_response,
            session_id=session_id,
            interview_stage=metadata.get("interview_stage"),
            audio_response_url=audio_response_url,
            job_role=metadata.get("job_role"),
            requires_coding=metadata.get("requires_coding")
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing audio: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/audio/upload", response_model=AudioTranscriptionResponse)
async def upload_audio_file(
    file: UploadFile = File(...),
    user_id: Optional[str] = None,
    session_id: Optional[str] = None
):
    """
    Upload audio file, transcribe it, and get AI interviewer response.
    
    Args:
        file: Uploaded audio file
        user_id: User ID (generated if not provided)
        session_id: Session ID (if continuing a session)
        
    Returns:
        AudioTranscriptionResponse with transcription and AI response
    """
    if not voice_enabled or not voice_handler:
        raise HTTPException(status_code=501, detail="Voice processing not available")
    
    try:
        # Generate a user ID if not provided
        user_id = user_id or f"api-user-{uuid.uuid4()}"
        
        # Read the uploaded file
        audio_bytes = await file.read()
        
        # Transcribe the audio
        transcription_result = await voice_handler.transcribe_audio_bytes(
            audio_bytes,
            sample_rate=16000,  # Default sample rate
            channels=1          # Default channels
        )
        
        # Handle different return types from transcribe_audio_bytes
        if isinstance(transcription_result, str):
            # If it's a string, use it directly as the transcript
            transcription = transcription_result
        elif isinstance(transcription_result, dict):
            # If it's a dict, extract the transcript
            if transcription_result.get("success", False):
                transcription = transcription_result.get("transcript", "")
                # <custom_code>
                provider = transcription_result.get("provider", "unknown")
                logger.info(f"Transcription successful via {provider} (file upload).")
                # </custom_code>
            else:
                # Failed transcription
                error_msg = transcription_result.get("error", "Unknown transcription error")
                logger.error(f"Transcription failed: {error_msg}")
                raise HTTPException(status_code=422, detail=f"Failed to transcribe audio: {error_msg}")
        else:
            # Unexpected return type
            logger.error(f"Unexpected transcription result type: {type(transcription_result)}")
            raise HTTPException(status_code=500, detail="Internal transcription error")
        
        # Check if we have a valid transcription
        if not transcription or not isinstance(transcription, str) or transcription.strip() == "":
            # Use a default message instead of returning an error
            logger.info("Empty transcription detected, using default message")
            transcription = "Hello, I'd like to continue our interview."
            
        # Process the transcribed message
        ai_response, new_session_id = await interviewer.run_interview(
            user_id, transcription, session_id
        )
        
        # Get session metadata if available
        metadata = {}
        if interviewer.session_manager:
            session = interviewer.session_manager.get_session(new_session_id)
            if session and "metadata" in session:
                metadata = session["metadata"]
        
        # Generate speech response
        audio_filename = f"response_{uuid.uuid4()}.wav"
        
        # Use a path relative to the application directory
        app_dir = os.path.dirname(os.path.abspath(__file__))
        temp_audio_dir = os.path.join(app_dir, "temp_audio")
        
        # Create temp directory if it doesn't exist
        os.makedirs(temp_audio_dir, exist_ok=True)
        
        audio_path = os.path.join(temp_audio_dir, audio_filename)
        
        # Generate speech
        # <custom_code>
        # Use the updated speak method
        await voice_handler.speak(
            text=ai_response,
            voice=speech_config.get("tts_voice", "nova"), # For Deepgram fallback
            output_file=audio_path,
            play_audio=False
        )
        # </custom_code>
        
        # For simplicity, we're returning a URL that can be used to fetch the audio
        audio_url = f"/api/audio/response/{audio_filename}"
        
        return AudioTranscriptionResponse(
            transcription=transcription,
            response=ai_response,
            session_id=new_session_id,
            interview_stage=metadata.get("interview_stage"),
            audio_response_url=audio_url,
            job_role=metadata.get("job_role"),
            requires_coding=metadata.get("requires_coding")
        )
    except Exception as e:
        logger.error(f"Error processing audio file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/audio/response/{filename}")
async def get_audio_response(filename: str):
    """
    Get audio response file.
    
    Args:
        filename: Audio filename
        
    Returns:
        Audio file as streaming response
    """
    # Use a path relative to the application directory
    app_dir = os.path.dirname(os.path.abspath(__file__))
    audio_responses_dir = os.path.join(app_dir, "audio_responses")
    file_path = os.path.join(audio_responses_dir, filename)
    
    if not os.path.exists(file_path):
        # Try temp_audio directory as fallback
        temp_audio_dir = os.path.join(app_dir, "temp_audio")
        fallback_path = os.path.join(temp_audio_dir, filename)
        
        if os.path.exists(fallback_path):
            file_path = fallback_path
        else:
            logger.error(f"Audio file not found at {file_path} or {fallback_path}")
            raise HTTPException(status_code=404, detail="Audio file not found")
    
    logger.info(f"Serving audio file from {file_path}")
    def iterfile():
        with open(file_path, "rb") as f:
            yield from f
    
    return StreamingResponse(
        iterfile(),
        media_type="audio/wav"
    )

@app.get("/api/health",
    responses={
        200: {"description": "Service is healthy"},
        500: {"description": "Service is unhealthy", "model": ErrorResponse}
    }
)
async def health_check():
    """
    Health check endpoint.
    
    This endpoint checks if the service is running properly and if the
    database connection is available.
    
    Returns:
        Status of the service and its components
    """
    try:
        # Check AI Interviewer is working
        session_count = len(interviewer.list_active_sessions())
        
        # Check voice handler if enabled
        voice_status = "available" if voice_enabled and voice_handler else "unavailable"
        
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "active_sessions": session_count,
            "voice_processing": voice_status,
            "version": app.version
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Service is unhealthy: {str(e)}"
        )

# Mount the React frontend static files
frontend_build_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend/build")
if os.path.exists(frontend_build_path):
    app.mount("/", StaticFiles(directory=frontend_build_path, html=True), name="frontend")
    logger.info(f"Frontend mounted from {frontend_build_path}")
else:
    logger.warning(f"Frontend build directory not found at {frontend_build_path}. Frontend will not be served.")

    # Fallback route to handle React Router's client-side routing
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """
        Serve the React SPA for any non-API routes to handle client-side routing.
        """
        # Only intercept non-API and non-static routes
        if not full_path.startswith("api/") and not full_path.startswith("static/"):
            index_path = os.path.join(frontend_build_path, "index.html")
            if os.path.exists(index_path):
                return FileResponse(index_path)
        
        # If we get here, the path wasn't found
        raise HTTPException(status_code=404, detail="Not found")

# Define models for coding challenge requests/responses
class CodingSubmissionRequest(BaseModel):
    challenge_id: str
    code: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    timestamp: Optional[str] = Field(None, description="Timestamp of code submission (auto-generated if None)")

class CodingHintRequest(BaseModel):
    challenge_id: str
    code: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    error_message: Optional[str] = None
    timestamp: Optional[str] = Field(None, description="Timestamp of hint request (auto-generated if None)")

class CodingSubmissionResponse(BaseModel):
    status: str
    challenge_id: str
    execution_results: dict
    feedback: dict
    evaluation: dict

class CodingHintResponse(BaseModel):
    status: str
    challenge_id: str
    hints: List[str]

class ChallengeCompleteRequest(BaseModel):
    message: str = Field(..., description="Message to include with submission, should contain detailed coding evaluation results from /api/coding/submit")
    user_id: str = Field(..., description="User ID")
    challenge_completed: bool = Field(True, description="Whether the challenge was successfully completed")
    evaluation_summary: Optional[Dict] = Field(None, description="Optional evaluation summary from /api/coding/submit endpoint")
    
    class Config:
        schema_extra = {
            "example": {
                "message": "I've completed the coding challenge. My solution passed 5 out of 6 test cases. The main issue was handling edge cases with empty input arrays.",
                "user_id": "user-123",
                "challenge_completed": True,
                "evaluation_summary": {
                    "passed": True,
                    "test_results": {"passed": 5, "failed": 1, "total": 6},
                    "feedback": "Good solution that handles most cases correctly."
                }
            }
        }

# Add routes for handling coding challenges

@app.post(
    "/api/coding/submit",
    response_model=CodingSubmissionResponse,
    responses={
        200: {"description": "Successfully submitted code solution"},
        400: {"description": "Bad request - missing required fields", "model": ErrorResponse},
        429: {"description": "Rate limit exceeded", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    },
    dependencies=[Depends(log_request_time)]
)
@limiter.limit("10/minute")
async def submit_code_solution(request: Request, submission: CodingSubmissionRequest):
    """
    Submit a candidate's code solution for evaluation.
    
    This endpoint processes a submitted solution for a coding challenge and returns feedback.
    
    Frontend Implementation Guidelines:
    1. After calling this endpoint and receiving the evaluation results, store them.
    2. Present the results to the user and allow them to review/confirm.
    3. When the user is ready to continue the interview, call:
       `/api/interview/{session_id}/challenge-complete`
    4. Pass the evaluation results in both:
       - As structured data in the `evaluation_summary` field 
       - As human-readable text in the `message` field
    
    This two-step process (submit then complete) allows the frontend to:
    - Process and display detailed evaluation results to the user
    - Let the user review their submission before continuing
    - Ensure the AI interviewer has the full context when providing feedback
    
    Args:
        submission: CodingSubmissionRequest containing the code solution and challenge ID
        
    Returns:
        CodingSubmissionResponse with evaluation results
    """
    try:
        # Generate timestamp if not provided
        timestamp = submission.timestamp or datetime.now().isoformat()
        
        # Call the submit_code_for_challenge tool
        from ai_interviewer.tools.coding_tools import submit_code_for_challenge
        
        result = submit_code_for_challenge(
            challenge_id=submission.challenge_id,
            candidate_code=submission.code
        )
        
        # If session ID is provided, update session state with the completed challenge
        if submission.session_id and submission.user_id and interviewer.session_manager:
            session = interviewer.session_manager.get_session(submission.session_id)
            if session:
                metadata = session.get("metadata", {})
                
                # Update completed challenges list
                challenges = metadata.get("completed_challenges", [])
                challenges.append({
                    "challenge_id": submission.challenge_id,
                    "timestamp": timestamp,
                    "passed": result.get("evaluation", {}).get("passed", False)
                })
                metadata["completed_challenges"] = challenges
                
                # Store code snapshot for tracking code evolution
                code_snapshots = metadata.get("code_snapshots", [])
                code_snapshots.append({
                    "challenge_id": submission.challenge_id,
                    "code": submission.code,
                    "timestamp": timestamp,
                    "event_type": "submission",
                    "execution_results": {
                        "passed": result.get("evaluation", {}).get("passed", False),
                        "pass_rate": result.get("evaluation", {}).get("pass_rate", 0),
                        "execution_time": result.get("execution_results", {}).get("execution_time", 0)
                    }
                })
                metadata["code_snapshots"] = code_snapshots
                
                # Update session
                session["metadata"] = metadata
                interviewer.session_manager.update_session(submission.session_id, session)
                
                # Log the code snapshot event
                logger.info(f"Stored code snapshot for session {submission.session_id}, challenge {submission.challenge_id}")
        
        return result
    except Exception as e:
        logger.error(f"Error submitting code solution: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post(
    "/api/coding/hint",
    response_model=CodingHintResponse,
    responses={
        200: {"description": "Successfully retrieved hints"},
        400: {"description": "Bad request - missing required fields", "model": ErrorResponse},
        429: {"description": "Rate limit exceeded", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    },
    dependencies=[Depends(log_request_time)]
)
@limiter.limit("15/minute")
async def get_coding_hint(request: Request, hint_request: CodingHintRequest):
    """
    Get a hint for a coding challenge based on current code.
    
    This endpoint processes the current code and returns targeted hints to help the candidate.
    
    Args:
        hint_request: CodingHintRequest containing the current code and challenge ID
        
    Returns:
        CodingHintResponse with hints
    """
    try:
        # Generate timestamp if not provided
        timestamp = hint_request.timestamp or datetime.now().isoformat()
        
        # Call the get_coding_hint tool
        from ai_interviewer.tools.coding_tools import get_coding_hint
        
        result = get_coding_hint(
            challenge_id=hint_request.challenge_id,
            current_code=hint_request.code,
            error_message=hint_request.error_message
        )
        
        # If session ID is provided, store code snapshot for tracking hint requests
        if hint_request.session_id and hint_request.user_id and interviewer.session_manager:
            session = interviewer.session_manager.get_session(hint_request.session_id)
            if session:
                metadata = session.get("metadata", {})
                
                # Store code snapshot for hint request
                code_snapshots = metadata.get("code_snapshots", [])
                code_snapshots.append({
                    "challenge_id": hint_request.challenge_id,
                    "code": hint_request.code,
                    "timestamp": timestamp,
                    "event_type": "hint_request",
                    "error_message": hint_request.error_message,
                    "hints_provided": result.get("hints", [])
                })
                metadata["code_snapshots"] = code_snapshots
                
                # Update session
                session["metadata"] = metadata
                interviewer.session_manager.update_session(hint_request.session_id, session)
                
                # Log the hint request event
                logger.info(f"Stored hint request snapshot for session {hint_request.session_id}, challenge {hint_request.challenge_id}")
        
        return result
    except Exception as e:
        logger.error(f"Error getting coding hint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post(
    "/api/interview/{session_id}/challenge-complete",
    response_model=MessageResponse,
    responses={
        200: {"description": "Successfully continued after challenge"},
        400: {"description": "Bad request - missing user ID", "model": ErrorResponse},
        404: {"description": "Session not found", "model": ErrorResponse},
        429: {"description": "Rate limit exceeded", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    },
    dependencies=[Depends(log_request_time)]
)
@limiter.limit("15/minute")
async def continue_after_challenge(request: Request, session_id: str, request_data: ChallengeCompleteRequest):
    """
    Continue an interview after completing a coding challenge.
    
    This endpoint continues the interview after a coding challenge has been submitted.
    
    For optimal AI feedback, the frontend should:
    1. First submit the code to /api/coding/submit to get detailed evaluation
    2. Include those evaluation results in both:
       - The 'message' field (as human-readable text)
       - The 'evaluation_summary' field (as structured data from the /api/coding/submit response)
    
    This ensures the AI interviewer has complete context about the code submission
    to provide specific and relevant feedback during the subsequent conversation.
    
    Args:
        session_id: Session ID to continue
        request_data: ChallengeCompleteRequest containing user message and completion status
        
    Returns:
        MessageResponse with the AI's response and session ID
    """
    try:
        if not request_data.user_id:
            raise HTTPException(status_code=400, detail="User ID is required")
        
        # Get the session
        if not interviewer.session_manager:
            raise HTTPException(status_code=500, detail="Session manager not available")
            
        session = interviewer.session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
            
        # Update metadata to indicate we're resuming from a challenge
        metadata = session.get("metadata", {})
        metadata["resuming_from_challenge"] = True
        metadata["challenge_completed"] = request_data.challenge_completed
        
        # Store evaluation summary if provided
        if request_data.evaluation_summary:
            metadata["coding_evaluation"] = request_data.evaluation_summary
            logger.info(f"Stored coding evaluation in session metadata: {request_data.evaluation_summary}")
        
        session["metadata"] = metadata
        interviewer.session_manager.update_session(session_id, session)
        
        # Prepare a more detailed message if evaluation summary is provided
        message = request_data.message
        if request_data.evaluation_summary and not "passed" in message.lower():
            # Ensure evaluation details are included in the message
            test_results = request_data.evaluation_summary.get("test_results", {})
            passed = test_results.get("passed", 0)
            total = test_results.get("total", 0)
            
            # Only append if not already mentioned in the message
            if not any(keyword in message.lower() for keyword in [f"{passed} test", f"{passed}/{total}", f"{passed} out of {total}"]):
                message += f" The solution passed {passed} out of {total} test cases."
            
            # Add feedback if available and not already in message
            feedback = request_data.evaluation_summary.get("feedback", "")
            if feedback and feedback not in message:
                message += f" Feedback: {feedback}"
        
        # Continue the interview with enhanced context
        ai_response, new_session_id = await interviewer.run_interview(
            request_data.user_id,
            message,
            session_id
        )
        
        # Get updated session metadata
        metadata = {}
        if interviewer.session_manager:
            session = interviewer.session_manager.get_session(new_session_id)
            if session and "metadata" in session:
                metadata = session["metadata"]
        
        return MessageResponse(
            response=ai_response,
            session_id=new_session_id,
            interview_stage=metadata.get("interview_stage"),
            job_role=metadata.get("job_role"),
            requires_coding=metadata.get("requires_coding")
        )
    except ValueError as e:
        if "session" in str(e).lower():
            raise HTTPException(status_code=404, detail=f"Session not found: {str(e)}")
        else:
            raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error continuing after challenge: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Add these models after the existing Pydantic models
class QuestionGenerationRequest(BaseModel):
    job_role: str = Field(..., description="Job role for the interview (e.g., 'Frontend Developer')")
    skill_areas: Optional[List[str]] = Field(None, description="List of specific skills to focus on")
    difficulty_level: str = Field("intermediate", description="Level of difficulty (beginner, intermediate, advanced)")
    previous_questions: Optional[List[str]] = Field(None, description="List of questions already asked")
    previous_responses: Optional[List[str]] = Field(None, description="List of candidate's previous responses")
    current_topic: Optional[str] = Field(None, description="Current discussion topic, if any")
    follow_up_to: Optional[str] = Field(None, description="Specific question or response to follow up on")
    
    class Config:
        schema_extra = {
            "example": {
                "job_role": "Frontend Developer",
                "skill_areas": ["JavaScript", "React", "CSS"],
                "difficulty_level": "intermediate",
                "current_topic": "Component architecture"
            }
        }

class ResponseAnalysisRequest(BaseModel):
    question: str = Field(..., description="The question that was asked")
    response: str = Field(..., description="The candidate's response to analyze")
    job_role: str = Field(..., description="Job role for context")
    skill_areas: Optional[List[str]] = Field(None, description="Skills that were being evaluated")
    expected_topics: Optional[List[str]] = Field(None, description="Expected topics in a good answer")
    experience_level: str = Field("intermediate", description="Experience level of the candidate (beginner, intermediate, advanced)")
    
    class Config:
        schema_extra = {
            "example": {
                "question": "Explain the virtual DOM in React and why it's important.",
                "response": "The virtual DOM is React's way of improving performance by creating a lightweight copy of the actual DOM. When state changes, React first updates the virtual DOM and then compares it with the previous version to identify the minimal set of DOM operations needed. This approach is more efficient than directly manipulating the DOM.",
                "job_role": "Frontend Developer",
                "skill_areas": ["React", "JavaScript", "Web Performance"],
                "expected_topics": ["Virtual DOM concept", "Reconciliation", "Performance benefits"],
                "experience_level": "intermediate"
            }
        }

# Add these API endpoints before the app.on_event("shutdown") handler
@app.post(
    "/api/questions/generate",
    responses={
        200: {"description": "Successfully generated question"},
        429: {"description": "Rate limit exceeded", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    },
    dependencies=[Depends(log_request_time)]
)
@limiter.limit("20/minute")
async def generate_question(request: Request, req_data: QuestionGenerationRequest):
    """
    Generate a dynamic interview question based on job role and other parameters.
    
    This endpoint generates contextually-relevant interview questions that can be
    tailored to specific skill areas, difficulty levels, and previous responses.
    
    Args:
        req_data: QuestionGenerationRequest containing job role and other parameters
        
    Returns:
        Generated question with metadata
    """
    try:
        result = generate_interview_question(
            job_role=req_data.job_role,
            skill_areas=req_data.skill_areas,
            difficulty_level=req_data.difficulty_level,
            previous_questions=req_data.previous_questions,
            previous_responses=req_data.previous_responses,
            current_topic=req_data.current_topic,
            follow_up_to=req_data.follow_up_to
        )
        return result
    except Exception as e:
        logger.error(f"Error generating question: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post(
    "/api/questions/analyze-response",
    responses={
        200: {"description": "Successfully analyzed response"},
        429: {"description": "Rate limit exceeded", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    },
    dependencies=[Depends(log_request_time)]
)
@limiter.limit("15/minute")
async def analyze_response(request: Request, req_data: ResponseAnalysisRequest):
    """
    Analyze a candidate's response to identify strengths, weaknesses, and potential follow-up areas.
    
    This endpoint performs a deep analysis of candidate responses including:
    - Key concept extraction
    - Depth of understanding assessment
    - Conceptual connections
    - Evidence of practical experience
    - Problem-solving approach
    - Technical accuracy evaluation
    
    Args:
        req_data: ResponseAnalysisRequest containing question, response, and context
        
    Returns:
        Comprehensive analysis of the response with depth of understanding metrics
    """
    try:
        result = analyze_candidate_response(
            question=req_data.question,
            response=req_data.response,
            job_role=req_data.job_role,
            skill_areas=req_data.skill_areas,
            expected_topics=req_data.expected_topics,
            experience_level=req_data.experience_level
        )
        return result
    except Exception as e:
        logger.error(f"Error analyzing response: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Add a Pydantic model for code snapshot responses
class CodeSnapshotResponse(BaseModel):
    challenge_id: str
    code: str
    timestamp: str
    event_type: str
    execution_results: Optional[Dict] = None
    error_message: Optional[str] = None
    hints_provided: Optional[List[str]] = None

@app.get(
    "/api/coding/snapshots/{session_id}",
    response_model=List[CodeSnapshotResponse],
    responses={
        200: {"description": "Successfully retrieved code snapshots"},
        404: {"description": "Session not found", "model": ErrorResponse},
        429: {"description": "Rate limit exceeded", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    },
    dependencies=[Depends(log_request_time)]
)
@limiter.limit("30/minute")
async def get_code_snapshots(
    request: Request, 
    session_id: str, 
    challenge_id: Optional[str] = None,
    user_id: Optional[str] = None
):
    """
    Get code evolution snapshots for a session.
    
    This endpoint retrieves the history of code submissions and hint requests
    for a session, showing how the candidate's code evolved over time.
    
    Args:
        session_id: Session ID to get snapshots for
        challenge_id: Optional challenge ID to filter by
        user_id: Optional user ID for verification
        
    Returns:
        List of code snapshots with metadata, sorted by timestamp
    """
    try:
        # Verify session exists
        if not interviewer.session_manager:
            raise HTTPException(status_code=500, detail="Session manager not available")
            
        session = interviewer.session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
            
        # If user_id is provided, verify it matches the session
        if user_id and session.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="User ID does not match session")
            
        # Get code snapshots from AIInterviewer
        snapshots = interviewer.get_code_snapshots(session_id, challenge_id)
        
        # Return snapshots
        return snapshots
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error retrieving code snapshots: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Context management related models
class ContextSettingsRequest(BaseModel):
    session_id: str = Field(..., description="Session ID to update settings for")
    max_messages: int = Field(20, description="Maximum number of messages to keep before summarization",
                             ge=10, le=100)
    
    class Config:
        schema_extra = {
            "example": {
                "session_id": "sess-abc123",
                "max_messages": 25
            }
        }

class ContextSettingsResponse(BaseModel):
    success: bool = Field(..., description="Whether the update was successful")
    session_id: str = Field(..., description="Session ID")
    max_messages: int = Field(..., description="Maximum messages setting")
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "session_id": "sess-abc123",
                "max_messages": 25
            }
        }

class SummaryResponse(BaseModel):
    session_id: str = Field(..., description="Session ID")
    summary: str = Field(..., description="Current conversation summary")
    has_summary: bool = Field(..., description="Whether a summary exists")
    
    class Config:
        schema_extra = {
            "example": {
                "session_id": "sess-abc123",
                "summary": "The candidate introduced themselves as a frontend developer with 5 years of experience...",
                "has_summary": True
            }
        }

@app.put(
    "/api/interview/context-settings",
    response_model=ContextSettingsResponse,
    responses={
        200: {"description": "Successfully updated context settings"},
        404: {"description": "Session not found", "model": ErrorResponse},
        422: {"description": "Invalid parameters", "model": ErrorResponse},
        429: {"description": "Rate limit exceeded", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    },
    dependencies=[Depends(log_request_time)]
)
@limiter.limit("30/minute")
async def update_context_settings(request: Request, settings: ContextSettingsRequest):
    """
    Update context management settings for an interview session.
    
    This endpoint allows configuring how the system manages long-running conversations,
    such as the threshold for when to summarize older content.
    """
    try:
        # Verify the session exists
        session = interviewer.session_manager.get_session(settings.session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session {settings.session_id} not found")
        
        # Configure context management settings
        success = interviewer.session_manager.configure_context_management(
            settings.session_id, 
            max_messages=settings.max_messages
        )
        
        if success:
            return {
                "success": True,
                "session_id": settings.session_id,
                "max_messages": settings.max_messages
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to update context settings")
    except HTTPException:
        # Re-raise existing HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error updating context settings: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get(
    "/api/interview/{session_id}/summary",
    response_model=SummaryResponse,
    responses={
        200: {"description": "Successfully retrieved summary"},
        404: {"description": "Session not found", "model": ErrorResponse},
        429: {"description": "Rate limit exceeded", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    },
    dependencies=[Depends(log_request_time)]
)
@limiter.limit("30/minute")
async def get_conversation_summary(request: Request, session_id: str):
    """
    Get the current conversation summary for an interview session.
    
    This endpoint retrieves the AI-generated summary of earlier parts of the conversation
    that have been condensed to manage context length.
    """
    try:
        # Verify the session exists
        session = interviewer.session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        
        # Get the current summary
        summary = interviewer.session_manager.get_conversation_summary(session_id)
        
        return {
            "session_id": session_id,
            "summary": summary or "",
            "has_summary": bool(summary)
        }
    except HTTPException:
        # Re-raise existing HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error retrieving conversation summary: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

class ForceSummarizeRequest(BaseModel):
    session_id: str = Field(..., description="Session ID")
    user_id: str = Field(..., description="User ID associated with the session")
    
    class Config:
        schema_extra = {
            "example": {
                "session_id": "sess-abc123",
                "user_id": "user-123"
            }
        }

class ForceSummarizeResponse(BaseModel):
    success: bool = Field(..., description="Whether the summarization was successful")
    session_id: str = Field(..., description="Session ID")
    summary: str = Field(..., description="Generated summary")
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "session_id": "sess-abc123",
                "summary": "The candidate introduced themselves as a frontend developer with 5 years of experience..."
            }
        }

@app.post(
    "/api/interview/force-summarize",
    response_model=ForceSummarizeResponse,
    responses={
        200: {"description": "Successfully summarized conversation"},
        400: {"description": "Bad request - missing parameters", "model": ErrorResponse},
        403: {"description": "Authentication/authorization error", "model": ErrorResponse},
        404: {"description": "Session not found", "model": ErrorResponse},
        429: {"description": "Rate limit exceeded", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    },
    dependencies=[Depends(log_request_time)]
)
@limiter.limit("10/minute")
async def force_summarize_conversation(request: Request, req_data: ForceSummarizeRequest):
    """
    Force the system to summarize the current conversation.
    
    This endpoint manually triggers the context management system to generate a summary
    of the conversation so far, reducing the message history while preserving key information.
    """
    try:
        # Verify the session exists and belongs to the user
        session = interviewer.session_manager.get_session(req_data.session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session {req_data.session_id} not found")
        
        if session.get("user_id") != req_data.user_id:
            raise HTTPException(status_code=403, detail="User ID does not match session owner")
        
        # Get all messages
        messages = session.get("messages", [])
        
        # Extract messages as message objects
        message_objects = extract_messages_from_transcript(messages)
        
        if len(message_objects) < 5:
            raise HTTPException(status_code=400, detail="Not enough messages to summarize")
        
        # Use the LLM to generate a summary
        # Keep the last 5 messages for continuity
        messages_to_keep = 5
        messages_to_summarize = message_objects[:-messages_to_keep] if len(message_objects) > messages_to_keep else message_objects
        
        # Create the prompt
        current_summary = interviewer.session_manager.get_conversation_summary(req_data.session_id) or ""
        
        if current_summary:
            summary_prompt = [
                SystemMessage(content=f"You are a helpful assistant that summarizes conversations while retaining all key information. Below is an existing summary and new conversation parts to integrate. Create a comprehensive summary that includes all important details about the candidate, their skills, experiences, and responses to interview questions."),
                HumanMessage(content=f"EXISTING SUMMARY:\n{current_summary}\n\nNEW CONVERSATION TO INTEGRATE:\n" + "\n".join([f"{m.type}: {m.content}" for m in messages_to_summarize if hasattr(m, 'content')]))
            ]
        else:
            summary_prompt = [
                SystemMessage(content=f"You are a helpful assistant that summarizes conversations while retaining all key information. Create a comprehensive summary of this interview conversation that includes all important details about the candidate, their skills, experiences, and responses to interview questions."),
                HumanMessage(content="\n".join([f"{m.type}: {m.content}" for m in messages_to_summarize if hasattr(m, 'content')]))
            ]
        
        # Generate summary
        summary_response = interviewer.summarization_model.invoke(summary_prompt)
        new_summary = summary_response.content if hasattr(summary_response, 'content') else ""
        
        # Update the session with the new summary and reduced message list
        interviewer.session_manager.update_conversation_summary(req_data.session_id, new_summary)
        
        # Create a list of messages to keep - the most recent ones
        kept_messages = message_objects[-messages_to_keep:] if len(message_objects) > messages_to_keep else []
        interviewer.session_manager.reduce_message_history(req_data.session_id, kept_messages)
        
        # Update message count in metadata
        metadata = session.get("metadata", {})
        metadata["message_count"] = len(kept_messages)
        interviewer.session_manager.update_session_metadata(req_data.session_id, metadata)
        
        return {
            "success": True,
            "session_id": req_data.session_id,
            "summary": new_summary
        }
    except HTTPException:
        # Re-raise existing HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error forcing summarization: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

class InterviewInsightsResponse(BaseModel):
    session_id: str = Field(..., description="Session ID")
    candidate_details: Dict[str, Any] = Field(..., description="Basic candidate details")
    key_skills: List[str] = Field(default_factory=list, description="Candidate's key skills")
    notable_experiences: List[str] = Field(default_factory=list, description="Notable experiences mentioned")
    strengths: List[str] = Field(default_factory=list, description="Areas of strength")
    areas_for_improvement: List[str] = Field(default_factory=list, description="Areas for improvement")
    coding_ability: Dict[str, Any] = Field(default_factory=dict, description="Coding ability assessment")
    communication_ability: str = Field("", description="Communication ability assessment")
    
    class Config:
        schema_extra = {
            "example": {
                "session_id": "sess-abc123",
                "candidate_details": {
                    "name": "Jane Smith",
                    "years_of_experience": "5",
                    "current_role": "Senior Frontend Developer"
                },
                "key_skills": ["JavaScript", "React", "TypeScript"],
                "notable_experiences": ["Built a real-time dashboard application", "Led a team of 5 developers"],
                "strengths": ["Problem solving", "Technical communication"],
                "areas_for_improvement": ["Backend knowledge could be expanded"],
                "coding_ability": {
                    "assessed": True,
                    "languages": ["JavaScript", "Python"],
                    "level": "Strong in frontend technologies"
                },
                "communication_ability": "Clear and concise technical communication"
            }
        }

@app.get(
    "/api/interview/{session_id}/insights",
    response_model=InterviewInsightsResponse,
    responses={
        200: {"description": "Successfully retrieved interview insights"},
        404: {"description": "Session not found", "model": ErrorResponse},
        429: {"description": "Rate limit exceeded", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    },
    dependencies=[Depends(log_request_time)]
)
@limiter.limit("30/minute")
async def get_interview_insights(request: Request, session_id: str, user_id: Optional[str] = None):
    """
    Get structured insights extracted from the interview for a given session.
    
    This endpoint retrieves AI-extracted structured information about the candidate,
    including skills, experiences, and areas of strength/improvement.
    
    Args:
        session_id: Session ID to get insights for
        user_id: Optional user ID for verification
        
    Returns:
        Structured interview insights extracted from the conversation
    """
    try:
        # Verify session exists
        if not interviewer.session_manager:
            raise HTTPException(status_code=500, detail="Session manager not available")
            
        session = interviewer.session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
            
        # If user_id is provided, verify it matches the session
        if user_id and session.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="User ID does not match session")
            
        # Get interview insights from session metadata
        metadata = session.get("metadata", {})
        insights = metadata.get("interview_insights", {})
        
        if not insights:
            # If no insights exist yet, provide default structure
            insights = {
                "candidate_details": {},
                "key_skills": [],
                "notable_experiences": [],
                "strengths": [],
                "areas_for_improvement": [],
                "coding_ability": {
                    "assessed": False,
                    "languages": [],
                    "level": ""
                },
                "communication_ability": ""
            }
        
        # Ensure insights has the required fields for the response model
        for field in ["candidate_details", "key_skills", "notable_experiences", 
                     "strengths", "areas_for_improvement", "coding_ability"]:
            if field not in insights:
                insights[field] = {} if field == "candidate_details" or field == "coding_ability" else []
        
        if "communication_ability" not in insights:
            insights["communication_ability"] = ""
        
        # Add session_id to response
        insights["session_id"] = session_id
        
        # Return formatted insights
        return insights
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error retrieving interview insights: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class ExtractInsightsRequest(BaseModel):
    session_id: str = Field(..., description="Session ID to extract insights for")
    user_id: str = Field(..., description="User ID associated with the session")
    
    class Config:
        schema_extra = {
            "example": {
                "session_id": "sess-abc123",
                "user_id": "user-123"
            }
        }

@app.post(
    "/api/interview/extract-insights",
    response_model=InterviewInsightsResponse,
    responses={
        200: {"description": "Successfully extracted and updated insights"},
        400: {"description": "Bad request - missing parameters", "model": ErrorResponse},
        403: {"description": "Authentication/authorization error", "model": ErrorResponse},
        404: {"description": "Session not found", "model": ErrorResponse},
        429: {"description": "Rate limit exceeded", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    },
    dependencies=[Depends(log_request_time)]
)
@limiter.limit("10/minute")
async def extract_interview_insights(request: Request, req_data: ExtractInsightsRequest):
    """
    Manually trigger the extraction of insights from an interview session.
    
    This endpoint forces the system to analyze the conversation and extract
    structured information about the candidate's skills, experiences, and abilities.
    
    Args:
        req_data: ExtractInsightsRequest containing session ID and user ID
        
    Returns:
        Structured interview insights extracted from the conversation
    """
    try:
        # Verify the session exists and belongs to the user
        session = interviewer.session_manager.get_session(req_data.session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session {req_data.session_id} not found")
        
        if session.get("user_id") != req_data.user_id:
            raise HTTPException(status_code=403, detail="User ID does not match session owner")
        
        # Trigger insights extraction
        insights = await interviewer.extract_and_update_insights(req_data.session_id)
        
        if not insights:
            raise HTTPException(status_code=500, detail="Failed to extract insights")
        
        # Ensure insights has the required fields for the response model
        for field in ["candidate_details", "key_skills", "notable_experiences", 
                     "strengths", "areas_for_improvement", "coding_ability"]:
            if field not in insights:
                insights[field] = {} if field == "candidate_details" or field == "coding_ability" else []
        
        if "communication_ability" not in insights:
            insights["communication_ability"] = ""
        
        # Add session_id to response
        insights["session_id"] = req_data.session_id
        
        return insights
    except HTTPException:
        # Re-raise existing HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error extracting insights: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def start_server(host: str = "0.0.0.0", port: int = 8000):
    """
    Start the FastAPI server.
    
    Args:
        host: Host to bind the server to
        port: Port to bind the server to
    """
    import uvicorn
    
    # Create audio responses directory if it doesn't exist (use app directory)
    app_dir = os.path.dirname(os.path.abspath(__file__))
    audio_responses_dir = os.path.join(app_dir, "audio_responses")
    temp_audio_dir = os.path.join(app_dir, "temp_audio")
    
    # Create necessary directories
    os.makedirs(audio_responses_dir, exist_ok=True)
    os.makedirs(temp_audio_dir, exist_ok=True)
    
    # Configure Uvicorn logging
    log_config = uvicorn.config.LOGGING_CONFIG
    log_config["formatters"]["access"]["fmt"] = "%(asctime)s - %(levelname)s - %(message)s"
    log_config["formatters"]["default"]["fmt"] = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    
    # Start the server
    uvicorn.run(
        app, 
        host=host, 
        port=port,
        log_config=log_config
    )

# Memory-related endpoints
class EnhancedMemoryQuery(BaseModel):
    user_id: str = Field(..., description="User ID to search memories for")
    query: str = Field(..., description="Search query for memories")
    max_results: int = Field(5, description="Maximum number of results to return")
    
    class Config:
        schema_extra = {
            "example": {
                "user_id": "user-123",
                "query": "python",
                "max_results": 5
            }
        }

class EnhancedMemoryResponse(BaseModel):
    memories: List[Dict[str, Any]] = Field(..., description="List of memory items found")
    query: str = Field(..., description="Original search query")
    user_id: str = Field(..., description="User ID searched for")
    
    class Config:
        schema_extra = {
            "example": {
                "memories": [
                    {
                        "type": "candidate_profile",
                        "key": "profile-123",
                        "value": {
                            "key_skills": ["Python", "JavaScript"],
                            "notable_experiences": ["Built a distributed system at Company X"]
                        }
                    }
                ],
                "query": "python",
                "user_id": "user-123"
            }
        }

@app.post(
    "/api/memory/search",
    response_model=EnhancedMemoryResponse,
    responses={
        200: {"description": "Successfully searched memories"},
        400: {"description": "Bad request - missing parameters", "model": ErrorResponse},
        429: {"description": "Rate limit exceeded", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    },
    dependencies=[Depends(log_request_time)]
)
@limiter.limit("30/minute")
async def search_memories(request: Request, query_data: EnhancedMemoryQuery):
    """
    Search through cross-session memories for a specific user.
    """
    try:
        if not hasattr(interviewer, 'memory_manager') or not interviewer.memory_manager:
            raise HTTPException(
                status_code=500,
                detail="Memory management is not available on this server instance"
            )
        
        memories = interviewer.memory_manager.search_memories(
            query=query_data.query,
            user_id=query_data.user_id,
            max_results=query_data.max_results
        )
        
        return {
            "memories": memories,
            "query": query_data.query,
            "user_id": query_data.user_id
        }
    except Exception as e:
        logger.error(f"Error searching memories: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to search memories: {str(e)}"
        )

class CandidateProfileResponse(BaseModel):
    user_id: str = Field(..., description="User ID")
    profile: Optional[Dict[str, Any]] = Field(None, description="Candidate profile data if found")
    has_profile: bool = Field(..., description="Whether a profile was found")
    
    class Config:
        schema_extra = {
            "example": {
                "user_id": "user-123",
                "profile": {
                    "key_skills": ["Python", "JavaScript", "AWS"],
                    "notable_experiences": ["Built a distributed system at Company X"],
                    "strengths": ["Problem solving", "System design"],
                    "areas_for_improvement": ["Frontend design"]
                },
                "has_profile": True
            }
        }

@app.get(
    "/api/memory/profile/{user_id}",
    response_model=CandidateProfileResponse,
    responses={
        200: {"description": "Successfully retrieved candidate profile"},
        404: {"description": "Profile not found", "model": ErrorResponse},
        429: {"description": "Rate limit exceeded", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    },
    dependencies=[Depends(log_request_time)]
)
@limiter.limit("30/minute")
async def get_candidate_profile(request: Request, user_id: str):
    """
    Get a candidate's profile data from cross-session memory.
    """
    try:
        if not hasattr(interviewer, 'memory_manager') or not interviewer.memory_manager:
            raise HTTPException(
                status_code=500, 
                detail="Memory management is not available on this server instance"
            )
        
        profile = interviewer.memory_manager.get_candidate_profile(user_id)
        
        return {
            "user_id": user_id,
            "profile": profile,
            "has_profile": profile is not None
        }
    except Exception as e:
        logger.error(f"Error retrieving candidate profile: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve candidate profile: {str(e)}"
        )

if __name__ == "__main__":
    # Run the server directly if this module is executed
    start_server() 