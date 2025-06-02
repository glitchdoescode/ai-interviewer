"""
Proctoring data models for the AI Interviewer platform.

This module defines Pydantic models for proctoring session management,
event logging, and configuration.
"""

from typing import Optional, Dict, Any, List, Literal
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum


class ProctoringEventType(str, Enum):
    """Types of proctoring events that can be logged."""
    FACE_DETECTED = "face_detected"
    NO_FACE_DETECTED = "no_face_detected"
    MULTIPLE_FACES = "multiple_faces"
    GAZE_AWAY = "gaze_away"
    GAZE_RETURN = "gaze_return"
    TAB_SWITCH = "tab_switch"
    COPY_PASTE = "copy_paste"
    NEW_WINDOW = "new_window"
    FOCUS_LOST = "focus_lost"
    FOCUS_GAINED = "focus_gained"
    FACE_AUTH_SUCCESS = "face_auth_success"
    FACE_AUTH_FAILURE = "face_auth_failure"
    AUDIO_ANOMALY = "audio_anomaly"
    MULTIPLE_VOICES = "multiple_voices"
    SCREEN_CAPTURE = "screen_capture"
    CANDIDATE_ABSENT = "candidate_absent"
    CANDIDATE_PRESENT = "candidate_present"
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    SESSION_PAUSE = "session_pause"
    SESSION_RESUME = "session_resume"


class AnomalySeverity(str, Enum):
    """Severity levels for anomalies."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ProctoringSessionStatus(str, Enum):
    """Status of a proctoring session."""
    CREATED = "created"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    TERMINATED = "terminated"


class ProctoringEvent(BaseModel):
    """Model for individual proctoring events."""
    event_id: str = Field(..., description="Unique identifier for the event")
    session_id: str = Field(..., description="Proctoring session ID")
    interview_session_id: str = Field(..., description="Associated interview session ID")
    event_type: ProctoringEventType = Field(..., description="Type of proctoring event")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="When the event occurred")
    severity: AnomalySeverity = Field(default=AnomalySeverity.LOW, description="Severity of the anomaly")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score for detection")
    
    # Event-specific data
    data: Dict[str, Any] = Field(default_factory=dict, description="Event-specific data")
    
    # Evidence
    screenshot_url: Optional[str] = Field(None, description="URL to screenshot evidence")
    video_segment_url: Optional[str] = Field(None, description="URL to video segment")
    audio_segment_url: Optional[str] = Field(None, description="URL to audio segment")
    
    # Processing metadata
    processed: bool = Field(default=False, description="Whether the event has been processed")
    processing_notes: Optional[str] = Field(None, description="Notes from processing")

    class Config:
        schema_extra = {
            "example": {
                "event_id": "evt_123abc",
                "session_id": "ps_456def",
                "interview_session_id": "is_789ghi",
                "event_type": "multiple_faces",
                "timestamp": "2025-01-27T14:30:00Z",
                "severity": "high",
                "confidence": 0.95,
                "data": {
                    "face_count": 2,
                    "face_locations": [[100, 100, 200, 200], [300, 150, 400, 250]]
                },
                "screenshot_url": "/api/proctoring/evidence/screenshot_123.jpg",
                "processed": False
            }
        }


class ProctoringConfig(BaseModel):
    """Configuration settings for a proctoring session."""
    # Face monitoring settings
    face_detection_enabled: bool = Field(default=True, description="Enable face detection")
    face_detection_interval: float = Field(default=2.0, description="Face detection interval in seconds")
    multiple_face_threshold: int = Field(default=1, description="Maximum allowed faces")
    gaze_tracking_enabled: bool = Field(default=True, description="Enable gaze tracking")
    gaze_away_threshold: float = Field(default=5.0, description="Time in seconds before gaze away is flagged")
    
    # Face authentication settings
    face_auth_enabled: bool = Field(default=True, description="Enable periodic face authentication")
    face_auth_interval: float = Field(default=300.0, description="Face auth interval in seconds")
    face_auth_threshold: float = Field(default=0.7, description="Face recognition confidence threshold")
    
    # Screen monitoring settings
    screen_monitoring_enabled: bool = Field(default=True, description="Enable screen activity monitoring")
    tab_switch_detection: bool = Field(default=True, description="Detect tab switches")
    copy_paste_detection: bool = Field(default=True, description="Detect copy-paste actions")
    window_focus_monitoring: bool = Field(default=True, description="Monitor window focus changes")
    
    # Audio monitoring settings
    audio_monitoring_enabled: bool = Field(default=False, description="Enable audio monitoring")
    voice_detection_enabled: bool = Field(default=False, description="Enable voice detection")
    multiple_speaker_detection: bool = Field(default=False, description="Detect multiple speakers")
    background_noise_threshold: float = Field(default=0.3, description="Background noise threshold")
    
    # Evidence collection settings
    screenshot_on_anomaly: bool = Field(default=True, description="Capture screenshots on anomalies")
    video_recording_enabled: bool = Field(default=False, description="Enable video recording")
    audio_recording_enabled: bool = Field(default=False, description="Enable audio recording")
    evidence_retention_days: int = Field(default=30, description="Days to retain evidence")
    
    # Alert settings
    real_time_alerts: bool = Field(default=True, description="Enable real-time alerts")
    alert_webhooks: List[str] = Field(default_factory=list, description="Webhook URLs for alerts")
    alert_email_addresses: List[str] = Field(default_factory=list, description="Email addresses for alerts")
    
    # Performance settings
    max_concurrent_sessions: int = Field(default=50, description="Maximum concurrent sessions")
    processing_queue_size: int = Field(default=1000, description="Event processing queue size")
    
    class Config:
        schema_extra = {
            "example": {
                "face_detection_enabled": True,
                "face_detection_interval": 2.0,
                "multiple_face_threshold": 1,
                "gaze_tracking_enabled": True,
                "face_auth_enabled": True,
                "face_auth_interval": 300.0,
                "screen_monitoring_enabled": True,
                "audio_monitoring_enabled": False,
                "real_time_alerts": True,
                "screenshot_on_anomaly": True
            }
        }


class ProctoringSession(BaseModel):
    """Model for a proctoring session."""
    session_id: str = Field(..., description="Unique proctoring session identifier")
    interview_session_id: str = Field(..., description="Associated interview session ID")
    user_id: str = Field(..., description="User ID of the candidate")
    
    # Session metadata
    status: ProctoringSessionStatus = Field(default=ProctoringSessionStatus.CREATED, description="Session status")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Session creation time")
    started_at: Optional[datetime] = Field(None, description="Session start time")
    ended_at: Optional[datetime] = Field(None, description="Session end time")
    last_activity: datetime = Field(default_factory=datetime.utcnow, description="Last activity timestamp")
    
    # Configuration
    config: ProctoringConfig = Field(default_factory=ProctoringConfig, description="Session configuration")
    
    # Session state
    current_face_encoding: Optional[str] = Field(None, description="Base64 encoded face template for authentication")
    baseline_established: bool = Field(default=False, description="Whether baseline face has been established")
    
    # Statistics
    total_events: int = Field(default=0, description="Total number of events logged")
    anomaly_count: int = Field(default=0, description="Number of anomalies detected")
    high_severity_count: int = Field(default=0, description="Number of high severity anomalies")
    
    # Real-time state
    is_candidate_present: bool = Field(default=True, description="Whether candidate is currently present")
    last_face_detected: Optional[datetime] = Field(None, description="Last time face was detected")
    current_gaze_state: Literal["on_screen", "away", "unknown"] = Field(default="unknown", description="Current gaze state")
    
    class Config:
        schema_extra = {
            "example": {
                "session_id": "ps_123abc456",
                "interview_session_id": "is_789def012",
                "user_id": "user_345ghi789",
                "status": "active",
                "created_at": "2025-01-27T14:00:00Z",
                "started_at": "2025-01-27T14:05:00Z",
                "total_events": 15,
                "anomaly_count": 2,
                "is_candidate_present": True,
                "current_gaze_state": "on_screen"
            }
        }


class ProctoringReport(BaseModel):
    """Model for a comprehensive proctoring report."""
    report_id: str = Field(..., description="Unique report identifier")
    session_id: str = Field(..., description="Proctoring session ID")
    interview_session_id: str = Field(..., description="Interview session ID")
    user_id: str = Field(..., description="User ID")
    generated_at: datetime = Field(default_factory=datetime.utcnow, description="Report generation time")
    
    # Session summary
    session_duration: float = Field(..., description="Session duration in seconds")
    total_events: int = Field(..., description="Total events recorded")
    anomaly_summary: Dict[AnomalySeverity, int] = Field(..., description="Anomaly count by severity")
    
    # Key findings
    integrity_score: float = Field(..., ge=0.0, le=1.0, description="Overall integrity score")
    cheating_probability: float = Field(..., ge=0.0, le=1.0, description="Probability of cheating")
    confidence_level: float = Field(..., ge=0.0, le=1.0, description="Confidence in the assessment")
    
    # Detailed analysis
    face_analysis: Dict[str, Any] = Field(default_factory=dict, description="Face detection analysis")
    screen_analysis: Dict[str, Any] = Field(default_factory=dict, description="Screen activity analysis")
    audio_analysis: Dict[str, Any] = Field(default_factory=dict, description="Audio analysis")
    
    # Timeline of events
    critical_events: List[Dict[str, Any]] = Field(default_factory=list, description="Timeline of critical events")
    
    # Evidence
    evidence_files: List[str] = Field(default_factory=list, description="List of evidence file URLs")
    
    # Recommendations
    recommendations: List[str] = Field(default_factory=list, description="Recommendations for further action")
    
    class Config:
        schema_extra = {
            "example": {
                "report_id": "rpt_123abc456",
                "session_id": "ps_789def012",
                "interview_session_id": "is_345ghi678",
                "user_id": "user_901jkl234",
                "generated_at": "2025-01-27T16:00:00Z",
                "session_duration": 3600.0,
                "total_events": 45,
                "anomaly_summary": {"low": 15, "medium": 3, "high": 2, "critical": 0},
                "integrity_score": 0.85,
                "cheating_probability": 0.15,
                "confidence_level": 0.9,
                "recommendations": [
                    "Review video segments at timestamps 15:30 and 42:15",
                    "Candidate showed normal behavior overall"
                ]
            }
        }


# Request/Response models for API endpoints
class CreateProctoringSessionRequest(BaseModel):
    """Request to create a new proctoring session."""
    interview_session_id: str = Field(..., description="Interview session to monitor")
    user_id: str = Field(..., description="User ID of the candidate")
    config: Optional[ProctoringConfig] = Field(None, description="Custom configuration")

    class Config:
        schema_extra = {
            "example": {
                "interview_session_id": "is_123abc456",
                "user_id": "user_789def012",
                "config": {
                    "face_detection_enabled": True,
                    "audio_monitoring_enabled": False
                }
            }
        }


class LogProctoringEventRequest(BaseModel):
    """Request to log a proctoring event."""
    session_id: str = Field(..., description="Proctoring session ID")
    event_type: ProctoringEventType = Field(..., description="Type of event")
    severity: AnomalySeverity = Field(default=AnomalySeverity.LOW, description="Event severity")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Detection confidence")
    data: Dict[str, Any] = Field(default_factory=dict, description="Event-specific data")
    evidence_data: Optional[str] = Field(None, description="Base64 encoded evidence")

    class Config:
        schema_extra = {
            "example": {
                "session_id": "ps_123abc456",
                "event_type": "multiple_faces",
                "severity": "high",
                "confidence": 0.95,
                "data": {
                    "face_count": 2,
                    "detection_time": "2025-01-27T14:30:00Z"
                }
            }
        }


class ProctoringSessionResponse(BaseModel):
    """Response model for proctoring session operations."""
    success: bool = Field(..., description="Whether the operation was successful")
    session: ProctoringSession = Field(..., description="The proctoring session")
    message: Optional[str] = Field(None, description="Additional message")

    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "session": {
                    "session_id": "ps_123abc456",
                    "status": "active",
                    "total_events": 5
                },
                "message": "Proctoring session created successfully"
            }
        }


class ProctoringEventResponse(BaseModel):
    """Response model for event logging operations."""
    success: bool = Field(..., description="Whether the event was logged successfully")
    event_id: str = Field(..., description="The logged event ID")
    message: Optional[str] = Field(None, description="Additional message")

    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "event_id": "evt_123abc456",
                "message": "Event logged successfully"
            }
        }


class ProctoringStatusResponse(BaseModel):
    """Response model for proctoring status queries."""
    session_id: str = Field(..., description="Proctoring session ID")
    status: ProctoringSessionStatus = Field(..., description="Current session status")
    is_active: bool = Field(..., description="Whether the session is currently active")
    current_anomalies: int = Field(..., description="Number of unresolved anomalies")
    last_activity: datetime = Field(..., description="Last activity timestamp")

    class Config:
        schema_extra = {
            "example": {
                "session_id": "ps_123abc456",
                "status": "active",
                "is_active": True,
                "current_anomalies": 2,
                "last_activity": "2025-01-27T14:30:00Z"
            }
        } 