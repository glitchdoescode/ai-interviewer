"""
State definitions for the AI Interviewer platform.

This module contains the InterviewState class which defines the structure
of the state that is shared across the LangGraph nodes in the interview workflow.
"""
from typing import Dict, List, Optional, Any
from langchain_core.messages import BaseMessage
from langgraph.graph import MessagesState

from ai_interviewer.models.rubric import InterviewEvaluation

class InterviewState(MessagesState):
    """
    State class for the interview process.
    
    This class extends MessagesState which provides a built-in 'messages' field
    with proper handling of message additions and updates.
    
    Attributes:
        interview_id: Unique identifier for the interview session
        candidate_id: Identifier for the candidate (optional for MVP)
        current_question_id: ID of the current question being asked
        current_question_text: Text of the current question
        candidate_responses: List of candidate's responses
        coding_challenge_state: State related to coding challenges
        evaluation: Complete interview evaluation using rubric
        interview_stage: Current stage of the interview
        reports: Paths to generated reports
        session_metadata: Metadata for asynchronous session management
    """
    # Required for identification
    interview_id: str
    
    # Optional for MVP
    candidate_id: Optional[str] = None
    
    # Question tracking
    current_question_id: Optional[str] = None
    current_question_text: Optional[str] = None
    question_history: List[str] = []  # List of question texts
    candidate_responses: List[Dict[str, Any]] = []  # List of response objects with question_id, answer, evaluation
    
    # Coding challenge
    coding_challenge_state: Optional[Dict] = None
    
    # Evaluation using our rubric
    evaluation: InterviewEvaluation = InterviewEvaluation(trust_score=0.0)
    
    # Interview progress
    interview_stage: str = "greeting"  # One of: greeting, qa, coding, feedback, finished
    current_topic: Optional[str] = None  # Current topic being discussed
    
    # Report generation
    reports: Optional[Dict[str, str]] = None  # Paths to generated reports
    
    # Session management for asynchronous support
    session_metadata: Dict[str, Any] = {
        "created_at": None,  # ISO format datetime string
        "last_active": None,  # ISO format datetime string
        "is_completed": False,
        "timeout_minutes": 60,  # Default 1-hour timeout
        "completed_at": None,  # ISO format datetime string when completed
        "resume_context": None,  # Optional context for session resumption
        "paused_at": None,  # ISO format datetime string when last paused
        "total_duration": 0,  # Total session duration in seconds
        "pause_count": 0,  # Number of times the session was paused
    } 