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
from typing import Dict, Any, Optional, List, Literal, Union
from datetime import datetime
import inspect # <--- Import inspect
import contextlib # Add for lifespan manager

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
from starlette.middleware.sessions import SessionMiddleware # <--- ADD IMPORT

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

# Auth imports
from motor.motor_asyncio import AsyncIOMotorDatabase
from ai_interviewer.auth import routes as auth_routes
from ai_interviewer.auth.config import settings as auth_settings
from ai_interviewer.auth.security import get_current_active_user # <--- IMPORT
from ai_interviewer.models.user_models import User # <--- IMPORT
from ai_interviewer.auth.security import RoleChecker
from ai_interviewer.models.user_models import UserRole
from starlette import status

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

@contextlib.asynccontextmanager
async def lifespan(app_instance: FastAPI): # app_instance is the conventional name, FastAPI passes itself.
    logger.critical("--- LIFESPAN FUNCTION CALLED ---") 
    try:
        logger.info("Lifespan: Startup phase started.")
        # global memory_manager, interviewer # No longer need to modify globals here directly for app state
        
        # Initialize memory_manager
        logger.info("Lifespan: Attempting to setup memory_manager...")
        local_memory_manager = await setup_memory_manager_async()
        app_instance.state.memory_manager = local_memory_manager # Store in app state
        logger.info(f"Lifespan: memory_manager initialized and stored in app.state: {app_instance.state.memory_manager}")
        if hasattr(app_instance.state.memory_manager, 'db') and app_instance.state.memory_manager.db is not None:
            logger.info(f"Lifespan: app.state.memory_manager.db successfully configured: {app_instance.state.memory_manager.db}")
        else:
            logger.error("Lifespan: app.state.memory_manager.db is NOT configured after setup!")
            
        # Initialize interviewer
        logger.info("Lifespan: Attempting to setup interviewer...")
        local_interviewer = await setup_ai_interviewer_async(app_instance.state.memory_manager) # Pass memory_manager if needed
        app_instance.state.interviewer = local_interviewer # Store in app state
        logger.info(f"Lifespan: interviewer initialized and stored in app.state: {app_instance.state.interviewer}")

        # Initialize DockerSandbox
        logger.info("Lifespan: Attempting to setup DockerSandbox...")
        try:
            app_instance.state.docker_sandbox = DockerSandbox()
            logger.info(f"Lifespan: DockerSandbox initialized and stored in app.state: {app_instance.state.docker_sandbox}")
        except RuntimeError as e:
            logger.error(f"Lifespan: Failed to initialize DockerSandbox: {e}. Code execution will not work.")
            app_instance.state.docker_sandbox = None

        logger.info("Lifespan: Startup phase completed successfully.")
        yield
    except Exception as e:
        logger.critical(f"LIFESPAN EXCEPTION DURING STARTUP: {e}", exc_info=True)
        raise
    finally:
        logger.info("Lifespan: Shutdown phase started.")
        # Cleanup logic moved from deprecated on_event
        active_interviewer = getattr(app_instance.state, 'interviewer', None)
        if active_interviewer and hasattr(active_interviewer, 'cleanup'):
            try:
                active_interviewer.cleanup()
                logger.info("AI Interviewer resources cleaned up during lifespan shutdown")
            except Exception as e:
                logger.error(f"Error cleaning up AI Interviewer during lifespan shutdown: {e}")

        active_memory_manager = getattr(app_instance.state, 'memory_manager', None)
        if active_memory_manager:
            try:
                if hasattr(active_memory_manager, 'use_async') and active_memory_manager.use_async:
                    if hasattr(active_memory_manager, 'aclose'):
                        await active_memory_manager.aclose()
                        logger.info("Async memory manager closed during lifespan shutdown")
                elif hasattr(active_memory_manager, 'close'):
                    active_memory_manager.close()
                    logger.info("Sync memory manager closed during lifespan shutdown")
            except Exception as e:
                logger.error(f"Error closing memory manager during lifespan shutdown: {e}")
        
        # Clean up voice handler resources
        # voice_handler is still global for now, consider moving to app.state if it makes sense
        global voice_handler 
        if 'voice_handler' in globals() and voice_handler and hasattr(voice_handler, 'close'):
            try:
                voice_handler.close()
                logger.info("Voice handler resources cleaned up during lifespan shutdown")
            except Exception as e:
                logger.error(f"Error cleaning up voice handler during lifespan shutdown: {e}")
        logger.info("Lifespan: Shutdown phase completed.")

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
    allow_origins=["*"],  # Update with specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
    coding_challenge_detail: Optional[Dict[str, Any]] = Field(None, description="Structured details of the coding challenge, if applicable") # ADDED
    
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
                }
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
        200: {"description": "Successfully started interview"},
        429: {"description": "Rate limit exceeded", "model": ErrorResponse},
        500: {"description": "Internal server error", "model": ErrorResponse}
    },
    dependencies=[Depends(log_request_time)]
)
@limiter.limit("10/minute")
async def start_interview(
    request: Request, 
    request_data: MessageRequest,
    current_user: User = Depends(get_current_active_user) # <--- ADD DEPENDENCY
):
    """
    Start a new interview session for the authenticated user.
    
    The user_id from the JWT token will be used.
    
    Args:
        request_data: MessageRequest containing the user's message and optional user ID
        
    Returns:
        MessageResponse with the AI's response and session ID
    """
    try:
        # Use user_id from the authenticated user
        user_id = current_user.id # <--- USE ID FROM TOKEN
        
        logger.info(f"[SERVER] start_interview called. User ID: {user_id}")
        logger.info(f"[SERVER] Request data job_role: '{request_data.job_role}', seniority_level: '{request_data.seniority_level}'")

        active_interviewer = request.app.state.interviewer # <--- Get from app.state
        if not active_interviewer:
            logger.error("Interviewer not available in app state for start_interview")
            raise HTTPException(status_code=503, detail="Interview service not available.")

        # Process the user message with job role parameters
        # run_interview now returns a dictionary
        response_data = await active_interviewer.run_interview(
            user_id, 
            request_data.message,
            job_role=request_data.job_role,
            seniority_level=request_data.seniority_level,
            required_skills=request_data.required_skills,
            job_description=request_data.job_description,
            requires_coding=request_data.requires_coding
        )
        
        # Get session metadata if available (session_id is in response_data)
        metadata = {}
        if active_interviewer.session_manager and response_data.get("session_id"):
            session = active_interviewer.session_manager.get_session(response_data["session_id"])
            if session and "metadata" in session:
                metadata = session["metadata"] # This metadata might be slightly stale regarding stage
        
        logger.info(f"[SERVER] start_interview RETURN: response='{response_data['ai_response'][:50]}...', session_id='{response_data['session_id']}', interview_stage='{response_data.get('interview_stage')}', job_role='{metadata.get('job_role')}', requires_coding='{metadata.get('requires_coding')}', coding_challenge_detail_present={response_data.get('coding_challenge_detail') is not None}") # Added log
        return MessageResponse(
            response=response_data["ai_response"],
            session_id=response_data["session_id"],
            interview_stage=response_data.get("interview_stage"), # Use stage from run_interview
            job_role=metadata.get("job_role"), # Keep these from potentially updated session metadata
            requires_coding=metadata.get("requires_coding"),
            coding_challenge_detail=response_data.get("coding_challenge_detail") # ADDED
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
async def continue_interview(
    request: Request, 
    session_id: str, 
    request_data: MessageRequest,
    current_user: User = Depends(get_current_active_user) # <--- ADD DEPENDENCY
):
    """
    Continue an existing interview session for the authenticated user.
    
    The user_id from the JWT token will be used and validated against the session.
    
    Args:
        session_id: Session ID to continue
        request_data: MessageRequest containing the user's message and user ID
        
    Returns:
        MessageResponse with the AI's response and session ID
    """
    try:
        # Validate that the authenticated user owns this session or has rights to access it.
        # For now, we'll use current_user.id directly. 
        # More complex logic (e.g., admin access) can be added later.
        user_id_from_token = current_user.id

        active_interviewer = request.app.state.interviewer # <--- Get from app.state
        if not active_interviewer:
            logger.error("Interviewer not available in app state for continue_interview")
            raise HTTPException(status_code=503, detail="Interview service not available.")
        
        # Original request_data.user_id might be used for logging or other purposes, 
        # but the authoritative user_id is from the token.
        # We should ensure that the session being continued belongs to this user.
        # The AIInterviewer.run_interview should ideally handle this check if session_id is provided.
        # For now, let's pass the token user_id.
        
        # Process the user message with job role parameters (will only apply if session is new)
        # run_interview now returns a dictionary
        response_data = await active_interviewer.run_interview(
            user_id_from_token, # <--- USE ID FROM TOKEN
            request_data.message, 
            session_id,
            job_role=request_data.job_role,
            seniority_level=request_data.seniority_level,
            required_skills=request_data.required_skills,
            job_description=request_data.job_description,
            requires_coding=request_data.requires_coding
        )
        
        # Get session metadata if available (session_id is in response_data)
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
            coding_challenge_detail=response_data.get("coding_challenge_detail") # ADDED
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
        # Ensure the authenticated user is requesting their own sessions
        if current_user.id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="You do not have permission to access these sessions."
            )
        
        active_interviewer = request.app.state.interviewer # <--- Get from app.state
        if not active_interviewer:
            logger.error("Interviewer not available in app state for get_user_sessions")
            raise HTTPException(status_code=503, detail="Interview service not available.")
            
        sessions = active_interviewer.get_user_sessions(user_id, include_completed)
        
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
        media_type="audio/wav"
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
async def submit_code_solution(
    request: Request,
    submission: CodingSubmissionRequest,
    current_user: User = Depends(get_current_active_user)
):
    logger.info(
        f"Received code submission: Challenge ID: {submission.challenge_id}, "
        f"Language: {submission.language}, User ID: {submission.user_id or current_user.id}, "
        f"Session ID: {submission.session_id}, Code: {submission.code[:100]}..."
    )

    # Get the AIInterviewer instance from app state
    interviewer_instance = getattr(request.app.state, 'interviewer', None)

    if not interviewer_instance or not interviewer_instance.session_manager: # MODIFIED
        raise HTTPException(status_code=503, detail="Session management or interviewer not available")

    # Retrieve session metadata
    session_data = interviewer_instance.session_manager.get_session(submission.session_id) # MODIFIED
    if not session_data or "metadata" not in session_data:
        logger.error(f"Session {submission.session_id} not found or has no metadata.")
        raise HTTPException(status_code=404, detail="Session not found or invalid.")
    
    session_metadata = session_data["metadata"]
    
    # --- ADDED LOGS FOR FULL METADATA INSPECTION ---
    logger.info(f"[SUBMIT_CODE] Full session_metadata for session {submission.session_id}: {session_metadata}")
    # --- END ADDED LOGS ---
    
    # --- ADDED LOG ---
    raw_challenge_details_from_session = session_metadata.get("current_coding_challenge_details_for_submission")
    logger.info(f"[SUBMIT_CODE] Raw 'current_coding_challenge_details_for_submission' from session {submission.session_id}: {raw_challenge_details_from_session}")
    # --- END ADDED LOG ---

    # ADDED: Strip the submitted code
    candidate_submitted_code = submission.code.strip()
    logger.info(f"[SUBMIT_CODE] Original submitted code length: {len(submission.code)}, Stripped code length: {len(candidate_submitted_code)}")
    if len(submission.code) != len(candidate_submitted_code):
        logger.info(f"[SUBMIT_CODE] Whitespace was stripped. First 50 chars of stripped code: {candidate_submitted_code[:50]}")

    challenge_data = None # Initialize challenge_data

    # Validate and retrieve challenge_data from session_metadata
    # challenge_data_from_session = session_metadata.get("current_coding_challenge_details_for_submission") # Original line
    challenge_data_from_session = raw_challenge_details_from_session # Use the already fetched value

    if not isinstance(challenge_data_from_session, (dict, list)): # Check if it's a dict or list
        logger.warning(f"'current_coding_challenge_details_for_submission' in session {submission.session_id} is not a dict or list. Type: {type(challenge_data_from_session)}")
        raise HTTPException(status_code=400, detail="Invalid format for 'current_coding_challenge_details_for_submission' in session metadata")

    # --- ADDED LOG FOR TEST CASES ---
    retrieved_test_cases = challenge_data_from_session.get('test_cases') if isinstance(challenge_data_from_session, dict) else "Not a dict"
    logger.info(f"[SUBMIT_CODE] Test cases retrieved from session for challenge {submission.challenge_id}: {json.dumps(retrieved_test_cases, indent=2)}")
    if isinstance(retrieved_test_cases, list):
        logger.info(f"[SUBMIT_CODE] Number of test cases retrieved: {len(retrieved_test_cases)}")
    # --- END ADDED LOG ---

    try:
        # Assume skill_level might be part of session or a default
        # For now, using a default. This should ideally come from user context or session.
        skill_level = "intermediate" 
        if submission.session_id and interviewer_instance and interviewer_instance.session_manager:
            session_data = interviewer_instance.session_manager.get_session(submission.session_id)
            if session_data and session_data.get("metadata"):
                skill_level = session_data["metadata"].get("seniority_level", "intermediate") # Use seniority as proxy
                skill_level = skill_level.lower() if skill_level else "intermediate"
                if skill_level not in ["beginner", "intermediate", "advanced"]:
                    skill_level = "intermediate" # Default if not one of the expected

        tool_input_args = {
            "challenge_data": challenge_data_from_session,
            "candidate_code": candidate_submitted_code, # MODIFIED to use stripped code
            "skill_level": skill_level
        }
        evaluation_results_dict = await submit_code_for_generated_challenge.ainvoke(tool_input_args) # MODIFIED to use .ainvoke()

        # Ensure the response matches the CodingSubmissionResponse model
        # The tool's output structure is already very close.
        # CodingSubmissionResponse: status, challenge_id, execution_results, feedback, evaluation
        # Tool output: status, challenge_id, execution_results, feedback, evaluation

        if evaluation_results_dict.get("status") == "error":
             # If the tool itself returned an error (e.g. processing issue)
            logger.error(f"Tool 'submit_code_for_generated_challenge' returned an error: {evaluation_results_dict.get('message')}")
            # Return a 500 or a more specific error based on tool output
            return CodingSubmissionResponse(
                status="ERROR_TOOL_FAILURE",
                challenge_id=submission.challenge_id,
                execution_results={"message": evaluation_results_dict.get('message', "Tool execution failed")},
                feedback={"message": "Feedback generation failed due to tool error."},
                evaluation={"message": "Evaluation failed due to tool error."}
            )

        # Store code snapshot for submission event
        if submission.session_id and interviewer_instance and interviewer_instance.session_manager:
            session_data = interviewer_instance.session_manager.get_session(submission.session_id)
            if session_data:
                # Verify user ownership
                if session_data.get("user_id") != (submission.user_id or current_user.id):
                    logger.warning(f"User ID mismatch for session {submission.session_id}. Submission user: {submission.user_id or current_user.id}, Session owner: {session_data.get('user_id')}")
                    # Decide if this should be an error or just a warning
                
                metadata = session_data.get("metadata", {})
                code_snapshots = metadata.get("code_snapshots", [])
                
                snapshot = {
                    "challenge_id": submission.challenge_id,
                    "code": candidate_submitted_code, # MODIFIED to store stripped code
                    "timestamp": submission.timestamp or datetime.now().isoformat(),
                    "event_type": "submission",
                    "execution_results": evaluation_results_dict.get("execution_results"),
                    # "error_message": None, # No direct error message here, it's in execution_results
                    # "hints_provided": None 
                }
                code_snapshots.append(snapshot)
                metadata["code_snapshots"] = code_snapshots
                interviewer_instance.session_manager.update_session_metadata(submission.session_id, metadata)
                logger.info(f"Stored submission snapshot for session {submission.session_id}, challenge {submission.challenge_id}")

        # Construct overall_summary for the frontend
        overall_summary_data = None
        if "execution_results" in evaluation_results_dict and isinstance(evaluation_results_dict["execution_results"], dict):
            exec_res = evaluation_results_dict["execution_results"]
            overall_summary_data = {
                "pass_count": exec_res.get("pass_count", 0),
                "fail_count": exec_res.get("fail_count", (exec_res.get("total_tests", 0) - exec_res.get("pass_count", 0))),
                "total_tests": exec_res.get("total_tests", 0),
                "status_text": exec_res.get("status", "unknown").upper(), # Initialize status_text here
                "error_message": None,
                "all_tests_passed": False # Initialize all_tests_passed
            }
            
            # If the primary status is 'error', capture the error message
            if overall_summary_data["status_text"] == "ERROR":
                overall_summary_data["error_message"] = evaluation_results_dict["execution_results"].get("errors", "Unknown execution error")
            
            # Refine status_text based on counts if specific status isn't "ERROR"
            if overall_summary_data["status_text"] != "ERROR":
                if overall_summary_data["pass_count"] == overall_summary_data["total_tests"] and overall_summary_data["total_tests"] > 0:
                    overall_summary_data["status_text"] = "ALL TESTS PASSED"
                    overall_summary_data["all_tests_passed"] = True # Set all_tests_passed to True
                elif overall_summary_data["pass_count"] > 0 and overall_summary_data["pass_count"] < overall_summary_data["total_tests"]:
                    overall_summary_data["status_text"] = "SOME TESTS FAILED"
                elif overall_summary_data["total_tests"] > 0 and overall_summary_data["pass_count"] == 0:
                    overall_summary_data["status_text"] = "ALL TESTS FAILED"
                elif overall_summary_data["total_tests"] == 0:
                     overall_summary_data["status_text"] = "NO TESTS EXECUTED"

        # --- ADDED DETAILED LOGGING ---
        logger.info(f"[SUBMIT_CODE_FINAL_ASSEMBLY] evaluation_results_dict: {json.dumps(evaluation_results_dict, indent=2)}")
        logger.info(f"[SUBMIT_CODE_FINAL_ASSEMBLY] Constructed overall_summary_data: {json.dumps(overall_summary_data, indent=2)}")
        # --- END ADDED DETAILED LOGGING ---

        # --- MODIFICATION START: Update session with ToolMessage and set stage to FEEDBACK ---
        if interviewer_instance and interviewer_instance.session_manager:
            try:
                # Create a ToolMessage with the evaluation results
                # The 'name' of the tool that was conceptually called by the submission.
                # The 'tool_call_id' should ideally be unique or linked if possible.
                tool_call_id = f"eval_{submission.challenge_id}_{uuid.uuid4().hex[:4]}"
                
                # The content of the ToolMessage is typically a string representation of the tool's output.
                # submit_code_for_generated_challenge already returns a dict. We'll use its JSON string.
                tool_message_content = json.dumps(evaluation_results_dict)
                
                tool_message = ToolMessage(content=tool_message_content, tool_call_id=tool_call_id, name="submit_code_for_generated_challenge")
                
                # Add this ToolMessage to the session history
                # This assumes session_manager has a method like add_message_to_session or similar
                # For now, let's fetch messages, append, and update.
                # More robust way: interviewer_instance.workflow.update_state(...) if graph directly managed
                
                current_messages = session_data.get("messages", [])
                current_messages.append({
                    "type": "tool", # Storing as dict for now, as per current session format
                    "data": {
                        "content": tool_message_content,
                        "tool_call_id": tool_call_id,
                        # Add name if your AIMessage processing expects it for tool messages
                        "name": "submit_code_for_generated_challenge" 
                    }
                })
                session_data["messages"] = current_messages
                
                # Update the interview stage to FEEDBACK
                session_metadata["interview_stage"] = InterviewStage.FEEDBACK.value
                session_data["metadata"] = session_metadata # Ensure metadata is part of session_data being updated

                # Corrected session update:
                # 1. Update metadata (which includes the stage)
                interviewer_instance.session_manager.update_session_metadata(submission.session_id, session_metadata)
                
                # 2. Add the tool message to the session's message history
                # Assuming add_message_to_session handles storing the message appropriately
                interviewer_instance.session_manager.add_message_to_session(
                    session_id=submission.session_id,
                    message_content=tool_message_content, # This is the JSON string of evaluation_results_dict
                    role="tool",
                    # Pass name and tool_call_id if your add_message_to_session supports them as kwargs
                    # or if it expects a more structured message object.
                    # Based on the ToolMessage object created above:
                    name="submit_code_for_generated_challenge",
                    tool_call_id=tool_call_id 
                )
                logger.info(f"Session {submission.session_id} updated with ToolMessage and stage set to FEEDBACK using corrected methods.")

                # --- REVISED SESSION AND GRAPH STATE UPDATE (PART 1: Checkpoint) ---
                if interviewer_instance.checkpointer:
                    config = {"configurable": {"thread_id": submission.session_id}}
                    try:
                        checkpoint_tuple = await interviewer_instance.checkpointer.aget_tuple(config)
                        if checkpoint_tuple and checkpoint_tuple.checkpoint:
                            current_graph_messages = []
                            # Handle if checkpoint is a dict (common for LangGraph state)
                            if isinstance(checkpoint_tuple.checkpoint, dict):
                                current_graph_messages = checkpoint_tuple.checkpoint.get("messages", [])
                            # Handle if checkpoint is an InterviewState object itself
                            elif hasattr(checkpoint_tuple.checkpoint, "messages"):
                                current_graph_messages = checkpoint_tuple.checkpoint.messages
                            else:
                                logger.warning(f"Unrecognized checkpoint structure for session {submission.session_id}. Type: {type(checkpoint_tuple.checkpoint)}")
                                # Default to empty list if structure is unknown, or handle error

                            if not isinstance(current_graph_messages, list):
                                logger.error(f"Messages in checkpoint for session {submission.session_id} is not a list but {type(current_graph_messages)}. Re-initializing.")
                                current_graph_messages = []
                            
                            current_graph_messages.append(tool_message)
                            
                            # Update the messages back into the checkpoint structure
                            if isinstance(checkpoint_tuple.checkpoint, dict):
                                checkpoint_tuple.checkpoint["messages"] = current_graph_messages
                            elif hasattr(checkpoint_tuple.checkpoint, "messages"):
                                checkpoint_tuple.checkpoint.messages = current_graph_messages
                            
                            # Preserve existing metadata and parent_config from the tuple
                            await interviewer_instance.checkpointer.aput(
                                config, 
                                checkpoint_tuple.checkpoint, # The modified checkpoint object/dict
                                checkpoint_tuple.metadata, 
                                checkpoint_tuple.parent_config
                            )
                            logger.info(f"Appended ToolMessage to LangGraph checkpoint for session {submission.session_id}")
                        else:
                            logger.warning(f"Could not retrieve valid LangGraph checkpoint tuple for session {submission.session_id} to append ToolMessage.")
                    except Exception as e_checkpoint_get_put:
                        logger.error(f"Error getting or putting checkpoint for session {submission.session_id}: {e_checkpoint_get_put}", exc_info=True)
                else:
                    logger.warning(f"No checkpointer in interviewer_instance for session {submission.session_id}. Cannot append ToolMessage to graph state.")

                # --- (PART 2: Metadata update - temporarily commented out) ---
                # # Fetch fresh metadata to avoid overwriting concurrent updates
                # fresh_session_data = interviewer_instance.session_manager.get_session(submission.session_id)
                # if fresh_session_data and "metadata" in fresh_session_data:
                #     session_metadata_for_stage_update = fresh_session_data["metadata"]
                # else:
                #     logger.warning(f"Could not fetch fresh metadata for session {submission.session_id} before stage update. Using existing or empty metadata.")
                #     session_metadata_for_stage_update = session_metadata # Fallback to potentially stale
                # session_metadata_for_stage_update["interview_stage"] = InterviewStage.FEEDBACK.value
                # interviewer_instance.session_manager.update_session_metadata(submission.session_id, session_metadata_for_stage_update)
                # logger.info(f"Session {submission.session_id} metadata updated to stage FEEDBACK.")
                # --- END REVISED SESSION AND GRAPH STATE UPDATE ---

            except Exception as e_session_update:
                logger.error(f"Error updating session after code submission for {submission.session_id}: {e_session_update}", exc_info=True)
                # Decide if this should fail the request or just log. For now, just log.
        # --- MODIFICATION END ---

        return CodingSubmissionResponse(
            status=evaluation_results_dict.get("status", "unknown"),
            challenge_id=evaluation_results_dict.get("challenge_id", submission.challenge_id),
            execution_results=evaluation_results_dict.get("execution_results", {}),
            feedback=evaluation_results_dict.get("feedback", {}),
            evaluation=evaluation_results_dict.get("evaluation", {}),
            overall_summary=overall_summary_data
        )

    except Exception as e:
        logger.error(f"Error in submit_code_solution endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing submission: {str(e)}")

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

        # Call the get_coding_hint tool
        from ai_interviewer.tools.coding_tools import get_coding_hint
        
        result = get_coding_hint(
            challenge_id=hint_request.challenge_id,
            current_code=hint_request.code,
            error_message=hint_request.error_message
        )
        
        # If session ID is provided, store code snapshot for tracking hint requests
        if hint_request.session_id and interviewer_instance and interviewer_instance.session_manager: # user_id_from_token is now used
            session = interviewer_instance.session_manager.get_session(hint_request.session_id)
            if session:
                # Verify session ownership
                if session.get("user_id") != user_id_from_token:
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
                interviewer_instance.session_manager.update_session(hint_request.session_id, session)
                
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
async def continue_after_challenge(
    request: Request,
    session_id: str,
    request_data: ChallengeCompleteRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    Continue an interview after completing a coding challenge.
    
    The authenticated user's ID will be used and verified against the session.
    
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
        # Use user_id from the authenticated user
        user_id_from_token = current_user.id
        
        # if not request_data.user_id: # No longer needed from request
        #     raise HTTPException(status_code=400, detail="User ID is required")
        
        # Get the session
        active_interviewer = request.app.state.interviewer
        if not active_interviewer or not active_interviewer.session_manager:
            raise HTTPException(status_code=500, detail="Session manager not available")
            
        session = active_interviewer.session_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
            
        # Verify session ownership
        if session.get("user_id") != user_id_from_token:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User does not own this session.")

        # Update metadata to indicate we're resuming from a challenge
        metadata = session.get("metadata", {})
        metadata["resuming_from_challenge"] = True
        metadata["challenge_completed"] = request_data.challenge_completed
        
        # Store evaluation summary if provided
        if request_data.evaluation_summary:
            metadata["coding_evaluation"] = request_data.evaluation_summary
            logger.info(f"Stored coding evaluation in session metadata: {request_data.evaluation_summary}")
        
        session["metadata"] = metadata
        active_interviewer.session_manager.update_session(session_id, session)
        
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
        # run_interview now returns a dictionary
        response_data = await active_interviewer.run_interview(
            user_id_from_token, # Use ID from token
            message,
            session_id
        )
        
        # Get updated session metadata (session_id is in response_data)
        current_session_id = response_data["session_id"]
        current_interview_stage = response_data.get("interview_stage")
        updated_metadata = {}
        if active_interviewer.session_manager:
            session_after_run = active_interviewer.session_manager.get_session(current_session_id)
            if session_after_run and "metadata" in session_after_run:
                updated_metadata = session_after_run["metadata"]
        
        logger.info(f"[SERVER] continue_after_challenge RETURN: response='{response_data['ai_response'][:50]}...', session_id='{current_session_id}', interview_stage='{current_interview_stage}', job_role='{updated_metadata.get('job_role')}'") # Added log
        return MessageResponse(
            response=response_data["ai_response"],
            session_id=current_session_id,
            interview_stage=current_interview_stage, # Use stage from run_interview
            job_role=updated_metadata.get("job_role"), # Keep these from potentially updated session metadata
            requires_coding=updated_metadata.get("requires_coding"),
            coding_challenge_detail=response_data.get("coding_challenge_detail") # ADDED
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
@limiter.limit("15/minute")
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
@limiter.limit("10/minute")
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
@limiter.limit("10/minute")
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
                "problem_statement": "Write a function that finds the most frequent element in a list",
                "test_cases": [
                    {"input": [1, 2, 2, 3], "expected_output": 2}
                ],
                "reference_solution": "def find_most_frequent(lst):\n    return max(set(lst), key=lst.count)",
                "difficulty_level": "intermediate",
                "skills_targeted": ["Python", "Data Structures"]
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
@limiter.limit("10/minute")
async def generate_coding_problem(request: Request, req_data: ProblemGenerationRequest):
    """
    Generate a coding problem based on job description and required skills.
    """
    try:
        # Log detailed request information
        logger.info("=== PROBLEM GENERATION REQUEST RECEIVED ===")
        logger.info(f"Client IP: {request.client.host}")
        logger.info(f"Job Description: {req_data.job_description[:50]}...")
        logger.info(f"Skills Required: {req_data.skills_required}")
        logger.info(f"Difficulty Level: {req_data.difficulty_level}")
        
        # Call the problem generation tool using the invoke method
        logger.info("Calling generate_coding_challenge_from_jd tool asynchronously...")
        # Ensure the tool is awaited correctly if it's an async function
        if asyncio.iscoroutinefunction(generate_coding_challenge_from_jd.func):
            result = await generate_coding_challenge_from_jd.ainvoke({
                "job_description": req_data.job_description,
                "skills_required": req_data.skills_required,
                "difficulty_level": req_data.difficulty_level
            })
        else: # Fallback if it's somehow not an async func (shouldn't happen with @tool async def)
            result = generate_coding_challenge_from_jd.invoke({
                "job_description": req_data.job_description,
                "skills_required": req_data.skills_required,
                "difficulty_level": req_data.difficulty_level
            })
        
        # Log the successful response
        logger.info("Problem generation successful!")
        logger.info(f"Problem Statement (first 50 chars): {result.get('problem_statement', '')[:50]}...")
        logger.info(f"Number of Test Cases: {len(result.get('test_cases', []))}")
        logger.info(f"Skills Targeted: {result.get('skills_targeted', [])}")
        
        return result
    except Exception as e:
        logger.error("=== PROBLEM GENERATION ERROR ===")
        logger.error(f"Error type: {type(e).__name__}")
        logger.error(f"Error message: {str(e)}")
        logger.error(f"Stack trace:", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate coding problem: {str(e)}"
        )

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



if __name__ == "__main__":
    # Run the server directly if this module is executed
    start_server() 