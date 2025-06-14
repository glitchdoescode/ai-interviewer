"""
Unit tests for RealtimeSessionManager.
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from collections import deque

from ai_interviewer.services.realtime_session_manager import (
    RealtimeSessionManager,
    AudioSessionMetadata,
    ContextInjectionRecord,
    ToolExecutionRecord
)
from ai_interviewer.utils.session_manager import SessionManager
from ai_interviewer.utils.memory_manager import InterviewMemoryManager


class TestAudioSessionMetadata:
    """Test AudioSessionMetadata dataclass."""
    
    def test_audio_session_metadata_creation(self):
        """Test creating AudioSessionMetadata."""
        metadata = AudioSessionMetadata(
            session_id="test-session",
            connection_status="connected"
        )
        
        assert metadata.session_id == "test-session"
        assert metadata.connection_status == "connected"
        assert metadata.total_audio_duration == 0.0
        assert metadata.message_count == 0
        assert metadata.context_injections == 0
        assert metadata.tool_executions == 0
        assert metadata.performance_metrics is not None
        assert metadata.performance_metrics['avg_response_time'] == 0.0
    
    def test_audio_session_metadata_with_custom_metrics(self):
        """Test AudioSessionMetadata with custom performance metrics."""
        custom_metrics = {
            'avg_response_time': 1.5,
            'peak_response_time': 3.0,
            'total_processing_time': 15.0,
            'error_count': 2
        }
        
        metadata = AudioSessionMetadata(
            session_id="test-session",
            connection_status="connected",
            performance_metrics=custom_metrics
        )
        
        assert metadata.performance_metrics == custom_metrics


class TestContextInjectionRecord:
    """Test ContextInjectionRecord dataclass."""
    
    def test_context_injection_record_creation(self):
        """Test creating ContextInjectionRecord."""
        timestamp = datetime.now()
        record = ContextInjectionRecord(
            timestamp=timestamp,
            injection_type="initial",
            content_hash="abc123",
            priority=100,
            success=True
        )
        
        assert record.timestamp == timestamp
        assert record.injection_type == "initial"
        assert record.content_hash == "abc123"
        assert record.priority == 100
        assert record.success is True
        assert record.error_message is None
    
    def test_context_injection_record_with_error(self):
        """Test ContextInjectionRecord with error."""
        timestamp = datetime.now()
        record = ContextInjectionRecord(
            timestamp=timestamp,
            injection_type="tool_result",
            content_hash="def456",
            priority=80,
            success=False,
            error_message="Injection failed"
        )
        
        assert record.success is False
        assert record.error_message == "Injection failed"


class TestToolExecutionRecord:
    """Test ToolExecutionRecord dataclass."""
    
    def test_tool_execution_record_creation(self):
        """Test creating ToolExecutionRecord."""
        timestamp = datetime.now()
        input_data = {"param1": "value1"}
        output_data = {"result": "success"}
        
        record = ToolExecutionRecord(
            timestamp=timestamp,
            tool_name="test_tool",
            execution_id="exec-123",
            input_data=input_data,
            output_data=output_data,
            execution_time=1.5,
            success=True
        )
        
        assert record.timestamp == timestamp
        assert record.tool_name == "test_tool"
        assert record.execution_id == "exec-123"
        assert record.input_data == input_data
        assert record.output_data == output_data
        assert record.execution_time == 1.5
        assert record.success is True
        assert record.error_message is None


class TestRealtimeSessionManager:
    """Test RealtimeSessionManager class."""
    
    @pytest.fixture
    def mock_session_manager(self):
        """Create mock SessionManager."""
        mock = Mock(spec=SessionManager)
        mock.get_session.return_value = None
        mock.create_session.return_value = "test-session-id"
        mock.update_session_metadata.return_value = True
        mock.update_session_activity.return_value = True
        return mock
    
    @pytest.fixture
    def mock_memory_manager(self):
        """Create mock InterviewMemoryManager."""
        mock = Mock(spec=InterviewMemoryManager)
        mock.save_interview_memory.return_value = True
        return mock
    
    @pytest.fixture
    def realtime_manager(self, mock_session_manager, mock_memory_manager):
        """Create RealtimeSessionManager instance."""
        return RealtimeSessionManager(
            session_manager=mock_session_manager,
            memory_manager=mock_memory_manager,
            batch_size=5,
            batch_timeout=10.0,
            max_cache_size=100
        )
    
    def test_initialization(self, mock_session_manager, mock_memory_manager):
        """Test RealtimeSessionManager initialization."""
        manager = RealtimeSessionManager(
            session_manager=mock_session_manager,
            memory_manager=mock_memory_manager,
            batch_size=10,
            batch_timeout=30.0
        )
        
        assert manager.session_manager == mock_session_manager
        assert manager.memory_manager == mock_memory_manager
        assert manager.batch_size == 10
        assert manager.batch_timeout == 30.0
        assert manager._running is False
        assert len(manager._session_cache) == 0
        assert len(manager._pending_updates) == 0
    
    @pytest.mark.asyncio
    async def test_start_stop(self, realtime_manager):
        """Test starting and stopping background tasks."""
        # Start manager
        await realtime_manager.start()
        assert realtime_manager._running is True
        assert len(realtime_manager._background_tasks) == 2  # batch processor + cache cleanup
        
        # Stop manager
        await realtime_manager.stop()
        assert realtime_manager._running is False
        assert len(realtime_manager._background_tasks) == 0
    
    def test_register_event_callback(self, realtime_manager):
        """Test registering event callbacks."""
        callback = Mock()
        
        realtime_manager.register_event_callback('session_started', callback)
        assert callback in realtime_manager._event_callbacks['session_started']
        
        # Test unknown event type
        realtime_manager.register_event_callback('unknown_event', callback)
        # Should not raise error, just log warning
    
    @pytest.mark.asyncio
    async def test_start_audio_session_new(self, realtime_manager, mock_session_manager):
        """Test starting a new audio session."""
        session_id = "test-session"
        user_id = "test-user"
        initial_metadata = {"key": "value"}
        
        # Mock session manager to return None (new session)
        mock_session_manager.get_session.return_value = None
        
        # Start audio session
        audio_metadata = await realtime_manager.start_audio_session(
            session_id=session_id,
            user_id=user_id,
            initial_metadata=initial_metadata
        )
        
        # Verify audio metadata
        assert audio_metadata.session_id == session_id
        assert audio_metadata.connection_status == "connecting"
        assert audio_metadata.start_time is not None
        
        # Verify session is cached
        assert session_id in realtime_manager._session_cache
        assert session_id in realtime_manager._context_injection_buffer
        assert session_id in realtime_manager._tool_execution_buffer
        
        # Verify session manager calls
        mock_session_manager.create_session.assert_called_once()
        
        # Verify pending updates
        assert len(realtime_manager._pending_updates) == 1
        update = realtime_manager._pending_updates[0]
        assert update['type'] == 'audio_session_start'
        assert update['session_id'] == session_id
    
    @pytest.mark.asyncio
    async def test_start_audio_session_existing(self, realtime_manager, mock_session_manager):
        """Test starting audio session for existing session."""
        session_id = "test-session"
        user_id = "test-user"
        
        # Mock existing session
        existing_session = {
            'session_id': session_id,
            'user_id': user_id,
            'metadata': {'existing': 'data'}
        }
        mock_session_manager.get_session.return_value = existing_session
        
        # Start audio session
        audio_metadata = await realtime_manager.start_audio_session(
            session_id=session_id,
            user_id=user_id
        )
        
        # Verify session manager calls
        mock_session_manager.create_session.assert_not_called()
        mock_session_manager.update_session_metadata.assert_called_once()
        
        # Verify metadata update includes audio session
        call_args = mock_session_manager.update_session_metadata.call_args
        assert call_args[0][0] == session_id
        metadata = call_args[0][1]
        assert 'audio_session' in metadata
        assert 'existing' in metadata  # Original metadata preserved
    
    @pytest.mark.asyncio
    async def test_update_connection_status(self, realtime_manager):
        """Test updating connection status."""
        session_id = "test-session"
        
        # First start a session
        await realtime_manager.start_audio_session(session_id, "test-user")
        
        # Update connection status
        await realtime_manager.update_connection_status(session_id, "connected")
        
        # Verify status updated
        metadata = realtime_manager.get_session_metadata(session_id)
        assert metadata.connection_status == "connected"
        
        # Verify pending update
        assert len(realtime_manager._pending_updates) == 2  # start + status update
        status_update = realtime_manager._pending_updates[1]
        assert status_update['type'] == 'connection_status_update'
        assert status_update['old_status'] == 'connecting'
        assert status_update['new_status'] == 'connected'
    
    @pytest.mark.asyncio
    async def test_update_connection_status_nonexistent(self, realtime_manager):
        """Test updating connection status for nonexistent session."""
        # This should not raise an error, just log a warning
        await realtime_manager.update_connection_status("nonexistent", "connected")
        
        # No updates should be pending
        assert len(realtime_manager._pending_updates) == 0
    
    @pytest.mark.asyncio
    async def test_record_context_injection(self, realtime_manager):
        """Test recording context injection."""
        session_id = "test-session"
        
        # Start session first
        await realtime_manager.start_audio_session(session_id, "test-user")
        
        # Record context injection
        await realtime_manager.record_context_injection(
            session_id=session_id,
            injection_type="initial",
            content_hash="abc123",
            priority=100,
            success=True
        )
        
        # Verify injection recorded in buffer
        history = realtime_manager.get_context_injection_history(session_id)
        assert len(history) == 1
        record = history[0]
        assert record.injection_type == "initial"
        assert record.content_hash == "abc123"
        assert record.success is True
        
        # Verify session metadata updated
        metadata = realtime_manager.get_session_metadata(session_id)
        assert metadata.context_injections == 1
        
        # Verify pending update
        context_update = None
        for update in realtime_manager._pending_updates:
            if update['type'] == 'context_injection':
                context_update = update
                break
        
        assert context_update is not None
        assert context_update['session_id'] == session_id
    
    @pytest.mark.asyncio
    async def test_record_tool_execution(self, realtime_manager):
        """Test recording tool execution."""
        session_id = "test-session"
        
        # Start session first
        await realtime_manager.start_audio_session(session_id, "test-user")
        
        # Record tool execution
        input_data = {"param": "value"}
        output_data = {"result": "success"}
        
        await realtime_manager.record_tool_execution(
            session_id=session_id,
            tool_name="test_tool",
            execution_id="exec-123",
            input_data=input_data,
            output_data=output_data,
            execution_time=1.5,
            success=True
        )
        
        # Verify execution recorded in buffer
        history = realtime_manager.get_tool_execution_history(session_id)
        assert len(history) == 1
        record = history[0]
        assert record.tool_name == "test_tool"
        assert record.execution_id == "exec-123"
        assert record.input_data == input_data
        assert record.output_data == output_data
        assert record.execution_time == 1.5
        assert record.success is True
        
        # Verify session metadata updated
        metadata = realtime_manager.get_session_metadata(session_id)
        assert metadata.tool_executions == 1
        assert metadata.performance_metrics['total_processing_time'] == 1.5
        assert metadata.performance_metrics['peak_response_time'] == 1.5
        assert metadata.performance_metrics['avg_response_time'] == 1.5
    
    @pytest.mark.asyncio
    async def test_update_audio_processing_stats(self, realtime_manager):
        """Test updating audio processing statistics."""
        session_id = "test-session"
        
        # Start session first
        await realtime_manager.start_audio_session(session_id, "test-user")
        
        # Update audio stats
        await realtime_manager.update_audio_processing_stats(
            session_id=session_id,
            audio_duration=2.5,
            processing_time=0.8
        )
        
        # Verify stats updated
        metadata = realtime_manager.get_session_metadata(session_id)
        assert metadata.total_audio_duration == 2.5
        assert metadata.message_count == 1
        assert metadata.performance_metrics['peak_response_time'] == 0.8
    
    @pytest.mark.asyncio
    async def test_end_audio_session(self, realtime_manager, mock_session_manager):
        """Test ending audio session."""
        session_id = "test-session"
        
        # Start session first
        await realtime_manager.start_audio_session(session_id, "test-user")
        
        # Mock existing session for final persistence
        mock_session_manager.get_session.return_value = {
            'session_id': session_id,
            'metadata': {}
        }
        
        # End session
        final_metadata = await realtime_manager.end_audio_session(session_id)
        
        # Verify final metadata
        assert final_metadata is not None
        assert final_metadata.connection_status == "disconnected"
        assert final_metadata.end_time is not None
        
        # Verify session removed from cache
        assert session_id not in realtime_manager._session_cache
        assert session_id not in realtime_manager._context_injection_buffer
        assert session_id not in realtime_manager._tool_execution_buffer
        
        # Verify final persistence called
        mock_session_manager.update_session_metadata.assert_called()
    
    @pytest.mark.asyncio
    async def test_end_nonexistent_session(self, realtime_manager):
        """Test ending nonexistent session."""
        result = await realtime_manager.end_audio_session("nonexistent")
        assert result is None
    
    def test_get_session_metadata(self, realtime_manager):
        """Test getting session metadata."""
        # Should return None for nonexistent session
        assert realtime_manager.get_session_metadata("nonexistent") is None
    
    def test_get_context_injection_history(self, realtime_manager):
        """Test getting context injection history."""
        # Should return empty list for nonexistent session
        assert realtime_manager.get_context_injection_history("nonexistent") == []
    
    def test_get_tool_execution_history(self, realtime_manager):
        """Test getting tool execution history."""
        # Should return empty list for nonexistent session
        assert realtime_manager.get_tool_execution_history("nonexistent") == []
    
    @pytest.mark.asyncio
    async def test_batch_processing(self, realtime_manager, mock_session_manager):
        """Test batch processing of updates."""
        session_id = "test-session"
        
        # Configure small batch size for testing
        realtime_manager.batch_size = 2
        
        # Start session (adds 1 update)
        await realtime_manager.start_audio_session(session_id, "test-user")
        assert len(realtime_manager._pending_updates) == 1
        
        # Add another update (should trigger batch flush)
        await realtime_manager.update_connection_status(session_id, "connected")
        
        # Both updates should be processed (batch size reached)
        assert len(realtime_manager._pending_updates) == 0
        
        # Verify session manager was called
        assert mock_session_manager.update_session_activity.call_count >= 2
    
    @pytest.mark.asyncio
    async def test_event_callbacks(self, realtime_manager):
        """Test event callback triggering."""
        callback = AsyncMock()
        sync_callback = Mock()
        
        # Register callbacks
        realtime_manager.register_event_callback('session_started', callback)
        realtime_manager.register_event_callback('session_started', sync_callback)
        
        session_id = "test-session"
        
        # Start session (should trigger callbacks)
        audio_metadata = await realtime_manager.start_audio_session(session_id, "test-user")
        
        # Verify callbacks were called
        callback.assert_called_once_with(session_id, audio_metadata)
        sync_callback.assert_called_once_with(session_id, audio_metadata)
    
    @pytest.mark.asyncio
    async def test_error_handling_in_process_update(self, realtime_manager, mock_session_manager):
        """Test error handling in update processing."""
        # Make session manager raise an exception
        mock_session_manager.update_session_activity.side_effect = Exception("DB error")
        
        session_id = "test-session"
        
        # This should not raise an exception, just log the error
        await realtime_manager.start_audio_session(session_id, "test-user")
        
        # Force process pending updates
        await realtime_manager._flush_pending_updates()
        
        # Error should be handled gracefully
        assert len(realtime_manager._pending_updates) == 0  # Updates should be processed despite error
    
    @pytest.mark.asyncio
    async def test_memory_manager_integration(self, realtime_manager, mock_memory_manager):
        """Test integration with memory manager."""
        session_id = "test-session"
        
        # Start session
        await realtime_manager.start_audio_session(session_id, "test-user")
        
        # Record context injection
        await realtime_manager.record_context_injection(
            session_id=session_id,
            injection_type="initial",
            content_hash="abc123",
            priority=100,
            success=True
        )
        
        # Force flush updates
        await realtime_manager._flush_pending_updates()
        
        # Verify memory manager was called
        mock_memory_manager.save_interview_memory.assert_called()
        call_args = mock_memory_manager.save_interview_memory.call_args
        assert call_args[1]['session_id'] == session_id
        assert call_args[1]['memory_type'] == 'context_injection'


@pytest.mark.asyncio
async def test_integration_with_real_components():
    """Integration test with more realistic components."""
    # This would be an integration test that uses real SessionManager
    # and tests the full flow
    pass 
 
 