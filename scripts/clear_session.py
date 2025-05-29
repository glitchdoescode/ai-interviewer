#!/usr/bin/env python
"""Script to clear problematic checkpoint sessions by session ID."""
import os
import logging
import argparse
from pymongo import MongoClient
from ai_interviewer.utils.db_utils import clear_session_checkpoints, create_new_session
from ai_interviewer.utils.config import get_db_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

def main():
    """Run the session clearing script."""
    parser = argparse.ArgumentParser(description='Clear problematic session checkpoints')
    parser.add_argument('--session-id', type=str, required=True, 
                        help='Session ID to clear')
    parser.add_argument('--create-new', action='store_true',
                        help='Create a new session for the user after clearing')
    parser.add_argument('--user-id', type=str,
                        help='User ID (required if creating a new session)')
    parser.add_argument('--uri', type=str, help='MongoDB URI (optional, defaults to config)')
    parser.add_argument('--db', type=str, help='Database name (optional, defaults to config)')
    parser.add_argument('--collection', type=str, default='checkpoints',
                        help='Collection name for checkpoints (default: checkpoints)')
    parser.add_argument('--sessions-collection', type=str, default='interview_sessions',
                        help='Collection name for sessions (default: interview_sessions)')
    
    args = parser.parse_args()
    
    # Get database config
    db_config = get_db_config()
    
    # Use provided args or fall back to config
    mongo_uri = args.uri or db_config.get('uri')
    db_name = args.db or db_config.get('database')
    checkpoint_collection = args.collection
    sessions_collection = args.sessions_collection
    
    if not mongo_uri:
        logger.error("MongoDB URI not provided and not found in config")
        return
        
    if not db_name:
        logger.error("Database name not provided and not found in config")
        return
    
    # Validate session ID
    session_id = args.session_id
    if not session_id:
        logger.error("Session ID is required")
        return
    
    # Check if creating new session
    create_new = args.create_new
    user_id = args.user_id
    
    if create_new and not user_id:
        logger.error("User ID is required when creating a new session")
        return
    
    logger.info(f"Connecting to MongoDB at {mongo_uri}")
    logger.info(f"Using database: {db_name}, checkpoint collection: {checkpoint_collection}")
    
    # Confirm with user
    confirm = input(f"This will delete all checkpoints for session {session_id}. Continue? (y/n): ")
    if confirm.lower() != 'y':
        logger.info("Operation cancelled")
        return
    
    # Connect to MongoDB
    try:
        client = MongoClient(mongo_uri)
        
        # Clear session checkpoints
        result = clear_session_checkpoints(client, db_name, checkpoint_collection, session_id)
        
        if result["status"] == "success":
            logger.info(f"Successfully cleared {result['deleted_count']} checkpoints for session {session_id}")
            
            # Create new session if requested
            if create_new:
                new_session = create_new_session(client, db_name, sessions_collection, user_id)
                
                if new_session["status"] == "success":
                    logger.info(f"Created new session {new_session['session_id']} for user {user_id}")
                else:
                    logger.error(f"Failed to create new session: {new_session.get('error')}")
        else:
            logger.error(f"Failed to clear session: {result.get('error')}")
            
    except Exception as e:
        logger.error(f"Error: {str(e)}")
    finally:
        if 'client' in locals():
            client.close()

if __name__ == "__main__":
    main() 