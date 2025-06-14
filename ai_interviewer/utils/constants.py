"""
Constants used throughout the AI Interviewer application.
"""

# Default configuration values
DEFAULT_MAX_MESSAGES = 20
DEFAULT_TEMPERATURE = 0.3  # Reduced from 0.7 for faster, more focused responses
DEFAULT_TOP_P = 0.8  # Reduced from 0.9 for faster sampling
DEFAULT_MAX_TOKENS = 1024  # Reduced from 2048 for faster generation

# Session metadata keys
CANDIDATE_NAME_KEY = "candidate_name"
SESSION_ID_KEY = "session_id"
USER_ID_KEY = "user_id"
INTERVIEW_STAGE_KEY = "interview_stage"
JOB_ROLE_KEY = "job_role"
REQUIRES_CODING_KEY = "requires_coding"

# Error messages
ERROR_NO_MESSAGES = "No messages provided"
ERROR_EMPTY_RESPONSE = "Empty response received"

# Interview stages
class InterviewStage:
    INTRODUCTION = "introduction"
    TECHNICAL_QUESTIONS = "technical_questions"
    CODING_CHALLENGE = "coding_challenge"
    CODING_CHALLENGE_WAITING = "coding_challenge_waiting"
    FEEDBACK = "feedback"
    CONCLUSION = "conclusion"
    BEHAVIORAL_QUESTIONS = "behavioral_questions"

# Logging constants
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s" 