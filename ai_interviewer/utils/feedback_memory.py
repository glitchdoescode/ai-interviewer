"""
Utility module for storing and retrieving feedback interaction data in session memory.
Tracks what feedback areas have been explored and candidate preferences.
"""

import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class FeedbackMemoryManager:
    """Manages feedback interaction memory for interview sessions."""
    
    def __init__(self, session_manager=None):
        """
        Initialize the feedback memory manager.
        
        Args:
            session_manager: SessionManager instance for persistence
        """
        self.session_manager = session_manager
    
    def store_feedback_interaction(self, session_id: str, interaction_data: Dict[str, Any]) -> bool:
        """
        Store feedback interaction data in session memory.
        
        Args:
            session_id: Session ID
            interaction_data: Data about the feedback interaction
            
        Returns:
            True if stored successfully, False otherwise
        """
        try:
            if not self.session_manager:
                logger.warning("No session manager available for storing feedback interaction")
                return False
            
            # Get current session
            session = self.session_manager.get_session(session_id)
            if not session:
                logger.error(f"Session {session_id} not found")
                return False
            
            # Get or create feedback history
            metadata = session.get("metadata", {})
            feedback_history = metadata.get("feedback_interactions", [])
            
            # Add timestamp to interaction data
            interaction_data["timestamp"] = datetime.now().isoformat()
            
            # Store the interaction
            feedback_history.append(interaction_data)
            metadata["feedback_interactions"] = feedback_history
            
            # Update session metadata
            self.session_manager.update_session_metadata(session_id, metadata)
            
            logger.info(f"Stored feedback interaction for session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error storing feedback interaction: {e}")
            return False
    
    def get_explored_areas(self, session_id: str) -> List[str]:
        """
        Get list of feedback areas already explored in this session.
        
        Args:
            session_id: Session ID
            
        Returns:
            List of explored feedback area names
        """
        try:
            if not self.session_manager:
                return []
            
            session = self.session_manager.get_session(session_id)
            if not session:
                return []
            
            metadata = session.get("metadata", {})
            feedback_history = metadata.get("feedback_interactions", [])
            
            explored_areas = []
            for interaction in feedback_history:
                if interaction.get("type") == "area_explored":
                    area = interaction.get("area")
                    if area and area not in explored_areas:
                        explored_areas.append(area)
            
            return explored_areas
            
        except Exception as e:
            logger.error(f"Error getting explored areas: {e}")
            return []
    
    def get_candidate_preferences(self, session_id: str) -> Dict[str, Any]:
        """
        Get candidate's feedback preferences based on interaction history.
        
        Args:
            session_id: Session ID
            
        Returns:
            Dictionary of preferences and patterns
        """
        try:
            if not self.session_manager:
                return {}
            
            session = self.session_manager.get_session(session_id)
            if not session:
                return {}
            
            metadata = session.get("metadata", {})
            feedback_history = metadata.get("feedback_interactions", [])
            
            preferences = {
                "preferred_areas": [],
                "engagement_level": "medium",
                "detail_preference": "medium",
                "areas_of_interest": [],
                "interaction_count": len(feedback_history)
            }
            
            # Analyze interaction patterns
            area_frequency = {}
            total_interactions = 0
            
            for interaction in feedback_history:
                total_interactions += 1
                
                if interaction.get("type") == "area_explored":
                    area = interaction.get("area")
                    if area:
                        area_frequency[area] = area_frequency.get(area, 0) + 1
                
                # Track engagement indicators
                if interaction.get("candidate_response_length", 0) > 50:
                    preferences["engagement_level"] = "high"
                elif interaction.get("candidate_response_length", 0) < 20:
                    preferences["engagement_level"] = "low"
            
            # Determine preferred areas (most frequently accessed)
            if area_frequency:
                preferences["preferred_areas"] = sorted(
                    area_frequency.keys(), 
                    key=lambda x: area_frequency[x], 
                    reverse=True
                )[:3]
            
            return preferences
            
        except Exception as e:
            logger.error(f"Error getting candidate preferences: {e}")
            return {}
    
    def store_rubric_evaluation(self, session_id: str, rubric_data: Dict[str, Any]) -> bool:
        """
        Store rubric evaluation results in session memory.
        
        Args:
            session_id: Session ID
            rubric_data: Complete rubric evaluation data
            
        Returns:
            True if stored successfully, False otherwise
        """
        try:
            if not self.session_manager:
                logger.warning("No session manager available for storing rubric evaluation")
                return False
            
            session = self.session_manager.get_session(session_id)
            if not session:
                logger.error(f"Session {session_id} not found")
                return False
            
            metadata = session.get("metadata", {})
            metadata["rubric_evaluation"] = rubric_data
            metadata["rubric_evaluation_timestamp"] = datetime.now().isoformat()
            
            self.session_manager.update_session_metadata(session_id, metadata)
            
            logger.info(f"Stored rubric evaluation for session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error storing rubric evaluation: {e}")
            return False
    
    def get_rubric_evaluation(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get stored rubric evaluation results.
        
        Args:
            session_id: Session ID
            
        Returns:
            Rubric evaluation data or None if not found
        """
        try:
            if not self.session_manager:
                return None
            
            session = self.session_manager.get_session(session_id)
            if not session:
                return None
            
            metadata = session.get("metadata", {})
            return metadata.get("rubric_evaluation")
            
        except Exception as e:
            logger.error(f"Error getting rubric evaluation: {e}")
            return None
    
    def store_detailed_report(self, session_id: str, report_data: Dict[str, Any]) -> bool:
        """
        Store detailed interview report in session memory.
        
        Args:
            session_id: Session ID
            report_data: Complete report data
            
        Returns:
            True if stored successfully, False otherwise
        """
        try:
            if not self.session_manager:
                logger.warning("No session manager available for storing detailed report")
                return False
            
            session = self.session_manager.get_session(session_id)
            if not session:
                logger.error(f"Session {session_id} not found")
                return False
            
            metadata = session.get("metadata", {})
            metadata["detailed_report"] = report_data
            metadata["report_generation_timestamp"] = datetime.now().isoformat()
            
            self.session_manager.update_session_metadata(session_id, metadata)
            
            logger.info(f"Stored detailed report for session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error storing detailed report: {e}")
            return False
    
    def record_area_exploration(self, session_id: str, area: str, 
                               candidate_response: str = "", 
                               feedback_provided: str = "") -> bool:
        """
        Record that a feedback area was explored.
        
        Args:
            session_id: Session ID
            area: Feedback area that was explored
            candidate_response: Candidate's response when choosing this area
            feedback_provided: Summary of feedback provided
            
        Returns:
            True if recorded successfully, False otherwise
        """
        interaction_data = {
            "type": "area_explored",
            "area": area,
            "candidate_response": candidate_response,
            "candidate_response_length": len(candidate_response),
            "feedback_provided": feedback_provided,
            "feedback_length": len(feedback_provided)
        }
        
        return self.store_feedback_interaction(session_id, interaction_data)
    
    def record_feedback_menu_interaction(self, session_id: str, 
                                       menu_presented: str,
                                       candidate_choice: str,
                                       parsed_area: Optional[str] = None) -> bool:
        """
        Record interaction with feedback menu.
        
        Args:
            session_id: Session ID
            menu_presented: The menu options presented to candidate
            candidate_choice: Candidate's response to the menu
            parsed_area: The area that was parsed from candidate's choice
            
        Returns:
            True if recorded successfully, False otherwise
        """
        interaction_data = {
            "type": "menu_interaction",
            "menu_presented": menu_presented,
            "candidate_choice": candidate_choice,
            "parsed_area": parsed_area,
            "choice_successful": parsed_area is not None
        }
        
        return self.store_feedback_interaction(session_id, interaction_data)
    
    def get_feedback_summary(self, session_id: str) -> Dict[str, Any]:
        """
        Get a summary of all feedback interactions for this session.
        
        Args:
            session_id: Session ID
            
        Returns:
            Summary of feedback interactions
        """
        try:
            if not self.session_manager:
                return {"error": "No session manager available"}
            
            session = self.session_manager.get_session(session_id)
            if not session:
                return {"error": "Session not found"}
            
            metadata = session.get("metadata", {})
            feedback_history = metadata.get("feedback_interactions", [])
            rubric_evaluation = metadata.get("rubric_evaluation")
            
            explored_areas = self.get_explored_areas(session_id)
            preferences = self.get_candidate_preferences(session_id)
            
            return {
                "session_id": session_id,
                "total_interactions": len(feedback_history),
                "explored_areas": explored_areas,
                "candidate_preferences": preferences,
                "has_rubric_evaluation": rubric_evaluation is not None,
                "rubric_score": rubric_evaluation.get("total_score") if rubric_evaluation else None,
                "rubric_percentage": rubric_evaluation.get("percentage") if rubric_evaluation else None,
                "trust_score": rubric_evaluation.get("trust_score") if rubric_evaluation else None,
                "last_interaction": feedback_history[-1]["timestamp"] if feedback_history else None
            }
            
        except Exception as e:
            logger.error(f"Error getting feedback summary: {e}")
            return {"error": str(e)}


def create_feedback_memory_manager(session_manager=None) -> FeedbackMemoryManager:
    """
    Factory function to create a FeedbackMemoryManager instance.
    
    Args:
        session_manager: Optional SessionManager instance
        
    Returns:
        FeedbackMemoryManager instance
    """
    return FeedbackMemoryManager(session_manager) 