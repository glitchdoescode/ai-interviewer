"""
Realtime Session Management Bridge for AI Interviewer.

This module provides a bridge between the real-time audio components
(GeminiLiveAudioAdapter, ContextInjectionService, LangGraphIntegrationAdapter)
and the existing MongoDB session storage system.
"""
import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, asdict
from collections import deque
import json
import time

from ai_interviewer.utils.session_manager import SessionManager
from ai_interviewer.utils.memory_manager import InterviewMemoryManager

# Set up logging
logger = logging.getLogger(__name__)

@dataclass
class AudioSessionMetadata:
    """Metadata for audio session tracking."""
    session_id: str
    connection_status: str  # 'connecting', 'connected', 'disconnected', 'error'
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    total_audio_duration: float = 0.0  # Total audio processed in seconds
    message_count: int = 0
    context_injections: int = 0
    tool_executions: int = 0
    performance_metrics: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.performance_metrics is None:
            self.performance_metrics = {
                'avg_response_time': 0.0,
                'peak_response_time': 0.0,
                'total_processing_time': 0.0,
                'error_count': 0
            }

@dataclass
class ContextInjectionRecord:
    """Record of context injection for persistence."""
    timestamp: datetime
    injection_type: str  # 'initial', 'stage_transition', 'tool_result', 'session_update'
    content_hash: str  # Hash of content for deduplication
    priority: int
    success: bool
    error_message: Optional[str] = None

@dataclass
class ToolExecutionRecord:
    """Record of tool execution for persistence."""
    timestamp: datetime
    tool_name: str
    execution_id: str
    input_data: Dict[str, Any]
    output_data: Optional[Dict[str, Any]]
    execution_time: float
    success: bool
    error_message: Optional[str] = None

class RealtimeSessionManager:
    """
    Manages real-time session state and bridges with persistent storage.
    
    This class handles:
    - Real-time session state tracking
    - Audio session metadata persistence
    - Context injection history
    - Tool execution results
    - Performance monitoring
    - State synchronization between real-time and persistent storage
    """
    
    def __init__(
        self,
        session_manager: SessionManager,
        memory_manager: Optional[InterviewMemoryManager] = None,
        batch_size: int = 10,
        batch_timeout: float = 30.0,
        max_cache_size: int = 1000
    ):
        """
        Initialize the RealtimeSessionManager.
        
        Args:
            session_manager: Existing SessionManager instance
            memory_manager: Optional InterviewMemoryManager instance
            batch_size: Number of operations to batch before writing to DB
            batch_timeout: Maximum time to wait before writing batch to DB
            max_cache_size: Maximum number of sessions to keep in cache
        """
        self.session_manager = session_manager
        self.memory_manager = memory_manager
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.max_cache_size = max_cache_size
        
        # Real-time session cache
        self._session_cache: Dict[str, AudioSessionMetadata] = {}
        self._context_injection_buffer: Dict[str, deque] = {}
        self._tool_execution_buffer: Dict[str, deque] = {}
        
        # Batching for performance
        self._pending_updates: deque = deque()
        self._last_batch_write = datetime.now()
        
        # Event callbacks
        self._event_callbacks: Dict[str, List[Callable]] = {
            'session_started': [],
            'session_ended': [],
            'context_injected': [],
            'tool_executed': [],
            'state_updated': []
        }
        
        # Background tasks
        self._background_tasks: List[asyncio.Task] = []
        self._running = False
        
        logger.info("RealtimeSessionManager initialized")
    
    async def start(self):
        """Start background tasks for batch processing."""
        if self._running:
            return
            
        self._running = True
        
        # Start batch processor
        batch_task = asyncio.create_task(self._batch_processor())
        self._background_tasks.append(batch_task)
        
        # Start cache cleanup
        cleanup_task = asyncio.create_task(self._cache_cleanup())
        self._background_tasks.append(cleanup_task)
        
        logger.info("RealtimeSessionManager background tasks started")
    
    async def stop(self):
        """Stop background tasks and flush pending operations."""
        self._running = False
        
        # Cancel background tasks
        for task in self._background_tasks:
            task.cancel()
        
        # Wait for tasks to complete
        await asyncio.gather(*self._background_tasks, return_exceptions=True)
        self._background_tasks.clear()
        
        # Flush any pending updates
        await self._flush_pending_updates()
        
        logger.info("RealtimeSessionManager stopped")
    
    def register_event_callback(self, event_type: str, callback: Callable):
        """
        Register a callback for specific events.
        
        Args:
            event_type: Type of event ('session_started', 'session_ended', etc.)
            callback: Callback function to execute
        """
        if event_type in self._event_callbacks:
            self._event_callbacks[event_type].append(callback)
        else:
            logger.warning(f"Unknown event type: {event_type}")
    
    async def start_audio_session(
        self,
        session_id: str,
        user_id: str,
        initial_metadata: Optional[Dict[str, Any]] = None
    ) -> AudioSessionMetadata:
        """
        Start a new real-time audio session.
        
        Args:
            session_id: Session identifier
            user_id: User identifier
            initial_metadata: Optional initial metadata
            
        Returns:
            AudioSessionMetadata instance
        """
        audio_metadata = AudioSessionMetadata(
            session_id=session_id,
            connection_status='connecting',
            start_time=datetime.now()
        )
        
        # Cache the session
        self._session_cache[session_id] = audio_metadata
        
        # Initialize buffers
        self._context_injection_buffer[session_id] = deque(maxlen=100)
        self._tool_execution_buffer[session_id] = deque(maxlen=100)
        
        # Ensure session exists in persistent storage
        existing_session = self.session_manager.get_session(session_id)
        if not existing_session:
            # Create session with audio metadata
            metadata = initial_metadata or {}
            metadata['audio_session'] = asdict(audio_metadata)
            self.session_manager.create_session(user_id, metadata)
        else:
            # Update existing session with audio metadata
            metadata = existing_session.get('metadata', {})
            metadata['audio_session'] = asdict(audio_metadata)
            self.session_manager.update_session_metadata(session_id, metadata)
        
        # Queue update for batching
        await self._queue_update({
            'type': 'audio_session_start',
            'session_id': session_id,
            'metadata': asdict(audio_metadata),
            'timestamp': datetime.now()
        })
        
        # Trigger callbacks
        await self._trigger_event('session_started', session_id, audio_metadata)
        
        logger.info(f"Started audio session {session_id}")
        return audio_metadata
    
    async def update_connection_status(self, session_id: str, status: str):
        """
        Update the connection status for an audio session.
        
        Args:
            session_id: Session identifier
            status: New connection status
        """
        if session_id not in self._session_cache:
            logger.warning(f"Audio session {session_id} not found in cache")
            return
        
        metadata = self._session_cache[session_id]
        old_status = metadata.connection_status
        metadata.connection_status = status
        
        if status == 'connected' and old_status == 'connecting':
            # Mark actual connection time
            metadata.start_time = datetime.now()
        elif status in ['disconnected', 'error']:
            # Mark end time
            metadata.end_time = datetime.now()
        
        # Queue update
        await self._queue_update({
            'type': 'connection_status_update',
            'session_id': session_id,
            'old_status': old_status,
            'new_status': status,
            'timestamp': datetime.now()
        })
        
        logger.info(f"Updated connection status for {session_id}: {old_status} -> {status}")
    
    async def record_context_injection(
        self,
        session_id: str,
        injection_type: str,
        content_hash: str,
        priority: int,
        success: bool,
        error_message: Optional[str] = None
    ):
        """
        Record a context injection event.
        
        Args:
            session_id: Session identifier
            injection_type: Type of injection
            content_hash: Hash of injected content
            priority: Injection priority
            success: Whether injection was successful
            error_message: Optional error message
        """
        record = ContextInjectionRecord(
            timestamp=datetime.now(),
            injection_type=injection_type,
            content_hash=content_hash,
            priority=priority,
            success=success,
            error_message=error_message
        )
        
        # Add to buffer
        if session_id in self._context_injection_buffer:
            self._context_injection_buffer[session_id].append(record)
        
        # Update session metadata
        if session_id in self._session_cache:
            self._session_cache[session_id].context_injections += 1
        
        # Queue update
        await self._queue_update({
            'type': 'context_injection',
            'session_id': session_id,
            'record': asdict(record),
            'timestamp': datetime.now()
        })
        
        # Trigger callbacks
        await self._trigger_event('context_injected', session_id, record)
        
        logger.debug(f"Recorded context injection for {session_id}: {injection_type}")
    
    async def record_tool_execution(
        self,
        session_id: str,
        tool_name: str,
        execution_id: str,
        input_data: Dict[str, Any],
        output_data: Optional[Dict[str, Any]],
        execution_time: float,
        success: bool,
        error_message: Optional[str] = None
    ):
        """
        Record a tool execution event.
        
        Args:
            session_id: Session identifier
            tool_name: Name of executed tool
            execution_id: Unique execution identifier
            input_data: Tool input data
            output_data: Tool output data
            execution_time: Execution time in seconds
            success: Whether execution was successful
            error_message: Optional error message
        """
        record = ToolExecutionRecord(
            timestamp=datetime.now(),
            tool_name=tool_name,
            execution_id=execution_id,
            input_data=input_data,
            output_data=output_data,
            execution_time=execution_time,
            success=success,
            error_message=error_message
        )
        
        # Add to buffer
        if session_id in self._tool_execution_buffer:
            self._tool_execution_buffer[session_id].append(record)
        
        # Update session metadata
        if session_id in self._session_cache:
            metadata = self._session_cache[session_id]
            metadata.tool_executions += 1
            
            # Update performance metrics
            metrics = metadata.performance_metrics
            metrics['total_processing_time'] += execution_time
            
            if execution_time > metrics['peak_response_time']:
                metrics['peak_response_time'] = execution_time
            
            # Update average response time
            if metadata.tool_executions > 0:
                metrics['avg_response_time'] = (
                    metrics['total_processing_time'] / metadata.tool_executions
                )
            
            if not success:
                metrics['error_count'] += 1
        
        # Queue update
        await self._queue_update({
            'type': 'tool_execution',
            'session_id': session_id,
            'record': asdict(record),
            'timestamp': datetime.now()
        })
        
        # Trigger callbacks
        await self._trigger_event('tool_executed', session_id, record)
        
        logger.debug(f"Recorded tool execution for {session_id}: {tool_name} ({execution_time:.2f}s)")
    
    async def update_audio_processing_stats(
        self,
        session_id: str,
        audio_duration: float,
        processing_time: float
    ):
        """
        Update audio processing statistics.
        
        Args:
            session_id: Session identifier
            audio_duration: Duration of processed audio in seconds
            processing_time: Time taken to process audio in seconds
        """
        if session_id not in self._session_cache:
            return
        
        metadata = self._session_cache[session_id]
        metadata.total_audio_duration += audio_duration
        metadata.message_count += 1
        
        # Update performance metrics
        metrics = metadata.performance_metrics
        if processing_time > metrics['peak_response_time']:
            metrics['peak_response_time'] = processing_time
        
        # Queue lightweight update
        await self._queue_update({
            'type': 'audio_stats_update',
            'session_id': session_id,
            'audio_duration': audio_duration,
            'processing_time': processing_time,
            'timestamp': datetime.now()
        })
    
    async def end_audio_session(self, session_id: str) -> Optional[AudioSessionMetadata]:
        """
        End an audio session and persist final state.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Final AudioSessionMetadata or None if session not found
        """
        if session_id not in self._session_cache:
            logger.warning(f"Audio session {session_id} not found in cache")
            return None
        
        metadata = self._session_cache[session_id]
        metadata.connection_status = 'disconnected'
        metadata.end_time = datetime.now()
        
        # Final persistence to database
        await self._persist_session_final_state(session_id, metadata)
        
        # Trigger callbacks
        await self._trigger_event('session_ended', session_id, metadata)
        
        # Clean up buffers
        self._context_injection_buffer.pop(session_id, None)
        self._tool_execution_buffer.pop(session_id, None)
        
        # Remove from cache
        final_metadata = self._session_cache.pop(session_id)
        
        logger.info(f"Ended audio session {session_id}")
        return final_metadata
    
    def get_session_metadata(self, session_id: str) -> Optional[AudioSessionMetadata]:
        """Get cached session metadata."""
        return self._session_cache.get(session_id)
    
    def get_context_injection_history(
        self, 
        session_id: str, 
        limit: int = 50
    ) -> List[ContextInjectionRecord]:
        """Get context injection history for a session."""
        if session_id not in self._context_injection_buffer:
            return []
        
        buffer = self._context_injection_buffer[session_id]
        return list(buffer)[-limit:]
    
    def get_tool_execution_history(
        self, 
        session_id: str, 
        limit: int = 50
    ) -> List[ToolExecutionRecord]:
        """Get tool execution history for a session."""
        if session_id not in self._tool_execution_buffer:
            return []
        
        buffer = self._tool_execution_buffer[session_id]
        return list(buffer)[-limit:]
    
    async def _queue_update(self, update: Dict[str, Any]):
        """Queue an update for batching."""
        self._pending_updates.append(update)
        
        # Force flush if batch is full
        if len(self._pending_updates) >= self.batch_size:
            await self._flush_pending_updates()
    
    async def _flush_pending_updates(self):
        """Flush pending updates to database."""
        if not self._pending_updates:
            return
        
        updates_to_process = list(self._pending_updates)
        self._pending_updates.clear()
        self._last_batch_write = datetime.now()
        
        try:
            # Process updates in batch
            for update in updates_to_process:
                await self._process_update(update)
            
            logger.debug(f"Processed {len(updates_to_process)} batched updates")
            
        except Exception as e:
            logger.error(f"Error processing batch updates: {e}")
            # Re-queue failed updates
            self._pending_updates.extendleft(reversed(updates_to_process))
    
    async def _process_update(self, update: Dict[str, Any]):
        """Process a single update."""
        update_type = update.get('type')
        session_id = update.get('session_id')
        
        if not session_id:
            return
        
        try:
            # Update session activity
            self.session_manager.update_session_activity(session_id)
            
            # Handle specific update types
            if update_type in ['audio_session_start', 'connection_status_update']:
                # Update session metadata with audio information
                session = self.session_manager.get_session(session_id)
                if session:
                    metadata = session.get('metadata', {})
                    if session_id in self._session_cache:
                        metadata['audio_session'] = asdict(self._session_cache[session_id])
                    self.session_manager.update_session_metadata(session_id, metadata)
            
            elif update_type == 'context_injection':
                # Store context injection in memory manager if available
                if self.memory_manager:
                    record = update.get('record', {})
                    self.memory_manager.save_interview_memory(
                        session_id=session_id,
                        memory_type='context_injection',
                        memory_data=record
                    )
            
            elif update_type == 'tool_execution':
                # Store tool execution in memory manager if available
                if self.memory_manager:
                    record = update.get('record', {})
                    self.memory_manager.save_interview_memory(
                        session_id=session_id,
                        memory_type='tool_execution',
                        memory_data=record
                    )
            
        except Exception as e:
            logger.error(f"Error processing update {update_type} for session {session_id}: {e}")
    
    async def _persist_session_final_state(
        self, 
        session_id: str, 
        metadata: AudioSessionMetadata
    ):
        """Persist final session state to database."""
        try:
            # Update session metadata
            session = self.session_manager.get_session(session_id)
            if session:
                session_metadata = session.get('metadata', {})
                session_metadata['audio_session'] = asdict(metadata)
                
                # Add summary statistics
                session_metadata['audio_session_summary'] = {
                    'total_duration': metadata.total_audio_duration,
                    'message_count': metadata.message_count,
                    'context_injections': metadata.context_injections,
                    'tool_executions': metadata.tool_executions,
                    'session_duration': (
                        (metadata.end_time - metadata.start_time).total_seconds()
                        if metadata.end_time and metadata.start_time else 0
                    ),
                    'performance_metrics': metadata.performance_metrics
                }
                
                self.session_manager.update_session_metadata(session_id, session_metadata)
            
            # Store detailed history in memory manager if available
            if self.memory_manager:
                # Store context injection history
                context_history = self.get_context_injection_history(session_id)
                if context_history:
                    self.memory_manager.save_interview_memory(
                        session_id=session_id,
                        memory_type='context_injection_history',
                        memory_data={'records': [asdict(r) for r in context_history]}
                    )
                
                # Store tool execution history
                tool_history = self.get_tool_execution_history(session_id)
                if tool_history:
                    self.memory_manager.save_interview_memory(
                        session_id=session_id,
                        memory_type='tool_execution_history',
                        memory_data={'records': [asdict(r) for r in tool_history]}
                    )
            
            logger.info(f"Persisted final state for session {session_id}")
            
        except Exception as e:
            logger.error(f"Error persisting final state for session {session_id}: {e}")
    
    async def _batch_processor(self):
        """Background task for processing batched updates."""
        while self._running:
            try:
                await asyncio.sleep(5.0)  # Check every 5 seconds
                
                # Check if batch timeout has been reached
                time_since_last_write = datetime.now() - self._last_batch_write
                if (self._pending_updates and 
                    time_since_last_write.total_seconds() >= self.batch_timeout):
                    await self._flush_pending_updates()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in batch processor: {e}")
    
    async def _cache_cleanup(self):
        """Background task for cleaning up old cache entries."""
        while self._running:
            try:
                await asyncio.sleep(300.0)  # Clean up every 5 minutes
                
                # Remove old entries if cache is too large
                if len(self._session_cache) > self.max_cache_size:
                    # Sort by last activity and remove oldest
                    sorted_sessions = sorted(
                        self._session_cache.items(),
                        key=lambda x: x[1].start_time or datetime.min
                    )
                    
                    # Remove oldest 20% of entries
                    entries_to_remove = len(sorted_sessions) // 5
                    for session_id, _ in sorted_sessions[:entries_to_remove]:
                        self._session_cache.pop(session_id, None)
                        self._context_injection_buffer.pop(session_id, None)
                        self._tool_execution_buffer.pop(session_id, None)
                    
                    logger.info(f"Cleaned up {entries_to_remove} old cache entries")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cache cleanup: {e}")
    
    async def _trigger_event(self, event_type: str, session_id: str, data: Any):
        """Trigger event callbacks."""
        try:
            callbacks = self._event_callbacks.get(event_type, [])
            for callback in callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(session_id, data)
                    else:
                        callback(session_id, data)
                except Exception as e:
                    logger.error(f"Error in event callback {callback}: {e}")
        except Exception as e:
            logger.error(f"Error triggering event {event_type}: {e}") 
 
 