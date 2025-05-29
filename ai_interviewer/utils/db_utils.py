"""Utility functions for database operations."""
import logging
import json
import uuid
from typing import Optional, Dict, Any, List, Union
from datetime import datetime

logger = logging.getLogger(__name__)

def migrate_tool_call_format(db_client, db_name: str, collection_name: str) -> Dict[str, int]:
    """
    Migrates tool_calls in MongoDB checkpoints from using 'arguments' to 'args'.
    
    Args:
        db_client: MongoDB client instance
        db_name: Database name
        collection_name: Collection name for checkpoints
        
    Returns:
        Dictionary with counts of documents processed and updated
    """
    try:
        collection = db_client[db_name][collection_name]
        
        # Stats to track progress
        stats = {
            "total_docs": 0,
            "updated_docs": 0,
            "errors": 0
        }
        
        # Find all documents that might contain tool_calls with 'arguments'
        cursor = collection.find({})
        
        for doc in cursor:
            stats["total_docs"] += 1
            try:
                metadata = doc.get("metadata", {})
                updated = False
                
                # Recursively find and update any 'arguments' to 'args' in the metadata
                def update_arguments_to_args(obj):
                    nonlocal updated
                    if isinstance(obj, dict):
                        # Check if this is a tool call with 'arguments'
                        if "name" in obj and "arguments" in obj and "type" in obj and obj.get("type") == "tool_call":
                            # Convert arguments to args
                            obj["args"] = obj.pop("arguments")
                            updated = True
                            
                            # Ensure there's an id field
                            if "id" not in obj:
                                import uuid
                                obj["id"] = f"tool_{uuid.uuid4().hex[:8]}"
                                updated = True
                                
                        # Recursively process all values
                        for key, value in list(obj.items()):
                            obj[key] = update_arguments_to_args(value)
                        return obj
                    elif isinstance(obj, list):
                        return [update_arguments_to_args(item) for item in obj]
                    else:
                        return obj
                
                # Update the metadata
                updated_metadata = update_arguments_to_args(metadata)
                
                # If changes were made, update the document
                if updated:
                    collection.update_one(
                        {"_id": doc["_id"]},
                        {"$set": {"metadata": updated_metadata}}
                    )
                    stats["updated_docs"] += 1
                    
            except Exception as e:
                logger.error(f"Error processing document {doc.get('_id')}: {str(e)}")
                stats["errors"] += 1
                
        logger.info(f"Migration complete: {stats}")
        return stats
        
    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")
        return {"error": str(e)}

def clear_session_checkpoints(db_client, db_name: str, collection_name: str, 
                             session_id: str) -> Dict[str, Any]:
    """
    Clears all checkpoints for a specific session to recover from broken sessions.
    
    Args:
        db_client: MongoDB client instance
        db_name: Database name
        collection_name: Collection name for checkpoints
        session_id: The session ID to clear
        
    Returns:
        Dictionary with status and details of the operation
    """
    try:
        collection = db_client[db_name][collection_name]
        
        # Find all documents for the session
        result = collection.delete_many({"thread_id": session_id})
        
        # Return operation status
        return {
            "status": "success",
            "deleted_count": result.deleted_count,
            "session_id": session_id
        }
        
    except Exception as e:
        logger.error(f"Failed to clear session {session_id}: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "session_id": session_id
        }

def create_new_session(db_client, db_name: str, collection_name: str, 
                      user_id: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Creates a new clean session with the provided metadata.
    
    Args:
        db_client: MongoDB client instance
        db_name: Database name
        collection_name: Collection name for sessions
        user_id: User ID to associate with the session
        metadata: Optional metadata to store with the session
        
    Returns:
        Dictionary with the session details
    """
    try:
        collection = db_client[db_name][collection_name]
        
        # Generate a new session ID
        session_id = f"sess-{uuid.uuid4()}"
        
        # Prepare session document
        session_doc = {
            "thread_id": session_id,
            "user_id": user_id,
            "created_at": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        
        # Insert the new session
        collection.insert_one(session_doc)
        
        return {
            "status": "success",
            "session_id": session_id,
            "user_id": user_id
        }
        
    except Exception as e:
        logger.error(f"Failed to create new session for user {user_id}: {str(e)}")
        return {
            "status": "error",
            "error": str(e),
            "user_id": user_id
        } 