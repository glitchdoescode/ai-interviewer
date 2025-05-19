"""
Session manager for {SYSTEM_NAME} sessions.

This module provides functionality for managing interview sessions,
including creation, retrieval, and persistence.
"""
import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
import pymongo
from pymongo.mongo_client import MongoClient
from ai_interviewer.utils.config import SYSTEM_NAME
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

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
        self.client = AsyncIOMotorClient(connection_uri)
        self.db = self.client[database_name]
        self.collection = self.db[collection_name]
        
        # Create indexes
        asyncio.create_task(self._create_indexes())
        
        logger.info(f"Session manager initialized with {connection_uri}")
    
    async def _create_indexes(self):
        """Create necessary indexes for the collection."""
        await self.collection.create_index([("session_id", pymongo.ASCENDING)], unique=True)
        await self.collection.create_index([("user_id", pymongo.ASCENDING)])
        await self.collection.create_index([("last_active", pymongo.DESCENDING)])
    
    async def create_session(self, user_id: str, metadata: Optional[Dict[str, Any]] = None) -> str:
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
            await self.collection.insert_one(document)
            logger.info(f"Created new session {session_id} for user {user_id}")
            return session_id
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            raise
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session details by ID.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session details or None if not found
        """
        try:
            session = await self.collection.find_one({"session_id": session_id})
            return session
        except Exception as e:
            logger.error(f"Error retrieving session {session_id}: {e}")
            return None
    
    async def get_user_sessions(self, user_id: str, include_completed: bool = False) -> List[Dict[str, Any]]:
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
                
            cursor = self.collection.find(
                query,
                sort=[("last_active", pymongo.DESCENDING)]
            )
            
            sessions = await cursor.to_list(length=None)
            
            logger.info(f"Found {len(sessions)} sessions for user {user_id}")
            return sessions
        except Exception as e:
            logger.error(f"Error retrieving sessions for user {user_id}: {e}")
            return []
    
    async def update_session_activity(self, session_id: str) -> bool:
        """
        Update the last activity timestamp for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if successful, False otherwise
        """
        try:
            result = await self.collection.update_one(
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
    
    async def update_session_metadata(self, session_id: str, metadata: Dict[str, Any]) -> bool:
        """
        Update metadata for a session.
        
        Args:
            session_id: Session identifier
            metadata: Metadata to update
            
        Returns:
            True if successful, False otherwise
        """
        try:
            result = await self.collection.update_one(
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
    
    async def complete_session(self, session_id: str) -> bool:
        """
        Mark a session as completed.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if successful, False otherwise
        """
        try:
            result = await self.collection.update_one(
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
    
    async def delete_session(self, session_id: str) -> bool:
        """
        Delete a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            True if successful, False otherwise
        """
        try:
            result = await self.collection.delete_one({"session_id": session_id})
            
            if result.deleted_count > 0:
                logger.info(f"Deleted session {session_id}")
                return True
            else:
                logger.warning(f"Session {session_id} not found for deletion")
                return False
        except Exception as e:
            logger.error(f"Error deleting session: {e}")
            return False
    
    async def list_active_sessions(self, max_inactive_minutes: int = 60) -> List[Dict[str, Any]]:
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
            cursor = self.collection.find(
                {
                    "status": "active",
                    "last_active": {"$gte": cutoff_datetime}
                },
                sort=[("last_active", pymongo.DESCENDING)]
            )
            
            sessions = await cursor.to_list(length=None)
            
            logger.info(f"Found {len(sessions)} active sessions")
            return sessions
        except Exception as e:
            logger.error(f"Error listing active sessions: {e}")
            return []
    
    async def get_most_recent_session(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the most recent session for a user.
        
        Args:
            user_id: User identifier
            
        Returns:
            Most recent session or None if not found
        """
        try:
            session = await self.collection.find_one(
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
    
    async def clean_inactive_sessions(self, max_inactive_minutes: int = 1440) -> int:
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
            result = await self.collection.update_many(
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
    
    async def close(self):
        """Close the MongoDB connection."""
        if self.client:
            await self.client.close()
            logger.info("MongoDB connection closed")
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit with proper cleanup."""
        await self.close()
    
    async def update_session_messages(self, session_id: str, messages: List[Any]) -> bool:
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
            result = await self.collection.update_one(
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