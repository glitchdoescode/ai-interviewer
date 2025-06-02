"""
Proctoring service for managing AI-powered interview monitoring.

This service handles proctoring session management, event logging,
and integration with the existing interview system.
"""

import uuid
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorDatabase, AsyncIOMotorCollection

from ai_interviewer.models.proctoring import (
    ProctoringSession,
    ProctoringEvent,
    ProctoringConfig,
    ProctoringReport,
    ProctoringSessionStatus,
    ProctoringEventType,
    AnomalySeverity,
    CreateProctoringSessionRequest,
    LogProctoringEventRequest
)

logger = logging.getLogger(__name__)


class ProctoringService:
    """Service for managing proctoring sessions and events."""
    
    def __init__(self, database: AsyncIOMotorDatabase):
        """Initialize the proctoring service."""
        self.db = database
        self.sessions_collection: AsyncIOMotorCollection = database.proctoring_sessions
        self.events_collection: AsyncIOMotorCollection = database.proctoring_events
        self.reports_collection: AsyncIOMotorCollection = database.proctoring_reports
        
        # Create indexes for efficient querying
        self._setup_indexes()
    
    def _setup_indexes(self):
        """Set up database indexes for optimal performance."""
        try:
            # Session indexes
            self.sessions_collection.create_index("session_id", unique=True)
            self.sessions_collection.create_index("interview_session_id")
            self.sessions_collection.create_index("user_id")
            self.sessions_collection.create_index("status")
            self.sessions_collection.create_index("created_at")
            
            # Event indexes
            self.events_collection.create_index("event_id", unique=True)
            self.events_collection.create_index("session_id")
            self.events_collection.create_index("event_type")
            self.events_collection.create_index("timestamp")
            self.events_collection.create_index("severity")
            self.events_collection.create_index([("session_id", 1), ("timestamp", -1)])
            
            # Report indexes
            self.reports_collection.create_index("report_id", unique=True)
            self.reports_collection.create_index("session_id")
            self.reports_collection.create_index("user_id")
            
            logger.info("Proctoring database indexes created successfully")
        except Exception as e:
            logger.warning(f"Error creating proctoring indexes: {e}")
    
    async def create_session(self, request: CreateProctoringSessionRequest) -> ProctoringSession:
        """Create a new proctoring session."""
        session_id = f"ps_{uuid.uuid4().hex[:12]}"
        
        # Use provided config or default
        config = request.config if request.config else ProctoringConfig()
        
        session = ProctoringSession(
            session_id=session_id,
            interview_session_id=request.interview_session_id,
            user_id=request.user_id,
            config=config,
            status=ProctoringSessionStatus.CREATED
        )
        
        # Store in database
        await self.sessions_collection.insert_one(session.dict())
        
        # Log session creation event
        await self.log_event(LogProctoringEventRequest(
            session_id=session_id,
            event_type=ProctoringEventType.SESSION_START,
            severity=AnomalySeverity.LOW,
            data={"created_at": session.created_at.isoformat()}
        ))
        
        logger.info(f"Created proctoring session {session_id} for interview {request.interview_session_id}")
        return session
    
    async def get_session(self, session_id: str) -> Optional[ProctoringSession]:
        """Retrieve a proctoring session by ID."""
        session_data = await self.sessions_collection.find_one({"session_id": session_id})
        if session_data:
            return ProctoringSession(**session_data)
        return None
    
    async def get_session_by_interview(self, interview_session_id: str) -> Optional[ProctoringSession]:
        """Retrieve a proctoring session by interview session ID."""
        session_data = await self.sessions_collection.find_one({"interview_session_id": interview_session_id})
        if session_data:
            return ProctoringSession(**session_data)
        return None
    
    async def update_session_status(self, session_id: str, status: ProctoringSessionStatus) -> bool:
        """Update the status of a proctoring session."""
        update_data = {
            "status": status,
            "last_activity": datetime.utcnow()
        }
        
        # Add timestamps for specific status changes
        if status == ProctoringSessionStatus.ACTIVE:
            update_data["started_at"] = datetime.utcnow()
        elif status in [ProctoringSessionStatus.COMPLETED, ProctoringSessionStatus.TERMINATED]:
            update_data["ended_at"] = datetime.utcnow()
        
        result = await self.sessions_collection.update_one(
            {"session_id": session_id},
            {"$set": update_data}
        )
        
        if result.modified_count > 0:
            # Log status change event
            event_type = {
                ProctoringSessionStatus.ACTIVE: ProctoringEventType.SESSION_START,
                ProctoringSessionStatus.PAUSED: ProctoringEventType.SESSION_PAUSE,
                ProctoringSessionStatus.COMPLETED: ProctoringEventType.SESSION_END,
                ProctoringSessionStatus.TERMINATED: ProctoringEventType.SESSION_END
            }.get(status, ProctoringEventType.SESSION_START)
            
            await self.log_event(LogProctoringEventRequest(
                session_id=session_id,
                event_type=event_type,
                severity=AnomalySeverity.LOW,
                data={"new_status": status, "timestamp": update_data["last_activity"].isoformat()}
            ))
            
            logger.info(f"Updated proctoring session {session_id} status to {status}")
            return True
        
        return False
    
    async def log_event(self, request: LogProctoringEventRequest) -> str:
        """Log a proctoring event."""
        event_id = f"evt_{uuid.uuid4().hex[:12]}"
        
        # Get session to associate with interview
        session = await self.get_session(request.session_id)
        if not session:
            raise ValueError(f"Proctoring session {request.session_id} not found")
        
        event = ProctoringEvent(
            event_id=event_id,
            session_id=request.session_id,
            interview_session_id=session.interview_session_id,
            event_type=request.event_type,
            severity=request.severity,
            confidence=request.confidence,
            data=request.data
        )
        
        # Store evidence if provided
        if request.evidence_data:
            # In a real implementation, you would save the evidence to a file storage system
            # and store the URL here. For now, we'll just note that evidence was provided.
            event.screenshot_url = f"/api/proctoring/evidence/{event_id}.jpg"
        
        # Store event in database
        await self.events_collection.insert_one(event.dict())
        
        # Update session statistics
        await self._update_session_stats(request.session_id, request.severity)
        
        logger.debug(f"Logged proctoring event {event_id}: {request.event_type} ({request.severity})")
        return event_id
    
    async def _update_session_stats(self, session_id: str, severity: AnomalySeverity):
        """Update session statistics after logging an event."""
        update_data = {
            "$inc": {"total_events": 1},
            "$set": {"last_activity": datetime.utcnow()}
        }
        
        # Increment anomaly counters
        if severity in [AnomalySeverity.MEDIUM, AnomalySeverity.HIGH, AnomalySeverity.CRITICAL]:
            update_data["$inc"]["anomaly_count"] = 1
        
        if severity in [AnomalySeverity.HIGH, AnomalySeverity.CRITICAL]:
            update_data["$inc"]["high_severity_count"] = 1
        
        await self.sessions_collection.update_one(
            {"session_id": session_id},
            update_data
        )
    
    async def get_session_events(self, session_id: str, limit: int = 100) -> List[ProctoringEvent]:
        """Get events for a proctoring session."""
        cursor = self.events_collection.find({"session_id": session_id}).sort("timestamp", -1).limit(limit)
        events = []
        async for event_data in cursor:
            events.append(ProctoringEvent(**event_data))
        return events
    
    async def get_recent_events(self, session_id: str, minutes: int = 5) -> List[ProctoringEvent]:
        """Get recent events for a session within the specified time window."""
        since = datetime.utcnow() - timedelta(minutes=minutes)
        cursor = self.events_collection.find({
            "session_id": session_id,
            "timestamp": {"$gte": since}
        }).sort("timestamp", -1)
        
        events = []
        async for event_data in cursor:
            events.append(ProctoringEvent(**event_data))
        return events
    
    async def get_anomalies(self, session_id: str, min_severity: AnomalySeverity = AnomalySeverity.MEDIUM) -> List[ProctoringEvent]:
        """Get anomalies for a session above a minimum severity level."""
        severity_order = {
            AnomalySeverity.LOW: 0,
            AnomalySeverity.MEDIUM: 1,
            AnomalySeverity.HIGH: 2,
            AnomalySeverity.CRITICAL: 3
        }
        
        min_level = severity_order[min_severity]
        severity_filter = [severity for severity, level in severity_order.items() if level >= min_level]
        
        cursor = self.events_collection.find({
            "session_id": session_id,
            "severity": {"$in": severity_filter}
        }).sort("timestamp", -1)
        
        events = []
        async for event_data in cursor:
            events.append(ProctoringEvent(**event_data))
        return events
    
    async def update_face_encoding(self, session_id: str, face_encoding: str) -> bool:
        """Update the baseline face encoding for a session."""
        result = await self.sessions_collection.update_one(
            {"session_id": session_id},
            {
                "$set": {
                    "current_face_encoding": face_encoding,
                    "baseline_established": True,
                    "last_activity": datetime.utcnow()
                }
            }
        )
        
        if result.modified_count > 0:
            logger.info(f"Updated face encoding for session {session_id}")
            return True
        return False
    
    async def update_session_state(self, session_id: str, state_updates: Dict[str, Any]) -> bool:
        """Update session state fields."""
        if not state_updates:
            return False
        
        # Add last_activity timestamp
        state_updates["last_activity"] = datetime.utcnow()
        
        result = await self.sessions_collection.update_one(
            {"session_id": session_id},
            {"$set": state_updates}
        )
        
        return result.modified_count > 0
    
    async def generate_session_report(self, session_id: str) -> ProctoringReport:
        """Generate a comprehensive proctoring report for a session."""
        session = await self.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        # Get all events for the session
        events = await self.get_session_events(session_id, limit=10000)
        
        # Calculate session duration
        session_duration = 0.0
        if session.started_at and session.ended_at:
            session_duration = (session.ended_at - session.started_at).total_seconds()
        elif session.started_at:
            session_duration = (datetime.utcnow() - session.started_at).total_seconds()
        
        # Analyze events by severity
        anomaly_summary = {
            AnomalySeverity.LOW: 0,
            AnomalySeverity.MEDIUM: 0,
            AnomalySeverity.HIGH: 0,
            AnomalySeverity.CRITICAL: 0
        }
        
        critical_events = []
        for event in events:
            anomaly_summary[event.severity] += 1
            
            # Include high and critical events in the timeline
            if event.severity in [AnomalySeverity.HIGH, AnomalySeverity.CRITICAL]:
                critical_events.append({
                    "timestamp": event.timestamp.isoformat(),
                    "event_type": event.event_type,
                    "severity": event.severity,
                    "data": event.data
                })
        
        # Calculate integrity score based on anomalies
        total_anomalies = anomaly_summary[AnomalySeverity.MEDIUM] + \
                         anomaly_summary[AnomalySeverity.HIGH] + \
                         anomaly_summary[AnomalySeverity.CRITICAL]
        
        # Simple scoring algorithm (can be made more sophisticated)
        if session_duration > 0:
            anomaly_rate = total_anomalies / (session_duration / 60)  # anomalies per minute
            integrity_score = max(0.0, 1.0 - (anomaly_rate * 0.1))  # Decrease by 10% per anomaly/minute
        else:
            integrity_score = 1.0 if total_anomalies == 0 else 0.5
        
        # Calculate cheating probability (inverse of integrity score with some adjustment)
        cheating_probability = min(1.0, (1.0 - integrity_score) + (anomaly_summary[AnomalySeverity.CRITICAL] * 0.2))
        
        # Generate recommendations
        recommendations = []
        if anomaly_summary[AnomalySeverity.CRITICAL] > 0:
            recommendations.append("Critical anomalies detected - manual review strongly recommended")
        elif anomaly_summary[AnomalySeverity.HIGH] > 0:
            recommendations.append("High severity anomalies detected - consider manual review")
        elif anomaly_summary[AnomalySeverity.MEDIUM] > 2:
            recommendations.append("Multiple medium severity anomalies - review recommended")
        else:
            recommendations.append("Candidate showed normal behavior during the interview")
        
        if integrity_score >= 0.9:
            recommendations.append("High integrity score - candidate behavior appears trustworthy")
        elif integrity_score < 0.5:
            recommendations.append("Low integrity score - significant concerns about interview integrity")
        
        report_id = f"rpt_{uuid.uuid4().hex[:12]}"
        
        report = ProctoringReport(
            report_id=report_id,
            session_id=session_id,
            interview_session_id=session.interview_session_id,
            user_id=session.user_id,
            session_duration=session_duration,
            total_events=len(events),
            anomaly_summary=anomaly_summary,
            integrity_score=integrity_score,
            cheating_probability=cheating_probability,
            confidence_level=0.8,  # Could be calculated based on data quality
            critical_events=critical_events,
            recommendations=recommendations
        )
        
        # Store report in database
        await self.reports_collection.insert_one(report.dict())
        
        logger.info(f"Generated proctoring report {report_id} for session {session_id}")
        return report
    
    async def get_report(self, report_id: str) -> Optional[ProctoringReport]:
        """Retrieve a proctoring report by ID."""
        report_data = await self.reports_collection.find_one({"report_id": report_id})
        if report_data:
            return ProctoringReport(**report_data)
        return None
    
    async def get_session_report(self, session_id: str) -> Optional[ProctoringReport]:
        """Get the most recent report for a session."""
        report_data = await self.reports_collection.find_one(
            {"session_id": session_id},
            sort=[("generated_at", -1)]
        )
        if report_data:
            return ProctoringReport(**report_data)
        return None
    
    async def cleanup_old_sessions(self, days: int = 30) -> int:
        """Clean up old proctoring sessions and associated data."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Find sessions to cleanup
        old_sessions = []
        cursor = self.sessions_collection.find({
            "created_at": {"$lt": cutoff_date},
            "status": {"$in": [ProctoringSessionStatus.COMPLETED, ProctoringSessionStatus.TERMINATED]}
        })
        async for session in cursor:
            old_sessions.append(session["session_id"])
        
        if not old_sessions:
            return 0
        
        # Delete events for old sessions
        await self.events_collection.delete_many({"session_id": {"$in": old_sessions}})
        
        # Delete old sessions
        result = await self.sessions_collection.delete_many({"session_id": {"$in": old_sessions}})
        
        logger.info(f"Cleaned up {result.deleted_count} old proctoring sessions")
        return result.deleted_count
    
    async def get_active_sessions(self) -> List[ProctoringSession]:
        """Get all currently active proctoring sessions."""
        cursor = self.sessions_collection.find({"status": ProctoringSessionStatus.ACTIVE})
        sessions = []
        async for session_data in cursor:
            sessions.append(ProctoringSession(**session_data))
        return sessions
    
    async def get_user_sessions(self, user_id: str, limit: int = 10) -> List[ProctoringSession]:
        """Get proctoring sessions for a specific user."""
        cursor = self.sessions_collection.find({"user_id": user_id}).sort("created_at", -1).limit(limit)
        sessions = []
        async for session_data in cursor:
            sessions.append(ProctoringSession(**session_data))
        return sessions 