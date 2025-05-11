"""
MongoDB-based checkpoint storage for LangGraph.

This module provides a checkpointer that uses MongoDB as a persistence layer.
"""

import logging
import time
import uuid
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional, Tuple, Type

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

from langgraph.checkpoint.base import BaseCheckpointSaver, CheckpointTuple, create_checkpoint
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage

logger = logging.getLogger(__name__)

class LangChainMongoSerializer(JsonPlusSerializer):
    """Custom serializer that properly handles LangChain message objects."""

    def _custom_encoder(self, obj: Any) -> Any:
        """Custom encoder for LangChain message objects."""
        # Handle LangChain message objects
        if isinstance(obj, BaseMessage):
            message_type = obj.__class__.__name__
            result = {
                "__type": "langchain_message",
                "message_type": message_type,
                "content": obj.content,
                "additional_kwargs": obj.additional_kwargs,
            }
            
            # Add special handling for tool calls
            if hasattr(obj, "tool_calls") and obj.tool_calls:
                result["tool_calls"] = obj.tool_calls
                
            return result
            
        # Use parent serializer for other types
        return super()._custom_encoder(obj)
    
    def _custom_decoder(self, obj: Dict[str, Any]) -> Any:
        """Custom decoder for LangChain message objects."""
        if isinstance(obj, dict):
            obj_type = obj.get("__type")
            
            if obj_type == "langchain_message":
                message_type = obj.get("message_type")
                content = obj.get("content", "")
                additional_kwargs = obj.get("additional_kwargs", {})
                
                # Create the appropriate message type
                if message_type == "HumanMessage":
                    return HumanMessage(content=content, additional_kwargs=additional_kwargs)
                elif message_type == "AIMessage":
                    message = AIMessage(content=content, additional_kwargs=additional_kwargs)
                    # Handle tool calls if present
                    if "tool_calls" in obj:
                        message.tool_calls = obj["tool_calls"]
                    return message
                elif message_type == "SystemMessage":
                    return SystemMessage(content=content, additional_kwargs=additional_kwargs)
                # Default to base message if type not recognized
                return BaseMessage(content=content, additional_kwargs=additional_kwargs)
                
        # Use parent decoder for other types
        return super()._custom_decoder(obj)

class MongoDBCheckpointer(BaseCheckpointSaver):
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
        super().__init__()
        # Connect to MongoDB
        self.client = MongoClient(connection_uri)
        self.db: Database = self.client[database_name]
        self.collection: Collection = self.db[collection_name]
        
        # Set up indexes for efficient retrieval
        self._setup_indexes()
        
        # Use custom serializer for LangChain messages
        self.serializer = LangChainMongoSerializer()
    
    def _setup_indexes(self) -> None:
        """Set up MongoDB indexes for efficient querying."""
        # Create indexes for fast lookup
        self.collection.create_index([("thread_id", 1), ("created_at", -1)])
        self.collection.create_index([("thread_id", 1), ("checkpoint_id", 1)], unique=True)
    
    def put(self, config: Dict, checkpoint_data: Dict[str, Any], metadata: Dict[str, Any], new_versions: Any = None) -> Dict:
        """Store a checkpoint in MongoDB.
        
        Args:
            config: Configuration containing thread ID
            checkpoint_data: The checkpoint data to store
            metadata: Additional metadata
            new_versions: Version information (optional)
            
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
        
        try:
            # Prepare document
            document = {
                "thread_id": thread_id,
                "checkpoint_id": checkpoint_id,
                "parent_id": config["configurable"].get("parent_id"),
                "created_at": datetime.utcnow(),
                "data": self.serializer.dumps(checkpoint_data),
                "metadata": self.serializer.dumps(metadata),  # Also serialize metadata
                "versions": self.serializer.dumps(new_versions) if new_versions is not None else "{}"
            }
            
            # Insert or update checkpoint
            self.collection.replace_one(
                {"thread_id": thread_id, "checkpoint_id": checkpoint_id},
                document,
                upsert=True
            )
        except Exception as e:
            logger.error(f"Error storing checkpoint: {e}")
            raise
        
        # Return updated config with checkpoint ID
        updated_config = config.copy()
        updated_config["configurable"] = {
            **config["configurable"],
            "checkpoint_id": checkpoint_id
        }
        
        return updated_config
    
    def get_tuple(self, config: Dict) -> Optional[CheckpointTuple]:
        """Retrieve a checkpoint from MongoDB.
        
        Args:
            config: Configuration with thread ID and optional checkpoint ID
            
        Returns:
            CheckpointTuple containing the checkpoint data or None if not found
        """
        thread_id = config["configurable"].get("thread_id")
        if not thread_id:
            logger.error("Thread ID is required in config for get_tuple")
            raise ValueError("Thread ID is required in config")
        
        # Get the specific checkpoint if ID is provided, otherwise get the latest
        checkpoint_id = config["configurable"].get("checkpoint_id")
        
        query = {"thread_id": thread_id}
        if checkpoint_id:
            query["checkpoint_id"] = checkpoint_id
            logger.debug(f"Looking for specific checkpoint with ID {checkpoint_id}")
            document = self.collection.find_one(query)
        else:
            # Get the most recent checkpoint for this thread
            logger.debug(f"Looking for most recent checkpoint for thread {thread_id}")
            document = self.collection.find_one(
                {"thread_id": thread_id},
                sort=[("created_at", -1)]
            )
        
        if not document:
            logger.warning(f"No checkpoint found for thread_id={thread_id}, checkpoint_id={checkpoint_id}")
            return None
        
        logger.debug(f"Found checkpoint with ID {document.get('checkpoint_id')} for thread {thread_id}")
        
        # Get parent config if it exists
        parent_config = None
        if document.get("parent_id"):
            parent_config = {
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_id": document["parent_id"]
                }
            }
            logger.debug(f"Found parent checkpoint with ID {document['parent_id']}")
        
        # Create checkpoint tuple
        result_config = {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_id": document["checkpoint_id"]
            }
        }
        
        try:
            # Convert the stored data back to Python objects
            logger.debug(f"Deserializing checkpoint data for checkpoint {document['checkpoint_id']}")
            checkpoint_data = self.serializer.loads(document["data"])
            
            # Verify that checkpoint_data contains expected fields
            if isinstance(checkpoint_data, dict):
                logger.debug(f"Checkpoint data has keys: {list(checkpoint_data.keys())}")
                # Check if messages field exists and is valid
                if "messages" in checkpoint_data:
                    messages = checkpoint_data["messages"]
                    logger.debug(f"Checkpoint contains {len(messages)} messages")
            else:
                logger.warning(f"Unexpected checkpoint data type: {type(checkpoint_data)}")
            
            # Create and return the checkpoint tuple
            checkpoint_tuple = CheckpointTuple(
                result_config,
                checkpoint_data,
                parent_config
            )
            return checkpoint_tuple
            
        except Exception as e:
            logger.error(f"Error deserializing checkpoint: {e}", exc_info=True)
            return None
    
    def list(self, config: Dict) -> Iterator[CheckpointTuple]:
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
            try:
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
            except Exception as e:
                logger.error(f"Error deserializing checkpoint: {e}")
                continue
    
    def put_writes(self, config: Dict, writes: List[Dict], task_id: str) -> None:
        """Store intermediate writes for a checkpoint.
        
        Args:
            config: Configuration with thread ID
            writes: List of intermediate writes
            task_id: ID of the task
        """
        thread_id = config["configurable"].get("thread_id")
        if not thread_id:
            raise ValueError("Thread ID is required in config")
        
        # Get the checkpoint ID
        checkpoint_id = config["configurable"].get("checkpoint_id")
        if not checkpoint_id:
            # If we don't have a checkpoint ID, we can't store intermediate writes
            logger.warning("No checkpoint_id in config, can't store intermediate writes")
            return
        
        # Create a writes collection if it doesn't exist yet
        writes_collection_name = f"{self.collection.name}_writes"
        writes_collection = self.db[writes_collection_name]
        
        # Set up indexes for the writes collection if needed
        if writes_collection_name not in self.db.list_collection_names():
            writes_collection.create_index([
                ("thread_id", 1),
                ("checkpoint_id", 1),
                ("task_id", 1)
            ], unique=True)
        
        try:
            # Store each write
            for write in writes:
                document = {
                    "thread_id": thread_id,
                    "checkpoint_id": checkpoint_id,
                    "task_id": task_id,
                    "write": self.serializer.dumps(write),
                    "created_at": datetime.utcnow()
                }
                
                # Insert or update the write
                writes_collection.replace_one(
                    {
                        "thread_id": thread_id,
                        "checkpoint_id": checkpoint_id,
                        "task_id": task_id
                    },
                    document,
                    upsert=True
                )
        except Exception as e:
            logger.error(f"Error storing writes: {e}")
            # Continue execution even if writes fail
    
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

# Remove the AsyncMongoDBCheckpointer for now until we properly implement it 