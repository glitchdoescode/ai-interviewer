"""
Context Injection Service for AI Interviewer Gemini Live API Integration.

This service bridges the existing LangGraph interview logic with the Gemini Live API
by formatting and injecting interview context silently into the real-time conversation.
"""
import asyncio
import logging
import json
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass

from ai_interviewer.core.ai_interviewer import InterviewState, InterviewStage
from ai_interviewer.services.gemini_live_adapter import GeminiLiveAudioAdapter
from ai_interviewer.utils.config import get_llm_config

logger = logging.getLogger(__name__)

# Context injection constants
SILENT_CONTEXT_PREFIX = "[SYSTEM CONTEXT - DO NOT RESPOND OR ACKNOWLEDGE - ABSORB SILENTLY]"
MAX_CONTEXT_LENGTH = 4000  # Maximum characters for context injection
CONTEXT_BATCH_DELAY = 0.5  # Delay between context injections to avoid rate limits

@dataclass
class ContextUpdate:
    """Represents a context update to be injected."""
    type: str  # 'initial', 'stage_transition', 'tool_result', 'session_update'
    content: str
    priority: int  # Higher number = higher priority
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None

class ContextInjectionService:
    """
    Service for injecting interview context into Gemini Live API conversations.
    
    This service monitors InterviewState changes and translates them into
    silent context updates that maintain interview flow without interrupting
    the natural conversation.
    """
    
    def __init__(self, gemini_adapter: Optional[GeminiLiveAudioAdapter] = None):
        """
        Initialize the Context Injection Service.
        
        Args:
            gemini_adapter: Optional pre-initialized GeminiLiveAudioAdapter
        """
        self.gemini_adapter = gemini_adapter
        self.current_context = {}
        self.context_history: List[ContextUpdate] = []
        self.context_queue: List[ContextUpdate] = []
        self.injection_task: Optional[asyncio.Task] = None
        self.running = False
        
        # Event callbacks
        self.context_injected_callbacks: List[Callable] = []
        self.stage_transition_callbacks: List[Callable] = []
        
        logger.info("ContextInjectionService initialized")
    
    def set_gemini_adapter(self, adapter: GeminiLiveAudioAdapter):
        """Set or update the Gemini Live API adapter."""
        self.gemini_adapter = adapter
        logger.info("Gemini adapter set for context injection")
    
    def format_interview_context(self, interview_state: InterviewState) -> str:
        """
        Format interview context for injection.
        
        Args:
            interview_state: Current interview state
            
        Returns:
            Formatted context string
        """
        try:
            # Handle both InterviewState objects and dict representations
            def get_attr(obj, key, default=""):
                if hasattr(obj, key):
                    return getattr(obj, key)
                elif isinstance(obj, dict):
                    return obj.get(key, default)
                else:
                    return default
            
            config = get_llm_config()
            
            context_parts = [
                "=== INTERVIEW CONTEXT ===",
                f"AI Name: {config.get('system_name', 'AI Interviewer')}",
                f"Role: {get_attr(interview_state, 'job_role', 'Not specified')}",
                f"Level: {get_attr(interview_state, 'seniority_level', 'Not specified')}",
                f"Stage: {get_attr(interview_state, 'interview_stage', 'Unknown')}",
                f"Candidate: {get_attr(interview_state, 'candidate_name', 'Not provided')}",
                ""
            ]
            
            # Handle required_skills (could be list or string)
            skills = get_attr(interview_state, 'required_skills', [])
            if isinstance(skills, list):
                skills_str = ', '.join(skills) if skills else 'Not specified'
            else:
                skills_str = str(skills) if skills else 'Not specified'
            context_parts.append(f"Required Skills: {skills_str}")
            
            # Add other context information
            context_parts.extend([
                f"Coding Required: {get_attr(interview_state, 'requires_coding', True)}",
                f"Session: {get_attr(interview_state, 'session_id', 'Unknown')}",
                ""
            ])
            
            # Add stage-specific guidance
            stage = get_attr(interview_state, 'interview_stage', '')
            stage_guidance = self._get_stage_guidance(stage)
            if stage_guidance:
                context_parts.extend([
                    "=== STAGE GUIDANCE ===",
                    stage_guidance,
                    ""
                ])
            
            return "\n".join(context_parts)
            
        except Exception as e:
            logger.error(f"Error formatting interview context: {e}", exc_info=True)
            return "Interview context unavailable due to formatting error."
    
    def _get_stage_guidance(self, stage: str) -> str:
        """Get stage-specific guidance for context injection."""
        guidance_map = {
            InterviewStage.INTRODUCTION.value: "Focus on building rapport and understanding candidate background. Keep brief, 2-3 exchanges before moving to technical questions.",
            InterviewStage.TECHNICAL_QUESTIONS.value: "Assess technical depth with progressive difficulty. Ask 3-4 questions before moving on.",
            InterviewStage.CODING_CHALLENGE.value: "Present coding challenge clearly if role requires coding. Use generate_coding_challenge_from_jd tool.",
            InterviewStage.CODING_CHALLENGE_WAITING.value: "Wait for candidate to submit their coding solution. Provide encouragement if needed.",
            InterviewStage.BEHAVIORAL_QUESTIONS.value: "Ask behavioral questions to assess soft skills and past experiences. 2-3 questions typically.",
            InterviewStage.FEEDBACK.value: "Provide detailed, constructive feedback. Use feedback tools for comprehensive evaluation.",
            InterviewStage.CONCLUSION.value: "Wrap up positively with clear next steps."
        }
        return guidance_map.get(stage, "")
    
    async def inject_initial_context(self, interview_state: InterviewState):
        """
        Inject initial interview context at session start.
        
        Args:
            interview_state: Initial interview state
        """
        context_content = self.format_interview_context(interview_state)
        
        # Handle both InterviewState objects and dict representations
        def get_attr(obj, key, default=""):
            if hasattr(obj, key):
                return getattr(obj, key)
            elif isinstance(obj, dict):
                return obj.get(key, default)
            else:
                return default
        
        context_update = ContextUpdate(
            type="initial",
            content=context_content,
            priority=100,  # Highest priority
            timestamp=datetime.now(),
            metadata={"stage": get_attr(interview_state, 'interview_stage', 'unknown')}
        )
        
        await self._queue_context_injection(context_update)
        logger.info("Queued initial context injection")
    
    async def inject_stage_transition(self, from_stage: str, to_stage: str, context: Dict[str, Any]):
        """
        Inject context for interview stage transitions.
        
        Args:
            from_stage: Previous interview stage
            to_stage: New interview stage
            context: Additional context data
        """
        try:
            transition_content = f"=== STAGE TRANSITION ===\nFrom: {from_stage}\nTo: {to_stage}\n"
            
            # Add stage-specific transition guidance
            stage_guidance = self._get_stage_guidance(to_stage)
            if stage_guidance:
                transition_content += f"New Stage Guidance: {stage_guidance}\n"
            
            # Add any additional context
            if context:
                if "candidate_name" in context and context["candidate_name"]:
                    transition_content += f"Candidate: {context['candidate_name']}\n"
                if "job_role" in context:
                    transition_content += f"Role: {context['job_role']}\n"
                if "requires_coding" in context:
                    transition_content += f"Coding Required: {context['requires_coding']}\n"
            
            context_update = ContextUpdate(
                type="stage_transition",
                content=transition_content,
                priority=90,
                timestamp=datetime.now(),
                metadata={"from_stage": from_stage, "to_stage": to_stage}
            )
            
            await self._queue_context_injection(context_update)
            
            # Notify callbacks
            for callback in self.stage_transition_callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(from_stage, to_stage, context)
                    else:
                        callback(from_stage, to_stage, context)
                except Exception as e:
                    logger.error(f"Error in stage transition callback: {e}", exc_info=True)
            
            logger.info(f"Queued stage transition injection: {from_stage} -> {to_stage}")
            
        except Exception as e:
            logger.error(f"Error injecting stage transition: {e}", exc_info=True)
    
    async def inject_tool_result(self, tool_name: str, tool_result: Dict[str, Any]):
        """
        Inject LangGraph tool results as context.
        
        Args:
            tool_name: Name of the tool that was executed
            tool_result: Result data from the tool
        """
        try:
            tool_content = f"=== TOOL RESULT ===\nTool: {tool_name}\n"
            
            # Format tool result based on tool type
            if tool_name == "generate_coding_challenge_from_jd":
                if "challenge" in tool_result:
                    challenge = tool_result["challenge"]
                    tool_content += f"Coding Challenge Generated:\n"
                    if "title" in challenge:
                        tool_content += f"Title: {challenge['title']}\n"
                    if "difficulty" in challenge:
                        tool_content += f"Difficulty: {challenge['difficulty']}\n"
                    if "problem_statement" in challenge:
                        # Truncate long problem statements
                        problem = challenge["problem_statement"]
                        if len(problem) > 300:
                            problem = problem[:300] + "..."
                        tool_content += f"Problem: {problem}\n"
            
            elif tool_name == "submit_code_for_generated_challenge":
                if "evaluation_summary" in tool_result:
                    tool_content += f"Code Evaluation: {tool_result['evaluation_summary']}\n"
                if "score" in tool_result:
                    tool_content += f"Score: {tool_result['score']}\n"
            
            else:
                # Generic tool result formatting
                if isinstance(tool_result, dict):
                    for key, value in tool_result.items():
                        if isinstance(value, str) and len(value) < 200:
                            tool_content += f"{key}: {value}\n"
                        elif isinstance(value, (int, float, bool)):
                            tool_content += f"{key}: {value}\n"
            
            context_update = ContextUpdate(
                type="tool_result",
                content=tool_content,
                priority=80,
                timestamp=datetime.now(),
                metadata={"tool_name": tool_name}
            )
            
            await self._queue_context_injection(context_update)
            logger.info(f"Queued tool result injection for: {tool_name}")
            
        except Exception as e:
            logger.error(f"Error injecting tool result: {e}", exc_info=True)
    
    async def update_session_context(self, session_metadata: Dict[str, Any]):
        """
        Update ongoing session context.
        
        Args:
            session_metadata: Updated session metadata
        """
        try:
            session_content = "=== SESSION UPDATE ===\n"
            
            # Add relevant session updates
            if "candidate_name" in session_metadata and session_metadata["candidate_name"]:
                session_content += f"Candidate Name: {session_metadata['candidate_name']}\n"
            
            if "interview_stage" in session_metadata:
                session_content += f"Current Stage: {session_metadata['interview_stage']}\n"
            
            if "message_count" in session_metadata:
                session_content += f"Messages: {session_metadata['message_count']}\n"
            
            context_update = ContextUpdate(
                type="session_update",
                content=session_content,
                priority=70,
                timestamp=datetime.now(),
                metadata=session_metadata
            )
            
            await self._queue_context_injection(context_update)
            logger.info("Queued session context update")
            
        except Exception as e:
            logger.error(f"Error updating session context: {e}", exc_info=True)
    
    async def _queue_context_injection(self, context_update: ContextUpdate):
        """
        Queue a context update for injection.
        
        Args:
            context_update: Context update to queue
        """
        self.context_queue.append(context_update)
        
        # Sort queue by priority (highest first)
        self.context_queue.sort(key=lambda x: x.priority, reverse=True)
        
        # Start injection task if not already running
        if not self.running:
            await self.start_injection_processing()
    
    async def start_injection_processing(self):
        """Start the context injection processing task."""
        if self.running:
            return
        
        self.running = True
        self.injection_task = asyncio.create_task(self._process_injection_queue())
        logger.info("Started context injection processing")
    
    async def stop_injection_processing(self):
        """Stop the context injection processing task."""
        self.running = False
        
        if self.injection_task and not self.injection_task.done():
            self.injection_task.cancel()
            try:
                await self.injection_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Stopped context injection processing")
    
    async def _process_injection_queue(self):
        """Process the context injection queue."""
        while self.running:
            try:
                if self.context_queue and self.gemini_adapter:
                    # Get highest priority context update
                    context_update = self.context_queue.pop(0)
                    
                    # Format for silent injection
                    silent_content = f"{SILENT_CONTEXT_PREFIX}\n{context_update.content}"
                    
                    # Inject silently into Gemini Live API
                    await self.gemini_adapter.inject_context({
                        "content": silent_content,
                        "type": context_update.type,
                        "timestamp": context_update.timestamp.isoformat()
                    }, silent=True)
                    
                    # Add to history
                    self.context_history.append(context_update)
                    
                    # Keep history size manageable
                    if len(self.context_history) > 50:
                        self.context_history = self.context_history[-30:]
                    
                    # Notify callbacks
                    for callback in self.context_injected_callbacks:
                        try:
                            if asyncio.iscoroutinefunction(callback):
                                await callback(context_update)
                            else:
                                callback(context_update)
                        except Exception as e:
                            logger.error(f"Error in context injected callback: {e}", exc_info=True)
                    
                    logger.debug(f"Injected context: {context_update.type}")
                    
                    # Delay between injections to avoid rate limits
                    await asyncio.sleep(CONTEXT_BATCH_DELAY)
                
                else:
                    # No context to inject, wait a bit
                    await asyncio.sleep(0.1)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing context injection queue: {e}", exc_info=True)
                await asyncio.sleep(1)  # Wait before retrying
    
    def add_context_injected_callback(self, callback: Callable):
        """Add callback for when context is injected."""
        self.context_injected_callbacks.append(callback)
    
    def add_stage_transition_callback(self, callback: Callable):
        """Add callback for stage transitions."""
        self.stage_transition_callbacks.append(callback)
    
    def get_context_history(self) -> List[ContextUpdate]:
        """Get the history of injected context updates."""
        return self.context_history.copy()
    
    def get_current_context_summary(self) -> Dict[str, Any]:
        """Get a summary of the current context state."""
        return {
            "queue_size": len(self.context_queue),
            "history_size": len(self.context_history),
            "running": self.running,
            "last_injection": self.context_history[-1].timestamp.isoformat() if self.context_history else None,
            "adapter_connected": self.gemini_adapter is not None
        }
    
    async def cleanup(self):
        """Clean up resources."""
        await self.stop_injection_processing()
        self.context_queue.clear()
        self.context_history.clear()
        self.context_injected_callbacks.clear()
        self.stage_transition_callbacks.clear()
        logger.info("ContextInjectionService cleaned up") 