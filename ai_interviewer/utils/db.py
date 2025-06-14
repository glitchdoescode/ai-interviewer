from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
import logging
from .config import get_db_config

logger = logging.getLogger(__name__)

def get_mongodb_client() -> MongoClient:
    """Get MongoDB client with proper connection settings."""
    db_config = get_db_config()
    uri = db_config.get("uri")
    options = db_config.get("options", {})
    
    try:
        # Initialize client with connection options from config
        client = MongoClient(
            uri,
            serverSelectionTimeoutMS=options.get("serverSelectionTimeoutMS", 30000),
            socketTimeoutMS=options.get("socketTimeoutMS", 45000),
            connectTimeoutMS=options.get("connectTimeoutMS", 30000)
        )
        
        # Test connection
        client.admin.command('ping')
        logger.info("Successfully connected to MongoDB")
        return client
    except ConnectionFailure as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise 