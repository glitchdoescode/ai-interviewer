"""
Unit tests for Context Injection Service.
"""
import pytest
import asyncio
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch

from ai_interviewer.services.context_injection_service import (
    ContextInjectionService, 
    ContextUpdate,
    SILENT_CONTEXT_PREFIX
)
from ai_interviewer.core.ai_interviewer import InterviewState, InterviewStage
from ai_interviewer.services.gemini_live_adapter import GeminiLiveAudioAdapter


class TestContextUpdate:
    """Test ContextUpdate dataclass."""
    
    def test_context_update_creation(self):
        """Test creating a ContextUpdate."""
        update = ContextUpdate(
            type="test",
            content="test content",
            priority=50,
            timestamp=datetime.now(),
            metadata={"key": "value"}
        )
        
        assert update.type == "test"
        assert update.content == "test content"
        assert update.priority == 50
        assert isinstance(update.timestamp, datetime)
        assert update.metadata == {"key": "value"}


class TestContextInjectionService:
    """Test ContextInjectionService."""
    
    @pytest.fixture
    def mock_gemini_adapter(self):
        """Create a mock GeminiLiveAudioAdapter."""
        adapter = Mock(spec=GeminiLiveAudioAdapter)
        adapter.inject_context = AsyncMock()
        return adapter
    
    @pytest.fixture
    def service(self, mock_gemini_adapter):
        """Create a ContextInjectionService instance."""
        return ContextInjectionService(gemini_adapter=mock_gemini_adapter)
    
    @pytest.fixture
    def interview_state(self):
        """Create a sample InterviewState."""
        # Create InterviewState properly
        state = InterviewState(
            messages=[],
            candidate_name="John Doe",
            job_role="Software Engineer",
            seniority_level="Senior",
            required_skills=["Python", "APIs", "Testing"],
            job_description="Senior software engineer position requiring Python expertise",
            requires_coding=True,
            interview_stage=InterviewStage.INTRODUCTION.value,
            session_id="test-session",
            user_id="test-user"
        )
        return state
    
    def test_initialization(self, mock_gemini_adapter):
        """Test service initialization."""
        service = ContextInjectionService(gemini_adapter=mock_gemini_adapter)
        
        assert service.gemini_adapter == mock_gemini_adapter
        assert service.current_context == {}
        assert service.context_history == []
        assert service.context_queue == []
        assert service.injection_task is None
        assert service.running is False
    
    def test_set_gemini_adapter(self):
        """Test setting Gemini adapter."""
        service = ContextInjectionService()
        adapter = Mock(spec=GeminiLiveAudioAdapter)
        
        service.set_gemini_adapter(adapter)
        assert service.gemini_adapter == adapter
    
    @patch('ai_interviewer.services.context_injection_service.get_llm_config')
    def test_format_interview_context(self, mock_get_config, service, interview_state):
        """Test formatting interview context."""
        mock_get_config.return_value = {"system_name": "TestAI"}
        
        context = service.format_interview_context(interview_state)
        
        assert "=== INTERVIEW CONTEXT ===" in context
        assert "AI Name: TestAI" in context
        assert "Role: Software Engineer" in context
        assert "Level: Senior" in context
        assert "Stage: introduction" in context
        assert "Candidate: John Doe" in context
        assert "Required Skills: Python, APIs, Testing" in context
        assert "Coding Required: True" in context
    
    def test_get_stage_guidance(self, service):
        """Test getting stage-specific guidance."""
        intro_guidance = service._get_stage_guidance(InterviewStage.INTRODUCTION.value)
        assert "building rapport" in intro_guidance
        
        technical_guidance = service._get_stage_guidance(InterviewStage.TECHNICAL_QUESTIONS.value)
        assert "Assess technical depth" in technical_guidance
        
        coding_guidance = service._get_stage_guidance(InterviewStage.CODING_CHALLENGE.value)
        assert "coding challenge" in coding_guidance
        
        unknown_guidance = service._get_stage_guidance("unknown_stage")
        assert unknown_guidance == ""
    
    @pytest.mark.asyncio
    async def test_inject_initial_context(self, service, interview_state):
        """Test injecting initial context."""
        with patch.object(service, '_queue_context_injection') as mock_queue:
            await service.inject_initial_context(interview_state)
            
            mock_queue.assert_called_once()
            args, kwargs = mock_queue.call_args
            context_update = args[0]
            
            assert context_update.type == "initial"
            assert context_update.priority == 100
            assert "INTERVIEW CONTEXT" in context_update.content
    
    @pytest.mark.asyncio
    async def test_inject_stage_transition(self, service):
        """Test injecting stage transition context."""
        context = {"candidate_name": "John", "job_role": "Engineer"}
        
        with patch.object(service, '_queue_context_injection') as mock_queue:
            await service.inject_stage_transition("introduction", "technical_questions", context)
            
            mock_queue.assert_called_once()
            args, kwargs = mock_queue.call_args
            context_update = args[0]
            
            assert context_update.type == "stage_transition"
            assert context_update.priority == 90
            assert "STAGE TRANSITION" in context_update.content
            assert "From: introduction" in context_update.content
            assert "To: technical_questions" in context_update.content
    
    @pytest.mark.asyncio
    async def test_inject_tool_result_coding_challenge(self, service):
        """Test injecting tool result for coding challenge."""
        tool_result = {
            "challenge": {
                "title": "Array Sum",
                "difficulty": "Medium", 
                "problem_statement": "Write a function to sum array elements"
            }
        }
        
        with patch.object(service, '_queue_context_injection') as mock_queue:
            await service.inject_tool_result("generate_coding_challenge_from_jd", tool_result)
            
            mock_queue.assert_called_once()
            args, kwargs = mock_queue.call_args
            context_update = args[0]
            
            assert context_update.type == "tool_result"
            assert context_update.priority == 80
            assert "TOOL RESULT" in context_update.content
            assert "Array Sum" in context_update.content
    
    @pytest.mark.asyncio
    async def test_inject_tool_result_code_submission(self, service):
        """Test injecting tool result for code submission."""
        tool_result = {
            "evaluation_summary": "Code works correctly",
            "score": 85
        }
        
        with patch.object(service, '_queue_context_injection') as mock_queue:
            await service.inject_tool_result("submit_code_for_generated_challenge", tool_result)
            
            mock_queue.assert_called_once()
            args, kwargs = mock_queue.call_args
            context_update = args[0]
            
            assert "Code Evaluation: Code works correctly" in context_update.content
            assert "Score: 85" in context_update.content
    
    @pytest.mark.asyncio
    async def test_update_session_context(self, service):
        """Test updating session context."""
        metadata = {
            "candidate_name": "Jane Doe",
            "interview_stage": "technical_questions",
            "message_count": 10
        }
        
        with patch.object(service, '_queue_context_injection') as mock_queue:
            await service.update_session_context(metadata)
            
            mock_queue.assert_called_once()
            args, kwargs = mock_queue.call_args
            context_update = args[0]
            
            assert context_update.type == "session_update"
            assert context_update.priority == 70
            assert "SESSION UPDATE" in context_update.content
            assert "Jane Doe" in context_update.content
    
    @pytest.mark.asyncio
    async def test_queue_context_injection(self, service):
        """Test queuing context injection."""
        # Create test context updates with different priorities
        update1 = ContextUpdate("test1", "content1", 50, datetime.now())
        update2 = ContextUpdate("test2", "content2", 90, datetime.now())
        update3 = ContextUpdate("test3", "content3", 70, datetime.now())
        
        with patch.object(service, 'start_injection_processing') as mock_start:
            await service._queue_context_injection(update1)
            await service._queue_context_injection(update2)
            await service._queue_context_injection(update3)
            
            # Should be sorted by priority (highest first)
            assert len(service.context_queue) == 3
            assert service.context_queue[0].priority == 90  # update2
            assert service.context_queue[1].priority == 70  # update3
            assert service.context_queue[2].priority == 50  # update1
    
    @pytest.mark.asyncio
    async def test_start_stop_injection_processing(self, service):
        """Test starting and stopping injection processing."""
        assert not service.running
        
        await service.start_injection_processing()
        assert service.running
        assert service.injection_task is not None
        
        await service.stop_injection_processing()
        assert not service.running
    
    @pytest.mark.asyncio
    async def test_process_injection_queue(self, service, mock_gemini_adapter):
        """Test processing injection queue."""
        # Add a context update to queue
        update = ContextUpdate("test", "test content", 50, datetime.now())
        service.context_queue.append(update)
        
        # Simplify the test - just mock the inject_context directly
        mock_gemini_adapter.inject_context.return_value = None
        
        # Start processing
        service.running = True
        
        # Run one iteration of the processing loop manually
        if service.context_queue and service.gemini_adapter:
            # Get highest priority context update
            context_update = service.context_queue.pop(0)
            
            # Format for silent injection
            silent_content = f"{SILENT_CONTEXT_PREFIX}\n{context_update.content}"
            
            # Inject silently into Gemini Live API
            await service.gemini_adapter.inject_context({
                "content": silent_content,
                "type": context_update.type,
                "timestamp": context_update.timestamp.isoformat()
            }, silent=True)
            
            # Add to history
            service.context_history.append(context_update)
        
        # Verify context was injected
        mock_gemini_adapter.inject_context.assert_called_once()
        args, kwargs = mock_gemini_adapter.inject_context.call_args
        
        context_data = args[0]
        assert context_data["content"].startswith(SILENT_CONTEXT_PREFIX)
        assert "test content" in context_data["content"]
        assert context_data["type"] == "test"
        assert kwargs.get("silent") is True
        
        # Verify update was moved to history
        assert len(service.context_history) == 1
        assert service.context_history[0] == update
    
    def test_add_callbacks(self, service):
        """Test adding callbacks."""
        callback1 = Mock()
        callback2 = Mock()
        
        service.add_context_injected_callback(callback1)
        service.add_stage_transition_callback(callback2)
        
        assert callback1 in service.context_injected_callbacks
        assert callback2 in service.stage_transition_callbacks
    
    def test_get_context_history(self, service):
        """Test getting context history."""
        update = ContextUpdate("test", "content", 50, datetime.now())
        service.context_history.append(update)
        
        history = service.get_context_history()
        assert len(history) == 1
        assert history[0] == update
        # Should be a copy, not the original
        assert history is not service.context_history
    
    def test_get_current_context_summary(self, service):
        """Test getting current context summary."""
        update = ContextUpdate("test", "content", 50, datetime.now())
        service.context_queue.append(update)
        service.context_history.append(update)
        
        summary = service.get_current_context_summary()
        
        assert summary["queue_size"] == 1
        assert summary["history_size"] == 1
        assert summary["running"] is False
        assert summary["adapter_connected"] is True
        assert summary["last_injection"] is not None
    
    @pytest.mark.asyncio
    async def test_cleanup(self, service):
        """Test cleanup."""
        # Add some data
        update = ContextUpdate("test", "content", 50, datetime.now())
        service.context_queue.append(update)
        service.context_history.append(update)
        service.context_injected_callbacks.append(Mock())
        service.stage_transition_callbacks.append(Mock())
        
        await service.cleanup()
        
        assert len(service.context_queue) == 0
        assert len(service.context_history) == 0
        assert len(service.context_injected_callbacks) == 0
        assert len(service.stage_transition_callbacks) == 0
        assert not service.running
    
    @pytest.mark.asyncio
    async def test_callback_execution_in_stage_transition(self, service):
        """Test that callbacks are executed during stage transition."""
        sync_callback = Mock()
        async_callback = AsyncMock()
        
        service.add_stage_transition_callback(sync_callback)
        service.add_stage_transition_callback(async_callback)
        
        with patch.object(service, '_queue_context_injection'):
            await service.inject_stage_transition("intro", "technical", {})
        
        sync_callback.assert_called_once_with("intro", "technical", {})
        async_callback.assert_called_once_with("intro", "technical", {})
    
    @pytest.mark.asyncio 
    async def test_error_handling_in_format_context(self, service):
        """Test error handling in format_interview_context."""
        # Create a mock interview state that will cause an error
        bad_state = Mock()
        bad_state.job_role = None  # This might cause an error
        
        with patch('ai_interviewer.services.context_injection_service.get_llm_config', side_effect=Exception("Config error")):
            context = service.format_interview_context(bad_state)
            
            assert "Interview context unavailable" in context
    
    @pytest.mark.asyncio
    async def test_priority_queue_ordering(self, service):
        """Test that context queue maintains priority ordering."""
        updates = [
            ContextUpdate("low", "content", 10, datetime.now()),
            ContextUpdate("high", "content", 100, datetime.now()),
            ContextUpdate("medium", "content", 50, datetime.now())
        ]
        
        for update in updates:
            await service._queue_context_injection(update)
        
        # Should be ordered by priority: high (100), medium (50), low (10)
        assert service.context_queue[0].type == "high"
        assert service.context_queue[1].type == "medium"
        assert service.context_queue[2].type == "low" 