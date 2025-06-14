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
import wave # Add this import
import json # Add this import
import sys  # Add regex module
from typing import Dict, Any, Optional, List, Literal, Union, Tuple
from datetime import datetime
import inspect # <--- Import inspect
import contextlib # Add for lifespan manager
from pathlib import Path
import time
import threading
import tempfile
import logging.config
import platform
import traceback
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # Add this import
from ai_interviewer.websocket.manager import WebSocketManager  # Add this import

from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends, UploadFile, File, Request, Response, status
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
from starlette.middleware.sessions import SessionMiddleware # <--- ADD IMPORT
from slowapi.middleware import SlowAPIMiddleware
from concurrent.futures import ThreadPoolExecutor

from ai_interviewer.core.ai_interviewer import AIInterviewer, InterviewStage # MODIFIED
from ai_interviewer.utils.speech_utils import VoiceHandler
from ai_interviewer.utils.config import get_llm_config, get_db_config, get_speech_config
from ai_interviewer.utils.transcript import extract_messages_from_transcript, safe_extract_content
from ai_interviewer.utils.memory_manager import InterviewMemoryManager
from langgraph.types import interrupt, Command
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage, ToolMessage # ADDED ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from ai_interviewer.tools.question_tools import generate_interview_question, analyze_candidate_response
from ai_interviewer.tools.problem_generation_tool import generate_coding_challenge_from_jd, submit_code_for_generated_challenge # MODIFIED
from ai_interviewer.tools.docker_sandbox import DockerSandbox # ADDED
from ai_interviewer.utils.constants import INTERVIEW_STAGE_KEY # REMOVED InterviewStage from here
from ai_interviewer.utils.feedback_memory import create_feedback_memory_manager
from ai_interviewer.tools.rubric_evaluation import evaluate_coding_submission_with_rubric

# Auth imports
from motor.motor_asyncio import AsyncIOMotorDatabase
from ai_interviewer.auth import routes as auth_routes
from ai_interviewer.auth.config import settings as auth_settings
from ai_interviewer.auth.security import get_current_active_user # <--- IMPORT
from ai_interviewer.models.user_models import User # <--- IMPORT
from ai_interviewer.auth.security import RoleChecker
from ai_interviewer.models.user_models import UserRole
from starlette import status

# Proctoring imports
from ai_interviewer.routers import proctoring

# Gemini Live API imports
from ai_interviewer.routers import gemini_live

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)
logger.info(f"AIInterviewer class loaded from: {inspect.getfile(AIInterviewer)}") # <--- Add this log
# Setup rate limiter
limiter = Limiter(key_func=get_remote_address)

# Global variable for the memory manager, initialized to None
memory_manager: Optional[InterviewMemoryManager] = None 
interviewer: Optional[AIInterviewer] = None # Also make interviewer global and initialized in lifespan

# Add import for streaming function
from ai_interviewer.utils.gemini_live_utils import generate_response_stream

# Simple request deduplication to prevent duplicate requests
_active_requests = set()
_request_lock = threading.Lock()
_recent_sessions = {}  # Track recent sessions by user+job to prevent duplicates
REQUEST_COOLDOWN = 10.0  # 10 second cooldown to prevent rapid session creation
SESSION_REUSE_WINDOW = 60.0  # 60 seconds to reuse existing sessions

def cleanup_old_sessions():
    """Clean up old session tracking entries to prevent memory leaks."""
    current_time = time.time()
    with _request_lock:
        expired_keys = [
            key for key, session_info in _recent_sessions.items()
            if current_time - session_info['created'] > SESSION_REUSE_WINDOW
        ]
        for key in expired_keys:
            del _recent_sessions[key]
        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired session tracking entries")

@contextlib.asynccontextmanager
async def lifespan(app_instance: FastAPI):
    """
    Lifespan context manager for FastAPI app.
    
    This handles startup and shutdown events for the application.
    """
    # Initialize the memory manager
    memory_manager = await setup_memory_manager_async()
    
    # Store the memory manager in app state
    app_instance.state.memory_manager = memory_manager
    
    # Initialize the AI Interviewer with the memory manager
    ai_interviewer = await setup_ai_interviewer_async(memory_manager)
    
    # Store the AI Interviewer instance in app state
    app_instance.state.interviewer = ai_interviewer  # Changed from ai_interviewer to interviewer
    
    # Initialize the voice handler
    app_instance.state.voice_handler = VoiceHandler()
    
    # Initialize the scheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(cleanup_old_sessions, 'interval', minutes=30)
    scheduler.start()
    
    # Store the scheduler in app state
    app_instance.state.scheduler = scheduler
    
    yield
    
    # Cleanup on shutdown
    scheduler.shutdown()
    if hasattr(app_instance.state, 'voice_handler'):
        app_instance.state.voice_handler.close()
    if hasattr(app_instance.state, 'memory_manager'):
        await app_instance.state.memory_manager.cleanup()

# Initialize FastAPI app with enhanced metadata for OpenAPI docs
app = FastAPI(
    title="AI Interviewer API",
    description=f"""
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
    
    Authentication is handled via JWT Bearer tokens. Use the {auth_settings.API_V1_STR}/auth/token endpoint to log in.
    Register new users at {auth_settings.API_V1_STR}/auth/register.
    """,
    version="1.0.0",
    docs_url="/api/docs",  # Enable default Swagger UI at /api/docs
    redoc_url="/api/redoc",  # Enable ReDoc at /api/redoc
    lifespan=lifespan  # <--- ADD LIFESPAN MANAGER HERE
)
logger.info(f"FastAPI app created. Registered lifespan: {app.router.lifespan}") # <--- NEW LOG to check registration

# Add rate limiter exception handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add SessionMiddleware for session management (e.g., for OAuth state)
app.add_middleware(
    SessionMiddleware,
    secret_key=auth_settings.SECRET_KEY, # Use the secret key from your settings
    # session_cookie="your_session_cookie_name", # Optional: customize cookie name
    # max_age=14 * 24 * 60 * 60,  # Optional: cookie expiry in seconds (e.g., 14 days)
    # https_only=True, # Optional: for production, ensure served over HTTPS
)

# Add CORS middleware to allow cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Dependency for monitoring request timing (MOVED EARLIER)
async def log_request_time(request: Request):
    request.state.start_time = datetime.now()
    yield
    process_time = (datetime.now() - request.state.start_time).total_seconds() * 1000
    logger.info(f"Request to {request.url.path} took {process_time:.2f}ms")

# Include authentication routes
app.include_router(
    auth_routes.router,
    prefix=f"{auth_settings.API_V1_STR}/auth",
    tags=["Authentication"],
    dependencies=[Depends(log_request_time)]
)

# Include proctoring routes
app.include_router(
    proctoring.router
    # Removed dependencies=[Depends(log_request_time)] as WebSocket endpoints can't use HTTP dependencies
)

# Include Gemini Live API routes
app.include_router(
    gemini_live.router,
    prefix="/api/gemini-live",
    tags=["Gemini Live API"]
    # No dependencies for WebSocket endpoints
)

# Add rate limiter middleware
app.state.limiter = limiter
# app.add_middleware(RateLimitMiddleware)

# Mount the auth router
app.include_router(auth_routes.router, prefix="/api")

# Import and mount organization and job posting routers
# from ai_interviewer.routers.organization import router as organization_router
# from ai_interviewer.routers.job_posting import router as job_posting_router

# app.include_router(organization_router, prefix="/api")
# app.include_router(job_posting_router, prefix="/api")

# Async function to setup memory manager (adapted from existing code)
async def setup_memory_manager_async():
    db_config = get_db_config()
    logger.info(f"Attempting to initialize InterviewMemoryManager with db_config: {db_config}")
    mm = InterviewMemoryManager(
        connection_uri=db_config["uri"],
        db_name=db_config["database"],
        checkpoint_collection=db_config["sessions_collection"],
        store_collection="interview_memory_store",
        use_async=True
    )
    logger.info(f"InterviewMemoryManager instance created: {mm}")
    if hasattr(mm, 'db'):
        logger.info(f"InterviewMemoryManager instance mm.db immediately after init: {mm.db}")
    else:
        logger.warning("InterviewMemoryManager instance mm has NO 'db' attribute immediately after init.")
    
    await mm.async_setup()
    logger.info("InterviewMemoryManager mm.async_setup() completed.")
    if hasattr(mm, 'db'):
        logger.info(f"InterviewMemoryManager instance mm.db after async_setup: {mm.db}")
    else:
        logger.warning("InterviewMemoryManager instance mm has NO 'db' attribute after async_setup.")
        
    logger.info("Memory manager initialized and setup successfully via lifespan event.")
    return mm

# Async function to setup AIInterviewer instance
async def setup_ai_interviewer_async(mm_instance: Optional[InterviewMemoryManager] = None): # Accept memory_manager
    # Pass the already initialized memory_manager if provided, or let AIInterviewer initialize its own
    interviewer_instance = AIInterviewer(use_mongodb=True, memory_manager_instance=mm_instance)
    if not hasattr(interviewer_instance, 'summarization_model'):
        llm_config_val = get_llm_config()
        interviewer_instance.summarization_model = ChatGoogleGenerativeAI(
            model=llm_config_val["model"],
            temperature=0.1
        )
        logger.info("Added summarization model to interviewer instance via lifespan event.")
    
    if not hasattr(interviewer_instance, 'run_interview'):
        logger.critical("CRITICAL: AIInterviewer instance does NOT have 'run_interview' method during lifespan setup!")
    else:
        logger.info("CONFIRMED: AIInterviewer instance has 'run_interview' method during lifespan setup.")
    logger.info("AI Interviewer initialized successfully via lifespan event.")
    return interviewer_instance

# Dependency to get the database instance is now in ai_interviewer.core.database
# async def get_motor_db(request: Request) -> AsyncIOMotorDatabase: # Add request: Request
#     # global memory_manager # No longer access global
#     # logger.info(f"get_motor_db called. Current global memory_manager: {memory_manager}")
#     
#     mm = getattr(request.app.state, 'memory_manager', None)
#     logger.info(f"get_motor_db called. App state memory_manager: {mm}")
# 
#     if mm and hasattr(mm, 'db'):
#         logger.info(f"get_motor_db: app.state.memory_manager.db: {mm.db}")
#     elif mm:
#         logger.warning("get_motor_db: app.state.memory_manager exists but has NO 'db' attribute.")
#     else:
#         logger.warning("get_motor_db: app.state.memory_manager is None.")
# 
#     if not mm or not hasattr(mm, 'db') or mm.db is None:
#         logger.error("Database client (app.state.memory_manager.db) not available or not initialized.")
#         raise HTTPException(status_code=503, detail="Database service not available or not initialized.")
#     return mm.db

# Initialize VoiceHandler for speech processing
try:
    speech_config = get_speech_config() # Needed for tts_voice later
    voice_handler = VoiceHandler() # Correct: No api_key argument
    voice_enabled = True
    logger.info("Voice processing enabled")
except Exception as e:
    logger.warning(f"Voice processing disabled: {e}", exc_info=True)
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
    stream: Optional[bool] = Field(False, description="Whether to stream the response in real-time")
    
    class Config:
        schema_extra = {
            "example": {
                "message": "Hello, I'm here for the interview.",
                "user_id": "user-123",
                "job_role": "Frontend Developer",
                "seniority_level": "Mid-level",
                "required_skills": ["JavaScript", "React", "HTML/CSS"],
                "job_description": "Looking for a developer with strong React skills.",
                "requires_coding": True,
                "stream": False
            }
        }

class MessageResponse(BaseModel):
    response: str = Field(..., description="AI interviewer's response")
    session_id: str = Field(..., description="Session ID for continuing the conversation")
    interview_stage: Optional[str] = Field(None, description="Current stage of the interview")
    job_role: Optional[str] = Field(None, description="Job role for the interview")
    requires_coding: Optional[bool] = Field(None, description="Whether this role requires coding challenges")
    coding_challenge_detail: Optional[Dict[str, Any]] = Field(None, description="Structured details of the coding challenge, if applicable") # ADDED
    audio_response_url: Optional[str] = Field(None, description="URL to the synthesized audio response, if available") # ADDED
    
    class Config:
        schema_extra = {
            "example": {
                "response": "Hello! Welcome to your technical interview for the Frontend Developer position. Could you please introduce yourself?",
                "session_id": "sess-abc123",
                "interview_stage": "introduction",
                "job_role": "Frontend Developer",
                "requires_coding": True,
                "coding_challenge_detail": {
                    "challenge_id": "coding-challenge-123",
                    "language": "JavaScript",
                    "code": "function findMostFrequent(lst) { return max(set(lst), key=lst.count); }",
                    "user_id": "user-123",
                    "session_id": "sess-abc123",
                    "timestamp": "2023-07-15T14:30:00.000Z"
                },
                "audio_response_url": "https://example.com/audio-response.mp3"
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
        200: {"description": "Successfully started new interview"},
        400: {"description": "Bad request - missing user ID", "model": ErrorResponse},
        409: {"description": "Conflict - duplicate session request", "model": ErrorResponse},
        429: {"description": "Rate limit exceeded", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    },
    dependencies=[Depends(log_request_time)]
)
@limiter.limit("60/minute")
async def start_interview(request: Request, request_data: MessageRequest, current_user: User = Depends(get_current_active_user)):
    """Start a new interview session with deduplication and job role parameters."""
    # Use authenticated user's ID
    user_id = current_user.id
    
    # Create a unique key for user + job combination
    user_job_key = f"{user_id}_{request_data.job_role}_{request_data.seniority_level}"
    current_time = time.time()
    
    # Deduplication logic - prevent multiple sessions for same user+job in short timeframe
    request_key = f"start_{user_job_key}_{hash(request_data.message) % 10000}"
    
    # Check for recent duplicate sessions first
    with _request_lock:
        # Clean up old entries
        cleanup_threshold = current_time - 3600  # 1 hour threshold
        expired_keys = [k for k, v in _recent_sessions.items() if v['created'] < cleanup_threshold]
        for k in expired_keys:
            del _recent_sessions[k]
        
        # Check for recent session with same user+job
        if user_job_key in _recent_sessions:
            recent_session = _recent_sessions[user_job_key]
            time_since_creation = current_time - recent_session['created']
            if time_since_creation < 300:  # 5 minute window
                logger.info(f"Returning existing recent session {recent_session['session_id']} for user {user_id} + job {request_data.job_role}")
                # Return existing session instead of creating new one
                existing_stage = "introduction"
                try:
                    sess_mgr = getattr(app.state, 'session_manager', None)
                    if sess_mgr:
                        sess_rec = sess_mgr.get_session(recent_session['session_id'])
                        if sess_rec and isinstance(sess_rec, dict):
                            existing_stage = sess_rec.get('metadata', {}).get('interview_stage', 'introduction')
                except Exception:
                    pass  # If anything goes wrong, keep introduction as default

                if existing_stage == "feedback":
                    tailored_response = "Welcome back! Let's continue reviewing your coding submission. What part of your solution would you like feedback on next?"
                else:
                    tailored_response = "I see you've already started an interview for this role recently. Let me continue from where we left off. How can I help you today?"

                return MessageResponse(
                    response=tailored_response,
                    session_id=recent_session['session_id'],
                    interview_stage=existing_stage,
                    job_role=request_data.job_role,
                    requires_coding=request_data.requires_coding
                )
        
        # Check for active request
        if request_key in _active_requests:
            raise HTTPException(status_code=409, detail="Duplicate request in progress")
        
        # Add to active requests
        _active_requests.add(request_key)
    
    try:
        # Rest of the function logic
        start_time = time.time()
        logger.info(f"[SERVER] start_interview called. User ID: {current_user.id}")
        logger.info(f"[SERVER] Request data job_role: '{request_data.job_role}', seniority_level: '{request_data.seniority_level}'")

        # Ensure we have an active interviewer instance
        active_interviewer = getattr(app.state, 'interviewer', None)
        if not active_interviewer:
            raise HTTPException(status_code=503, detail="AI Interviewer service not available")
        
        # Use the authenticated user's ID instead of request_data.user_id
        user_id = current_user.id  # This ensures we use the authenticated user's ID
        
        # Call the run_interview method
        response_data = await active_interviewer.run_interview(
            user_id=user_id,
            user_message=request_data.message,
            session_id=None,  # Always create new session for start_interview
            job_role=request_data.job_role,
            seniority_level=request_data.seniority_level,
            required_skills=request_data.required_skills,
            job_description=request_data.job_description,
            requires_coding=request_data.requires_coding
        )
        
        # Get job role and requires_coding from the actual session metadata
        metadata = {}
        if active_interviewer.session_manager and response_data.get("session_id"):
            session = active_interviewer.session_manager.get_session(response_data["session_id"])
            if session and "metadata" in session:
                metadata = session["metadata"]  # This metadata might be slightly stale regarding stage
        
        logger.info(f"[SERVER] start_interview RETURN: response='{response_data['ai_response'][:50]}...', session_id='{response_data['session_id']}', interview_stage='{response_data.get('interview_stage')}', job_role='{metadata.get('job_role')}', requires_coding='{metadata.get('requires_coding')}', coding_challenge_detail_present={response_data.get('coding_challenge_detail') is not None}") # Added log
        logger.info(f"[SERVER] Request to /api/interview took {(time.time() - start_time) * 1000:.2f}ms")
        
        # Track the new session to prevent future duplicates
        with _request_lock:
            _recent_sessions[user_job_key] = {
                'session_id': response_data["session_id"],
                'created': current_time
            }
            logger.info(f"Tracked new session {response_data['session_id']} for user {current_user.id} + job {request_data.job_role}")
        
        return MessageResponse(
            response=response_data["ai_response"],
            session_id=response_data["session_id"],
            interview_stage=response_data.get("interview_stage"), # Use stage from run_interview
            job_role=metadata.get("job_role"), # Keep these from potentially updated session metadata
            requires_coding=metadata.get("requires_coding"),
            coding_challenge_detail=response_data.get("coding_challenge_detail"), # ADDED
            audio_response_url=response_data.get("audio_response_url") # ADDED
        )
    except Exception as e:
        logger.error(f"Error starting interview: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Always remove the request key from active requests
        with _request_lock:
            _active_requests.discard(request_key)

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
@limiter.limit("60/minute")
async def continue_interview(
    request: Request, 
    session_id: str, 
    request_data: MessageRequest,
    current_user: User = Depends(get_current_active_user) # <--- ADD DEPENDENCY
):
    """
    Continue an existing interview session with either streaming or non-streaming response.
    
    If request_data.stream is True, returns a Server-Sent Events (SSE) response for real-time streaming.
    Otherwise, returns a standard JSON response.
    """
    try:
        # Check for stream parameter first
        if request_data.stream:
            # Streaming response path with deduplication
            stream_request_key = f"{current_user.id}_{session_id}_stream"
            
            with _request_lock:
                if stream_request_key in _active_requests:
                    logger.warning(f"Duplicate streaming request detected for session {session_id}")
                    raise HTTPException(status_code=429, detail="Streaming request already in progress for this session")
                _active_requests.add(stream_request_key)
            
            # Handle streaming response with optimized session handling
            async def stream_response():
                session_updates = {}  # Declare here for proper scope
                
                # Initialize critical variables early to prevent scope issues
                coding_challenge_detail = None
                tool_executed = False
                tool_output_content = None
                parsed_tool_call_data = None
                
                try:
                    # Get the active interviewer from app state
                    active_interviewer = getattr(app.state, 'interviewer', None)
                    if not active_interviewer:
                        yield f"data: {json.dumps({'error': 'AI Interviewer not available'})}\n\n"
                        return

                    logger.info(f"Starting streaming response for session {session_id}")
                    
                    # Get or create session first for faster initial response
                    session_id_to_use = active_interviewer._get_or_create_session(
                        user_id=request_data.user_id,
                        session_id=session_id,
                        job_role=request_data.job_role,
                        seniority_level=request_data.seniority_level,
                        required_skills=request_data.required_skills,
                        job_description=request_data.job_description,
                        requires_coding=request_data.requires_coding
                    )
                    
                    # Build the conversation state for direct streaming
                    from ai_interviewer.core.ai_interviewer import InterviewState
                    import uuid
                    from ai_interviewer.utils.gemini_live_utils import generate_response_stream
                    
                    # Get existing messages from session
                    messages = []
                    if active_interviewer.session_manager:
                        session_data = active_interviewer.session_manager.get_session(session_id_to_use)
                        if session_data and 'messages' in session_data:
                            # Extract and convert messages to proper LangChain format
                            raw_messages = session_data['messages']
                            
                            # DEBUG: Log the actual message format
                            logger.info(f"Streaming: Raw messages type: {type(raw_messages)}")
                            if raw_messages:
                                logger.info(f"Streaming: First message type: {type(raw_messages[0])}")
                                logger.info(f"Streaming: First message content: {raw_messages[0]}")
                                logger.info(f"Streaming: Total raw messages: {len(raw_messages)}")
                            else:
                                logger.warning(f"Streaming: Raw messages is empty for session {session_id_to_use}")
                            
                            from ai_interviewer.utils.transcript import extract_messages_from_transcript
                            try:
                                messages = extract_messages_from_transcript(raw_messages)
                                logger.info(f"Streaming: Successfully extracted {len(messages)} messages for session {session_id_to_use}")
                            except Exception as extract_error:
                                logger.error(f"Streaming: Failed to extract messages for session {session_id_to_use}: {extract_error}")
                                # Fallback: create messages from transcript if available
                                messages = []
                        else:
                            logger.warning(f"Streaming: No 'messages' key in session data for {session_id_to_use}. Session keys: {list(session_data.keys()) if session_data else 'None'}")
                    else:
                        logger.warning(f"Streaming: No session manager available")
                    
                    # CRITICAL FIX: Get messages from LangGraph checkpointer instead of session data
                    messages = []
                    try:
                        # Get checkpointer from the active interviewer
                        if hasattr(active_interviewer, 'checkpointer') and active_interviewer.checkpointer:
                            # Create the config that LangGraph uses to identify the thread
                            config = {"configurable": {"thread_id": session_id_to_use}}
                            
                            # Get the latest checkpoint state
                            checkpoint_state = await active_interviewer.checkpointer.aget(config)
                            
                            if checkpoint_state and 'channel_values' in checkpoint_state:
                                # Extract messages from the checkpoint state
                                channel_values = checkpoint_state['channel_values']
                                if 'messages' in channel_values:
                                    messages = channel_values['messages']
                                    logger.info(f"Streaming: Retrieved {len(messages)} messages from LangGraph checkpointer for session {session_id_to_use}")
                                else:
                                    logger.info(f"Streaming: No messages in checkpoint state for session {session_id_to_use}. Available keys: {list(channel_values.keys())}")
                            else:
                                logger.info(f"Streaming: No checkpoint state found for session {session_id_to_use}")
                        else:
                            logger.warning(f"Streaming: No checkpointer available in interviewer")
                            
                    except Exception as checkpoint_error:
                        logger.error(f"Streaming: Failed to retrieve messages from checkpointer for session {session_id_to_use}: {checkpoint_error}")
                        messages = []
                    
                    # Create interview state
                    try:
                        # CRITICAL FIX: Get job details from session metadata instead of fallbacks
                        session_metadata = {}
                        if active_interviewer.session_manager:
                            session_data = active_interviewer.session_manager.get_session(session_id_to_use)
                            if session_data and 'metadata' in session_data:
                                session_metadata = session_data['metadata']
                                logger.info(f"Streaming: Retrieved session metadata with job_role='{session_metadata.get('job_role')}', seniority_level='{session_metadata.get('seniority_level')}'")
                            else:
                                logger.warning(f"Streaming: No metadata found in session {session_id_to_use}. Session data keys: {list(session_data.keys()) if session_data else 'None'}")
                        else:
                            logger.warning(f"Streaming: No session manager available for session {session_id_to_use}")
                        
                        # Use session metadata first, then request data, then fallbacks
                        job_role = session_metadata.get('job_role') or request_data.job_role or "Software Engineer"
                        seniority_level = session_metadata.get('seniority_level') or request_data.seniority_level or "Mid-level"
                        required_skills = session_metadata.get('required_skills') or request_data.required_skills or ["Programming", "Problem-solving"]
                        job_description = session_metadata.get('job_description') or request_data.job_description or "Software development role"
                        requires_coding = session_metadata.get('requires_coding')
                        if requires_coding is None:
                            requires_coding = request_data.requires_coding if request_data.requires_coding is not None else True
                        
                        # CRITICAL FIX: Get the actual current stage from session metadata or checkpointer
                        current_stage = session_metadata.get('interview_stage', 'introduction')
                        
                        # Try to get more up-to-date stage from checkpointer if available
                        try:
                            if hasattr(active_interviewer, 'checkpointer') and active_interviewer.checkpointer:
                                config = {"configurable": {"thread_id": session_id_to_use}}
                                checkpoint_state = await active_interviewer.checkpointer.aget(config)
                                if checkpoint_state and 'channel_values' in checkpoint_state:
                                    channel_values = checkpoint_state['channel_values']
                                    if 'interview_stage' in channel_values:
                                        current_stage = channel_values['interview_stage']
                                        logger.info(f"Streaming: Got current stage '{current_stage}' from checkpointer for session {session_id_to_use}")
                                    else:
                                        logger.info(f"Streaming: No interview_stage in checkpoint channel_values for session {session_id_to_use}")
                        except Exception as checkpoint_stage_error:
                            logger.warning(f"Streaming: Failed to get stage from checkpointer for session {session_id_to_use}: {checkpoint_stage_error}")
                        
                        logger.info(f"Streaming: Using job details: job_role='{job_role}', seniority_level='{seniority_level}', current_stage='{current_stage}'")
                        
                        # Ensure all required fields have correct values for InterviewState
                        from ai_interviewer.core.ai_interviewer import InterviewState
                        interview_state = InterviewState(
                            messages=messages,
                            session_id=session_id_to_use,
                            user_id=request_data.user_id or "unknown",
                            job_role=job_role,
                            seniority_level=seniority_level,
                            required_skills=required_skills,
                            job_description=job_description,
                            requires_coding=requires_coding,
                            interview_stage=current_stage,  # Use actual current stage instead of hardcoded "introduction"
                            candidate_name="",
                            conversation_summary="",
                            message_count=len(messages),
                            max_messages_before_summary=20
                        )
                        
                        logger.info(f"Streaming: Created InterviewState with {len(interview_state.messages)} messages and stage '{current_stage}' for session {session_id_to_use}")
                    except Exception as state_error:
                        logger.error(f"Streaming: Failed to create InterviewState for session {session_id_to_use}: {state_error}")
                        # Enhanced fallback with session metadata values instead of hardcoded defaults
                        interview_state = {
                            'messages': messages,
                            'session_id': session_id_to_use,
                            'user_id': request_data.user_id or "unknown",
                            'job_role': job_role,  # Use the session metadata value
                            'seniority_level': seniority_level,  # Use the session metadata value
                            'required_skills': required_skills,  # Use the session metadata value
                            'job_description': job_description,  # Use the session metadata value
                            'requires_coding': requires_coding,  # Use the session metadata value
                            'interview_stage': current_stage,  # Use actual current stage instead of hardcoded "introduction"
                            'candidate_name': "",
                            'conversation_summary': "",
                            'message_count': len(messages),
                            'max_messages_before_summary': 20
                        }
                    
                    # Build system prompt and context
                    system_prompt = active_interviewer._build_system_prompt(interview_state)
                    
                    # DEBUG: Log the exact system prompt being used
                    logger.info(f"Streaming: Generated system prompt (first 200 chars): {system_prompt[:200]}...")
                    
                    # CRITICAL DEBUG: Check if CODING_CHALLENGE instructions are included
                    if current_stage == 'coding_challenge':
                        if 'generate_coding_challenge_from_jd' in system_prompt:
                            logger.info("Streaming: ✓ System prompt contains CODING_CHALLENGE tool call instructions")
                        else:
                            logger.error("Streaming: ✗ System prompt missing CODING_CHALLENGE tool call instructions despite being in coding_challenge stage!")
                            # Log more of the system prompt for debugging
                            logger.error(f"Streaming: Full system prompt: {system_prompt}")
                    
                    # Look for job role mentions in the system prompt
                    if "Data Scientist" in system_prompt:
                        logger.info("Streaming: ✓ System prompt contains 'Data Scientist'")
                    elif "Software Engineer" in system_prompt:
                        logger.warning("Streaming: ✗ System prompt contains 'Software Engineer' instead of expected job role")
                    else:
                        logger.warning("Streaming: ✗ System prompt doesn't contain expected job role")
                    
                    # Add user message to context
                    user_content = f"User: {request_data.message}"
                    
                    # Create full prompt for streaming with reduced context for speed
                    full_prompt = f"{system_prompt}\n\nConversation so far:\n"
                    # Use only last 5 messages instead of 10 for faster processing
                    for msg in messages[-5:]:  
                        if hasattr(msg, 'content'):
                            # Truncate long messages to reduce context size
                            content = msg.content[:500] if len(msg.content) > 500 else msg.content
                            full_prompt += f"{content}\n"
                    full_prompt += f"\n{user_content}\n\nAI Interviewer:"
                    
                    # DEBUG: Check if conversation history contains wrong job information
                    if "Software Engineer" in full_prompt and "Data Scientist" not in full_prompt:
                        logger.warning("Streaming: ✗ Conversation history contains 'Software Engineer' but not 'Data Scientist'")
                    elif "Data Scientist" in full_prompt:
                        logger.info("Streaming: ✓ Conversation history contains 'Data Scientist'")
                    
                    # DEBUG: Log how many messages are in conversation history
                    logger.info(f"Streaming: Using {len(messages[-5:])} messages from conversation history")
                    
                    # Stream response directly from Gemini with optimized parameters
                    accumulated_response = ""
                    buffered_chunks: List[str] = []

                    async for chunk in generate_response_stream(full_prompt, temperature=0.3, max_tokens=1024):
                        if chunk.strip():
                            accumulated_response += chunk
                            buffered_chunks.append(chunk)

                    # We will decide after potential tool-call parsing whether these chunks should be sent
                    
                    # CRITICAL FIX: Check if the accumulated response is a tool call and execute it
                    tool_executed = False
                    parsed_tool_call_data = None
                    tool_output_content = None  # Initialize in outer scope
                    tool_result = None  # Add this to preserve tool result for final parsing
                    
                    if accumulated_response.strip():
                        try:
                            # Detect JSON blocks within markdown code fences or plain JSON
                            json_block_match = re.search(r'```(?:json)?\s*\n?(\{.*?\})\s*\n?```', accumulated_response, re.DOTALL)
                            if json_block_match:
                                json_str = json_block_match.group(1).strip()
                                logger.info(f"Streaming: Extracted JSON block from markdown fences: '{json_str[:100]}...'")
                            else:
                                # Try to find any JSON object in the response
                                json_str = accumulated_response.strip()
                            
                            # Attempt to parse as JSON
                            parsed_tool_call_data = json.loads(json_str)
                            
                            # Validate it has the expected tool call structure
                            if "name" in parsed_tool_call_data and "args" in parsed_tool_call_data:
                                tool_name = parsed_tool_call_data["name"]
                                logger.info(f"Streaming: Successfully parsed JSON tool call data: {parsed_tool_call_data}")
                                
                                # Execute the tool
                                logger.info(f"Streaming: Detected tool call '{tool_name}', executing...")
                                tool_to_execute = None
                                for tool in active_interviewer.tools:
                                    if tool.name == tool_name:
                                        tool_to_execute = tool
                                        break
                                
                                if tool_to_execute:
                                    try:
                                        # Execute the tool (always try async first since we're in async context)
                                        tool_args = parsed_tool_call_data["args"]
                                        
                                        # Always try async first in streaming context
                                        try:
                                            tool_result = await tool_to_execute.ainvoke(tool_args)
                                            logger.info(f"Streaming: Tool '{tool_name}' executed successfully via ainvoke")
                                        except AttributeError:
                                            # Fall back to sync if ainvoke not available
                                            try:
                                                tool_result = tool_to_execute.invoke(tool_args)
                                                logger.info(f"Streaming: Tool '{tool_name}' executed successfully via invoke")
                                            except Exception as sync_error:
                                                raise Exception(f"Both async and sync invocation failed. Async error: ainvoke not available. Sync error: {sync_error}")
                                        
                                        tool_executed = True
                                        
                                        # Convert tool result to appropriate content
                                        if isinstance(tool_result, dict):
                                            tool_output_content = json.dumps(tool_result, indent=2)
                                        else:
                                            tool_output_content = str(tool_result)
                                        
                                        logger.info(f"Streaming: Tool output (first 200 chars): {tool_output_content[:200]}...")
                                        
                                        # CRITICAL FIX: Extract coding challenge details if tool was executed
                                        coding_challenge_detail = None
                                        if tool_executed and tool_result:
                                            try:
                                                # Use the tool_result directly instead of parsing tool_output_content
                                                if isinstance(tool_result, dict):
                                                    if 'challenge' in tool_result:
                                                        coding_challenge_detail = tool_result['challenge']
                                                        logger.info(f"Streaming: Extracted coding challenge details from 'challenge' key for frontend: {str(coding_challenge_detail)[:200]}...")
                                                    elif 'problem_statement' in tool_result:
                                                        # Tool output is directly the challenge
                                                        coding_challenge_detail = tool_result
                                                        logger.info(f"Streaming: Using tool output directly as coding challenge details")
                                                    else:
                                                        logger.warning(f"Streaming: Tool result does not contain expected challenge structure: {list(tool_result.keys())}")
                                                else:
                                                    logger.warning(f"Streaming: Tool result is not a dict: {type(tool_result)}")
                                            except Exception as parse_error:
                                                logger.warning(f"Streaming: Failed to extract coding challenge from tool result: {parse_error}")
                                        elif tool_executed and tool_output_content:
                                            # Fallback: try to parse tool_output_content as JSON if tool_result is not available
                                            try:
                                                tool_output_dict = json.loads(tool_output_content)
                                                if 'challenge' in tool_output_dict:
                                                    coding_challenge_detail = tool_output_dict['challenge']
                                                    logger.info(f"Streaming: Extracted coding challenge details from tool_output_content fallback for frontend: {str(coding_challenge_detail)[:200]}...")
                                                elif 'problem_statement' in tool_output_dict:
                                                    coding_challenge_detail = tool_output_dict
                                                    logger.info(f"Streaming: Using tool_output_content directly as coding challenge details (fallback)")
                                            except (json.JSONDecodeError, KeyError) as parse_error:
                                                logger.warning(f"Streaming: Failed to parse coding challenge from tool output: {parse_error}")
                                        
                                        if challenge_details:
                                            immediate_challenge_data = {
                                                "type": "coding_challenge_generated",
                                                "coding_challenge_detail": challenge_details,
                                                "session_id": session_id_to_use
                                            }
                                            
                                            # Send as separate, clean streaming chunk
                                            challenge_chunk = f"data: {json.dumps(immediate_challenge_data)}\\n\\n"
                                            yield challenge_chunk
                                            logger.info(f"Streaming: Immediately sent coding challenge details to frontend for session {session_id_to_use}")
                                            
                                    except Exception as e:
                                        logger.error(f"Streaming: Failed to send immediate challenge details: {e}")
                                        
                                else:
                                    logger.warning(f"Streaming: Tool '{tool_name}' not found in available tools")
                                    tool_output_content = f"Tool {tool_name} not available"
                                    
                        except (json.JSONDecodeError, TypeError) as e:
                            logger.info(f"Streaming: Response not a JSON tool call (or parsing error: {e}). Content: '{accumulated_response[:100]}...'")
                            # Continue with normal response processing
                    
                    # If no tool was executed, stream the buffered chunks now (normal conversation path)
                    if not tool_executed and buffered_chunks:
                        for chunk in buffered_chunks:
                            chunk_data = {
                                "text": chunk,
                                "session_id": session_id_to_use
                            }
                            yield f"data: {json.dumps(chunk_data)}\n\n"
                    
                    # Save the conversation after streaming completes
                    if accumulated_response.strip():
                        # Add messages to state - handle both InterviewState object and dict fallback
                        from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
                        
                        try:
                            # Always start by adding the user message
                            user_message = HumanMessage(content=request_data.message)
                            
                            if tool_executed:
                                # TOOL EXECUTION PATH: Save tool call, tool result, and generate follow-up response
                                logger.info(f"Streaming: Processing tool execution path for session {session_id_to_use}")
                                
                                # Create AIMessage with tool_calls
                                ai_tool_call_message = AIMessage(
                                    content=accumulated_response,
                                    tool_calls=[parsed_tool_call_data] if 'parsed_tool_call_data' in locals() else []
                                )
                                
                                # Create ToolMessage with the tool result
                                tool_message = ToolMessage(
                                    content=tool_output_content,
                                    tool_call_id=parsed_tool_call_data.get("id", "unknown") if 'parsed_tool_call_data' in locals() else "unknown"
                                )
                                
                                # CRITICAL FIX: Skip follow-up response for coding challenge tool to prevent concatenation
                                if 'generate_coding_challenge_from_jd' in str(parsed_tool_call_data):
                                    # For coding challenge, just send a brief response without LLM generation
                                    follow_up_response = "Perfect! I've generated a coding challenge for you based on the job requirements. Please take a look at the problem statement and let me know when you're ready to start coding!"
                                    
                                    # Don't stream this since we already sent challenge details
                                    logger.info(f"Streaming: Using pre-defined follow-up for coding challenge tool")
                                else:
                                    # Generate follow-up AI response to present the tool output naturally for other tools
                                    follow_up_prompt = f"{system_prompt}\n\nConversation so far:\n"
                                    for msg in messages[-3:]:  # Include recent context
                                        if hasattr(msg, 'content'):
                                            content = msg.content[:300] if len(msg.content) > 300 else msg.content
                                            follow_up_prompt += f"{content}\n"
                                    
                                    follow_up_prompt += f"\nUser: {request_data.message}\n"
                                    follow_up_prompt += f"Tool Output: {tool_output_content}\n\n"
                                    follow_up_prompt += "AI Interviewer (present the tool output naturally):"
                                    
                                    # Generate follow-up response
                                    follow_up_response = ""
                                    async for chunk in generate_response_stream(follow_up_prompt, temperature=0.3, max_tokens=512):
                                        if chunk.strip():
                                            follow_up_response += chunk
                                            # Stream the follow-up response to frontend
                                            chunk_data = {
                                                "text": chunk,
                                                "session_id": session_id_to_use,
                                                "type": "follow_up"
                                            }
                                            yield f"data: {json.dumps(chunk_data)}\n\n"
                                
                                ai_follow_up_message = AIMessage(content=follow_up_response.strip())
                                
                                # Build final message list
                                if hasattr(interview_state, 'messages'):
                                    interview_state.messages.extend([user_message, ai_tool_call_message, tool_message, ai_follow_up_message])
                                    final_messages = interview_state.messages
                                else:
                                    interview_state['messages'].extend([user_message, ai_tool_call_message, tool_message, ai_follow_up_message])
                                    final_messages = interview_state['messages']
                                
                                logger.info(f"Streaming: Added 4 messages (user, AI tool call, tool result, AI follow-up) for session {session_id_to_use}")
                                
                            else:
                                # NORMAL PATH: Just add user message and AI response
                                ai_message = AIMessage(content=accumulated_response)
                                
                                if hasattr(interview_state, 'messages'):
                                    interview_state.messages.extend([user_message, ai_message])
                                    final_messages = interview_state.messages
                                else:
                                    interview_state['messages'].extend([user_message, ai_message])
                                    final_messages = interview_state['messages']
                                
                                logger.info(f"Streaming: Added 2 messages (user, AI) for session {session_id_to_use}")
                                
                            logger.info(f"Streaming: Successfully updated messages for session {session_id_to_use}, total messages: {len(final_messages)}")
                            
                            # CRITICAL FIX: Save messages to LangGraph checkpointer
                            if active_interviewer and hasattr(active_interviewer, 'checkpointer') and active_interviewer.checkpointer:
                                try:
                                    # Create thread config for LangGraph
                                    thread_config = {"configurable": {"thread_id": session_id_to_use}}
                                    
                                    # Use LangGraph's simpler approach - save via workflow
                                    # Create a temporary state dict compatible with LangGraph
                                    state_update = {
                                        "messages": final_messages,
                                        "session_id": session_id_to_use,
                                        "user_id": request_data.user_id
                                    }
                                    
                                    # Use the compiled workflow to update state
                                    if hasattr(active_interviewer, 'workflow') and active_interviewer.workflow:
                                        # Update the state using LangGraph's state management
                                        await active_interviewer.workflow.aupdate_state(
                                            config=thread_config,
                                            values=state_update
                                        )
                                        logger.info(f"Streaming: Updated LangGraph workflow state with {len(final_messages)} messages for session {session_id_to_use}")
                                    else:
                                        logger.warning(f"Streaming: No workflow available to update state for session {session_id_to_use}")
                                    
                                except Exception as checkpointer_error:
                                    logger.error(f"Streaming: Failed to update LangGraph state for session {session_id_to_use}: {checkpointer_error}")
                                    # Continue anyway - we'll still save to session manager
                            
                            # Batch save to session manager (single database operation)
                            existing_metadata = {}  # Initialize here to fix scope issue
                            if active_interviewer.session_manager:
                                # CRITICAL FIX: Merge with existing metadata instead of overwriting
                                existing_session = active_interviewer.session_manager.get_session(session_id_to_use)
                                if existing_session and 'metadata' in existing_session:
                                    existing_metadata = existing_session['metadata'].copy()
                                
                                # CRITICAL FIX: Add stage determination to streaming response
                                try:
                                    # Get current stage from session metadata
                                    current_stage = existing_metadata.get('interview_stage', 'introduction')
                                    
                                    # Create AIMessage object from the accumulated response
                                    ai_message = AIMessage(content=accumulated_response.strip())
                                    
                                    # CRITICAL FIX: If a coding challenge tool was executed, force stage to coding_challenge_waiting
                                    if tool_executed and 'generate_coding_challenge_from_jd' in str(parsed_tool_call_data):
                                        new_stage = 'coding_challenge_waiting'
                                        logger.info(f"Streaming: Tool execution detected - forcing stage transition to 'coding_challenge_waiting' for session {session_id_to_use}")
                                    else:
                                        # Call stage determination logic for normal transitions
                                        new_stage = active_interviewer._determine_interview_stage(
                                            final_messages, ai_message, current_stage
                                        )
                                    
                                    # Update stage if it changed
                                    if new_stage != current_stage:
                                        logger.info(f"Streaming: Stage transition from '{current_stage}' to '{new_stage}' for session {session_id_to_use}")
                                        existing_metadata['interview_stage'] = new_stage
                                        
                                        # CRITICAL FIX: Update the LangGraph workflow state with the new stage
                                        try:
                                            # Create thread config
                                            thread_config = {"configurable": {"thread_id": session_id_to_use}}
                                            
                                            # Update workflow state with new stage
                                            if hasattr(active_interviewer, 'workflow') and active_interviewer.workflow:
                                                await active_interviewer.workflow.aupdate_state(
                                                    config=thread_config,
                                                    values={"interview_stage": new_stage}
                                                )
                                                logger.info(f"Streaming: Updated LangGraph workflow state with new stage '{new_stage}' for session {session_id_to_use}")
                                            else:
                                                logger.warning(f"Streaming: No workflow available to update stage for session {session_id_to_use}")
                                        except Exception as workflow_stage_error:
                                            logger.error(f"Streaming: Failed to update workflow state with new stage for session {session_id_to_use}: {workflow_stage_error}")
                                    else:
                                        logger.info(f"Streaming: Staying in stage '{current_stage}' for session {session_id_to_use}")
                                        
                                except Exception as stage_error:
                                    logger.error(f"Streaming: Failed to determine interview stage for session {session_id_to_use}: {stage_error}")
                                    # Continue without stage update if determination fails
                                
                                # Update only specific fields, preserving job details and stage
                                metadata_updates = existing_metadata.copy()
                                metadata_updates.update({
                                    'last_ai_response': accumulated_response[:100] + '...' if len(accumulated_response) > 100 else accumulated_response,
                                    'message_count': len(final_messages),
                                    'last_active': time.time()
                                })
                                
                                # CRITICAL FIX: Save challenge details to session metadata for submit endpoint
                                if coding_challenge_detail:
                                    metadata_updates['current_coding_challenge_details_for_submission'] = coding_challenge_detail
                                    logger.info(f"Streaming: Saved challenge details to session metadata for submission endpoint")
                                
                                # Queue metadata update with complete metadata
                                queue_db_update(
                                    session_id_to_use,
                                    'metadata',
                                    metadata=metadata_updates  # Now contains complete metadata including challenge details
                                )
                                
                                # Also queue message count update
                                queue_db_update(
                                    session_id_to_use, 
                                    'messages', 
                                    message_count=len(final_messages)
                                )
                                
                                logger.info(f"Queued background updates for session {session_id_to_use}")
                                
                        except Exception as save_error:
                            logger.error(f"Streaming: Failed to queue updates for session {session_id_to_use}: {save_error}")
                            # Continue anyway - the streaming worked, just queuing failed
                    
                    # CRITICAL FIX: Include stage information in final streaming response
                    try:
                        # Get the updated stage from metadata_updates if available
                        final_stage = existing_metadata.get('interview_stage', 'introduction')
                        
                        # CRITICAL FIX: Extract coding challenge details if tool was executed
                        coding_challenge_detail = None
                        if tool_executed and tool_output_content:
                            try:
                                # Parse the tool output to extract challenge details
                                tool_output_dict = json.loads(tool_output_content)
                                if 'challenge' in tool_output_dict:
                                    coding_challenge_detail = tool_output_dict['challenge']
                                    logger.info(f"Streaming: Extracted coding challenge details for frontend: {str(coding_challenge_detail)[:200]}...")
                                elif 'problem_statement' in tool_output_dict:
                                    # Tool output is directly the challenge
                                    coding_challenge_detail = tool_output_dict
                                    logger.info(f"Streaming: Using tool output directly as coding challenge details")
                            except (json.JSONDecodeError, KeyError) as parse_error:
                                logger.warning(f"Streaming: Failed to parse coding challenge from tool output: {parse_error}")
                        
                        final_metadata = {
                            'interview_stage': final_stage,
                            'job_role': existing_metadata.get('job_role'),
                            'requires_coding': existing_metadata.get('requires_coding'),
                            'message_count': len(final_messages)
                        }
                        
                        # Add coding challenge details to metadata if available
                        if coding_challenge_detail:
                            final_metadata['coding_challenge_detail'] = coding_challenge_detail
                        
                        # Send final response with metadata in a format that matches MessageResponse
                        final_response = {
                            'type': 'complete',
                            'interview_stage': final_stage,
                            'job_role': existing_metadata.get('job_role'),
                            'requires_coding': existing_metadata.get('requires_coding'),
                            'metadata': final_metadata
                        }
                        
                        # CRITICAL FIX: Include coding_challenge_detail at top level for frontend compatibility
                        if coding_challenge_detail:
                            final_response['coding_challenge_detail'] = coding_challenge_detail
                            logger.info(f"Streaming: Including coding challenge detail in final response for session {session_id_to_use}")
                        
                        # DEBUG: Log the exact JSON being sent to frontend
                        final_response_json = json.dumps(final_response)
                        logger.info(f"Streaming: Sending final response JSON (first 500 chars): {final_response_json[:500]}...")
                        
                        yield f"data: {final_response_json}\\n\\n"
                        logger.info(f"Streaming: Sent stage '{final_stage}' to frontend for session {session_id_to_use}")
                        
                    except Exception as metadata_error:
                        logger.error(f"Streaming: Failed to send metadata to frontend for session {session_id_to_use}: {metadata_error}")
                    
                    yield f"data: [DONE]\\n\\n"
                        
                except Exception as e:
                    logger.error(f"Streaming error for session {session_id}: {str(e)}")
                    yield f"data: {json.dumps({'error': f'Streaming failed: {str(e)}'})}\n\n"
                finally:
                    # Cleanup: Remove request from active set
                    with _request_lock:
                        _active_requests.discard(stream_request_key)
                    logger.info(f"Cleaned up streaming request for session {session_id}")

            return StreamingResponse(stream_response(), media_type="text/plain")
        
        # Non-streaming path with optimized session handling
        start_time = time.time()
        
        # Pre-validate session exists to fail fast
        active_interviewer = getattr(app.state, 'interviewer', None)
        if not active_interviewer:
            raise HTTPException(status_code=503, detail="AI Interviewer service not available")
        
        logger.info(f"Non-streaming request for session {session_id}, user {request_data.user_id}")
        
        # Call the run_interview method
        response_data = await active_interviewer.run_interview(
            user_id=request_data.user_id,
            user_message=request_data.message,
            session_id=session_id,
            job_role=request_data.job_role,
            seniority_level=request_data.seniority_level,
            required_skills=request_data.required_skills,
            job_description=request_data.job_description,
            requires_coding=request_data.requires_coding
        )
        
        # Standard response processing...
        # [Rest of existing logic remains the same]
        metadata = {}
        if active_interviewer.session_manager and response_data.get("session_id"):
            session = active_interviewer.session_manager.get_session(response_data["session_id"])
            if session and "metadata" in session:
                metadata = session["metadata"] # This metadata might be slightly stale regarding stage
        
        logger.info(f"[SERVER] continue_interview RETURN: response='{response_data['ai_response'][:50]}...', session_id='{response_data['session_id']}', interview_stage='{response_data.get('interview_stage')}', job_role='{metadata.get('job_role')}', requires_coding='{metadata.get('requires_coding')}', coding_challenge_detail_present={response_data.get('coding_challenge_detail') is not None}") # Added log
        return MessageResponse(
            response=response_data["ai_response"],
            session_id=response_data["session_id"],
            interview_stage=response_data.get("interview_stage"), # Use stage from run_interview
            job_role=metadata.get("job_role"), # Keep these from potentially updated session metadata
            requires_coding=metadata.get("requires_coding"),
            coding_challenge_detail=response_data.get("coding_challenge_detail"), # ADDED
            audio_response_url=response_data.get("audio_response_url") # ADDED
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
async def get_user_sessions(
    request: Request, 
    user_id: str, # This is the path parameter
    include_completed: bool = False,
    current_user: User = Depends(get_current_active_user) # <--- ADD DEPENDENCY
):
    """
    Get all sessions for the authenticated user specified by user_id.
    
    Ensures that the user_id in the path matches the authenticated user.
    
    Args:
        user_id: User ID to get sessions for
        include_completed: Whether to include completed sessions (default: false)
        
    Returns:
        List of SessionResponse objects containing session details
    """
    try:
        logger.info(f"API: get_user_sessions called for user {user_id}, include_completed={include_completed}")
        
        # Ensure the authenticated user is requesting their own sessions
        if current_user.id != user_id:
            logger.warning(f"User {current_user.id} attempted to access sessions for {user_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="You do not have permission to access these sessions."
            )
        
        active_interviewer = request.app.state.interviewer # <--- Get from app.state
        if not active_interviewer:
            logger.error("Interviewer not available in app state for get_user_sessions")
            raise HTTPException(status_code=503, detail="Interview service not available.")
            
        logger.info(f"Fetching sessions from interviewer for user {user_id}")
        sessions = active_interviewer.get_user_sessions(user_id, include_completed)
        
        logger.info(f"Found {len(sessions) if sessions else 0} sessions for user {user_id}")
        
        if not sessions:
            logger.info(f"No sessions found for user {user_id}")
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
            
            # Extract interview stage and related info
            interview_stage = metadata.get("interview_stage")
            job_role = metadata.get("job_role")
            requires_coding = metadata.get("requires_coding", True)
            
            logger.info(f"Processing session {session['session_id']} with stage {interview_stage}")

            response.append(SessionResponse(
                session_id=session["session_id"],
                user_id=session["user_id"],
                created_at=created_at_str,
                last_active=last_active_str,
                interview_stage=interview_stage,
                job_role=job_role,
                requires_coding=requires_coding
            ))
        
        logger.info(f"Returning {len(response)} formatted sessions for user {user_id}")
        return response
    except Exception as e:
        logger.error(f"Error getting user sessions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error retrieving sessions: {str(e)}")

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
async def transcribe_and_respond(
    request: Request,
    request_data: AudioTranscriptionRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    Transcribe audio and get AI interviewer response.
    
    This endpoint transcribes the provided audio data and sends the transcription
    to the AI interviewer for a response. The authenticated user's ID will be used.
    
    Args:
        request_data: AudioTranscriptionRequest containing audio data and optional session info
        current_user: The authenticated user.
        
    Returns:
        AudioTranscriptionResponse with transcription, AI response, and session ID
    """
    if not voice_enabled or not voice_handler: # voice_handler is still global for now
        raise HTTPException(status_code=501, detail="Voice processing not available")
    
    try:
        # Use user_id from the authenticated user
        user_id = current_user.id
        
        active_interviewer = request.app.state.interviewer # <--- Get from app.state
        if not active_interviewer:
            logger.error("Interviewer not available in app state for transcribe_and_respond")
            raise HTTPException(status_code=503, detail="Interview service not available.")

        # Enhanced logging for audio data debugging
        logger.info(f"Processing audio transcription request from user: {user_id}")
        logger.info(f"Audio data received, length: {len(request_data.audio_data)}")
        
        # Check if we have an existing session with candidate information
        session_data = {}
        candidate_name_before = None
        if request_data.session_id and active_interviewer.session_manager: # <--- Use active_interviewer
            existing_session = active_interviewer.session_manager.get_session(request_data.session_id) # <--- Use active_interviewer
            if existing_session and "metadata" in existing_session:
                session_data = existing_session["metadata"]
                candidate_name_before = session_data.get('candidate_name')
                logger.info(f"Restored session data with candidate: {candidate_name_before or 'Unknown'}")
        
        # Extract base64 data from data URI format
        audio_data_str = request_data.audio_data
        if "base64," in audio_data_str:
            parts = audio_data_str.split("base64,")
            audio_data_str = parts[1]
        
        try:
            audio_bytes = base64.b64decode(audio_data_str)
        except Exception as e:
            logger.error(f"Error decoding base64 audio data: {e}")
            raise HTTPException(status_code=422, detail=f"Invalid base64 audio data: {str(e)}")
        
        if len(audio_bytes) < 200: # Minimal check for valid audio
            logger.warning(f"Audio data too small: {len(audio_bytes)} bytes, likely silent or corrupt")
            # Return a default response instead of erroring out, to keep flow smooth
            transcription = "I couldn't hear you clearly. Could you please repeat that?"
            ai_response_content = "I'm sorry, I didn't catch that. Could you say it again?"
            # run_interview not called, so create a basic response structure
            temp_session_id = request_data.session_id or active_interviewer._get_or_create_session(user_id)
            metadata = {}
            if active_interviewer.session_manager:
                current_session = active_interviewer.session_manager.get_session(temp_session_id)
                if current_session: metadata = current_session.get("metadata", {})

            return AudioTranscriptionResponse(
                transcription=transcription,
                response=ai_response_content,
                session_id=temp_session_id,
                interview_stage=metadata.get("interview_stage", InterviewStage.INTRODUCTION.value),
                audio_response_url=None, # No audio to respond with
                job_role=metadata.get("job_role"),
                requires_coding=metadata.get("requires_coding")
            )
            
        transcription_result = await voice_handler.transcribe_audio_bytes(
            audio_bytes,
            sample_rate=request_data.sample_rate, # Gemini will use its optimal/required rate
            channels=request_data.channels # Gemini will use its optimal/required channels
        )
        
        if isinstance(transcription_result, dict) and transcription_result.get("success", False):
            transcription = transcription_result.get("transcript", "")
            provider = transcription_result.get("provider", "gemini")
            logger.info(f"Transcription successful via {provider}.")
        else:
            error_msg = transcription_result.get("error", "Unknown transcription error") if isinstance(transcription_result, dict) else "Transcription failed"
            logger.error(f"Transcription failed: {error_msg}")
            # Default message for smoother UX
            transcription = "I'm having a bit of trouble understanding the audio."
        
        if not transcription.strip():
            transcription = "I couldn't hear anything clearly."

        # run_interview now returns a dictionary
        response_data = await active_interviewer.run_interview(
            user_id, 
            transcription, 
            request_data.session_id,
            job_role=request_data.job_role,
            seniority_level=request_data.seniority_level,
            required_skills=request_data.required_skills,
            job_description=request_data.job_description,
            requires_coding=request_data.requires_coding
        )
        
        ai_response_content = response_data["ai_response"]
        current_session_id = response_data["session_id"]
        current_interview_stage = response_data.get("interview_stage")

        metadata = {}
        if active_interviewer.session_manager:
            session = active_interviewer.session_manager.get_session(current_session_id)
            if session and "metadata" in session:
                metadata = session["metadata"]
        
        audio_response_url = None
        synthesized_audio_bytes = await voice_handler.speak(
            text=ai_response_content,
            voice=speech_config.get("tts_voice", "Aoede"), 
            play_audio=False # Server does not play audio
        )
        
        if synthesized_audio_bytes:
            audio_filename = f"{current_session_id}_{int(datetime.now().timestamp())}.wav"
            app_dir = os.path.dirname(os.path.abspath(__file__))
            audio_responses_dir = os.path.join(app_dir, "audio_responses")
            os.makedirs(audio_responses_dir, exist_ok=True)
            audio_path = os.path.join(audio_responses_dir, audio_filename)
            
            # Write a proper WAV file
            try:
                with wave.open(audio_path, 'wb') as wf:
                    wf.setnchannels(1)      # Mono - typical for Gemini TTS
                    wf.setsampwidth(2)      # 16-bit PCM - typical for Gemini TTS
                    wf.setframerate(24000)  # Standard Gemini TTS output rate
                    wf.writeframes(synthesized_audio_bytes)
                logger.info(f"Generated audio response at {audio_path} as proper WAV.")
            except Exception as e:
                logger.error(f"Error writing WAV file {audio_path}: {e}. Saving raw bytes as fallback.")
                # Fallback: Save raw bytes if wave writing fails (though this might be unplayable)
                with open(audio_path, 'wb') as f:
                    f.write(synthesized_audio_bytes)

            audio_response_url = f"/api/audio/response/{audio_filename}"
        else:
            logger.warning(f"Failed to generate audio response with Gemini TTS.")
        
        logger.info(f"[SERVER] transcribe_and_respond RETURN: transcription='{transcription[:50]}...', response='{ai_response_content[:50]}...', session_id='{current_session_id}', interview_stage='{current_interview_stage}', audio_url='{audio_response_url}'") # Added log
        return AudioTranscriptionResponse(
            transcription=transcription,
            response=ai_response_content,
            session_id=current_session_id,
            interview_stage=current_interview_stage, # Use stage from run_interview
            audio_response_url=audio_response_url,
            job_role=metadata.get("job_role"), # Keep these from potentially updated session metadata
            requires_coding=metadata.get("requires_coding")
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing audio: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/audio/upload", response_model=AudioTranscriptionResponse)
async def upload_audio_file(
    request: Request, # Added request parameter for logging
    file: UploadFile = File(...),
    session_id: Optional[str] = None, # Changed from Form to Query
    job_role: Optional[str] = None,
    seniority_level: Optional[str] = None,
    required_skills: Optional[List[str]] = None, # This will be tricky with form-data, consider JSON payload for complex types
    job_description: Optional[str] = None,
    requires_coding: Optional[bool] = None,
    current_user: User = Depends(get_current_active_user)
):
    if not voice_enabled or not voice_handler: # voice_handler still global
        raise HTTPException(status_code=501, detail="Voice processing not available")
    
    try:
        # Use user_id from the authenticated user
        user_id = current_user.id
        audio_bytes = await file.read()

        active_interviewer = request.app.state.interviewer # <--- Get from app.state
        if not active_interviewer:
            logger.error("Interviewer not available in app state for upload_audio_file")
            raise HTTPException(status_code=503, detail="Interview service not available.")

        if len(audio_bytes) < 200:
            logger.warning(f"Uploaded audio file too small: {len(audio_bytes)} bytes.")
            # Provide a default response
            transcription = "The uploaded audio was too short or unclear. Could you please try again?"
            ai_response_content = "I'm sorry, I couldn't process the uploaded audio. Please ensure it's clear and try again."
            # run_interview not called, so create a basic response structure
            temp_session_id = session_id or active_interviewer._get_or_create_session(user_id)
            metadata = {}
            if active_interviewer.session_manager:
                current_session = active_interviewer.session_manager.get_session(temp_session_id)
                if current_session: metadata = current_session.get("metadata", {})
            
            logger.info(f"[SERVER] upload_audio_file RETURN: transcription='{transcription[:50]}...', response='{ai_response_content[:50]}...', session_id='{temp_session_id}', interview_stage='{metadata.get('interview_stage')}', audio_url='{None}'") # Added log
            return AudioTranscriptionResponse(
                transcription=transcription,
                response=ai_response_content,
                session_id=temp_session_id,
                interview_stage=metadata.get("interview_stage", InterviewStage.INTRODUCTION.value),
                audio_response_url=None,
                job_role=metadata.get("job_role"),
                requires_coding=metadata.get("requires_coding")
            )

        transcription_result = await voice_handler.transcribe_audio_bytes(
            audio_bytes # Sample rate and channels will be handled by Gemini
        )
        
        if isinstance(transcription_result, dict) and transcription_result.get("success", False):
            transcription = transcription_result.get("transcript", "")
            provider = transcription_result.get("provider", "gemini")
            logger.info(f"Transcription successful via {provider} (file upload).")
        else:
            error_msg = transcription_result.get("error", "Unknown transcription error") if isinstance(transcription_result, dict) else "Transcription failed"
            logger.error(f"Transcription failed: {error_msg}")
            transcription = "I had trouble understanding the uploaded audio file."

        if not transcription.strip():
            transcription = "The uploaded audio file seems to be silent or unclear."
            
        # run_interview now returns a dictionary
        response_data = await active_interviewer.run_interview(
            user_id, 
            transcription, 
            session_id, # Pass original session_id
            job_role=job_role,
            seniority_level=seniority_level,
            required_skills=required_skills,
            job_description=job_description,
            requires_coding=requires_coding
        )
        
        ai_response_content = response_data["ai_response"]
        current_session_id = response_data["session_id"]
        current_interview_stage = response_data.get("interview_stage")

        metadata = {}
        if active_interviewer.session_manager:
            session = active_interviewer.session_manager.get_session(current_session_id)
            if session and "metadata" in session:
                metadata = session["metadata"]
        
        audio_response_url = None
        synthesized_audio_bytes = await voice_handler.speak(
            text=ai_response_content,
            voice=speech_config.get("tts_voice", "Aoede"),
            play_audio=False
        )
        
        if synthesized_audio_bytes:
            audio_filename = f"response_{current_session_id}_{int(datetime.now().timestamp())}.wav"
            app_dir = os.path.dirname(os.path.abspath(__file__))
            audio_responses_dir = os.path.join(app_dir, "audio_responses")
            os.makedirs(audio_responses_dir, exist_ok=True)
            audio_path = os.path.join(audio_responses_dir, audio_filename)
            
            # Write a proper WAV file
            try:
                with wave.open(audio_path, 'wb') as wf:
                    wf.setnchannels(1)      # Mono
                    wf.setsampwidth(2)      # 16-bit PCM
                    wf.setframerate(24000)  # Gemini TTS standard rate
                    wf.writeframes(synthesized_audio_bytes)
                logger.info(f"Generated audio response for upload at {audio_path} as proper WAV.")
            except Exception as e:
                logger.error(f"Error writing WAV file {audio_path} for upload: {e}. Saving raw bytes as fallback.")
                with open(audio_path, 'wb') as f:
                    f.write(synthesized_audio_bytes)
            
            audio_response_url = f"/api/audio/response/{audio_filename}"
        else:
            logger.warning(f"Failed to generate audio response for uploaded file with Gemini TTS.")
            
        logger.info(f"[SERVER] upload_audio_file RETURN: transcription='{transcription[:50]}...', response='{ai_response_content[:50]}...', session_id='{current_session_id}', interview_stage='{current_interview_stage}', audio_url='{audio_response_url}'") # Added log
        return AudioTranscriptionResponse(
            transcription=transcription,
            response=ai_response_content,
            session_id=current_session_id,
            interview_stage=current_interview_stage, # Use stage from run_interview
            audio_response_url=audio_response_url,
            job_role=metadata.get("job_role"), # Keep these from potentially updated session metadata
            requires_coding=metadata.get("requires_coding")
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing audio file upload: {e}", exc_info=True)
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
        media_type="audio/wav" # CHANGED back to audio/wav for .wav files
    )

@app.get("/api/health",
    responses={
        200: {"description": "Service is healthy"},
        500: {"description": "Service is unhealthy", "model": ErrorResponse}
    }
)
async def health_check(request: Request): # Add request: Request
    """
    Health check endpoint.
    
    This endpoint checks if the service is running properly and if the
    database connection is available.
    
    Returns:
        Status of the service and its components
    """
    try:
        # Access interviewer from app.state
        active_interviewer = request.app.state.interviewer
        if not active_interviewer:
            raise ValueError("AIInterviewer instance not found in application state.")

        # Check AI Interviewer is working
        session_count = len(active_interviewer.active_sessions)
        
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
    # Mount the static files under /static path
    app.mount("/static", StaticFiles(directory=os.path.join(frontend_build_path, "static")), name="static")
    
    # Use a catch-all route for serving the frontend, but only after all API routes are defined
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """
        Serve the React SPA for any non-API routes to handle client-side routing.
        """
        # Don't interfere with API routes
        if full_path.startswith("api/") or full_path.startswith("static/"):
            raise HTTPException(status_code=404, detail="Not found")
            
        index_path = os.path.join(frontend_build_path, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        
        # If we get here, the path wasn't found
        raise HTTPException(status_code=404, detail="Not found")
    
    logger.info(f"Frontend catch-all route registered for {frontend_build_path}")
else:
    logger.warning(f"Frontend build directory not found at {frontend_build_path}. Frontend will not be served.")

# Define models for coding challenge requests/responses
class CodingSubmissionRequest(BaseModel):
    challenge_id: str
    language: str # Added language field
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
    overall_summary: Optional[Dict[str, Any]] = Field(None, description="Overall summary of test case results") # ADDED

    class Config:
        schema_extra = {
            "example": {
                "status": "success",
                "challenge_id": "coding-challenge-123",
                "execution_results": {"test_results": {"passed": 5, "failed": 1, "total": 6}},
                "feedback": {"message": "Good solution that handles most cases correctly."},
                "evaluation": {"message": "Evaluation passed."},
                "overall_summary": {
                    "passed": True,
                    "test_results": {"passed": 5, "failed": 1, "total": 6},
                    "feedback": "Good solution that handles most cases correctly."
                }
            }
        }

class CodingHintResponse(BaseModel):
    status: str
    challenge_id: str
    hints: List[str]

class ChallengeCompleteRequest(BaseModel):
    message: str = Field(..., description="Message to include with submission, should contain detailed coding evaluation results from /api/coding/submit")
    user_id: str = Field(..., description="User ID")
    challenge_completed: bool = Field(True, description="Whether the challenge was successfully completed")
    evaluation_summary: Optional[Dict] = Field(None, description="Optional evaluation summary from /api/coding/submit endpoint")
    session_context: Optional[str] = Field(None, description="Optional context flag to indicate special handling, e.g. 'coding_feedback'")
    
    class Config:
        schema_extra = {
            "example": {
                "message": "I've completed the coding challenge. My solution passed all test cases.",
                "user_id": "user-123456",
                "challenge_completed": True,
                "evaluation_summary": {
                    "pass_count": 5,
                    "fail_count": 0,
                    "total_tests": 5,
                    "status": "success"
                },
                "session_context": "coding_feedback"
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
@limiter.limit("60/minute")
async def submit_code_solution(
    request: Request,
    submission: CodingSubmissionRequest,
    current_user: User = Depends(get_current_active_user)
):
    logger.info(f"[SUBMIT_CODE] Received submission for challenge_id: {submission.challenge_id}, session_id: {submission.session_id}, user_id (from submission): {submission.user_id}")
    active_interviewer = request.app.state.interviewer 
    
    if not active_interviewer or not active_interviewer.session_manager:
        logger.error("[SUBMIT_CODE] AI Interviewer (from app.state.interviewer) or Session Manager not initialized.")
        raise HTTPException(status_code=500, detail="AI Interviewer not available")

    # Prioritize user_id from token, fallback to submission
    user_id_from_token = current_user.id
    submission_user_id = submission.user_id or user_id_from_token
    
    # Ensure session_id is present
    if not submission.session_id:
        logger.warning("[SUBMIT_CODE] No session_id provided in submission.")
        raise HTTPException(status_code=400, detail="session_id is required for code submission.")
    
    session_id = submission.session_id

    try:
        # Validate session and user
        session_data = active_interviewer.session_manager.get_session(session_id)
        if not session_data:
            logger.warning(f"[SUBMIT_CODE] Session {session_id} not found.")
            raise HTTPException(status_code=404, detail="Session not found.")

        session_metadata = session_data.get("metadata", {})
        if not isinstance(session_metadata, dict):
            logger.warning(f"Metadata for session {session_id} is not a dict. Re-initializing.")
            session_metadata = {}

        # Check ownership of session
        session_owner_user_id = session_metadata.get("user_id", session_data.get("user_id"))

        if session_owner_user_id and session_owner_user_id != user_id_from_token:
            logger.warning(f"User ID mismatch for session {session_id}. Submission user: {submission_user_id}, Session owner: {session_owner_user_id}")

        # Retrieve challenge details from session metadata
        challenge_details_from_session = session_metadata.get("current_coding_challenge_details_for_submission")
        
        if not challenge_details_from_session or not isinstance(challenge_details_from_session, dict):
            logger.error(f"[SUBMIT_CODE] Coding challenge details not found or invalid in session {session_id} metadata.")
            raise HTTPException(status_code=400, detail="Coding challenge details not found in session. Please start a challenge first.")

        # Strip common markdown fences from code if present
        stripped_code = submission.code
        if submission.code.strip().startswith("```") and submission.code.strip().endswith("```"):
            lines = submission.code.strip().split('\n')
            if len(lines) > 1:
                stripped_code = '\n'.join(lines[1:-1])

        # Prepare challenge data for tool
        challenge_data_for_tool = {
            "challenge_id": submission.challenge_id,
            "test_cases": challenge_details_from_session.get("test_cases", []),
            "reference_solution": challenge_details_from_session.get("reference_solution", ""),
            "evaluation_criteria": challenge_details_from_session.get("evaluation_criteria", {}),
            "language": submission.language,
            "problem_statement": challenge_details_from_session.get("problem_statement", ""),
            "title": challenge_details_from_session.get("title", ""),
            "description": challenge_details_from_session.get("description", ""),
            "difficulty": challenge_details_from_session.get("difficulty", "intermediate"),
            "starter_code": challenge_details_from_session.get("starter_code", "")
        }

        tool_input_args = {
            "challenge_data": challenge_data_for_tool,
            "candidate_code": stripped_code,
            "skill_level": session_metadata.get("seniority_level", "intermediate")
        }

        # Call the code evaluation tool
        try:
            evaluation_results_dict = await submit_code_for_generated_challenge.ainvoke(tool_input_args)
            
            # Now call the rubric evaluation tool
            rubric_evaluation_json = await evaluate_coding_submission_with_rubric.ainvoke({
                "code": stripped_code,
                "execution_results": evaluation_results_dict.get("execution_results", {}),
                "problem_statement": challenge_data_for_tool["problem_statement"],
                "language": submission.language
            })
            
            # Parse the rubric evaluation JSON
            rubric_evaluation = json.loads(rubric_evaluation_json)
            
            # Store rubric evaluation in session metadata for feedback stage
            session_metadata["rubric_evaluation"] = rubric_evaluation
            
        except Exception as tool_error:
            logger.error(f"[SUBMIT_CODE] Error calling evaluation tools: {tool_error}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Error processing code submission: {str(tool_error)}")

        if not isinstance(evaluation_results_dict, dict):
            logger.error(f"[SUBMIT_CODE] Tool submit_code_for_generated_challenge did not return a dictionary. Received: {type(evaluation_results_dict)}")
            raise HTTPException(status_code=500, detail="Internal error: Code evaluation tool returned an unexpected format.")

        # Prepare the final response
        final_status = evaluation_results_dict.get("status", "error")
        final_challenge_id = evaluation_results_dict.get("challenge_id", submission.challenge_id)
        final_execution_results = evaluation_results_dict.get("execution_results", {})
        final_feedback = evaluation_results_dict.get("feedback", {})
        final_evaluation = evaluation_results_dict.get("evaluation", {})

        # Construct overall summary
        overall_summary_data = {
            "pass_count": final_execution_results.get("pass_count", final_execution_results.get("detailed_results", {}).get("passed", 0)),
            "fail_count": final_execution_results.get("fail_count", final_execution_results.get("detailed_results", {}).get("failed", 0)),
            "total_tests": final_execution_results.get("total_tests", 0),
            "status_text": "UNKNOWN",
            "error_message": final_execution_results.get("errors"),
            "all_tests_passed": False
        }

        if overall_summary_data["total_tests"] == 0 and isinstance(final_execution_results.get("detailed_results", {}).get("test_results"), list):
            overall_summary_data["total_tests"] = len(final_execution_results["detailed_results"]["test_results"])
        
        if overall_summary_data["total_tests"] > 0:
            if overall_summary_data["pass_count"] == overall_summary_data["total_tests"] and overall_summary_data["fail_count"] == 0:
                overall_summary_data["status_text"] = "ALL TESTS PASSED"
                overall_summary_data["all_tests_passed"] = True
            elif overall_summary_data["pass_count"] > 0:
                overall_summary_data["status_text"] = f"{overall_summary_data['pass_count']}/{overall_summary_data['total_tests']} TESTS PASSED"
            else:
                overall_summary_data["status_text"] = "ALL TESTS FAILED"
        elif final_execution_results.get("status") == "error":
             overall_summary_data["status_text"] = "EXECUTION ERROR"

        # Save snapshot of submission
        snapshot_timestamp = submission.timestamp or datetime.now().isoformat()
        snapshot_data = {
            "challenge_id": submission.challenge_id,
            "code": stripped_code,
            "timestamp": snapshot_timestamp,
            "event_type": "submission",
            "execution_results": final_execution_results,
            "user_id": submission_user_id,
            "rubric_evaluation": rubric_evaluation  # Include rubric evaluation in snapshot
        }
        
        if "code_snapshots" not in session_metadata:
            session_metadata["code_snapshots"] = []
        elif not isinstance(session_metadata["code_snapshots"], list):
            session_metadata["code_snapshots"] = []
            
        session_metadata["code_snapshots"].append(snapshot_data)
        
        # Keep stage as CODING_CHALLENGE_WAITING - don't change to FEEDBACK yet
        session_metadata[INTERVIEW_STAGE_KEY] = InterviewStage.CODING_CHALLENGE_WAITING.value
        
        try:
            active_interviewer.session_manager.update_session_metadata(session_id, session_metadata)
            logger.info(f"Updated session metadata for {session_id} after code submission, stage kept as CODING_CHALLENGE_WAITING.")
        except Exception as e_meta_update:
            logger.error(f"Error updating session metadata after code submission for {session_id}: {e_meta_update}", exc_info=True)

        return CodingSubmissionResponse(
            status=final_status,
            challenge_id=final_challenge_id,
            execution_results=final_execution_results,
            feedback=final_feedback,
            evaluation=final_evaluation,
            overall_summary=overall_summary_data
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[SUBMIT_CODE] Unexpected error processing submission for session {session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

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
@limiter.limit("60/minute")
async def get_coding_hint(
    request: Request,
    hint_request: CodingHintRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    Get a hint for a coding challenge based on current code.
    
    The authenticated user's ID will be used.
    
    This endpoint processes the current code and returns targeted hints to help the candidate.
    
    Args:
        hint_request: CodingHintRequest containing the current code and challenge ID
        
    Returns:
        CodingHintResponse with hints
    """
    try:
        # Generate timestamp if not provided
        timestamp = hint_request.timestamp or datetime.now().isoformat()
        
        # Use user_id from the authenticated user
        user_id_from_token = current_user.id
        
        logger.info(f"Attempting to generate hint for challenge: {hint_request.challenge_id}")

        # Call the get_coding_hint tool
        from ai_interviewer.tools.coding_tools import get_coding_hint
        
        # Use the invoke method instead of direct calling
        result = get_coding_hint.invoke({
            "challenge_id": hint_request.challenge_id,
            "current_code": hint_request.code,
            "error_message": hint_request.error_message
        })
        
        logger.info(f"Successfully generated hint for challenge: {hint_request.challenge_id}")
        
        # If session ID is provided, store code snapshot for tracking hint requests
        if hint_request.session_id and request.app.state.interviewer and request.app.state.interviewer.session_manager: 
            # Get interviewer instance from app state
            interviewer_instance = request.app.state.interviewer
            logger.info(f"Storing hint request in session: {hint_request.session_id}")
            
            session = interviewer_instance.session_manager.get_session(hint_request.session_id)
            if session:
                # Verify session ownership
                if session.get("user_id") != user_id_from_token:
                    logger.warning(f"Session ownership verification failed. User {user_id_from_token} tried to access session {hint_request.session_id}")
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User does not own this session.")
                
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
                interviewer_instance.session_manager.update_session_metadata(hint_request.session_id, metadata)
                
                # Log the hint request event
                logger.info(f"Stored hint request snapshot for session {hint_request.session_id}, challenge {hint_request.challenge_id}")
        
        # If hints weren't generated, provide fallback hints
        if not result.get("hints") or len(result.get("hints", [])) == 0:
            logger.warning(f"No hints were generated for challenge {hint_request.challenge_id}, adding fallback hints")
            result["hints"] = [
                "Break the problem down into smaller steps.",
                "Check for edge cases in your solution.",
                "Review the problem statement carefully for any specific requirements."
            ]
            result["status"] = "success"
            result["challenge_id"] = hint_request.challenge_id
        
        return result
    except Exception as e:
        logger.error(f"Error getting coding hint: {e}")
        logger.exception("Detailed exception info:")
        
        # Return a valid CodingHintResponse even in case of error
        return {
            "status": "error",
            "challenge_id": hint_request.challenge_id if hint_request else "unknown",
            "hints": [
                "Sorry, I couldn't generate a specific hint right now.",
                "Try breaking the problem down into smaller steps.",
                "Make sure your code syntax is correct."
            ]
        }

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
@limiter.limit("60/minute")
async def continue_after_challenge(
    request: Request,
    session_id: str,
    request_data: ChallengeCompleteRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Continue the interview after completing a coding challenge."""
    try:
        if not request_data.user_id:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"detail": "Missing user ID."}
            )
            
        # Get the memory manager and session manager from app state
        memory_manager = request.app.state.memory_manager
        session_manager = request.app.state.session_manager if hasattr(request.app.state, 'session_manager') else None
        
        if not memory_manager:
            memory_manager = await setup_memory_manager_async()
        if not session_manager:
            from ai_interviewer.utils.session_manager import SessionManager
            db_cfg = get_db_config()
            session_manager = SessionManager(connection_uri=memory_manager.connection_uri,
                                          database_name=memory_manager.db_name,
                                          collection_name=db_cfg["metadata_collection"])
            request.app.state.session_manager = session_manager

        # Initialize the interviewer with the memory manager
        interviewer = await setup_ai_interviewer_async(memory_manager)
        
        # Get current session metadata
        session_record = session_manager.get_session(session_id)
        if not session_record:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"detail": f"Session {session_id} not found."}
            )
        metadata = session_record.get("metadata", {})
        
        # Get the latest code submission and rubric evaluation
        code_snapshots = metadata.get("code_snapshots", [])
        latest_code = code_snapshots[-1] if code_snapshots else {}
        rubric_evaluation = metadata.get("rubric_evaluation", {})
        
        # Update metadata with feedback context
        metadata["session_context"] = request_data.session_context or "coding_feedback"
        metadata["challenge_completed"] = request_data.challenge_completed
        if request_data.evaluation_summary:
            metadata["last_evaluation"] = request_data.evaluation_summary
        
        # Set interview stage to feedback
        metadata[INTERVIEW_STAGE_KEY] = InterviewStage.FEEDBACK.value
        logger.info(f"Setting interview stage to FEEDBACK for session {session_id} before calling run_interview.")
        session_manager.update_session_metadata(session_id, metadata)
        
        # Build enhanced message with rich evaluation context
        candidate_code_section = ""
        execution_results_section = ""
        structured_feedback_section = ""

        # Add code from latest submission
        if latest_code:
            language = latest_code.get("language", "python").lower()
            code = latest_code.get("code", "")
            if code:
                candidate_code_section = f"\nCandidate code (language: {language}):\n```{language}\n{code}\n```\n"

        # Add execution results
        if latest_code.get("execution_results"):
            exec_json = json.dumps(latest_code["execution_results"], indent=2)[:4000]
            execution_results_section = f"\nExecution results:\n```json\n{exec_json}\n```\n"

        # Add rubric evaluation
        if rubric_evaluation:
            feedback_json = json.dumps(rubric_evaluation, indent=2)[:4000]
            structured_feedback_section = f"\nStructured Feedback Analysis:\n```json\n{feedback_json}\n```\n"

        enhanced_message = f"""SYSTEM INSTRUCTION: This is a code feedback session. The user has completed a coding challenge and needs specific feedback.
CRITICAL INSTRUCTIONS:
1. DO NOT send any form of greeting or welcome message
2. DO NOT say \"I see you've already started an interview\" or similar
3. DO NOT start a new conversation
4. MAINTAIN feedback stage and provide detailed code review
5. FOCUS on the code submission and specific feedback
6. USE the rubric evaluation to provide structured feedback

{candidate_code_section}{execution_results_section}{structured_feedback_section}"""

        # Run interview with feedback context
        result = await interviewer.run_interview(
            user_id=request_data.user_id,
            user_message=enhanced_message,
            session_id=session_id,
            handle_digression=False
        )
        
        # Create response object
        response = {
            "response": result.get("response", ""),
            "session_id": session_id,
            "interview_stage": InterviewStage.FEEDBACK.value,  # Explicitly set to feedback
            "job_role": metadata.get("job_role"),
            "requires_coding": metadata.get("requires_coding", True),
            "coding_challenge_detail": None,  # Not needed in feedback stage
            "rubric_evaluation": rubric_evaluation  # Include rubric evaluation in response
        }
        
        # Update metadata one final time to ensure stage persists
        metadata[INTERVIEW_STAGE_KEY] = InterviewStage.FEEDBACK.value
        session_manager.update_session_metadata(session_id, metadata)
        
        logger.info(f"[SERVER] continue_after_challenge RETURN: response='{result.get('response', '')[:50]}...', session_id='{session_id}', interview_stage='feedback'")
        return response

    except Exception as e:
        logger.error(f"Error in continue_after_challenge: {str(e)}")
        logger.exception(e)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": f"Failed to continue interview after challenge: {str(e)}"}
        )

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
    dependencies=[Depends(log_request_time), Depends(RoleChecker([UserRole.INTERVIEWER, UserRole.ADMIN]))]
)
@limiter.limit("20/minute")
async def generate_question(
    request: Request,
    req_data: QuestionGenerationRequest,
    current_user: User = Depends(RoleChecker([UserRole.INTERVIEWER, UserRole.ADMIN])) # Ensure current_user is populated for RoleChecker
):
    """
    Generate a dynamic interview question based on job role and other parameters.
    
    This endpoint is protected and requires INTERVIEWER or ADMIN role.
    
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
    dependencies=[Depends(log_request_time), Depends(RoleChecker([UserRole.INTERVIEWER, UserRole.ADMIN]))]
)
@limiter.limit("60/minute")
async def analyze_response(
    request: Request,
    req_data: ResponseAnalysisRequest,
    current_user: User = Depends(RoleChecker([UserRole.INTERVIEWER, UserRole.ADMIN])) # Ensure current_user is populated for RoleChecker
):
    """
    Analyze a candidate's response to identify strengths, weaknesses, and potential follow-up areas.
    
    This endpoint is protected and requires INTERVIEWER or ADMIN role.
    
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
    current_user: User = Depends(get_current_active_user)
):
    if not interviewer_instance or not interviewer_instance.session_manager:
        raise HTTPException(status_code=503, detail="Session management not available")
    
    # Verify user owns the session or is admin
    session_data = interviewer_instance.session_manager.get_session(session_id)
    if not session_data:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Ensure that current_user.id matches session_data.get('user_id') or current_user.role is admin
    # This check depends on how user_id is stored in session_data and User model structure
    # Assuming session_data['user_id'] and current_user.id are comparable
    if not (str(session_data.get('user_id')) == str(current_user.id) or current_user.role == UserRole.ADMIN):
        logger.warning(f"Unauthorized attempt to access snapshots for session {session_id} by user {current_user.id}")
        raise HTTPException(status_code=403, detail="Not authorized to access these snapshots")

    try:
        snapshots = interviewer_instance.session_manager.get_code_snapshots(session_id, challenge_id)
        return snapshots
    except Exception as e:
        logger.error(f"Error retrieving snapshots for session {session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve snapshots: {str(e)}")

# New Models for Run Code functionality
class CodeRunRequest(BaseModel):
    language: str = Field(..., description="Programming language (e.g., 'python', 'javascript')")
    code: str = Field(..., description="Source code to execute")
    input_str: Optional[str] = Field("", description="String to pass as standard input to the code")
    user_id: Optional[str] = Field(None, description="User ID for logging or context")
    session_id: Optional[str] = Field(None, description="Session ID for logging or context")

    class Config:
        schema_extra = {
            "example": {
                "language": "python",
                "code": "print(input())",
                "input_str": "Hello, Sandbox!",
                "user_id": "user-123",
                "session_id": "session-abc"
            }
        }

class CodeRunResponse(BaseModel):
    status: str = Field(..., description="Execution status (e.g., 'success', 'error')")
    stdout: str = Field(..., description="Standard output from the code execution")
    stderr: str = Field(..., description="Standard error from the code execution")
    error_message: Optional[str] = Field(None, description="Specific error message if execution failed")
    execution_time: Optional[float] = Field(None, description="Execution time in seconds, if available")

    class Config:
        schema_extra = {
            "example": {
                "status": "success",
                "stdout": "Hello, Sandbox!",
                "stderr": "",
                "error_message": None,
                "execution_time": 0.123
            }
        }
# End of New Models for Run Code functionality

@app.post(
    "/api/coding/run",
    response_model=CodeRunResponse,
    responses={
        200: {"description": "Successfully executed code"},
        400: {"description": "Bad request - missing required fields or unsupported language", "model": ErrorResponse},
        422: {"description": "Validation Error", "model": ErrorResponse},
        429: {"description": "Rate limit exceeded", "model": ErrorResponse},
        500: {"description": "Internal server error or execution failed", "model": ErrorResponse}
    },
    dependencies=[Depends(log_request_time)]
)
@limiter.limit("20/minute")
async def run_code_in_sandbox(
    request: Request,
    run_request: CodeRunRequest,
    current_user: User = Depends(get_current_active_user)
):
    logger.info(f"Received request to run code in sandbox for language: {run_request.language}, user: {run_request.user_id or current_user.id}")
    
    # Get DockerSandbox instance from app state
    sandbox = getattr(request.app.state, 'docker_sandbox', None)
    if not sandbox:
        logger.error("DockerSandbox not available in app state. Cannot execute code.")
        raise HTTPException(status_code=500, detail="Code execution sandbox is not configured or unavailable.")

    try:
        # Ensure that language is supported by the sandbox
        supported_languages = ["python", "javascript", "js"] # Can be expanded
        if run_request.language.lower() not in supported_languages:
            raise HTTPException(status_code=400, detail=f"Unsupported language: {run_request.language}. Supported: {', '.join(supported_languages)}")

        # Execute code using the sandbox
        execution_result = await sandbox.execute_code_with_stdin(
            language=run_request.language,
            code=run_request.code,
            input_str=run_request.input_str or "" # Ensure input_str is not None
        )
        
        logger.info(f"Code execution result: {execution_result.get('status')}, stdout: {execution_result.get('stdout', '')[:100]}..., stderr: {execution_result.get('stderr', '')[:100]}...")

        # Determine status code based on execution result
        if execution_result.get("status") == "success":
            return CodeRunResponse(
                status="success",
                stdout=execution_result.get("stdout", ""),
                stderr=execution_result.get("stderr", ""),
                error_message=None, # No error message for success
                execution_time=execution_result.get("execution_time") 
            )
        else: # Covers "error" or any other non-success status
            # For errors, FastAPI will return 500 if not caught by specific HTTPException
            # We can customize the response more if needed
            error_message = execution_result.get("error_message", "Unknown execution error")
            
            # If it's a timeout, return 408 (Request Timeout) or a custom error
            if "timed out" in error_message.lower():
                 raise HTTPException(status_code=408, detail=f"Execution timed out. {error_message}")

            # For other errors, a 500 might be appropriate, or a 400 if it's due to bad code.
            # Let's use 400 if there's stderr, implying a code issue, else 500.
            status_code = 400 if execution_result.get("stderr") else 500
            
            # Raise HTTPException to ensure proper error propagation and logging by FastAPI
            raise HTTPException(
                status_code=status_code, 
                detail=f"Code execution failed: {error_message}. STDOUT: {execution_result.get('stdout', '')[:200]} STDERR: {execution_result.get('stderr', '')[:200]}"
            )

    except HTTPException as http_exc: # Re-raise HTTPExceptions to let FastAPI handle them
        raise http_exc
    except Exception as e:
        logger.error(f"Unexpected error during code execution: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during code execution: {str(e)}")

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
async def update_context_settings(
    request: Request,
    settings: ContextSettingsRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    Update context management settings for an interview session.
    
    The authenticated user's ID will be verified against the session.
    
    This endpoint allows configuring how the system manages long-running conversations,
    such as the threshold for when to summarize older content.
    """
    try:
        # Verify the session exists
        session = interviewer_instance.session_manager.get_session(settings.session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session {settings.session_id} not found")
        
        # Verify session ownership
        if session.get("user_id") != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User does not own this session.")

        # Configure context management settings
        success = interviewer_instance.session_manager.configure_context_management(
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
async def get_conversation_summary(
    request: Request,
    session_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Get the current conversation summary for an interview session.
    
    The authenticated user's ID will be verified against the session.
    
    This endpoint retrieves the AI-generated summary of earlier parts of the conversation
    that have been condensed to manage context length.
    """
    try:
        # Verify the session exists
        session = interviewer_instance.session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        
        # Verify session ownership
        if session.get("user_id") != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User does not own this session.")

        # Get the current summary
        summary = interviewer_instance.session_manager.get_conversation_summary(session_id)
        
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
@limiter.limit("60/minute")
async def force_summarize_conversation(
    request: Request,
    req_data: ForceSummarizeRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    Force the system to summarize the current conversation.
    
    The authenticated user's ID will be used and verified against the session.
    
    This endpoint manually triggers the context management system to generate a summary
    of the conversation so far, reducing the message history while preserving key information.
    """
    try:
        # Verify the session exists and belongs to the user
        session = interviewer_instance.session_manager.get_session(req_data.session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session {req_data.session_id} not found")
        
        # Verify user_id from request matches token and session owner
        if req_data.user_id != current_user.id:
             raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User ID in request does not match authenticated user.")
        if session.get("user_id") != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User ID does not match session owner")
        
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
        current_summary = interviewer_instance.session_manager.get_conversation_summary(req_data.session_id) or ""
        
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
        summary_response = interviewer_instance.summarization_model.invoke(summary_prompt)
        new_summary = summary_response.content if hasattr(summary_response, 'content') else ""
        
        # Update the session with the new summary and reduced message list
        interviewer_instance.session_manager.update_conversation_summary(req_data.session_id, new_summary)
        
        # Create a list of messages to keep - the most recent ones
        kept_messages = message_objects[-messages_to_keep:] if len(message_objects) > messages_to_keep else []
        interviewer_instance.session_manager.reduce_message_history(req_data.session_id, kept_messages)
        
        # Update message count in metadata
        metadata = session.get("metadata", {})
        metadata["message_count"] = len(kept_messages)
        interviewer_instance.session_manager.update_session_metadata(req_data.session_id, metadata)
        
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
async def get_interview_insights(
    request: Request,
    session_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Get structured insights extracted from the interview for a given session.
    
    The authenticated user's ID will be verified against the session.
    
    This endpoint retrieves AI-extracted structured information about the candidate,
    including skills, experiences, and areas of strength/improvement.
    
    Args:
        session_id: Session ID to get insights for
        current_user: The authenticated user.
        
    Returns:
        Structured interview insights extracted from the conversation
    """
    try:
        # Verify session exists
        if not interviewer_instance or not interviewer_instance.session_manager:
            raise HTTPException(status_code=500, detail="Session manager not available")
            
        session = interviewer_instance.session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
            
        # Verify it matches the session's user_id
        if session.get("user_id") != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User ID does not match session owner or user lacks permission.")
            
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
@limiter.limit("60/minute")
async def extract_interview_insights(
    request: Request,
    req_data: ExtractInsightsRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    Manually trigger the extraction of insights from an interview session.
    
    The authenticated user's ID will be used and verified against the session.
    
    Args:
        req_data: ExtractInsightsRequest containing session ID and user ID
        current_user: The authenticated user.
        
    Returns:
        Structured interview insights extracted from the conversation
    """
    try:
        # Verify the session exists and belongs to the user
        session = interviewer_instance.session_manager.get_session(req_data.session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session {req_data.session_id} not found")
        
        # Verify user_id from request matches token and session owner
        if req_data.user_id != current_user.id:
             raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User ID in request does not match authenticated user.")
        if session.get("user_id") != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User ID does not match session owner")
        
        # Trigger insights extraction
        insights = await interviewer_instance.extract_and_update_insights(req_data.session_id)
        
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

class ProblemGenerationRequest(BaseModel):
    """Request model for problem generation."""
    job_description: str = Field(..., description="Description of the job position")
    skills_required: List[str] = Field(..., description="List of required technical skills")
    difficulty_level: str = Field("intermediate", description="Desired difficulty level (beginner, intermediate, advanced)")

    class Config:
        schema_extra = {
            "example": {
                "job_description": "We're looking for a Python backend developer with strong experience in API development and data structures.",
                "skills_required": ["Python", "FastAPI", "Data Structures", "Algorithms"],
                "difficulty_level": "intermediate"
            }
        }

class CodingProblemResponse(BaseModel):
    """Response model for coding problem generation."""
    problem_statement: str = Field(..., description="Clear description of the problem")
    test_cases: List[Dict[str, Any]] = Field(..., description="List of test cases")
    reference_solution: str = Field(..., description="Reference solution in Python")
    difficulty_level: str = Field(..., description="Difficulty level of the problem")
    skills_targeted: List[str] = Field(..., description="Skills being tested")

    class Config:
        schema_extra = {
            "example": {
                "problem_statement": "Write a function to find the longest palindromic substring",
                "test_cases": [{"input": "babad", "expected": "bab"}],
                "reference_solution": "def longest_palindrome(s): ...",
                "difficulty_level": "intermediate",
                "skills_targeted": ["dynamic programming", "string manipulation"]
            }
        }

@app.post(
    "/api/coding/generate-problem",
    response_model=CodingProblemResponse,
    responses={
        200: {"description": "Successfully generated coding problem"},
        429: {"description": "Rate limit exceeded", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    },
    dependencies=[Depends(log_request_time), Depends(RoleChecker([UserRole.INTERVIEWER, UserRole.ADMIN]))]
)
@limiter.limit("60/minute")
async def generate_coding_problem(request: Request, req_data: ProblemGenerationRequest):
    """Generate a coding problem based on job requirements and difficulty level."""
    try:
        result = await generate_coding_challenge_from_jd.ainvoke({
            "job_description": req_data.job_description,
            "skills_required": req_data.skills_required,
            "difficulty_level": req_data.difficulty_level
        })
        
        # Parse the JSON result
        parsed_result = json.loads(result)
        
        if parsed_result.get("status") == "success":
            challenge = parsed_result.get("challenge", {})
            return CodingProblemResponse(
                problem_statement=challenge.get("problem_statement", ""),
                test_cases=challenge.get("test_cases", []),
                reference_solution=challenge.get("reference_solution", ""),
                difficulty_level=challenge.get("difficulty_level", req_data.difficulty_level),
                skills_targeted=challenge.get("skills_targeted", req_data.skills_required)
            )
        else:
            raise HTTPException(status_code=500, detail="Failed to generate coding problem")
            
    except json.JSONDecodeError:
        logger.error("Failed to parse coding problem generation result")
        raise HTTPException(status_code=500, detail="Failed to parse problem generation result")
    except Exception as e:
        logger.error(f"Error generating coding problem: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating coding problem: {str(e)}")

# Move FeedbackSummaryResponse class definition here, before the endpoint
class FeedbackSummaryResponse(BaseModel):
    """Response model for feedback summary."""
    session_id: str = Field(..., description="Session ID")
    total_interactions: int = Field(..., description="Total number of feedback interactions")
    explored_areas: List[str] = Field(..., description="List of feedback areas explored")
    candidate_preferences: Dict[str, Any] = Field(..., description="Candidate's feedback preferences")
    has_rubric_evaluation: bool = Field(..., description="Whether rubric evaluation exists")
    rubric_score: Optional[float] = Field(None, description="Overall rubric score")
    rubric_percentage: Optional[float] = Field(None, description="Rubric score as percentage")
    trust_score: Optional[float] = Field(None, description="Trust score")
    last_interaction: Optional[str] = Field(None, description="Timestamp of last interaction")

    class Config:
        schema_extra = {
            "example": {
                "session_id": "sess-123",
                "total_interactions": 5,
                "explored_areas": ["rubric_scores", "code_quality"],
                "candidate_preferences": {"most_engaged": "code_quality"},
                "has_rubric_evaluation": True,
                "rubric_score": 3.2,
                "rubric_percentage": 80.0,
                "trust_score": 0.85,
                "last_interaction": "2023-12-01T10:30:00Z"
            }
        }

# ADDED: Feedback summary endpoint
@app.get(
    "/api/interview/{session_id}/feedback-summary",
    response_model=FeedbackSummaryResponse,
    responses={
        200: {"description": "Successfully retrieved feedback summary"},
        404: {"description": "Session not found", "model": ErrorResponse},
        429: {"description": "Rate limit exceeded", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    },
    dependencies=[Depends(log_request_time)]
)
@limiter.limit("30/minute")
async def get_feedback_summary(
    request: Request,
    session_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """Get feedback summary for an interview session."""
    try:
        # Get feedback memory manager
        feedback_memory = create_feedback_memory_manager()
        
        # Get feedback summary
        feedback_summary = feedback_memory.get_feedback_summary(session_id)
        if not feedback_summary:
            raise HTTPException(status_code=404, detail="No feedback found for this session")
        
        # Format feedback for TTS
        feedback_text = f"""Here's a summary of your interview feedback.

Overall Score: {feedback_summary.get('rubric_score', 0)}/4.0 ({feedback_summary.get('rubric_percentage', 0)}%)

We've explored the following areas:
"""
        for area in feedback_summary.get('explored_areas', []):
            feedback_text += f"- {area}\n"
        
        # Generate audio if TTS is available
        audio_response_url = None
        try:
            from ai_interviewer.utils.audio import text_to_speech
            audio_data = await text_to_speech(feedback_text)
            if audio_data:
                # Save audio file
                audio_filename = f"feedback_summary_{session_id}.wav"
                audio_path = os.path.join("audio_responses", audio_filename)
                os.makedirs("audio_responses", exist_ok=True)
                with open(audio_path, "wb") as f:
                    f.write(audio_data)
                audio_response_url = f"/api/audio/response/{audio_filename}"
        except Exception as e:
            logger.warning(f"Failed to generate audio for feedback summary: {e}")
        
        # Return response with audio URL if available
        return {
            "session_id": session_id,
            "total_interactions": feedback_summary.get('total_interactions', 0),
            "explored_areas": feedback_summary.get('explored_areas', []),
            "candidate_preferences": feedback_summary.get('candidate_preferences', {}),
            "has_rubric_evaluation": feedback_summary.get('has_rubric_evaluation', False),
            "rubric_score": feedback_summary.get('rubric_score'),
            "rubric_percentage": feedback_summary.get('rubric_percentage'),
            "trust_score": feedback_summary.get('trust_score'),
            "last_interaction": feedback_summary.get('last_interaction'),
            "audio_response_url": audio_response_url
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting feedback summary: {e}")
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
async def search_memories(
    request: Request,
    query_data: EnhancedMemoryQuery,
    current_user: User = Depends(get_current_active_user)
):
    """
    Search through cross-session memories for a specific user.
    Ensures the authenticated user can only search their own memories.
    """
    try:
        # Ensure user is searching their own memories
        if query_data.user_id != current_user.id:
            # If we want to allow admins/interviewers to search, we'd add RoleChecker here
            # and check roles. For now, strict self-search.
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only search your own memories."
            )

        if not hasattr(interviewer_instance, 'memory_manager') or not interviewer_instance.memory_manager:
            raise HTTPException(
                status_code=500,
                detail="Memory management is not available on this server instance"
            )
        
        memories = interviewer_instance.memory_manager.search_memories(
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
async def get_candidate_profile(
    request: Request,
    user_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Get a candidate's profile data from cross-session memory.
    Ensures the authenticated user can only access their own profile.
    """
    try:
        # Ensure user is requesting their own profile
        if user_id != current_user.id:
            # If we want to allow admins/interviewers to view, we'd add RoleChecker here
            # and check roles. For now, strict self-access.
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only access your own profile."
            )

        if not hasattr(interviewer_instance, 'memory_manager') or not interviewer_instance.memory_manager:
            raise HTTPException(
                status_code=500,
                detail="Memory management is not available on this server instance"
            )
        
        profile = interviewer_instance.memory_manager.get_candidate_profile(user_id)
        
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

# Create background task executor for non-blocking operations
background_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="bg_task")

def run_background_task(func, *args, **kwargs):
    """Run a function in the background without blocking the main thread."""
    def wrapper():
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Background task error: {e}")
    
    background_executor.submit(wrapper)

async def async_background_task(coro):
    """Run an async coroutine in the background."""
    try:
        await coro
    except Exception as e:
        logger.error(f"Async background task error: {e}")

# Batch operation queue for database efficiency
db_update_queue = []
last_batch_process = time.time()
BATCH_INTERVAL = 2.0  # Process batches every 2 seconds

async def process_db_batch():
    """Process queued database updates in batches."""
    global db_update_queue, last_batch_process
    
    if not db_update_queue:
        return
        
    try:
        # Get the session manager
        active_interviewer = getattr(app.state, 'interviewer', None)
        if not active_interviewer or not hasattr(active_interviewer, 'session_manager'):
            return
            
        session_manager = active_interviewer.session_manager
        
        # Group updates by type
        metadata_updates = []
        message_updates = []
        
        for update in db_update_queue:
            if update['type'] == 'metadata':
                metadata_updates.append({
                    'session_id': update['session_id'],
                    'metadata': update['metadata']
                })
                logger.info(f"Batch processing: queued metadata update for {update['session_id']} with job_role='{update['metadata'].get('job_role')}'")
            elif update['type'] == 'messages':
                message_updates.append({
                    'session_id': update['session_id'],
                    'message_count': update['message_count']
                })
        
        # Batch update metadata
        if metadata_updates:
            session_manager.batch_update_sessions(metadata_updates)
            
        # Clear processed updates
        db_update_queue.clear()
        last_batch_process = time.time()
        
        logger.info(f"Processed batch: {len(metadata_updates)} metadata, {len(message_updates)} message updates")
        
    except Exception as e:
        logger.error(f"Error processing database batch: {e}")
        db_update_queue.clear()  # Clear on error to prevent buildup

def queue_db_update(session_id: str, update_type: str, **kwargs):
    """Queue a database update for batch processing."""
    global db_update_queue, last_batch_process
    
    update = {
        'session_id': session_id,
        'type': update_type,
        'timestamp': time.time(),
        **kwargs
    }
    
    db_update_queue.append(update)
    
    # Process batch if it's been too long or queue is full
    current_time = time.time()
    if (current_time - last_batch_process > BATCH_INTERVAL or 
        len(db_update_queue) >= 10):
        asyncio.create_task(process_db_batch())

# Import models and functions needed for the report endpoint
from ai_interviewer.models.rubric import InterviewEvaluation
from ai_interviewer.tools.report_tools import _calculate_summary_statistics

# Detailed report response model
class DetailedReportResponse(BaseModel):
    session_id: str = Field(..., description="Session ID")
    candidate_name: str = Field("", description="Candidate name")
    job_role: str = Field("", description="Job role")
    timestamp: str = Field(..., description="Report generation timestamp")
    interview_data: Dict[str, Any] = Field(..., description="Interview data including questions and answers")
    evaluation_data: Dict[str, Any] = Field(..., description="Evaluation data with scores and feedback")
    summary_statistics: Dict[str, Any] = Field(..., description="Summary statistics from the evaluation")
    
    class Config:
        schema_extra = {
            "example": {
                "session_id": "abc123",
                "candidate_name": "John Doe",
                "job_role": "Software Engineer",
                "timestamp": "2023-06-15T14:30:00Z",
                "interview_data": {
                    "questions_and_answers": ["Tell me about yourself", "Explain REST API"],
                    "total_messages": 2,
                    "job_description": "We're looking for a Python backend developer with strong experience in API development and data structures.",
                    "required_skills": ["Python", "FastAPI", "Data Structures", "Algorithms"]
                },
                "evaluation_data": {
                    "qa_evaluations": [{"question": "scores...", "answer": "I am a software engineer...", "score": 4.5}, {"question": "Explain REST API", "answer": "REST API is...", "score": 4.0}],
                    "coding_evaluation": {"scores...": {}}
                },
                "summary_statistics": {
                    "qa_average": 4.2,
                    "coding_average": 3.8,
                    "overall_average": 4.0
                }
            }
        }

# Add this after the feedback-summary endpoint
@app.get(
    "/api/interview/{session_id}/detailed-report",
    response_model=DetailedReportResponse,
    responses={
        200: {"description": "Successfully retrieved detailed interview report"},
        404: {"description": "Session not found", "model": ErrorResponse},
        429: {"description": "Rate limit exceeded", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    },
    dependencies=[Depends(log_request_time)]
)
@limiter.limit("30/minute")
async def get_detailed_report(
    request: Request,
    session_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """Get detailed interview report for a session, including evaluation data and statistics."""
    try:
        if not ai_interviewer.session_manager:
            raise HTTPException(status_code=500, detail="Session management not available")
        
        # Get the interview memory data
        interview_memory = await ai_interviewer.session_manager.get_session_memory(session_id)
        if not interview_memory:
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        
        # Get the session state
        session_state = await ai_interviewer.resume_interview(session_id, current_user.id)
        if not session_state or not session_state[0]:
            raise HTTPException(status_code=404, detail=f"Session state for {session_id} not found")
        
        state = session_state[0]
        
        # Create feedback memory manager for getting evaluation data
        feedback_memory = create_feedback_memory_manager(ai_interviewer.session_manager)
        
        # Get interview messages
        messages = interview_memory.get_messages()
        
        # Extract Q&A pairs
        qa_pairs = []
        for i in range(0, len(messages) - 1, 2):
            if i+1 < len(messages):
                qa_pairs.append({
                    "question": messages[i].content,
                    "answer": messages[i+1].content
                })
        
        # Get evaluation data from feedback memory
        evaluation_data = feedback_memory.get_full_evaluation(session_id)
        
        # Calculate summary statistics if evaluation data exists
        summary_statistics = {}
        if evaluation_data and "qa_evaluations" in evaluation_data:
            try:
                eval_model = InterviewEvaluation(**evaluation_data)
                summary_statistics = _calculate_summary_statistics(eval_model)
            except Exception as e:
                logger.warning(f"Error calculating statistics: {str(e)}")
                summary_statistics = {
                    "qa_average": 0,
                    "coding_average": 0,
                    "overall_average": 0,
                    "total_questions": 0,
                    "coding_completed": False
                }
        
        # Build the response
        return DetailedReportResponse(
            session_id=session_id,
            candidate_name=state.candidate_name,
            job_role=state.job_role,
            timestamp=datetime.utcnow().isoformat(),
            interview_data={
                "questions_and_answers": qa_pairs,
                "total_messages": len(messages),
                "job_description": state.job_description,
                "required_skills": state.required_skills
            },
            evaluation_data=evaluation_data or {},
            summary_statistics=summary_statistics
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting detailed report for session {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving detailed report: {str(e)}")

if __name__ == "__main__":
    # Run the server directly if this module is executed
    start_server() 