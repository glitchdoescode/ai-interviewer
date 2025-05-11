"""
State definitions for the AI Interviewer platform.

This module contains the InterviewState class which defines the structure
of the state that is shared across the LangGraph nodes in the interview workflow.
"""
from typing import Dict, List, Optional
from langchain_core.messages import BaseMessage
from langgraph.graph import MessagesState

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
        evaluation_notes: Notes/scores from evaluating the candidate
        interview_stage: Current stage of the interview
    """
    # Required for identification
    interview_id: str
    
    # Optional for MVP
    candidate_id: Optional[str] = None
    
    # Question tracking
    current_question_id: Optional[str] = None
    current_question_text: Optional[str] = None
    question_history: List[Dict] = []
    candidate_responses: List[str] = []
    
    # Coding challenge
    coding_challenge_state: Optional[Dict] = None
    
    # Evaluation
    evaluation_notes: List[str] = []
    
    # Workflow state
    interview_stage: str = "greeting"  # greeting, qa, coding, feedback, finished
    current_topic: Optional[str] = None 