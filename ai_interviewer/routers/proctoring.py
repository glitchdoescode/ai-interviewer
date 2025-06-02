"""
FastAPI router for proctoring endpoints.

This module provides REST API endpoints for the AI-powered proctoring system,
including session management, event logging, and real-time communication.
"""

import logging
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Depends, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from ai_interviewer.models.proctoring import (
    CreateProctoringSessionRequest,
    LogProctoringEventRequest,
    ProctoringSessionResponse,
    ProctoringEventResponse,
    ProctoringStatusResponse,
    ProctoringSession,
    ProctoringEvent,
    ProctoringReport,
    ProctoringSessionStatus,
    ProctoringConfig
)
from ai_interviewer.services.proctoring_service import ProctoringService
from ai_interviewer.websocket.proctoring_manager import proctoring_ws_manager
from ai_interviewer.auth.security import get_current_active_user
from ai_interviewer.models.user_models import User

logger = logging.getLogger(__name__)

# Dependency for request timing (imported from server)
# Import log_request_time dependency
async def log_request_time(request: Request):
    """Log request timing for HTTP endpoints (not WebSocket)."""
    request.state.start_time = datetime.now()
    yield
    process_time = (datetime.now() - request.state.start_time).total_seconds() * 1000
    logger.info(f"Request to {request.url.path} took {process_time:.2f}ms")

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Create router
router = APIRouter(prefix="/api/proctoring", tags=["proctoring"])


def get_proctoring_service(request: Request) -> ProctoringService:
    """Dependency to get the proctoring service from app state."""
    if not hasattr(request.app.state, 'memory_manager') or not request.app.state.memory_manager:
        raise HTTPException(status_code=500, detail="Database not initialized")
    
    memory_manager = request.app.state.memory_manager
    if not hasattr(memory_manager, 'db') or not memory_manager.db:
        raise HTTPException(status_code=500, detail="Database connection not available")
    
    return ProctoringService(memory_manager.db)


@router.post("/sessions", response_model=ProctoringSessionResponse)
@limiter.limit("10/minute")
async def create_proctoring_session(
    request: Request,
    session_request: CreateProctoringSessionRequest,
    current_user: User = Depends(get_current_active_user),
    proctoring_service: ProctoringService = Depends(get_proctoring_service),
    _: None = Depends(log_request_time)
):
    """Create a new proctoring session."""
    try:
        session = await proctoring_service.create_session(session_request)
        logger.info(f"Created proctoring session {session.session_id} for user {current_user.email}")
        
        return ProctoringSessionResponse(
            success=True,
            session=session,
            message="Proctoring session created successfully"
        )
    except Exception as e:
        logger.error(f"Error creating proctoring session: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create proctoring session: {str(e)}")


@router.get("/sessions/{session_id}", response_model=ProctoringSession)
@limiter.limit("30/minute")
async def get_proctoring_session(
    request: Request,
    session_id: str,
    current_user: User = Depends(get_current_active_user),
    proctoring_service: ProctoringService = Depends(get_proctoring_service)
):
    """Get a proctoring session by ID."""
    session = await proctoring_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Proctoring session not found")
    
    return session


@router.put("/sessions/{session_id}/status")
@limiter.limit("20/minute")
async def update_session_status(
    request: Request,
    session_id: str,
    status: ProctoringSessionStatus,
    current_user: User = Depends(get_current_active_user),
    proctoring_service: ProctoringService = Depends(get_proctoring_service)
):
    """Update the status of a proctoring session."""
    success = await proctoring_service.update_session_status(session_id, status)
    if not success:
        raise HTTPException(status_code=404, detail="Proctoring session not found")
    
    # Notify WebSocket connections
    await proctoring_ws_manager.broadcast_to_session(session_id, {
        "type": "session_status_updated",
        "session_id": session_id,
        "new_status": status,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    return {"success": True, "session_id": session_id, "new_status": status}


@router.get("/sessions/{session_id}/status", response_model=ProctoringStatusResponse)
@limiter.limit("60/minute")
async def get_session_status(
    request: Request,
    session_id: str,
    current_user: User = Depends(get_current_active_user),
    proctoring_service: ProctoringService = Depends(get_proctoring_service)
):
    """Get the current status of a proctoring session."""
    session = await proctoring_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Proctoring session not found")
    
    # Count unresolved anomalies (events with high severity that haven't been processed)
    recent_events = await proctoring_service.get_recent_events(session_id, minutes=30)
    current_anomalies = sum(1 for event in recent_events 
                          if event.severity in ["high", "critical"] and not event.processed)
    
    return ProctoringStatusResponse(
        session_id=session_id,
        status=session.status,
        is_active=session.status == ProctoringSessionStatus.ACTIVE,
        current_anomalies=current_anomalies,
        last_activity=session.last_activity
    )


@router.post("/events", response_model=ProctoringEventResponse)
@limiter.limit("100/minute")
async def log_proctoring_event(
    request: Request,
    event_request: LogProctoringEventRequest,
    current_user: User = Depends(get_current_active_user),
    proctoring_service: ProctoringService = Depends(get_proctoring_service)
):
    """Log a proctoring event."""
    try:
        event_id = await proctoring_service.log_event(event_request)
        
        # Notify WebSocket connections if it's a significant event
        if event_request.severity in ["high", "critical"]:
            await proctoring_ws_manager.send_alert(
                event_request.session_id,
                "anomaly_detected",
                event_request.severity,
                {
                    "event_type": event_request.event_type,
                    "event_id": event_id,
                    "confidence": event_request.confidence
                }
            )
        
        return ProctoringEventResponse(
            success=True,
            event_id=event_id,
            message="Event logged successfully"
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error logging proctoring event: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to log event: {str(e)}")


@router.get("/sessions/{session_id}/events", response_model=List[ProctoringEvent])
@limiter.limit("30/minute")
async def get_session_events(
    request: Request,
    session_id: str,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    proctoring_service: ProctoringService = Depends(get_proctoring_service)
):
    """Get events for a proctoring session."""
    events = await proctoring_service.get_session_events(session_id, limit)
    return events


@router.get("/sessions/{session_id}/anomalies", response_model=List[ProctoringEvent])
@limiter.limit("30/minute")
async def get_session_anomalies(
    request: Request,
    session_id: str,
    min_severity: str = "medium",
    current_user: User = Depends(get_current_active_user),
    proctoring_service: ProctoringService = Depends(get_proctoring_service)
):
    """Get anomalies for a proctoring session."""
    try:
        from ai_interviewer.models.proctoring import AnomalySeverity
        severity = AnomalySeverity(min_severity)
        anomalies = await proctoring_service.get_anomalies(session_id, severity)
        return anomalies
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid severity level")


@router.put("/sessions/{session_id}/face-encoding")
@limiter.limit("10/minute")
async def update_face_encoding(
    request: Request,
    session_id: str,
    face_encoding: str,
    current_user: User = Depends(get_current_active_user),
    proctoring_service: ProctoringService = Depends(get_proctoring_service)
):
    """Update the baseline face encoding for a session."""
    success = await proctoring_service.update_face_encoding(session_id, face_encoding)
    if not success:
        raise HTTPException(status_code=404, detail="Proctoring session not found")
    
    return {"success": True, "message": "Face encoding updated successfully"}


@router.post("/sessions/{session_id}/report", response_model=ProctoringReport)
@limiter.limit("5/minute")
async def generate_session_report(
    request: Request,
    session_id: str,
    current_user: User = Depends(get_current_active_user),
    proctoring_service: ProctoringService = Depends(get_proctoring_service)
):
    """Generate a comprehensive proctoring report for a session."""
    try:
        report = await proctoring_service.generate_session_report(session_id)
        return report
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating report: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")


@router.get("/sessions/{session_id}/report", response_model=Optional[ProctoringReport])
@limiter.limit("30/minute")
async def get_session_report(
    request: Request,
    session_id: str,
    current_user: User = Depends(get_current_active_user),
    proctoring_service: ProctoringService = Depends(get_proctoring_service)
):
    """Get the most recent report for a session."""
    report = await proctoring_service.get_session_report(session_id)
    return report


@router.get("/reports/{report_id}", response_model=ProctoringReport)
@limiter.limit("30/minute")
async def get_report(
    request: Request,
    report_id: str,
    current_user: User = Depends(get_current_active_user),
    proctoring_service: ProctoringService = Depends(get_proctoring_service)
):
    """Get a proctoring report by ID."""
    report = await proctoring_service.get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    return report


@router.get("/sessions", response_model=List[ProctoringSession])
@limiter.limit("20/minute")
async def get_user_sessions(
    request: Request,
    user_id: Optional[str] = None,
    active_only: bool = False,
    limit: int = 10,
    current_user: User = Depends(get_current_active_user),
    proctoring_service: ProctoringService = Depends(get_proctoring_service)
):
    """Get proctoring sessions for a user or all active sessions."""
    if user_id:
        sessions = await proctoring_service.get_user_sessions(user_id, limit)
    elif active_only:
        sessions = await proctoring_service.get_active_sessions()
    else:
        # Return user's own sessions if no user_id specified
        sessions = await proctoring_service.get_user_sessions(current_user.id, limit)
    
    return sessions


@router.get("/config/default", response_model=ProctoringConfig)
async def get_default_config(request: Request, _: None = Depends(log_request_time)):
    """Get default proctoring configuration."""
    return ProctoringConfig()


@router.get("/stats")
@limiter.limit("30/minute")
async def get_proctoring_stats(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    proctoring_service: ProctoringService = Depends(get_proctoring_service)
):
    """Get proctoring system statistics."""
    active_sessions = await proctoring_service.get_active_sessions()
    ws_stats = proctoring_ws_manager.get_stats()
    
    return {
        "active_sessions": len(active_sessions),
        "websocket_connections": ws_stats["total_connections"],
        "websocket_sessions": ws_stats["active_sessions"],
        "websocket_users": ws_stats["active_users"]
    }


# WebSocket endpoint for real-time proctoring communication
@router.websocket("/ws/{session_id}")
async def proctoring_websocket(websocket: WebSocket, session_id: str, user_id: str):
    """WebSocket endpoint for real-time proctoring communication."""
    connection_id = None
    try:
        # Connect to WebSocket manager
        connection_id = await proctoring_ws_manager.connect(websocket, session_id, user_id)
        
        # Handle messages
        while True:
            try:
                message = await websocket.receive_text()
                await proctoring_ws_manager.handle_message(connection_id, message)
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected: {connection_id}")
                break
            except Exception as e:
                logger.error(f"Error handling WebSocket message: {e}")
                await proctoring_ws_manager._send_error(connection_id, "Error processing message")
                
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
    finally:
        if connection_id:
            await proctoring_ws_manager.disconnect(connection_id)


# WebSocket management endpoints
@router.get("/websocket/connections/{session_id}")
@limiter.limit("30/minute")
async def get_session_connections(
    request: Request,
    session_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """Get WebSocket connections for a session."""
    connections = proctoring_ws_manager.get_session_connections(session_id)
    connection_info = []
    
    for conn_id in connections:
        info = proctoring_ws_manager.get_connection_info(conn_id)
        if info:
            connection_info.append(info)
    
    return {
        "session_id": session_id,
        "connection_count": len(connections),
        "connections": connection_info
    }


@router.post("/websocket/broadcast/{session_id}")
@limiter.limit("10/minute")
async def broadcast_to_session(
    request: Request,
    session_id: str,
    message: dict,
    current_user: User = Depends(get_current_active_user)
):
    """Broadcast a message to all connections in a session."""
    await proctoring_ws_manager.broadcast_to_session(session_id, message)
    return {"success": True, "session_id": session_id, "message": "Message broadcasted"}


@router.post("/alerts/{session_id}")
@limiter.limit("20/minute")
async def send_alert(
    request: Request,
    session_id: str,
    alert_type: str,
    severity: str,
    data: dict,
    current_user: User = Depends(get_current_active_user)
):
    """Send an alert to all connections monitoring a session."""
    await proctoring_ws_manager.send_alert(session_id, alert_type, severity, data)
    return {"success": True, "alert_sent": True}


# Cleanup and maintenance endpoints
@router.post("/maintenance/cleanup")
@limiter.limit("1/hour")
async def cleanup_old_sessions(
    request: Request,
    days: int = 30,
    current_user: User = Depends(get_current_active_user),
    proctoring_service: ProctoringService = Depends(get_proctoring_service)
):
    """Clean up old proctoring sessions and data."""
    # Only allow admin users to perform cleanup
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    cleaned_count = await proctoring_service.cleanup_old_sessions(days)
    return {
        "success": True,
        "cleaned_sessions": cleaned_count,
        "retention_days": days
    } 