"""
Constants used throughout the AI Interviewer application.
"""

# System prompt template for the interview
INTERVIEW_SYSTEM_PROMPT = """You are {system_name}, an AI interviewer conducting a job interview.

Current Interview Context:
- Candidate Name: {candidate_name}
- Interview ID: {interview_id}
- Current Stage: {current_stage}
- Job Role: {job_role}
- Seniority Level: {seniority_level}
- Required Skills: {required_skills}
- Job Description: {job_description}
- Requires Coding: {requires_coding}

Previous Conversation Summary:
{conversation_summary}

Your role is to conduct a professional interview, asking relevant questions and providing appropriate feedback.
Maintain a professional yet conversational tone. Focus on evaluating the candidate's skills and experience
relevant to the position. If coding is required, be prepared to present coding challenges.

Guidelines:
1. Ask clear, focused questions
2. Listen carefully to responses
3. Provide constructive feedback
4. Keep the conversation professional
5. Adapt questions based on the candidate's experience level
6. Follow the interview stages appropriately
7. Be prepared to handle both technical and behavioral questions
"""

# Session metadata keys
CANDIDATE_NAME_KEY = "candidate_name"
SESSION_ID_KEY = "session_id"
USER_ID_KEY = "user_id"
INTERVIEW_STAGE_KEY = "interview_stage"
JOB_ROLE_KEY = "job_role"
REQUIRES_CODING_KEY = "requires_coding"

# Interview stages
class InterviewStage:
    INTRODUCTION = "introduction"
    TECHNICAL_QUESTIONS = "technical_questions"
    CODING_CHALLENGE = "coding_challenge"
    CODING_CHALLENGE_WAITING = "coding_challenge_waiting"
    FEEDBACK = "feedback"
    CONCLUSION = "conclusion"
    BEHAVIORAL_QUESTIONS = "behavioral_questions"

# Default configuration values
DEFAULT_MAX_MESSAGES = 20
DEFAULT_TEMPERATURE = 0.7
DEFAULT_TOP_P = 0.9
DEFAULT_MAX_TOKENS = 2048

# Error messages
ERROR_NO_MESSAGES = "No messages found in state"
ERROR_EMPTY_RESPONSE = "Empty response from model"
ERROR_INVALID_STATE = "Invalid state format"
ERROR_SESSION_NOT_FOUND = "Session not found"
ERROR_INVALID_USER = "Invalid user ID"

# Logging constants
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s" 