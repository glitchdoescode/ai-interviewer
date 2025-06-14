"""
LangGraph Integration Adapter for AI Interviewer Gemini Live API Integration.

This adapter bridges the Gemini Live API real-time conversation flow with the existing
LangGraph interview logic, handling state management, tool calls, and stage transitions.
"""
import asyncio
import logging
import re
import json
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass

from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

from ai_interviewer.core.ai_interviewer import AIInterviewer, InterviewState, InterviewStage
from ai_interviewer.services.context_injection_service import ContextInjectionService
from ai_interviewer.services.gemini_live_adapter import GeminiLiveAudioAdapter

logger = logging.getLogger(__name__)

# Tool detection patterns
TOOL_TRIGGER_PATTERNS = {
    "generate_coding_challenge_from_jd": [
        r"(?i)coding\s+challenge",
        r"(?i)programming\s+problem",
        r"(?i)let.s\s+start\s+with\s+the\s+coding",
        r"(?i)time\s+for\s+a\s+coding\s+exercise"
    ],
    "submit_code_for_generated_challenge": [
        r"(?i)here.s\s+my\s+solution",
        r"(?i)submit\s+code",
        r"(?i)my\s+answer\s+is",
        r"(?i)```.*```"  # Code blocks
    ],
    "analyze_candidate_response": [
        r"(?i)what\s+do\s+you\s+think",
        r"(?i)how\s+did\s+i\s+do",
        r"(?i)can\s+you\s+evaluate"
    ]
}

# Stage transition patterns
STAGE_TRANSITION_PATTERNS = {
    InterviewStage.TECHNICAL_QUESTIONS.value: [
        r"(?i)technical\s+questions?",
        r"(?i)let.s\s+talk\s+about\s+your\s+experience",
        r"(?i)tell\s+me\s+about.*technical"
    ],
    InterviewStage.CODING_CHALLENGE.value: [
        r"(?i)coding\s+challenge",
        r"(?i)programming\s+exercise",
        r"(?i)write\s+some\s+code"
    ],
    InterviewStage.BEHAVIORAL_QUESTIONS.value: [
        r"(?i)behavioral\s+questions?",
        r"(?i)tell\s+me\s+about\s+a\s+time",
        r"(?i)describe\s+a\s+situation"
    ],
    InterviewStage.FEEDBACK.value: [
        r"(?i)feedback",
        r"(?i)how\s+did\s+i\s+perform",
        r"(?i)evaluation"
    ],
    InterviewStage.CONCLUSION.value: [
        r"(?i)wrap\s+up",
        r"(?i)conclude",
        r"(?i)final\s+thoughts",
        r"(?i)thank\s+you\s+for.*interview"
    ]
}

@dataclass
class ConversationTurn:
    """Represents a single conversation turn."""
    timestamp: datetime
    speaker: str  # 'human' or 'ai'
    content: str
    audio_data: Optional[bytes] = None
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class ToolExecutionResult:
    """Result of a tool execution."""
    tool_name: str
    success: bool
    result: Dict[str, Any]
    execution_time_ms: int
    error: Optional[str] = None

class LangGraphIntegrationAdapter:
    """
    Integration adapter that bridges Gemini Live API with LangGraph interview logic.
    
    This adapter handles:
    - Real-time conversation state management
    - Tool call detection and execution
    - Stage transition management
    - Session persistence
    """
    
    def __init__(self, 
                 ai_interviewer: AIInterviewer,
                 context_service: ContextInjectionService,
                 gemini_adapter: GeminiLiveAudioAdapter):
        """
        Initialize the LangGraph Integration Adapter.
        
        Args:
            ai_interviewer: The core AI interviewer instance
            context_service: Context injection service
            gemini_adapter: Gemini Live API adapter
        """
        self.ai_interviewer = ai_interviewer
        self.context_service = context_service
        self.gemini_adapter = gemini_adapter
        
        # State management
        self.current_session_id: Optional[str] = None
        self.current_state: Optional[InterviewState] = None
        self.conversation_buffer: List[ConversationTurn] = []
        self.tool_execution_queue: List[Dict[str, Any]] = []
        
        # Processing tasks
        self.processing_task: Optional[asyncio.Task] = None
        self.running = False
        
        # Event callbacks
        self.stage_transition_callbacks: List[Callable] = []
        self.tool_execution_callbacks: List[Callable] = []
        self.state_update_callbacks: List[Callable] = []
        
        # Performance metrics
        self.tool_execution_times: List[float] = []
        self.avg_tool_execution_time = 0.0
        
        logger.info("LangGraphIntegrationAdapter initialized")
    
    async def start_session(self, 
                          user_id: str, 
                          session_config: Dict[str, Any]) -> Tuple[str, InterviewState]:
        """
        Start a new interview session.
        
        Args:
            user_id: User identifier
            session_config: Session configuration
            
        Returns:
            Tuple of (session_id, initial_state)
        """
        try:
            # Extract session parameters
            job_role = session_config.get("job_role", "Software Engineer")
            seniority_level = session_config.get("seniority_level", "Mid-level")
            required_skills = session_config.get("required_skills", [])
            job_description = session_config.get("job_description", "")
            requires_coding = session_config.get("requires_coding", True)
            
            # Create initial interview state
            self.current_state = InterviewState(
                candidate_name=session_config.get("candidate_name", ""),
                job_role=job_role,
                seniority_level=seniority_level,
                required_skills=required_skills,
                job_description=job_description,
                requires_coding=requires_coding,
                interview_stage=InterviewStage.INTRODUCTION.value,
                session_id="",  # Will be set after creation
                user_id=user_id,
                conversation_summary="",
                message_count=0
            )
            
            # Get or create session via AI interviewer
            self.current_session_id = self.ai_interviewer._get_or_create_session(
                user_id=user_id,
                job_role=job_role,
                seniority_level=seniority_level,
                required_skills=required_skills,
                job_description=job_description,
                requires_coding=requires_coding
            )
            
            # Update session ID in state
            self.current_state.session_id = self.current_session_id
            
            # Inject initial context
            await self.context_service.inject_initial_context(self.current_state)
            
            # Start processing
            await self.start_processing()
            
            logger.info(f"Started interview session: {self.current_session_id}")
            return self.current_session_id, self.current_state
            
        except Exception as e:
            logger.error(f"Error starting session: {e}", exc_info=True)
            raise
    
    async def handle_conversation_turn(self, 
                                     speaker: str, 
                                     content: str, 
                                     audio_data: Optional[bytes] = None) -> bool:
        """
        Process a conversation turn and update interview state.
        
        Args:
            speaker: 'human' or 'ai'
            content: Text content of the turn
            audio_data: Optional audio data
            
        Returns:
            True if processing was successful
        """
        try:
            if not self.current_state:
                logger.error("No active session for conversation turn")
                return False
            
            # Create conversation turn
            turn = ConversationTurn(
                timestamp=datetime.now(),
                speaker=speaker,
                content=content,
                audio_data=audio_data
            )
            
            # Add to buffer
            self.conversation_buffer.append(turn)
            
            # Keep buffer size manageable
            if len(self.conversation_buffer) > 50:
                self.conversation_buffer = self.conversation_buffer[-30:]
            
            # Update message count
            self.current_state.message_count += 1
            
            # Detect and handle stage transitions
            await self._detect_and_handle_stage_transitions(content, speaker)
            
            # Detect and queue tool calls
            await self._detect_and_queue_tool_calls(content, speaker)
            
            # Update session context
            await self._update_session_context()
            
            # Notify callbacks
            for callback in self.state_update_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(self.current_state, turn)
                    else:
                        callback(self.current_state, turn)
                except Exception as e:
                    logger.error(f"Error in state update callback: {e}", exc_info=True)
            
            return True
            
        except Exception as e:
            logger.error(f"Error handling conversation turn: {e}", exc_info=True)
            return False
    
    async def _detect_and_handle_stage_transitions(self, content: str, speaker: str):
        """Detect and handle interview stage transitions."""
        if not self.current_state:
            return
        
        current_stage = self.current_state.interview_stage
        new_stage = None
        
        # Check for stage transition patterns
        for stage, patterns in STAGE_TRANSITION_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, content):
                    new_stage = stage
                    break
            if new_stage:
                break
        
        # Special logic for automatic stage progression
        if not new_stage:
            new_stage = self._determine_next_stage_automatically()
        
        # Handle stage transition if detected
        if new_stage and new_stage != current_stage:
            await self._transition_to_stage(new_stage)
    
    def _determine_next_stage_automatically(self) -> Optional[str]:
        """Determine next stage based on conversation flow and state."""
        if not self.current_state:
            return None
        
        current_stage = self.current_state.interview_stage
        message_count = self.current_state.message_count
        
        # Automatic progression logic
        if current_stage == InterviewStage.INTRODUCTION.value and message_count >= 6:
            return InterviewStage.TECHNICAL_QUESTIONS.value
        elif current_stage == InterviewStage.TECHNICAL_QUESTIONS.value and message_count >= 15:
            if self.current_state.requires_coding:
                return InterviewStage.CODING_CHALLENGE.value
            else:
                return InterviewStage.BEHAVIORAL_QUESTIONS.value
        elif current_stage == InterviewStage.CODING_CHALLENGE.value and message_count >= 25:
            return InterviewStage.BEHAVIORAL_QUESTIONS.value
        elif current_stage == InterviewStage.BEHAVIORAL_QUESTIONS.value and message_count >= 35:
            return InterviewStage.FEEDBACK.value
        elif current_stage == InterviewStage.FEEDBACK.value and message_count >= 45:
            return InterviewStage.CONCLUSION.value
        
        return None
    
    async def _transition_to_stage(self, new_stage: str):
        """Handle transition to a new interview stage."""
        if not self.current_state:
            return
        
        old_stage = self.current_state.interview_stage
        self.current_state.interview_stage = new_stage
        
        # Inject stage transition context
        context = {
            "candidate_name": self.current_state.candidate_name,
            "job_role": self.current_state.job_role,
            "requires_coding": self.current_state.requires_coding,
            "message_count": self.current_state.message_count
        }
        
        await self.context_service.inject_stage_transition(old_stage, new_stage, context)
        
        # Notify callbacks
        for callback in self.stage_transition_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(old_stage, new_stage, self.current_state)
                else:
                    callback(old_stage, new_stage, self.current_state)
            except Exception as e:
                logger.error(f"Error in stage transition callback: {e}", exc_info=True)
        
        logger.info(f"Stage transition: {old_stage} -> {new_stage}")
    
    async def _detect_and_queue_tool_calls(self, content: str, speaker: str):
        """Detect tool call patterns and queue for execution."""
        # Check for tool trigger patterns
        for tool_name, patterns in TOOL_TRIGGER_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, content):
                    await self._queue_tool_execution(tool_name, content, speaker)
                    break
    
    async def _queue_tool_execution(self, tool_name: str, content: str, speaker: str):
        """Queue a tool for execution."""
        if not self.current_state:
            return
        
        # Prepare tool arguments based on tool type
        tool_args = await self._prepare_tool_arguments(tool_name, content)
        
        tool_execution = {
            "tool_name": tool_name,
            "tool_args": tool_args,
            "content": content,
            "speaker": speaker,
            "timestamp": datetime.now(),
            "state_snapshot": {
                "job_role": self.current_state.job_role,
                "required_skills": self.current_state.required_skills,
                "job_description": self.current_state.job_description,
                "interview_stage": self.current_state.interview_stage
            }
        }
        
        self.tool_execution_queue.append(tool_execution)
        logger.info(f"Queued tool execution: {tool_name}")
    
    async def _prepare_tool_arguments(self, tool_name: str, content: str) -> Dict[str, Any]:
        """Prepare arguments for tool execution."""
        if not self.current_state:
            return {}
        
        if tool_name == "generate_coding_challenge_from_jd":
            return {
                "job_description": self.current_state.job_description,
                "skills_required": self.current_state.required_skills,
                "difficulty_level": "intermediate"  # Could be dynamic based on seniority
            }
        
        elif tool_name == "submit_code_for_generated_challenge":
            # Extract code from content (simplified)
            code_match = re.search(r"```(?:python|javascript|java|cpp)?\n(.*?)\n```", content, re.DOTALL)
            code = code_match.group(1) if code_match else content
            
            return {
                "code_submission": code,
                "programming_language": "python"  # Could be detected
            }
        
        elif tool_name == "analyze_candidate_response":
            return {
                "response_text": content,
                "context": f"Interview stage: {self.current_state.interview_stage}"
            }
        
        return {}
    
    async def trigger_tool_call(self, tool_name: str, tool_args: Dict[str, Any]) -> ToolExecutionResult:
        """
        Execute a LangGraph tool and inject results.
        
        Args:
            tool_name: Name of the tool to execute
            tool_args: Arguments for the tool
            
        Returns:
            Tool execution result
        """
        start_time = datetime.now()
        
        try:
            # Create a message for the tool call
            tool_message = AIMessage(content=json.dumps({
                "name": tool_name,
                "args": tool_args,
                "id": f"call_{int(start_time.timestamp())}"
            }))
            
            # Add to current state messages
            if self.current_state:
                self.current_state.messages.append(tool_message)
            
            # Execute through AI interviewer
            # This is a simplified approach - in practice, you might need to call specific tool methods
            result = await self._execute_tool_via_langgraph(tool_name, tool_args)
            
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            # Track performance
            self.tool_execution_times.append(execution_time)
            if len(self.tool_execution_times) > 100:
                self.tool_execution_times = self.tool_execution_times[-50:]
            
            self.avg_tool_execution_time = sum(self.tool_execution_times) / len(self.tool_execution_times)
            
            # Inject tool result as context
            await self.context_service.inject_tool_result(tool_name, result)
            
            # Create result
            tool_result = ToolExecutionResult(
                tool_name=tool_name,
                success=True,
                result=result,
                execution_time_ms=int(execution_time)
            )
            
            # Notify callbacks
            for callback in self.tool_execution_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(tool_result)
                    else:
                        callback(tool_result)
                except Exception as e:
                    logger.error(f"Error in tool execution callback: {e}", exc_info=True)
            
            logger.info(f"Tool executed successfully: {tool_name} ({execution_time:.1f}ms)")
            return tool_result
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"Error executing tool {tool_name}: {e}", exc_info=True)
            
            return ToolExecutionResult(
                tool_name=tool_name,
                success=False,
                result={},
                execution_time_ms=int(execution_time),
                error=str(e)
            )
    
    async def _execute_tool_via_langgraph(self, tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute tool via LangGraph workflow (simplified implementation)."""
        # This is a simplified implementation
        # In practice, you would integrate more deeply with the LangGraph workflow
        
        if tool_name == "generate_coding_challenge_from_jd":
            # Simulate coding challenge generation
            return {
                "challenge": {
                    "title": "Array Manipulation",
                    "difficulty": tool_args.get("difficulty_level", "intermediate"),
                    "problem_statement": "Write a function to manipulate arrays based on given criteria.",
                    "starter_code": "def solve_problem(arr):\n    # Your code here\n    pass",
                    "test_cases": [
                        {"input": "[1, 2, 3]", "expected_output": "[3, 2, 1]"}
                    ]
                }
            }
        
        elif tool_name == "submit_code_for_generated_challenge":
            # Simulate code evaluation
            return {
                "evaluation_summary": "Code structure is good, logic is correct",
                "score": 85,
                "feedback": "Well implemented solution with good practices"
            }
        
        elif tool_name == "analyze_candidate_response":
            # Simulate response analysis
            return {
                "analysis": "Candidate shows good technical understanding",
                "sentiment": "positive",
                "key_points": ["technical competence", "problem-solving approach"]
            }
        
        return {"result": "Tool executed successfully"}
    
    async def _update_session_context(self):
        """Update session context in the database and inject into conversation."""
        if not self.current_state or not self.current_session_id:
            return
        
        try:
            # Update session metadata
            session_metadata = {
                "candidate_name": self.current_state.candidate_name,
                "interview_stage": self.current_state.interview_stage,
                "message_count": self.current_state.message_count,
                "session_id": self.current_session_id,
                "last_updated": datetime.now().isoformat()
            }
            
            # Inject session context update
            await self.context_service.update_session_context(session_metadata)
            
            # Periodically create conversation summary
            if self.current_state.message_count % 20 == 0:
                await self._create_conversation_summary()
                
        except Exception as e:
            logger.error(f"Error updating session context: {e}", exc_info=True)
    
    async def _create_conversation_summary(self):
        """Create and inject conversation summary."""
        if not self.current_state or len(self.conversation_buffer) < 10:
            return
        
        try:
            # Create summary from conversation buffer
            recent_turns = self.conversation_buffer[-20:]  # Last 20 turns
            
            summary_parts = []
            for turn in recent_turns:
                summary_parts.append(f"{turn.speaker}: {turn.content[:100]}...")
            
            summary = "Recent conversation:\n" + "\n".join(summary_parts)
            
            # Update state
            self.current_state.conversation_summary = summary
            
            # Inject summary context
            await self.context_service.update_session_context({
                "conversation_summary": summary,
                "summary_created_at": datetime.now().isoformat()
            })
            
            logger.info("Created conversation summary")
            
        except Exception as e:
            logger.error(f"Error creating conversation summary: {e}", exc_info=True)
    
    async def start_processing(self):
        """Start background processing of tool execution queue."""
        if self.running:
            return
        
        self.running = True
        self.processing_task = asyncio.create_task(self._process_tool_queue())
        logger.info("Started LangGraph integration processing")
    
    async def stop_processing(self):
        """Stop background processing."""
        self.running = False
        
        if self.processing_task and not self.processing_task.done():
            self.processing_task.cancel()
            try:
                await self.processing_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Stopped LangGraph integration processing")
    
    async def _process_tool_queue(self):
        """Process the tool execution queue."""
        while self.running:
            try:
                if self.tool_execution_queue:
                    # Get next tool execution
                    tool_execution = self.tool_execution_queue.pop(0)
                    
                    # Execute tool
                    result = await self.trigger_tool_call(
                        tool_execution["tool_name"],
                        tool_execution["tool_args"]
                    )
                    
                    logger.debug(f"Processed tool: {tool_execution['tool_name']}")
                
                else:
                    # No tools to execute, wait a bit
                    await asyncio.sleep(0.1)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing tool queue: {e}", exc_info=True)
                await asyncio.sleep(1)  # Wait before retrying
    
    def add_stage_transition_callback(self, callback: Callable):
        """Add callback for stage transitions."""
        self.stage_transition_callbacks.append(callback)
    
    def add_tool_execution_callback(self, callback: Callable):
        """Add callback for tool executions."""
        self.tool_execution_callbacks.append(callback)
    
    def add_state_update_callback(self, callback: Callable):
        """Add callback for state updates."""
        self.state_update_callbacks.append(callback)
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        return {
            "avg_tool_execution_time_ms": self.avg_tool_execution_time,
            "tool_executions_count": len(self.tool_execution_times),
            "queue_size": len(self.tool_execution_queue),
            "conversation_buffer_size": len(self.conversation_buffer),
            "current_session": self.current_session_id,
            "current_stage": self.current_state.interview_stage if self.current_state else None
        }
    
    async def cleanup(self):
        """Clean up resources."""
        await self.stop_processing()
        
        self.conversation_buffer.clear()
        self.tool_execution_queue.clear()
        self.tool_execution_times.clear()
        
        self.stage_transition_callbacks.clear()
        self.tool_execution_callbacks.clear()
        self.state_update_callbacks.clear()
        
        self.current_session_id = None
        self.current_state = None
        
        logger.info("LangGraphIntegrationAdapter cleaned up") 