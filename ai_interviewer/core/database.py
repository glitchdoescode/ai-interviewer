from fastapi import Request, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
import logging

logger = logging.getLogger(__name__)

async def get_motor_db(request: Request) -> AsyncIOMotorDatabase:
    """Dependency to get the database instance from the application state."""
    mm = getattr(request.app.state, 'memory_manager', None)
    # logger.info(f"get_motor_db called. App state memory_manager: {mm}") # Optional: for verbose logging

    if not mm or not hasattr(mm, 'db') or mm.db is None:
        logger.error("Database client (request.app.state.memory_manager.db) not available or not initialized.")
        raise HTTPException(status_code=503, detail="Database service not available or not initialized.")
    
    # logger.info(f"get_motor_db: Returning app.state.memory_manager.db: {mm.db}") # Optional: for verbose logging
    return mm.db 