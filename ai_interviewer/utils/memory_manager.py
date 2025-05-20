"""
Memory management for AI Interviewer using LangGraph's persistent stores.

This module extends the memory capabilities of the AI Interviewer by implementing
both short-term (thread-level) and long-term (cross-thread) memory persistence.
"""
import logging
import uuid
from typing import Dict, List, Optional, Any, Tuple, Union
from datetime import datetime

from pymongo import MongoClient
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.collection import Collection
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.checkpoint.mongodb import MongoDBSaver
from langgraph.checkpoint.mongodb.aio import AsyncMongoDBSaver
from langgraph.store.mongodb.base import MongoDBStore
from langgraph.store.memory import InMemoryStore

from ai_interviewer.utils.config import get_db_config

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

class InterviewMemoryManager:
    """
    Manages both short-term (thread-level) and long-term (cross-thread) memory for the AI Interviewer.
    
    This class provides:
    1. Thread-level memory persistence via MongoDBSaver checkpointer (sync) or AsyncMongoDBSaver (async)
    2. Cross-thread memory persistence via MongoDBStore (sync) or InMemoryStore (async)
    3. Helper methods for common memory operations
    """
    
    def __init__(
        self,
        connection_uri: Optional[str] = None,
        db_name: Optional[str] = None,
        checkpoint_collection: Optional[str] = None,
        store_collection: Optional[str] = None,
        use_async: bool = True
    ):
        """
        Initialize the InterviewMemoryManager.
        
        Args:
            connection_uri: MongoDB connection URI (from env if None)
            db_name: Database name (from env if None)
            checkpoint_collection: Collection name for checkpoints (from env if None)
            store_collection: Collection name for cross-thread store (from env if None)
            use_async: Whether to use async clients and savers (default: True)
        """
        # Get database config
        db_config = get_db_config()
        self.connection_uri = connection_uri or db_config["uri"]
        self.db_name = db_name or db_config["database"]
        self.checkpoint_collection = checkpoint_collection or db_config["sessions_collection"]
        self.store_collection = store_collection or "interview_memory_store"
        self.use_async = use_async
        self.async_setup_completed = False
        
        try:
            if self.use_async:
                # Initialize async MongoDB client
                self.async_client = AsyncIOMotorClient(self.connection_uri)
                
                # Store params for async_checkpointer (don't initialize it yet to avoid "no running event loop" error)
                self.async_checkpointer = None
                self.async_checkpointer_params = {
                    "client": self.async_client,
                    "db_name": self.db_name,
                    "collection_name": self.checkpoint_collection
                }
                
                # Initialize async store for cross-thread memory
                # Use InMemoryStore for async operations as there is no AsyncMongoDBStore
                self.async_store = InMemoryStore()
                logger.info(f"Initialized InMemoryStore for async operations")
                
                # Initialize sync clients as None since we're in async mode
                self.client = None
                self.checkpointer = None
                self.store = None
                
                logger.info(f"Memory manager initialized with async MongoDB client: {self.db_name}")
                logger.info(f"Async checkpointer will be initialized during async_setup")
            else:
                # Initialize MongoDB client - synchronous version
                self.client = MongoClient(self.connection_uri)
                
                # Create store and checkpointer - synchronous version
                self.checkpointer = MongoDBSaver(
                    client=self.client,
                    db_name=self.db_name,
                    collection_name=self.checkpoint_collection
                )
                
                # Initialize store for cross-thread memory - synchronous version
                db = self.client[self.db_name]
                collection = db[self.store_collection]
                
                try:
                    # Pass the collection object directly to MongoDBStore
                    self.store = MongoDBStore(collection)
                    logger.info(f"Initialized MongoDB store with collection: {self.store_collection}")
                except Exception as store_error:
                    logger.error(f"Error initializing MongoDB store: {store_error}")
                    # Create a basic fallback store
                    from langgraph.store.base import SimpleStore
                    self.store = SimpleStore()
                    logger.warning("Using SimpleStore as fallback after MongoDB store initialization failed")
                
                # Initialize async clients as None since we're in sync mode
                self.async_client = None
                self.async_checkpointer = None
                self.async_store = None
                
                # Verify connections
                try:
                    db[self.checkpoint_collection].find_one({})
                    collection.find_one({})
                    logger.info("MongoDB connections verified")
                except Exception as e:
                    logger.warning(f"Could not verify MongoDB connections: {e}")
                
                logger.info(f"Memory manager initialized with synchronous MongoDB: {self.db_name}")
        except Exception as e:
            logger.error(f"Error initializing memory manager: {e}")
            raise
    
    async def async_setup(self):
        """Set up database collections and indexes for async operations."""
        try:
            if not self.use_async:
                logger.warning("Cannot use async_setup when initialized with use_async=False")
                return
            
            # Create the async checkpointer now that we're in an async context
            if self.async_checkpointer is None and hasattr(self, 'async_checkpointer_params'):
                logger.info("Initializing AsyncMongoDBSaver in async context")
                self.async_checkpointer = AsyncMongoDBSaver(**self.async_checkpointer_params)
            
            # Set up async checkpointer if it has a setup method
            if self.async_checkpointer and hasattr(self.async_checkpointer, 'setup') and callable(getattr(self.async_checkpointer, 'setup')):
                await self.async_checkpointer.setup()
                logger.info("Async checkpointer setup completed")
            
            # Check if async store has setup method 
            if hasattr(self.async_store, 'setup') and callable(getattr(self.async_store, 'setup')):
                await self.async_store.setup()
                logger.info("Async store setup completed")
            
            # Mark setup as completed
            self.async_setup_completed = True
            
            logger.info("Async memory manager setup complete")
        except Exception as e:
            logger.error(f"Error setting up async memory manager: {e}")
            raise
    
    def setup(self):
        """Set up database collections and indexes for sync operations."""
        try:
            if self.use_async:
                logger.warning("Cannot use sync setup when initialized with use_async=True, use async_setup instead")
                return
                
            # Set up checkpointer - MongoDBSaver may not have setup method
            if hasattr(self.checkpointer, 'setup') and callable(getattr(self.checkpointer, 'setup')):
                self.checkpointer.setup()
            
            # Check if store has setup method 
            if hasattr(self.store, 'setup') and callable(getattr(self.store, 'setup')):
                self.store.setup()
            
            logger.info("Memory manager setup complete")
        except Exception as e:
            logger.error(f"Error setting up memory manager: {e}")
            raise
    
    def get_checkpointer(self):
        """
        Get the appropriate checkpointer for thread-level memory persistence.
        
        Returns:
            MongoDBSaver or AsyncMongoDBSaver instance based on use_async setting
        """
        if self.use_async:
            if not self.async_checkpointer:
                logger.warning("Async checkpointer requested but not initialized. Make sure to call async_setup() first.")
            return self.async_checkpointer
        return self.checkpointer
    
    def get_store(self):
        """
        Get the appropriate store for cross-thread memory persistence.
        
        Returns:
            MongoDBStore or InMemoryStore instance based on use_async setting
        """
        if self.use_async:
            return self.async_store
        return self.store
    
    # Helper methods for common interview memory operations
    
    def save_user_memory(self, user_id: str, key: str, value: Any) -> bool:
        """
        Save a memory item for a specific user.
        
        Args:
            user_id: User identifier
            key: Memory key/identifier
            value: Memory value (must be JSON serializable)
            
        Returns:
            Success status
        """
        try:
            namespace = ("user", user_id)
            store = self.get_store()
            if store is None:
                logger.error("Store not initialized")
                return False
            store.put(namespace, key, value)
            return True
        except Exception as e:
            logger.error(f"Error saving user memory: {e}")
            return False
    
    def save_candidate_profile(self, user_id: str, profile_data: Dict[str, Any]) -> bool:
        """
        Save or update a candidate's profile with extracted information.
        
        Args:
            user_id: User identifier
            profile_data: Profile data dictionary
            
        Returns:
            Success status
        """
        try:
            namespace = ("candidate_profiles",)
            store = self.get_store()
            if store is None:
                logger.error("Store not initialized")
                return False
            
            # Add timestamp to the profile data
            profile_data["updated_at"] = datetime.now().isoformat()
            
            # Check if profile already exists
            existing_profiles = list(store.search(namespace, filter={"user_id": user_id}))
            
            if existing_profiles:
                # Update existing profile
                profile_id = existing_profiles[0].key
                current_data = existing_profiles[0].value
                # Merge with new data, preserving history where appropriate
                merged_data = self._merge_profile_data(current_data, profile_data)
                store.put(namespace, profile_id, merged_data)
                logger.info(f"Updated candidate profile for user {user_id}")
            else:
                # Create new profile
                profile_id = str(uuid.uuid4())
                profile_data["user_id"] = user_id
                profile_data["created_at"] = datetime.now().isoformat()
                store.put(namespace, profile_id, profile_data)
                logger.info(f"Created new candidate profile for user {user_id}")
            
            return True
        except Exception as e:
            logger.error(f"Error saving candidate profile: {e}")
            return False
    
    def get_candidate_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a candidate's profile data.
        
        Args:
            user_id: User identifier
            
        Returns:
            Profile data dictionary or None if not found
        """
        try:
            namespace = ("candidate_profiles",)
            store = self.get_store()
            if store is None:
                logger.error("Store not initialized")
                return None
            
            profiles = list(store.search(namespace, filter={"user_id": user_id}))
            
            if profiles:
                return profiles[0].value
            else:
                return None
        except Exception as e:
            logger.error(f"Error retrieving candidate profile: {e}")
            return None
    
    def save_interview_memory(self, session_id: str, memory_type: str, memory_data: Dict[str, Any]) -> bool:
        """
        Save interview-specific memory that persists across sessions.
        
        Args:
            session_id: Session identifier
            memory_type: Type of memory (e.g., "insights", "evaluations", "feedback")
            memory_data: Memory data to store
            
        Returns:
            Success status
        """
        try:
            namespace = ("interview_memories", memory_type)
            store = self.get_store()
            if store is None:
                logger.error("Store not initialized")
                return False
            
            memory_id = f"{session_id}_{datetime.now().isoformat()}"
            
            # Add metadata
            memory_data["session_id"] = session_id
            memory_data["created_at"] = datetime.now().isoformat()
            memory_data["memory_type"] = memory_type
            
            store.put(namespace, memory_id, memory_data)
            logger.info(f"Saved {memory_type} memory for session {session_id}")
            return True
        except Exception as e:
            logger.error(f"Error saving interview memory: {e}")
            return False
    
    def get_interview_memories(self, session_id: str, memory_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get interview memories for a specific session.
        
        Args:
            session_id: Session identifier
            memory_type: Optional type filter
            
        Returns:
            List of memory items
        """
        try:
            store = self.get_store()
            if store is None:
                logger.error("Store not initialized")
                return []
            
            if memory_type:
                namespace = ("interview_memories", memory_type)
                memories = list(store.search(namespace, filter={"session_id": session_id}))
            else:
                # Search across all memory types
                all_memories = []
                memory_types = ["insights", "evaluations", "feedback", "coding"]
                
                for mem_type in memory_types:
                    namespace = ("interview_memories", mem_type)
                    memories = list(store.search(namespace, filter={"session_id": session_id}))
                    all_memories.extend([m.value for m in memories])
                
                return all_memories
            
            return [m.value for m in memories]
        except Exception as e:
            logger.error(f"Error retrieving interview memories: {e}")
            return []
    
    def search_memories(self, query: str, user_id: Optional[str] = None, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Search for memories across all namespaces based on content.
        This is a simple implementation that will be enhanced with vector search.
        
        Args:
            query: Search query
            user_id: Optional user ID to restrict search
            max_results: Maximum number of results to return
            
        Returns:
            List of matching memory items
        """
        try:
            store = self.get_store()
            if store is None:
                logger.error("Store not initialized")
                return []
            
            all_results = []
            
            # Search in candidate profiles
            namespace = ("candidate_profiles",)
            if user_id:
                profiles = list(store.search(namespace, filter={"user_id": user_id}))
            else:
                profiles = list(store.search(namespace))
            
            # Add matching profiles
            for profile in profiles:
                profile_str = str(profile.value)
                if query.lower() in profile_str.lower():
                    all_results.append({
                        "type": "candidate_profile",
                        "key": profile.key,
                        "value": profile.value
                    })
            
            # Search in interview memories
            memory_types = ["insights", "evaluations", "feedback", "coding"]
            for mem_type in memory_types:
                namespace = ("interview_memories", mem_type)
                if user_id:
                    memories = list(store.search(namespace, filter={"user_id": user_id}))
                else:
                    memories = list(store.search(namespace))
                
                # Add matching memories
                for memory in memories:
                    memory_str = str(memory.value)
                    if query.lower() in memory_str.lower():
                        all_results.append({
                            "type": f"interview_{mem_type}",
                            "key": memory.key,
                            "value": memory.value
                        })
            
            # Return limited results
            return all_results[:max_results]
        except Exception as e:
            logger.error(f"Error searching memories: {e}")
            return []
    
    def close(self):
        """Close database connections and release resources."""
        try:
            if self.use_async:
                # Close async client if it exists
                if self.async_client:
                    self.async_client.close()
                    logger.info("Closed async MongoDB client")
            else:
                # Close sync client if it exists
                if self.client:
                    self.client.close()
                    logger.info("Closed MongoDB client")
        except Exception as e:
            logger.error(f"Error closing MongoDB connections: {e}")

    async def aclose(self):
        """Asynchronously close database connections and release resources."""
        try:
            if self.use_async:
                # Close async client if it exists
                if self.async_client:
                    await self.async_client.close()
                    logger.info("Closed async MongoDB client")
            else:
                # Close sync client if it exists
                if self.client:
                    self.client.close()
                    logger.info("Closed MongoDB client")
        except Exception as e:
            logger.error(f"Error closing MongoDB connections: {e}")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    # Private helper methods
    
    def _merge_profile_data(self, current_data: Dict[str, Any], new_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Intelligently merge profile data, preserving history where appropriate.
        
        Args:
            current_data: Current profile data
            new_data: New profile data to merge
            
        Returns:
            Merged profile data
        """
        result = dict(current_data)
        
        # Always update timestamp
        result["updated_at"] = new_data["updated_at"]
        
        # Fields that should be appended rather than overwritten
        list_fields = ["key_skills", "notable_experiences", "strengths", "areas_for_improvement"]
        
        for key, value in new_data.items():
            if key in list_fields and key in current_data and isinstance(current_data[key], list):
                # Append new items to list, avoiding duplicates
                existing_items = set(str(item).lower() for item in current_data[key])
                for item in value:
                    if str(item).lower() not in existing_items:
                        result[key].append(item)
                        existing_items.add(str(item).lower())
            else:
                # For other fields, simply overwrite
                result[key] = value
        
        return result 