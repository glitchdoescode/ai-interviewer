"""
WebSocket module for real-time communication in the AI Interviewer platform.

This module provides WebSocket managers and utilities for real-time features
including proctoring communication and event streaming.
"""

from .proctoring_manager import proctoring_ws_manager, ProctoringWebSocketManager

__all__ = ["proctoring_ws_manager", "ProctoringWebSocketManager"] 