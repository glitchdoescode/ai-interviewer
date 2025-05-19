"""
Configuration module for {SYSTEM_NAME}.

This module provides configuration settings and utilities for the {SYSTEM_NAME}.
"""
import os
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()
# Get the absolute path to the project root directory
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ENV_FILE_PATH = os.path.join(PROJECT_ROOT, ".env")


# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# MongoDB configuration
MONGODB_URI = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DATABASE = os.environ.get("MONGODB_DATABASE", "ai_interviewer")
MONGODB_SESSIONS_COLLECTION = os.environ.get("MONGODB_SESSIONS_COLLECTION", "interview_sessions")
MONGODB_METADATA_COLLECTION = os.environ.get("MONGODB_METADATA_COLLECTION", "interview_metadata")

# LLM configuration
LLM_MODEL = os.environ.get("LLM_MODEL", "gemini-pro")
LLM_TEMPERATURE = float(os.environ.get("LLM_TEMPERATURE", "0.2"))

# Session configuration
SESSION_TIMEOUT_MINUTES = int(os.environ.get("SESSION_TIMEOUT_MINUTES", "60"))
MAX_SESSION_HISTORY = int(os.environ.get("MAX_SESSION_HISTORY", "50"))

# Speech configuration
DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY", "")
SPEECH_RECORDING_DURATION = float(os.environ.get("SPEECH_RECORDING_DURATION", "30.0"))  # Max recording duration
SPEECH_SAMPLE_RATE = int(os.environ.get("SPEECH_SAMPLE_RATE", "16000"))
SPEECH_TTS_VOICE = os.environ.get("SPEECH_TTS_VOICE", "nova")
SPEECH_SILENCE_THRESHOLD = float(os.environ.get("SPEECH_SILENCE_THRESHOLD", "0.03"))  # Volume threshold to detect silence
SPEECH_SILENCE_DURATION = float(os.environ.get("SPEECH_SILENCE_DURATION", "2.0"))  # Seconds of silence to stop recording

# --- System Configuration ---
SYSTEM_NAME = os.getenv("SYSTEM_NAME", "AI Interviewer")

def get_db_config() -> Dict[str, str]:
    """
    Get MongoDB configuration.
    
    Returns:
        Dictionary with MongoDB configuration
    """
    return {
        "uri": MONGODB_URI,
        "database": MONGODB_DATABASE,
        "sessions_collection": MONGODB_SESSIONS_COLLECTION,
        "metadata_collection": MONGODB_METADATA_COLLECTION,
    }

def get_llm_config() -> Dict[str, Any]:
    """
    Get LLM configuration.
    
    Returns:
        Dictionary with LLM configuration
    """
    return {
        "model": LLM_MODEL,
        "temperature": LLM_TEMPERATURE,
    }

def get_session_config() -> Dict[str, Any]:
    """
    Get session configuration.
    
    Returns:
        Dictionary with session configuration
    """
    return {
        "timeout_minutes": SESSION_TIMEOUT_MINUTES,
        "max_history": MAX_SESSION_HISTORY,
    }

def get_config_value(key: str, default: Optional[Any] = None) -> Any:
    """
    Get a configuration value from environment variables.
    
    Args:
        key: Configuration key
        default: Default value if not found
        
    Returns:
        Configuration value
    """
    return os.environ.get(key, default)

def get_speech_config() -> Dict[str, Any]:
    """
    Get speech configuration.
    
    Returns:
        Dictionary with speech configuration
    """
    return {
        "api_key": DEEPGRAM_API_KEY,
        "recording_duration": SPEECH_RECORDING_DURATION,
        "sample_rate": SPEECH_SAMPLE_RATE,
        "tts_voice": SPEECH_TTS_VOICE,
        "silence_threshold": SPEECH_SILENCE_THRESHOLD,
        "silence_duration": SPEECH_SILENCE_DURATION,
    }

def log_config():
    """Log current configuration values (excluding sensitive information)."""
    logger.info("Current configuration:")
    logger.info(f"- MongoDB Database: {MONGODB_DATABASE}")
    logger.info(f"- Sessions Collection: {MONGODB_SESSIONS_COLLECTION}")
    logger.info(f"- Metadata Collection: {MONGODB_METADATA_COLLECTION}")
    logger.info(f"- LLM Model: {LLM_MODEL}")
    logger.info(f"- LLM Temperature: {LLM_TEMPERATURE}")
    logger.info(f"- Session Timeout: {SESSION_TIMEOUT_MINUTES} minutes")
    logger.info(f"- Max Session History: {MAX_SESSION_HISTORY} messages")
    logger.info(f"- Speech TTS Voice: {SPEECH_TTS_VOICE}")
    logger.info(f"- Speech Recording Max Duration: {SPEECH_RECORDING_DURATION} seconds")
    logger.info(f"- Speech Sample Rate: {SPEECH_SAMPLE_RATE} Hz")
    logger.info(f"- Speech Silence Threshold: {SPEECH_SILENCE_THRESHOLD}")
    logger.info(f"- Speech Silence Duration: {SPEECH_SILENCE_DURATION} seconds")
    logger.info(f"- Deepgram API Key: {'Configured' if DEEPGRAM_API_KEY else 'Not configured'}") 