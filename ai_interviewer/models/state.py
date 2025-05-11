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
    
    # Report paths
    reports: Dict[str, str] = {}  # Paths to generated reports (e.g., {"json_path": "...", "pdf_path": "..."})
    
    # Workflow state
    interview_stage: str = "greeting"  # greeting, qa, coding, feedback, finished
    current_topic: Optional[str] = None 