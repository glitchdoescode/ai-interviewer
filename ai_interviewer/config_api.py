"""
Configuration API for the AI Interviewer platform.
"""
from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Dict, Any
import logging

from ai_interviewer.utils.config import SYSTEM_NAME

logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

# Define Pydantic model for config response
class ConfigResponse(BaseModel):
    """Model for system configuration response."""
    system_name: str = Field(..., description="Name of the AI interviewer system")
    version: str = Field(..., description="API version")
    voice_enabled: bool = Field(..., description="Whether voice processing is enabled")
    features: Dict[str, bool] = Field(default_factory=dict, description="Available system features")

@router.get("/api/system-config", response_model=ConfigResponse)
async def get_system_config(request: Request):
    """Get system configuration details."""
    try:
        # Get these values from the app state
        app = request.app
        
        return {
            "system_name": SYSTEM_NAME,
            "version": getattr(app, "version", "1.0.0"),
            "voice_enabled": getattr(app.state, "voice_enabled", False),
            "features": {
                "coding_challenges": True,
                "voice_interface": getattr(app.state, "voice_enabled", False),
                "session_manager": getattr(app.state, "session_manager", None) is not None
            }
        }
    except Exception as e:
        logger.error(f"Error getting system config: {e}")
        raise HTTPException(status_code=500, detail=str(e)) 