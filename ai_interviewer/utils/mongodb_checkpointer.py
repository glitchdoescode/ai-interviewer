"""
MongoDB-based checkpoint storage for LangGraph.

This module provides a checkpointer that uses MongoDB as a persistence layer.
"""

import logging
import time
import uuid
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional, Tuple

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

from langgraph.checkpoint.base import checkpoint, CheckpointTuple, TConfig
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

logger = logging.getLogger(__name__)

class MongoDBCheckpointer:
    """MongoDB-based implementation of checkpointer for LangGraph.
    
    This class provides persistence for LangGraph state using MongoDB.
    
    Args:
        connection_uri: MongoDB connection URI
        database_name: Database name to use
        collection_name: Collection name to use for storing checkpoints
    """
    
    def __init__(
        self,
        connection_uri: str,
        database_name: str,
        collection_name: str,
    ):
        """Initialize with MongoDB connection details."""
        # Connect to MongoDB
        self.client = MongoClient(connection_uri)
        self.db: Database = self.client[database_name]
        self.collection: Collection = self.db[collection_name]
        
        # Set up indexes for efficient retrieval
        self._setup_indexes()
        
        # Serializer for converting Python objects to JSON and back
        self.serializer = JsonPlusSerializer()
    
    def _setup_indexes(self) -> None:
        """Set up MongoDB indexes for efficient querying."""
        # Create indexes for fast lookup
        self.collection.create_index([("thread_id", 1), ("created_at", -1)])
        self.collection.create_index([("thread_id", 1), ("checkpoint_id", 1)], unique=True)
    
    def put(self, config: TConfig, checkpoint_data: Dict[str, Any]) -> TConfig:
        """Store a checkpoint in MongoDB.
        
        Args:
            config: Configuration containing thread ID
            checkpoint_data: The checkpoint data to store
            
        Returns:
            Updated config with checkpoint ID
        """
        thread_id = config["configurable"].get("thread_id")
        if not thread_id:
            raise ValueError("Thread ID is required in config")
        
        # Check if we're updating an existing checkpoint
        checkpoint_id = config["configurable"].get("checkpoint_id")
        if not checkpoint_id:
            # Generate a new checkpoint ID
            checkpoint_id = str(uuid.uuid4())
        
        # Prepare document
        document = {
            "thread_id": thread_id,
            "checkpoint_id": checkpoint_id,
            "parent_id": config["configurable"].get("parent_id"),
            "created_at": datetime.utcnow(),
            "data": self.serializer.dumps(checkpoint_data)
        }
        
        # Insert or update checkpoint
        self.collection.replace_one(
            {"thread_id": thread_id, "checkpoint_id": checkpoint_id},
            document,
            upsert=True
        )
        
        # Return updated config with checkpoint ID
        updated_config = config.copy()
        updated_config["configurable"] = {
            **config["configurable"],
            "checkpoint_id": checkpoint_id
        }
        
        return updated_config
    
    def get_tuple(self, config: TConfig) -> Optional[CheckpointTuple]:
        """Retrieve a checkpoint from MongoDB.
        
        Args:
            config: Configuration with thread ID and optional checkpoint ID
            
        Returns:
            CheckpointTuple containing the checkpoint data or None if not found
        """
        thread_id = config["configurable"].get("thread_id")
        if not thread_id:
            raise ValueError("Thread ID is required in config")
        
        # Get the specific checkpoint if ID is provided, otherwise get the latest
        checkpoint_id = config["configurable"].get("checkpoint_id")
        
        query = {"thread_id": thread_id}
        if checkpoint_id:
            query["checkpoint_id"] = checkpoint_id
            document = self.collection.find_one(query)
        else:
            # Get the most recent checkpoint for this thread
            document = self.collection.find_one(
                {"thread_id": thread_id},
                sort=[("created_at", -1)]
            )
        
        if not document:
            return None
        
        # Get parent config if it exists
        parent_config = None
        if document.get("parent_id"):
            parent_config = {
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_id": document["parent_id"]
                }
            }
        
        # Create checkpoint tuple
        result_config = {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_id": document["checkpoint_id"]
            }
        }
        
        # Convert the stored data back to Python objects
        checkpoint_data = self.serializer.loads(document["data"])
        
        return CheckpointTuple(
            result_config,
            checkpoint_data,
            parent_config
        )
    
    def list(self, config: TConfig) -> Iterator[CheckpointTuple]:
        """List all checkpoints for a thread.
        
        Args:
            config: Configuration with thread ID
            
        Returns:
            Iterator of CheckpointTuple objects for the thread
        """
        thread_id = config["configurable"].get("thread_id")
        if not thread_id:
            raise ValueError("Thread ID is required in config")
        
        # Get all checkpoints for this thread
        documents = self.collection.find(
            {"thread_id": thread_id},
            sort=[("created_at", -1)]
        )
        
        for document in documents:
            # Get parent config if it exists
            parent_config = None
            if document.get("parent_id"):
                parent_config = {
                    "configurable": {
                        "thread_id": thread_id,
                        "checkpoint_id": document["parent_id"]
                    }
                }
            
            # Create checkpoint tuple
            result_config = {
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_id": document["checkpoint_id"]
                }
            }
            
            # Convert the stored data back to Python objects
            checkpoint_data = self.serializer.loads(document["data"])
            
            yield CheckpointTuple(
                result_config,
                checkpoint_data,
                parent_config
            )
    
    def close(self):
        """Close MongoDB connection."""
        if hasattr(self, 'client') and self.client:
            self.client.close()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

# Async version for async LangGraph workflows
class AsyncMongoDBCheckpointer(MongoDBCheckpointer):
    """Async MongoDB checkpointer implementation."""
    
    async def aput(self, config: TConfig, checkpoint: Dict[str, Any], metadata: Dict[str, Any]) -> None:
        """
        Store a checkpoint asynchronously.
        
        Args:
            config: Checkpoint configuration
            checkpoint: Checkpoint data
            metadata: Additional metadata
        """
        # For now, just use the synchronous version since pymongo doesn't have native async
        # In a production setting, you might want to use motor for async MongoDB operations
        self.put(config, checkpoint, metadata)
    
    async def aget(self, config: TConfig) -> Optional[CheckpointTuple]:
        """
        Retrieve a checkpoint asynchronously.
        
        Args:
            config: Checkpoint configuration
            
        Returns:
            CheckpointTuple if found, otherwise None
        """
        # For now, just use the synchronous version
        return self.get(config)
    
    async def alist(self, config: TConfig) -> List[CheckpointTuple]:
        """
        List all checkpoints for a thread asynchronously.
        
        Args:
            config: Checkpoint configuration
            
        Returns:
            List of CheckpointTuple objects
        """
        # For now, just use the synchronous version
        return self.list(config)
    
    async def adelete(self, config: TConfig) -> None:
        """
        Delete a checkpoint asynchronously.
        
        Args:
            config: Checkpoint configuration
        """
        # For now, just use the synchronous version
        self.delete(config)
    
    async def adelete_thread(self, thread_id: str) -> None:
        """
        Delete all checkpoints for a thread asynchronously.
        
        Args:
            thread_id: Thread ID to delete
        """
        # For now, just use the synchronous version
        self.delete_thread(thread_id) 