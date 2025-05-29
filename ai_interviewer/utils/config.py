"""Configuration loader for AI Interviewer."""
import os
from dotenv import load_dotenv
import yaml
import logging
from typing import Optional


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Default configuration values
DEFAULT_CONFIG = {
    "llm": {
        "provider": "google_genai",  # or "openai", "anthropic"
        "model": "gemini-pro",
        "temperature": 0.7,
        "system_name": "Dhruv"
    },
    "gemini_live": {
        "api_key": None, # Loaded from environment
        "project_id": None, # Optional, for Vertex AI
        "location": None, # Optional, for Vertex AI
        "stt_model_id": "gemini-2.0-flash-exp", # Model for API key usage
        "tts_model_id": "gemini-2.0-flash-exp", # Model for API key usage
        "tts_voice": "Puck"
    },
    "database": {
        "provider": "mongodb",
        "uri": "mongodb://localhost:27017/",
        "database": "ai_interviewer_db",
        "sessions_collection": "interview_sessions",
        "metadata_collection": "session_metadata", # For SessionManager
        "store_collection": "interview_memory_store", # For InterviewMemoryManager
        "users_collection": "users", # For user authentication data
        "password_reset_tokens_collection": "password_reset_tokens" # For password reset tokens
    },
    "speech": {
        "provider": "deepgram", # or "google_cloud_speech"
        "api_key": None, # Loaded from environment
        "tts_voice": "nova" # Default Deepgram voice
    },
    "code_execution": {
        "sandbox_type": "docker", # or "judge0"
        "timeout_seconds": 10,
        "max_output_chars": 5000
    },
    "rubric": {
        "qa_default_weight": 0.6,
        "coding_default_weight": 0.4
    },
    "logging": {
        "level": "INFO",
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        "datefmt": "%Y-%m-%d %H:%M:%S"
    }
}

def load_config() -> dict:
    """Load configuration from config.yaml or use defaults."""
    config_path = os.path.join(os.path.dirname(__file__), "..", "..", "config.yaml")
    
    config = DEFAULT_CONFIG.copy() # Start with defaults

    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                yaml_config = yaml.safe_load(f)
            
            # Deep merge YAML config into defaults
            if yaml_config:
                for key, value in yaml_config.items():
                    if isinstance(value, dict) and isinstance(config.get(key), dict):
                        config[key].update(value)
                    else:
                        config[key] = value
            logger.info("Loaded configuration from config.yaml")
        except Exception as e:
            logger.error(f"Error loading config.yaml: {e}. Using default configuration.")
    else:
        logger.info("config.yaml not found. Using default configuration.")

    # Override with environment variables where available
    # LLM
    config["llm"]["provider"] = os.environ.get("LLM_PROVIDER", config["llm"]["provider"])
    config["llm"]["model"] = os.environ.get("LLM_MODEL", config["llm"]["model"])
    config["llm"]["system_name"] = os.environ.get("SYSTEM_NAME", config["llm"]["system_name"])
    if os.environ.get("LLM_TEMPERATURE"):
        try:
            config["llm"]["temperature"] = float(os.environ.get("LLM_TEMPERATURE"))
        except ValueError:
            logger.warning("Invalid LLM_TEMPERATURE in .env, using default.")

    # Gemini Live API
    config["gemini_live"]["api_key"] = os.environ.get("GEMINI_API_KEY", config["gemini_live"]["api_key"])
    config["gemini_live"]["project_id"] = os.environ.get("GEMINI_PROJECT_ID", config["gemini_live"]["project_id"])
    config["gemini_live"]["location"] = os.environ.get("GEMINI_LOCATION", config["gemini_live"]["location"])
    config["gemini_live"]["stt_model_id"] = os.environ.get("GEMINI_STT_MODEL_ID", config["gemini_live"]["stt_model_id"])
    config["gemini_live"]["tts_model_id"] = os.environ.get("GEMINI_TTS_MODEL_ID", config["gemini_live"]["tts_model_id"])
    config["gemini_live"]["tts_voice"] = os.environ.get("GEMINI_TTS_VOICE", config["gemini_live"]["tts_voice"])


    # Database
    config["database"]["uri"] = os.environ.get("MONGODB_URI", config["database"]["uri"])
    config["database"]["database"] = os.environ.get("MONGODB_DATABASE", config["database"]["database"])
    config["database"]["sessions_collection"] = os.environ.get("MONGODB_SESSIONS_COLLECTION", config["database"]["sessions_collection"])
    config["database"]["metadata_collection"] = os.environ.get("MONGODB_METADATA_COLLECTION", config["database"]["metadata_collection"])
    config["database"]["store_collection"] = os.environ.get("MONGODB_STORE_COLLECTION", config["database"]["store_collection"])
    config["database"]["users_collection"] = os.environ.get("MONGODB_USERS_COLLECTION", config["database"]["users_collection"])
    config["database"]["password_reset_tokens_collection"] = os.environ.get("MONGODB_PASSWORD_RESET_TOKENS_COLLECTION", config["database"]["password_reset_tokens_collection"])

    # Speech (Deepgram)
    config["speech"]["provider"] = os.environ.get("SPEECH_PROVIDER", config["speech"]["provider"])
    config["speech"]["api_key"] = os.environ.get("DEEPGRAM_API_KEY", config["speech"]["api_key"])
    config["speech"]["tts_voice"] = os.environ.get("DEEPGRAM_TTS_VOICE", config["speech"]["tts_voice"])
    
    # Logging
    config["logging"]["level"] = os.environ.get("LOG_LEVEL", config["logging"]["level"]).upper()

    # Validate critical API keys
    if config["llm"]["provider"] == "google_genai" and not os.environ.get("GOOGLE_API_KEY"):
        logger.warning("GOOGLE_API_KEY environment variable not set for Google GenAI.")
    if config["speech"]["provider"] == "deepgram" and not config["speech"]["api_key"]:
        logger.warning("DEEPGRAM_API_KEY environment variable not set for Deepgram.")
    if not config["gemini_live"]["api_key"]:
        logger.warning("GEMINI_API_KEY environment variable not set for Gemini Live API.")


    return config

# Load configuration once
CONFIG = load_config()

def get_llm_config() -> dict:
    """Get LLM configuration."""
    return CONFIG.get("llm", {})

def get_gemini_live_config() -> dict:
    """Get Gemini Live API configuration."""
    return CONFIG.get("gemini_live", {})

def get_db_config() -> dict:
    """Get database configuration."""
    return CONFIG.get("database", {})

def get_speech_config() -> dict:
    """Get speech configuration."""
    return CONFIG.get("speech", {})
    
def get_code_execution_config() -> dict:
    """Get code execution configuration."""
    return CONFIG.get("code_execution", {})

def get_rubric_config() -> dict:
    """Get rubric configuration."""
    return CONFIG.get("rubric", {})

def get_logging_config() -> dict:
    """Get logging configuration."""
    return CONFIG.get("logging", {})

def log_config(level: Optional[str] = None, print_config: bool = False):
    """Configure application-wide logging and optionally print the config."""
    log_cfg = get_logging_config()
    log_level = level or log_cfg.get("level", "INFO").upper()
    
    # Ensure basicConfig is called only once or use a more robust setup
    # For simplicity here, we assume this is called early.
    # In a larger app, consider a dedicated logging setup module.
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format=log_cfg.get("format"),
        datefmt=log_cfg.get("datefmt")
    )
    
    logger.info(f"Logging configured to level: {log_level}")
    
    if print_config:
        # Be careful about printing sensitive information like API keys
        # Create a redacted version of the config for printing
        import copy
        printable_config = copy.deepcopy(CONFIG)
        if printable_config.get("gemini_live", {}).get("api_key"):
            printable_config["gemini_live"]["api_key"] = "***REDACTED***"
        if printable_config.get("speech", {}).get("api_key"):
            printable_config["speech"]["api_key"] = "***REDACTED***"
        if printable_config.get("llm", {}).get("api_key"): # If any LLM provider uses 'api_key'
            printable_config["llm"]["api_key"] = "***REDACTED***"
        if "GOOGLE_API_KEY" in printable_config.get("llm", {}): # Example for Google
             printable_config["llm"]["GOOGLE_API_KEY"] = "***REDACTED***"
        
        logger.info(f"Current configuration (redacted):\n{yaml.dump(printable_config, indent=2)}")

if __name__ == "__main__":
    # Example of using the config
    log_config(print_config=True) # Configure logging and print the (redacted) config
    
    llm_settings = get_llm_config()
    db_settings = get_db_config()
    speech_settings = get_speech_config()
    gemini_live_settings = get_gemini_live_config()
    
    logger.info(f"LLM Provider: {llm_settings.get('provider')}")
    logger.info(f"Database URI: {db_settings.get('uri')}")
    logger.info(f"Speech Provider: {speech_settings.get('provider')}")
    logger.info(f"Gemini Live API Key Set: {'Yes' if gemini_live_settings.get('api_key') else 'No'}")
    logger.info(f"Gemini Live STT Model: {gemini_live_settings.get('stt_model_id')}")