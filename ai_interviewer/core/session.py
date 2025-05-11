"""
Session management module for the AI Interviewer platform.

This module handles asynchronous interview sessions, including state persistence
and session resumption.
"""
import logging
import uuid
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from langchain_core.messages import HumanMessage, AIMessage
from langgraph.checkpoint import get_checkpointer
from langgraph.checkpoint.memory import MemorySaver

from ai_interviewer.models.state import InterviewState

# Configure logging
logger = logging.getLogger(__name__)

class SessionManager:
    """
    Manages asynchronous interview sessions.
    
    This class handles:
    - Session creation and resumption
    - State persistence
    - Session metadata tracking
    - Timeout management
    """
    
    def __init__(self, checkpointer=None):
        """
        Initialize the session manager.
        
        Args:
            checkpointer: Optional custom checkpointer. If not provided, uses MemorySaver.
        """
        self.checkpointer = checkpointer or MemorySaver()
        
    def create_session(self, candidate_id: Optional[str] = None) -> str:
        """
        Create a new interview session.
        
        Args:
            candidate_id: Optional identifier for the candidate
            
        Returns:
            str: The session ID (thread_id)
        """
        session_id = str(uuid.uuid4())
        
        # Initialize session state
        initial_state = InterviewState(
            interview_id=session_id,
            candidate_id=candidate_id,
            interview_stage="greeting",
            messages=[],
            question_history=[],
            candidate_responses=[],
            session_metadata={
                "created_at": datetime.now().isoformat(),
                "last_active": datetime.now().isoformat(),
                "is_completed": False,
                "timeout_minutes": 60  # Default 1-hour timeout
            }
        )
        
        # Save initial state
        self.checkpointer.save(session_id, initial_state.model_dump())
        logger.info(f"Created new session {session_id} for candidate {candidate_id}")
        
        return session_id
        
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a session's state.
        
        Args:
            session_id: The session identifier
            
        Returns:
            Optional[Dict[str, Any]]: The session state if found, None otherwise
        """
        try:
            state = self.checkpointer.get(session_id)
            if state:
                # Update last active timestamp
                if isinstance(state, dict) and "session_metadata" in state:
                    state["session_metadata"]["last_active"] = datetime.now().isoformat()
                    self.checkpointer.save(session_id, state)
                return state
            return None
        except Exception as e:
            logger.error(f"Error retrieving session {session_id}: {e}")
            return None
            
    def update_session(self, session_id: str, state: Dict[str, Any]) -> bool:
        """
        Update a session's state.
        
        Args:
            session_id: The session identifier
            state: The new state to save
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Update last active timestamp
            if "session_metadata" in state:
                state["session_metadata"]["last_active"] = datetime.now().isoformat()
            
            self.checkpointer.save(session_id, state)
            logger.info(f"Updated session {session_id}")
            return True
        except Exception as e:
            logger.error(f"Error updating session {session_id}: {e}")
            return False
            
    def complete_session(self, session_id: str) -> bool:
        """
        Mark a session as completed.
        
        Args:
            session_id: The session identifier
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            state = self.checkpointer.get(session_id)
            if state and isinstance(state, dict):
                if "session_metadata" in state:
                    state["session_metadata"]["is_completed"] = True
                    state["session_metadata"]["completed_at"] = datetime.now().isoformat()
                    self.checkpointer.save(session_id, state)
                    logger.info(f"Marked session {session_id} as completed")
                    return True
            return False
        except Exception as e:
            logger.error(f"Error completing session {session_id}: {e}")
            return False
            
    def is_session_active(self, session_id: str) -> bool:
        """
        Check if a session is still active (not timed out or completed).
        
        Args:
            session_id: The session identifier
            
        Returns:
            bool: True if session is active, False otherwise
        """
        try:
            state = self.checkpointer.get(session_id)
            if not state or not isinstance(state, dict):
                return False
                
            metadata = state.get("session_metadata", {})
            if metadata.get("is_completed", False):
                return False
                
            # Check timeout
            last_active = datetime.fromisoformat(metadata.get("last_active", ""))
            timeout_minutes = metadata.get("timeout_minutes", 60)
            timeout_threshold = datetime.now() - timedelta(minutes=timeout_minutes)
            
            return last_active > timeout_threshold
        except Exception as e:
            logger.error(f"Error checking session {session_id} status: {e}")
            return False
            
    def list_active_sessions(self) -> Dict[str, Dict[str, Any]]:
        """
        List all active sessions and their metadata.
        
        Returns:
            Dict[str, Dict[str, Any]]: Dictionary of active session IDs and their metadata
        """
        active_sessions = {}
        try:
            # Note: This is a basic implementation that works with MemorySaver
            # For production, you'd want to implement this with proper database queries
            for session_id in self.checkpointer.list_checkpoints():
                if self.is_session_active(session_id):
                    state = self.checkpointer.get(session_id)
                    if state and isinstance(state, dict):
                        active_sessions[session_id] = {
                            "candidate_id": state.get("candidate_id"),
                            "interview_stage": state.get("interview_stage"),
                            "metadata": state.get("session_metadata", {})
                        }
            return active_sessions
        except Exception as e:
            logger.error(f"Error listing active sessions: {e}")
            return {}
            
    def cleanup_expired_sessions(self) -> int:
        """
        Remove expired sessions from storage.
        
        Returns:
            int: Number of sessions cleaned up
        """
        cleaned_count = 0
        try:
            for session_id in self.checkpointer.list_checkpoints():
                if not self.is_session_active(session_id):
                    # In production, you might want to archive instead of delete
                    self.checkpointer.delete(session_id)
                    cleaned_count += 1
            logger.info(f"Cleaned up {cleaned_count} expired sessions")
            return cleaned_count
        except Exception as e:
            logger.error(f"Error cleaning up expired sessions: {e}")
            return 0 