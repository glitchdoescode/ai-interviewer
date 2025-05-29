#!/usr/bin/env python
"""Script to migrate tool_calls in MongoDB from 'arguments' to 'args'."""
import os
import logging
import argparse
from pymongo import MongoClient
from ai_interviewer.utils.db_utils import migrate_tool_call_format
from ai_interviewer.utils.config import get_db_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

def main():
    """Run the migration script."""
    parser = argparse.ArgumentParser(description='Migrate tool_calls from arguments to args')
    parser.add_argument('--uri', type=str, help='MongoDB URI (optional, defaults to config)')
    parser.add_argument('--db', type=str, help='Database name (optional, defaults to config)')
    parser.add_argument('--collection', type=str, default='checkpoints', 
                        help='Collection name for checkpoints (default: checkpoints)')
    
    args = parser.parse_args()
    
    # Get database config
    db_config = get_db_config()
    
    # Use provided args or fall back to config
    mongo_uri = args.uri or db_config.get('uri')
    db_name = args.db or db_config.get('database')
    collection_name = args.collection
    
    if not mongo_uri:
        logger.error("MongoDB URI not provided and not found in config")
        return
        
    if not db_name:
        logger.error("Database name not provided and not found in config")
        return
    
    logger.info(f"Connecting to MongoDB at {mongo_uri}")
    logger.info(f"Using database: {db_name}, collection: {collection_name}")
    
    # Confirm with user
    confirm = input(f"This will update tool_calls in {db_name}.{collection_name}. Continue? (y/n): ")
    if confirm.lower() != 'y':
        logger.info("Migration cancelled")
        return
    
    # Connect to MongoDB
    try:
        client = MongoClient(mongo_uri)
        
        # Run migration
        result = migrate_tool_call_format(client, db_name, collection_name)
        
        logger.info("Migration results:")
        for key, value in result.items():
            logger.info(f"  {key}: {value}")
            
        logger.info("Migration completed")
        
    except Exception as e:
        logger.error(f"Error during migration: {str(e)}")
    finally:
        if 'client' in locals():
            client.close()

if __name__ == "__main__":
    main() 