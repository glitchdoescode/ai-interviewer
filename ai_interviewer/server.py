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
from langgraph.types import interrupt, Command
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
interviewer = AIInterviewer()

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
    
    class Config:
        schema_extra = {
            "example": {
                "role_name": "Frontend Developer",
                "seniority_level": "Mid-level",
                "required_skills": ["JavaScript", "React", "HTML/CSS", "UI/UX"],
                "description": "We're looking for a Frontend Developer with strong React skills to join our team."
            }
        }

class MessageRequest(BaseModel):
    message: str = Field(..., description="User's message")
    user_id: Optional[str] = Field(None, description="User ID (generated if not provided)")
    job_role: Optional[str] = Field(None, description="Job role for the interview (e.g., 'Frontend Developer')")
    seniority_level: Optional[str] = Field(None, description="Seniority level (e.g., 'Junior', 'Mid-level', 'Senior')")
    required_skills: Optional[List[str]] = Field(None, description="List of required skills for the role")
    job_description: Optional[str] = Field(None, description="Detailed job description")
    
    class Config:
        schema_extra = {
            "example": {
                "message": "Hello, I'm here for the interview.",
                "user_id": "user-123",
                "job_role": "Frontend Developer",
                "seniority_level": "Mid-level",
                "required_skills": ["JavaScript", "React", "HTML/CSS"],
                "job_description": "Looking for a developer with strong React skills."
            }
        }

class MessageResponse(BaseModel):
    response: str = Field(..., description="AI interviewer's response")
    session_id: str = Field(..., description="Session ID for continuing the conversation")
    interview_stage: Optional[str] = Field(None, description="Current stage of the interview")
    job_role: Optional[str] = Field(None, description="Job role for the interview")
    
    class Config:
        schema_extra = {
            "example": {
                "response": "Hello! Welcome to your technical interview for the Frontend Developer position. Could you please introduce yourself?",
                "session_id": "sess-abc123",
                "interview_stage": "introduction",
                "job_role": "Frontend Developer"
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
    
    class Config:
        schema_extra = {
            "example": {
                "session_id": "sess-abc123",
                "user_id": "user-123",
                "created_at": "2023-07-15T14:30:00.000Z",
                "last_active": "2023-07-15T14:35:00.000Z",
                "interview_stage": "technical_questions"
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

class AudioTranscriptionResponse(BaseModel):
    transcription: str = Field(..., description="Transcribed text from audio")
    response: str = Field(..., description="AI interviewer's response")
    session_id: str = Field(..., description="Session ID for continuing the conversation")
    interview_stage: Optional[str] = Field(None, description="Current stage of the interview")
    audio_response_url: Optional[str] = Field(None, description="URL to audio response file")
    job_role: Optional[str] = Field(None, description="Job role for the interview")

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
    """Clean up resources when the server is shutting down."""
    try:
        interviewer.cleanup()
        logger.info("Resources cleaned up on server shutdown")
    except Exception as e:
        logger.error(f"Error cleaning up resources: {e}")

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
        description="We're looking for a Frontend Developer with strong React skills to build responsive and interactive web applications."
    ),
    JobRole(
        role_name="Backend Developer",
        seniority_level="Mid-level",
        required_skills=["Python", "Node.js", "Databases", "API Design", "Server Architecture"],
        description="Backend Developer responsible for server-side application logic, database management, and API development."
    ),
    JobRole(
        role_name="Full Stack Developer",
        seniority_level="Senior",
        required_skills=["JavaScript", "React", "Node.js", "Python", "Databases", "DevOps"],
        description="Senior Full Stack Developer with experience across the entire web stack from frontend to backend."
    ),
    JobRole(
        role_name="Data Scientist",
        seniority_level="Mid-level",
        required_skills=["Python", "Statistics", "Machine Learning", "Data Analysis", "SQL"],
        description="Data Scientist with strong analytical skills to develop machine learning models and extract insights from data."
    ),
    JobRole(
        role_name="DevOps Engineer",
        seniority_level="Mid-level",
        required_skills=["CI/CD", "Docker", "Kubernetes", "Cloud Platforms", "Linux", "Scripting"],
        description="DevOps Engineer to build and maintain CI/CD pipelines and cloud infrastructure."
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
            job_description=request_data.job_description
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
            job_role=metadata.get("job_role")
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
            job_description=request_data.job_description
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
            job_role=metadata.get("job_role")
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

            response.append(SessionResponse(
                session_id=session["session_id"],
                user_id=session["user_id"],
                created_at=created_at_str,
                last_active=last_active_str,
                interview_stage=session.get("metadata", {}).get("interview_stage")
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
            job_description=request_data.job_description
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
                success = await voice_handler.speak(
                    text=ai_response,
                    voice=speech_config.get("tts_voice", "nova"),
                    output_file=audio_path,
                    play_audio=False
                )
                
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
            job_role=metadata.get("job_role")
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
        await voice_handler.speak(
            text=ai_response,
            voice=speech_config.get("tts_voice", "nova"),
            output_file=audio_path,
            play_audio=False
        )
        
        # For simplicity, we're returning a URL that can be used to fetch the audio
        audio_url = f"/api/audio/response/{audio_filename}"
        
        return AudioTranscriptionResponse(
            transcription=transcription,
            response=ai_response,
            session_id=new_session_id,
            interview_stage=metadata.get("interview_stage"),
            audio_response_url=audio_url
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

class CodingHintRequest(BaseModel):
    challenge_id: str
    code: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    error_message: Optional[str] = None

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
    message: str
    user_id: str
    challenge_completed: bool = True
    
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
    
    Args:
        submission: CodingSubmissionRequest containing the code solution and challenge ID
        
    Returns:
        CodingSubmissionResponse with evaluation results
    """
    try:
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
                challenges = metadata.get("completed_challenges", [])
                challenges.append({
                    "challenge_id": submission.challenge_id,
                    "timestamp": datetime.now().isoformat(),
                    "passed": result.get("evaluation", {}).get("passed", False)
                })
                metadata["completed_challenges"] = challenges
                session["metadata"] = metadata
                interviewer.session_manager.update_session(submission.session_id, session)
        
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
        # Call the get_coding_hint tool
        from ai_interviewer.tools.coding_tools import get_coding_hint
        
        result = get_coding_hint(
            challenge_id=hint_request.challenge_id,
            current_code=hint_request.code,
            error_message=hint_request.error_message
        )
        
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
        session["metadata"] = metadata
        interviewer.session_manager.update_session(session_id, session)
        
        # Continue the interview
        ai_response, new_session_id = await interviewer.run_interview(
            request_data.user_id,
            request_data.message,
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
            job_role=metadata.get("job_role")
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
    
    class Config:
        schema_extra = {
            "example": {
                "question": "Explain the virtual DOM in React and why it's important.",
                "response": "The virtual DOM is React's way of improving performance by creating a lightweight copy of the actual DOM. When state changes, React first updates the virtual DOM and then compares it with the previous version to identify the minimal set of DOM operations needed. This approach is more efficient than directly manipulating the DOM.",
                "job_role": "Frontend Developer",
                "skill_areas": ["React", "JavaScript", "Web Performance"],
                "expected_topics": ["Virtual DOM concept", "Reconciliation", "Performance benefits"]
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
    
    This endpoint evaluates candidate responses on multiple dimensions including
    relevance, technical accuracy, and depth of knowledge.
    
    Args:
        req_data: ResponseAnalysisRequest containing question, response, and context
        
    Returns:
        Detailed analysis of the response
    """
    try:
        result = analyze_candidate_response(
            question=req_data.question,
            response=req_data.response,
            job_role=req_data.job_role,
            skill_areas=req_data.skill_areas,
            expected_topics=req_data.expected_topics
        )
        return result
    except Exception as e:
        logger.error(f"Error analyzing response: {e}")
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

if __name__ == "__main__":
    # Run the server directly if this module is executed
    start_server() 