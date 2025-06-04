"""
Face Authentication Service

Handles backend operations for face authentication including:
- Face enrollment data storage and retrieval
- Authentication event logging and verification
- Impersonation detection and alerts
- Session face authentication state management
"""

import base64
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

from ai_interviewer.models.proctoring import (
    ProctoringSession,
    ProctoringEvent,
    FaceAuthenticationStatus,
    ProctoringEventType,
    AnomalySeverity
)
from ai_interviewer.services.proctoring_service import ProctoringService

logger = logging.getLogger(__name__)


class FaceAuthenticationService:
    """Service for managing face authentication operations."""
    
    def __init__(self, proctoring_service: ProctoringService):
        self.proctoring_service = proctoring_service
    
    async def enroll_face(
        self,
        session_id: str,
        face_embedding: List[float],
        confidence: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Enroll a face for authentication.
        
        Args:
            session_id: Proctoring session ID
            face_embedding: Face embedding vector as list of floats
            confidence: Confidence score of the enrollment
            metadata: Additional metadata about the enrollment
            
        Returns:
            Dict with enrollment result and session update
        """
        try:
            # Get current session
            session = await self.proctoring_service.get_session(session_id)
            if not session:
                return {
                    "success": False,
                    "error": "Session not found",
                    "error_code": "SESSION_NOT_FOUND"
                }
            
            # Check if already enrolled
            if session.face_auth_status == FaceAuthenticationStatus.ENROLLED:
                return {
                    "success": False,
                    "error": "Face already enrolled",
                    "error_code": "ALREADY_ENROLLED"
                }
            
            # Check enrollment attempts
            max_attempts = session.config.face_auth_max_enrollment_attempts
            if session.face_enrollment_attempts >= max_attempts:
                return {
                    "success": False,
                    "error": f"Maximum enrollment attempts ({max_attempts}) exceeded",
                    "error_code": "MAX_ATTEMPTS_EXCEEDED"
                }
            
            # Encode embedding as base64 JSON
            embedding_json = json.dumps(face_embedding)
            embedding_b64 = base64.b64encode(embedding_json.encode()).decode()
            
            # Update session with enrollment data
            now = datetime.utcnow()
            session.face_auth_status = FaceAuthenticationStatus.ENROLLED
            session.face_enrollment_embedding = embedding_b64
            session.face_enrollment_timestamp = now
            session.last_face_authentication = now
            session.face_authentication_score = confidence
            session.face_enrollment_attempts += 1
            
            # Update session in database
            await self.proctoring_service.update_session(session)
            
            # Log enrollment success event
            await self.log_authentication_event(
                session_id=session_id,
                event_type=ProctoringEventType.FACE_ENROLLMENT_SUCCESS,
                confidence=confidence,
                data={
                    "enrollment_attempt": session.face_enrollment_attempts,
                    "embedding_size": len(face_embedding),
                    "metadata": metadata or {}
                }
            )
            
            logger.info(f"Face enrolled successfully for session {session_id}")
            
            return {
                "success": True,
                "session_id": session_id,
                "enrollment_timestamp": now.isoformat(),
                "confidence": confidence,
                "attempt": session.face_enrollment_attempts
            }
            
        except Exception as e:
            logger.error(f"Error enrolling face for session {session_id}: {str(e)}")
            
            # Log enrollment failure event
            await self.log_authentication_event(
                session_id=session_id,
                event_type=ProctoringEventType.FACE_ENROLLMENT_FAILURE,
                severity=AnomalySeverity.HIGH,
                data={
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
            
            return {
                "success": False,
                "error": f"Enrollment failed: {str(e)}",
                "error_code": "ENROLLMENT_ERROR"
            }
    
    async def authenticate_face(
        self,
        session_id: str,
        face_embedding: List[float],
        confidence: float = 1.0,
        similarity_score: float = 0.0
    ) -> Dict[str, Any]:
        """
        Authenticate a face against enrolled embedding.
        
        Args:
            session_id: Proctoring session ID
            face_embedding: Current face embedding vector
            confidence: Face detection confidence
            similarity_score: Calculated similarity score with enrolled embedding
            
        Returns:
            Dict with authentication result
        """
        try:
            # Get current session
            session = await self.proctoring_service.get_session(session_id)
            if not session:
                return {
                    "success": False,
                    "error": "Session not found",
                    "error_code": "SESSION_NOT_FOUND"
                }
            
            # Check if face is enrolled
            if session.face_auth_status != FaceAuthenticationStatus.ENROLLED:
                return {
                    "success": False,
                    "error": "Face not enrolled",
                    "error_code": "NOT_ENROLLED"
                }
            
            if not session.face_enrollment_embedding:
                return {
                    "success": False,
                    "error": "No enrollment data found",
                    "error_code": "NO_ENROLLMENT_DATA"
                }
            
            # Get authentication thresholds
            auth_threshold = session.config.face_auth_threshold
            impersonation_threshold = session.config.face_auth_impersonation_threshold
            
            # Update session with latest authentication data
            now = datetime.utcnow()
            session.face_authentication_score = similarity_score
            
            # Determine authentication result
            if similarity_score >= auth_threshold:
                # Authentication successful
                session.last_face_authentication = now
                session.face_auth_status = FaceAuthenticationStatus.AUTHENTICATED
                
                await self.proctoring_service.update_session(session)
                
                # Log success event
                await self.log_authentication_event(
                    session_id=session_id,
                    event_type=ProctoringEventType.FACE_AUTH_SUCCESS,
                    confidence=confidence,
                    data={
                        "similarity_score": similarity_score,
                        "threshold": auth_threshold,
                        "detection_confidence": confidence
                    }
                )
                
                return {
                    "success": True,
                    "authenticated": True,
                    "similarity_score": similarity_score,
                    "threshold": auth_threshold,
                    "timestamp": now.isoformat()
                }
                
            elif similarity_score < impersonation_threshold:
                # Possible impersonation detected
                session.face_auth_status = FaceAuthenticationStatus.FAILED
                
                await self.proctoring_service.update_session(session)
                
                # Log impersonation event
                await self.log_authentication_event(
                    session_id=session_id,
                    event_type=ProctoringEventType.IMPERSONATION_DETECTED,
                    severity=AnomalySeverity.CRITICAL,
                    confidence=confidence,
                    data={
                        "similarity_score": similarity_score,
                        "impersonation_threshold": impersonation_threshold,
                        "detection_confidence": confidence
                    }
                )
                
                return {
                    "success": False,
                    "authenticated": False,
                    "impersonation_detected": True,
                    "similarity_score": similarity_score,
                    "threshold": impersonation_threshold,
                    "error": "Possible impersonation detected",
                    "error_code": "IMPERSONATION_DETECTED"
                }
                
            else:
                # Authentication failed (low similarity)
                session.face_auth_status = FaceAuthenticationStatus.FAILED
                
                await self.proctoring_service.update_session(session)
                
                # Log failure event
                await self.log_authentication_event(
                    session_id=session_id,
                    event_type=ProctoringEventType.FACE_AUTH_FAILURE,
                    severity=AnomalySeverity.MEDIUM,
                    confidence=confidence,
                    data={
                        "similarity_score": similarity_score,
                        "threshold": auth_threshold,
                        "detection_confidence": confidence,
                        "reason": "Low similarity score"
                    }
                )
                
                return {
                    "success": False,
                    "authenticated": False,
                    "similarity_score": similarity_score,
                    "threshold": auth_threshold,
                    "error": "Authentication failed - low similarity",
                    "error_code": "LOW_SIMILARITY"
                }
                
        except Exception as e:
            logger.error(f"Error authenticating face for session {session_id}: {str(e)}")
            
            # Log authentication error
            await self.log_authentication_event(
                session_id=session_id,
                event_type=ProctoringEventType.FACE_AUTH_FAILURE,
                severity=AnomalySeverity.HIGH,
                data={
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
            
            return {
                "success": False,
                "error": f"Authentication error: {str(e)}",
                "error_code": "AUTHENTICATION_ERROR"
            }
    
    async def reset_face_authentication(self, session_id: str) -> Dict[str, Any]:
        """
        Reset face authentication for a session.
        
        Args:
            session_id: Proctoring session ID
            
        Returns:
            Dict with reset result
        """
        try:
            # Get current session
            session = await self.proctoring_service.get_session(session_id)
            if not session:
                return {
                    "success": False,
                    "error": "Session not found",
                    "error_code": "SESSION_NOT_FOUND"
                }
            
            # Reset face authentication data
            session.face_auth_status = FaceAuthenticationStatus.NOT_ENROLLED
            session.face_enrollment_embedding = None
            session.face_enrollment_timestamp = None
            session.last_face_authentication = None
            session.face_authentication_score = 0.0
            session.face_enrollment_attempts = 0
            
            # Update session
            await self.proctoring_service.update_session(session)
            
            # Log reset event
            await self.log_authentication_event(
                session_id=session_id,
                event_type=ProctoringEventType.FACE_AUTH_RESET,
                data={"reset_timestamp": datetime.utcnow().isoformat()}
            )
            
            logger.info(f"Face authentication reset for session {session_id}")
            
            return {
                "success": True,
                "session_id": session_id,
                "reset_timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error resetting face authentication for session {session_id}: {str(e)}")
            return {
                "success": False,
                "error": f"Reset failed: {str(e)}",
                "error_code": "RESET_ERROR"
            }
    
    async def get_face_authentication_status(self, session_id: str) -> Dict[str, Any]:
        """
        Get current face authentication status for a session.
        
        Args:
            session_id: Proctoring session ID
            
        Returns:
            Dict with current authentication status
        """
        try:
            session = await self.proctoring_service.get_session(session_id)
            if not session:
                return {
                    "success": False,
                    "error": "Session not found",
                    "error_code": "SESSION_NOT_FOUND"
                }
            
            # Calculate time since last authentication
            time_since_auth = None
            next_auth_due = None
            
            if session.last_face_authentication:
                time_since_auth = (datetime.utcnow() - session.last_face_authentication).total_seconds()
                auth_interval = session.config.face_auth_interval
                next_auth_due = max(0, auth_interval - time_since_auth)
            
            return {
                "success": True,
                "session_id": session_id,
                "face_auth_status": session.face_auth_status.value,
                "enrollment_timestamp": session.face_enrollment_timestamp.isoformat() if session.face_enrollment_timestamp else None,
                "last_authentication": session.last_face_authentication.isoformat() if session.last_face_authentication else None,
                "authentication_score": session.face_authentication_score,
                "enrollment_attempts": session.face_enrollment_attempts,
                "max_enrollment_attempts": session.config.face_auth_max_enrollment_attempts,
                "time_since_last_auth_seconds": time_since_auth,
                "next_auth_due_seconds": next_auth_due,
                "authentication_interval": session.config.face_auth_interval,
                "authentication_threshold": session.config.face_auth_threshold,
                "impersonation_threshold": session.config.face_auth_impersonation_threshold
            }
            
        except Exception as e:
            logger.error(f"Error getting face authentication status for session {session_id}: {str(e)}")
            return {
                "success": False,
                "error": f"Status retrieval failed: {str(e)}",
                "error_code": "STATUS_ERROR"
            }
    
    async def log_authentication_event(
        self,
        session_id: str,
        event_type: ProctoringEventType,
        severity: AnomalySeverity = AnomalySeverity.LOW,
        confidence: float = 1.0,
        data: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Log a face authentication event.
        
        Args:
            session_id: Proctoring session ID
            event_type: Type of authentication event
            severity: Severity level of the event
            confidence: Confidence score
            data: Additional event data
            
        Returns:
            Event ID if successful, None if failed
        """
        try:
            return await self.proctoring_service.log_event(
                session_id=session_id,
                event_type=event_type,
                severity=severity,
                confidence=confidence,
                data=data or {}
            )
        except Exception as e:
            logger.error(f"Error logging authentication event: {str(e)}")
            return None
    
    async def get_authentication_events(
        self,
        session_id: str,
        limit: int = 50,
        event_types: Optional[List[ProctoringEventType]] = None
    ) -> List[ProctoringEvent]:
        """
        Get face authentication events for a session.
        
        Args:
            session_id: Proctoring session ID
            limit: Maximum number of events to return
            event_types: Filter by specific event types
            
        Returns:
            List of authentication events
        """
        try:
            # Default to face authentication related events
            if event_types is None:
                event_types = [
                    ProctoringEventType.FACE_ENROLLMENT_SUCCESS,
                    ProctoringEventType.FACE_ENROLLMENT_FAILURE,
                    ProctoringEventType.FACE_AUTH_SUCCESS,
                    ProctoringEventType.FACE_AUTH_FAILURE,
                    ProctoringEventType.IMPERSONATION_DETECTED,
                    ProctoringEventType.FACE_AUTH_RESET
                ]
            
            events = await self.proctoring_service.get_events(
                session_id=session_id,
                limit=limit
            )
            
            # Filter by event types
            filtered_events = [
                event for event in events
                if event.event_type in event_types
            ]
            
            return filtered_events
            
        except Exception as e:
            logger.error(f"Error getting authentication events for session {session_id}: {str(e)}")
            return []
    
    async def is_authentication_due(self, session_id: str) -> Dict[str, Any]:
        """
        Check if face authentication is due for a session.
        
        Args:
            session_id: Proctoring session ID
            
        Returns:
            Dict with authentication due status
        """
        try:
            session = await self.proctoring_service.get_session(session_id)
            if not session:
                return {
                    "success": False,
                    "error": "Session not found"
                }
            
            if session.face_auth_status != FaceAuthenticationStatus.ENROLLED:
                return {
                    "success": True,
                    "is_due": False,
                    "reason": "Face not enrolled"
                }
            
            if not session.last_face_authentication:
                return {
                    "success": True,
                    "is_due": True,
                    "reason": "No previous authentication"
                }
            
            # Check if authentication interval has passed
            time_since_auth = datetime.utcnow() - session.last_face_authentication
            auth_interval = timedelta(seconds=session.config.face_auth_interval)
            
            is_due = time_since_auth >= auth_interval
            
            return {
                "success": True,
                "is_due": is_due,
                "time_since_last_auth": time_since_auth.total_seconds(),
                "auth_interval": session.config.face_auth_interval,
                "next_auth_in": max(0, (auth_interval - time_since_auth).total_seconds()) if not is_due else 0
            }
            
        except Exception as e:
            logger.error(f"Error checking authentication due status for session {session_id}: {str(e)}")
            return {
                "success": False,
                "error": f"Due check failed: {str(e)}"
            } 