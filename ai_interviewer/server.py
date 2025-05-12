"""
FastAPI server for the AI Interviewer platform.

This module provides a REST API for interacting with the AI Interviewer.
"""
import os
import uuid
import asyncio
import logging
import base64
from typing import Dict, Any, Optional, List
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
class MessageRequest(BaseModel):
    message: str = Field(..., description="User's message")
    user_id: Optional[str] = Field(None, description="User ID (generated if not provided)")
    
    class Config:
        schema_extra = {
            "example": {
                "message": "Hello, I'm here for the interview.",
                "user_id": "user-123"
            }
        }

class MessageResponse(BaseModel):
    response: str = Field(..., description="AI interviewer's response")
    session_id: str = Field(..., description="Session ID for continuing the conversation")
    interview_stage: Optional[str] = Field(None, description="Current stage of the interview")
    
    class Config:
        schema_extra = {
            "example": {
                "response": "Hello! Welcome to your technical interview. Could you please introduce yourself?",
                "session_id": "sess-abc123",
                "interview_stage": "introduction"
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
    audio_base64: str = Field(..., description="Base64-encoded audio data")
    sample_rate: int = Field(16000, description="Audio sample rate in Hz")
    channels: int = Field(1, description="Number of audio channels")

class AudioTranscriptionResponse(BaseModel):
    transcription: str = Field(..., description="Transcribed text from audio")
    response: str = Field(..., description="AI interviewer's response")
    session_id: str = Field(..., description="Session ID for continuing the conversation")
    interview_stage: Optional[str] = Field(None, description="Current stage of the interview")
    audio_response_url: Optional[str] = Field(None, description="URL to audio response file")

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

# API endpoints
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
        
        # Process the user message
        ai_response, session_id = await interviewer.run_interview(
            user_id, request_data.message
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
        
        # Process the user message
        ai_response, new_session_id = await interviewer.run_interview(
            request_data.user_id, request_data.message, session_id
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
        
        # Decode base64 audio
        audio_bytes = base64.b64decode(request_data.audio_base64)
        
        # Transcribe the audio
        transcription_result = await voice_handler.transcribe_audio_bytes(
            audio_bytes,
            sample_rate=request_data.sample_rate,
            channels=request_data.channels
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
            raise HTTPException(status_code=422, detail="No speech detected or empty transcription")
        
        # Process the transcribed message
        ai_response, session_id = await interviewer.run_interview(
            user_id, transcription, request_data.session_id
        )
        
        # Get session metadata if available
        metadata = {}
        if interviewer.session_manager:
            session = interviewer.session_manager.get_session(session_id)
            if session and "metadata" in session:
                metadata = session["metadata"]
        
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
            audio_response_url=audio_response_url
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
            raise HTTPException(status_code=422, detail="No speech detected or empty transcription")
        
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