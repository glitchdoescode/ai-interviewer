"""
Service layer for the AI Interviewer platform.

This module contains business logic services that handle core functionality
of the application.
"""

from .proctoring_service import ProctoringService
from .gemini_live_adapter import GeminiLiveAudioAdapter
from .context_injection_service import ContextInjectionService, ContextUpdate
from .langgraph_integration_adapter import (
    LangGraphIntegrationAdapter, 
    ConversationTurn, 
    ToolExecutionResult
)

# Session management bridge
from .realtime_session_manager import (
    RealtimeSessionManager,
    AudioSessionMetadata,
    ContextInjectionRecord,
    ToolExecutionRecord
)

__all__ = [
    "ProctoringService",
    "GeminiLiveAudioAdapter",
    "ContextInjectionService",
    "ContextUpdate",
    "LangGraphIntegrationAdapter",
    "ConversationTurn", 
    "ToolExecutionResult",
    
    # Session management bridge
    "RealtimeSessionManager",
    "AudioSessionMetadata",
    "ContextInjectionRecord",
    "ToolExecutionRecord"
] 