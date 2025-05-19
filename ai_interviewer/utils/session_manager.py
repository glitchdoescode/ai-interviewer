"""
Session manager for AI Interviewer sessions.

This module provides functionality for managing interview sessions,
including creation, retrieval, and persistence.
"""
import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
import pymongo
from pymongo.mongo_client import MongoClient

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

class SessionManager:
    """Manages interview sessions with MongoDB persistence."""
    
    def __init__(
        self,
        connection_uri: str,
        database_name: str = "ai_interviewer",
        collection_name: str = "interview_metadata"
    ):
        """
        Initialize the session manager.
        
        Args:
            connection_uri: MongoDB connection URI
            database_name: Name of the database
            collection_name: Name of the collection for session metadata
        """
        self.connection_uri = connection_uri
        self.database_name = database_name
        self.collection_name = collection_name
        
        # Initialize MongoDB connection
        self.client = MongoClient(connection_uri)
        self.db = self.client[database_name]
        self.collection = self.db[collection_name]
        
        # Create indexes
        self.collection.create_index([("session_id", pymongo.ASCENDING)], unique=True)
        self.collection.create_index([("user_id", pymongo.ASCENDING)])
        self.collection.create_index([("last_active", pymongo.DESCENDING)])
        
        logger.info(f"Session manager initialized with {connection_uri}")
    
    def create_session(self, user_id: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        Create a new interview session.
        
        Args:
            user_id: User identifier
            metadata: Optional additional metadata
            
        Returns:
            Session ID
        """
        session_id = str(uuid.uuid4())
        timestamp = datetime.now()
        
        # Prepare document
        document = {
            "session_id": session_id,
            "user_id": user_id,
            "created_at": timestamp,
            "last_active": timestamp,
            "status": "active",
            "metadata": metadata or {},
        }
        
        # Insert into MongoDB
        try:
            self.collection.insert_one(document)
            logger.info(f"Created new session {session_id} for user {user_id}")
            return session_id
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            raise
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session details by ID.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session details or None if not found
        """
        try:
            session = self.collection.find_one({"session_id": session_id})
            return session
        except Exception as e:
            logger.error(f"Error retrieving session {session_id}: {e}")
            return None
    
    def get_user_sessions(self, user_id: str, include_completed: bool = False) -> List[Dict[str, Any]]:
        """
        Get all sessions for a user.
        
        Args:
            user_id: User identifier
            include_completed: Whether to include completed sessions
            
        Returns:
            List of session details
        """
        try:
            query = {"user_id": user_id}
            
            if not include_completed:
                query["status"] = "active"
                
            sessions = list(self.collection.find(
                query,
                sort=[("last_active", pymongo.DESCENDING)]
            ))
            
            logger.info(f"Found {len(sessions)} sessions for user {user_id}")
            return sessions
        except Exception as e:
            logger.error(f"Error retrieving sessions for user {user_id}: {e}")
            return []
    
    def update_session_activity(self, session_id: str) -> bool:
        """
        Update the last activity timestamp for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if successful, False otherwise
        """
        try:
            result = self.collection.update_one(
                {"session_id": session_id},
                {"$set": {"last_active": datetime.now()}}
            )
            
            if result.modified_count > 0 or result.matched_count > 0:
                logger.info(f"Updated activity for session {session_id}")
                return True
            else:
                logger.warning(f"Session {session_id} not found for activity update")
                return False
        except Exception as e:
            logger.error(f"Error updating session activity: {e}")
            return False
    
    def update_session_metadata(self, session_id: str, metadata: Dict[str, Any]) -> bool:
        """
        Update metadata for a session.
        
        Args:
            session_id: Session identifier
            metadata: Metadata to update
            
        Returns:
            True if successful, False otherwise
        """
        try:
            result = self.collection.update_one(
                {"session_id": session_id},
                {"$set": {"metadata": metadata, "last_active": datetime.now()}}
            )
            
            if result.modified_count > 0 or result.matched_count > 0:
                logger.info(f"Updated metadata for session {session_id}")
                return True
            else:
                logger.warning(f"Session {session_id} not found for metadata update")
                return False
        except Exception as e:
            logger.error(f"Error updating session metadata: {e}")
            return False
    
    def complete_session(self, session_id: str) -> bool:
        """
        Mark a session as completed.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if successful, False otherwise
        """
        try:
            result = self.collection.update_one(
                {"session_id": session_id},
                {"$set": {"status": "completed", "completed_at": datetime.now()}}
            )
            
            if result.modified_count > 0:
                logger.info(f"Marked session {session_id} as completed")
                return True
            else:
                logger.warning(f"Session {session_id} not found for completion")
                return False
        except Exception as e:
            logger.error(f"Error completing session: {e}")
            return False
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if successful, False otherwise
        """
        try:
            result = self.collection.delete_one({"session_id": session_id})
            
            if result.deleted_count > 0:
                logger.info(f"Deleted session {session_id}")
                return True
            else:
                logger.warning(f"Session {session_id} not found for deletion")
                return False
        except Exception as e:
            logger.error(f"Error deleting session: {e}")
            return False
    
    def list_active_sessions(self, max_inactive_minutes: int = 60) -> List[Dict[str, Any]]:
        """
        List all active sessions.
        
        Args:
            max_inactive_minutes: Maximum inactive time in minutes
            
        Returns:
            List of active session details
        """
        cutoff_time = datetime.now().timestamp() - (max_inactive_minutes * 60)
        cutoff_datetime = datetime.fromtimestamp(cutoff_time)
        
        try:
            sessions = list(self.collection.find(
                {
                    "status": "active",
                    "last_active": {"$gte": cutoff_datetime}
                },
                sort=[("last_active", pymongo.DESCENDING)]
            ))
            
            logger.info(f"Found {len(sessions)} active sessions")
            return sessions
        except Exception as e:
            logger.error(f"Error listing active sessions: {e}")
            return []
    
    def get_most_recent_session(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the most recent session for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            Most recent session or None if not found
        """
        try:
            session = self.collection.find_one(
                {"user_id": user_id, "status": "active"},
                sort=[("last_active", pymongo.DESCENDING)]
            )
            
            if session:
                logger.info(f"Found most recent session {session['session_id']} for user {user_id}")
                return session
            else:
                logger.info(f"No active sessions found for user {user_id}")
                return None
        except Exception as e:
            logger.error(f"Error retrieving most recent session: {e}")
            return None
    
    def clean_inactive_sessions(self, max_inactive_minutes: int = 1440) -> int:
        """
        Clean up inactive sessions by marking them as completed.
        
        Args:
            max_inactive_minutes: Maximum inactive time in minutes (default: 24 hours)
            
        Returns:
            Number of sessions cleaned up
        """
        cutoff_time = datetime.now().timestamp() - (max_inactive_minutes * 60)
        cutoff_datetime = datetime.fromtimestamp(cutoff_time)
        
        try:
            result = self.collection.update_many(
                {
                    "status": "active",
                    "last_active": {"$lt": cutoff_datetime}
                },
                {
                    "$set": {
                        "status": "completed",
                        "completed_at": datetime.now(),
                        "completion_reason": "inactivity"
                    }
                }
            )
            
            count = result.modified_count
            if count > 0:
                logger.info(f"Cleaned up {count} inactive sessions")
            return count
        except Exception as e:
            logger.error(f"Error cleaning up inactive sessions: {e}")
            return 0
    
    def close(self):
        """Close the MongoDB connection."""
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with proper cleanup."""
        self.close()
    
    def update_session_messages(self, session_id: str, messages: List[Any]) -> bool:
        """
        Update the messages for a session.
        
        Args:
            session_id: Session identifier
            messages: List of message objects to save
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Convert messages to a serializable format if needed
            serializable_messages = []
            for msg in messages:
                if hasattr(msg, 'dict') and callable(getattr(msg, 'dict')):
                    # Handle Pydantic models or objects with dict method
                    serializable_messages.append(msg.dict())
                elif hasattr(msg, '__dict__'):
                    # Handle custom objects with __dict__
                    serializable_messages.append(msg.__dict__)
                else:
                    # Try direct serialization
                    serializable_messages.append(msg)
            
            # Update the messages in the collection
            result = self.collection.update_one(
                {"session_id": session_id},
                {
                    "$set": {
                        "messages": serializable_messages,
                        "last_active": datetime.now()
                    }
                }
            )
            
            if result.modified_count > 0 or result.matched_count > 0:
                logger.info(f"Updated messages for session {session_id}, count: {len(serializable_messages)}")
                return True
            else:
                logger.warning(f"Session {session_id} not found for messages update")
                return False
        except Exception as e:
            logger.error(f"Error updating session messages: {e}")
            return False
    
    def update_conversation_summary(self, session_id: str, summary: str) -> bool:
        """
        Update the conversation summary for a session.
        
        Args:
            session_id: Session identifier
            summary: New conversation summary
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get the current metadata
            session = self.get_session(session_id)
            if not session:
                logger.warning(f"Session {session_id} not found for summary update")
                return False
                
            metadata = session.get("metadata", {})
            
            # Update the summary in metadata
            metadata["conversation_summary"] = summary
            
            # Save the updated metadata
            result = self.collection.update_one(
                {"session_id": session_id},
                {"$set": {"metadata": metadata, "last_active": datetime.now()}}
            )
            
            if result.modified_count > 0 or result.matched_count > 0:
                logger.info(f"Updated conversation summary for session {session_id}")
                return True
            else:
                logger.warning(f"Session {session_id} not found for summary update")
                return False
        except Exception as e:
            logger.error(f"Error updating conversation summary: {e}")
            return False
            
    def get_conversation_summary(self, session_id: str) -> Optional[str]:
        """
        Get the current conversation summary for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Conversation summary or None if not found
        """
        try:
            session = self.get_session(session_id)
            if not session:
                return None
                
            metadata = session.get("metadata", {})
            return metadata.get("conversation_summary", "")
        except Exception as e:
            logger.error(f"Error retrieving conversation summary: {e}")
            return None
            
    def reduce_message_history(self, session_id: str, messages_to_keep: List[Any]) -> bool:
        """
        Update the session with a reduced set of messages, typically after summarization.
        
        Args:
            session_id: Session identifier
            messages_to_keep: List of message objects to retain
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Convert messages to a serializable format if needed
            serializable_messages = []
            for msg in messages_to_keep:
                if hasattr(msg, 'dict') and callable(getattr(msg, 'dict')):
                    # Handle Pydantic models or objects with dict method
                    serializable_messages.append(msg.dict())
                elif hasattr(msg, '__dict__'):
                    # Handle custom objects with __dict__
                    serializable_messages.append(msg.__dict__)
                else:
                    # Try direct serialization
                    serializable_messages.append(msg)
            
            # Update the session with the reduced messages
            result = self.collection.update_one(
                {"session_id": session_id},
                {
                    "$set": {
                        "messages": serializable_messages,
                        "last_active": datetime.now()
                    }
                }
            )
            
            if result.modified_count > 0 or result.matched_count > 0:
                logger.info(f"Updated session {session_id} with reduced message history, count: {len(serializable_messages)}")
                
                # Also update the message count in metadata
                session = self.get_session(session_id)
                if session:
                    metadata = session.get("metadata", {})
                    metadata["message_count"] = len(serializable_messages)
                    self.update_session_metadata(session_id, metadata)
                
                return True
            else:
                logger.warning(f"Session {session_id} not found for reducing message history")
                return False
        except Exception as e:
            logger.error(f"Error reducing message history: {e}")
            return False
            
    def configure_context_management(self, session_id: str, max_messages: int = 20) -> bool:
        """
        Configure context management settings for a session.
        
        Args:
            session_id: Session identifier
            max_messages: Maximum number of messages to keep before summarization
            
        Returns:
            True if successful, False otherwise
        """
        try:
            session = self.get_session(session_id)
            if not session:
                logger.warning(f"Session {session_id} not found for context management configuration")
                return False
                
            metadata = session.get("metadata", {})
            
            # Update context management settings
            metadata["max_messages_before_summary"] = max_messages
            
            # Save the updated metadata
            result = self.collection.update_one(
                {"session_id": session_id},
                {"$set": {"metadata": metadata, "last_active": datetime.now()}}
            )
            
            if result.modified_count > 0 or result.matched_count > 0:
                logger.info(f"Updated context management settings for session {session_id}")
                return True
            else:
                logger.warning(f"Session {session_id} not found for context management configuration")
                return False
        except Exception as e:
            logger.error(f"Error configuring context management: {e}")
            return False 