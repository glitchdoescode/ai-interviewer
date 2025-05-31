"""
Core AI Interviewer implementation using LangGraph.
"""
import logging
import uuid
import re # Added for stage transition logic
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Union, Any, Tuple, Literal

import asyncio
from typing import Dict, List, Optional, Any, Literal, Union, Tuple
import os
import asyncio
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END, MessagesState
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.mongodb import MongoDBSaver
from langgraph.types import interrupt, Command
from langchain_core.messages import RemoveMessage
import json




from langchain.schema import AIMessage, BaseMessage, SystemMessage
from langgraph.graph import StateGraph, END


from ai_interviewer.utils.config import get_llm_config
from ai_interviewer.utils.gemini_live_utils import generate_response_stream, transcribe_audio_gemini
from ai_interviewer.utils.constants import (
    INTERVIEW_SYSTEM_PROMPT,
    CANDIDATE_NAME_KEY,
    SESSION_ID_KEY,
    USER_ID_KEY,
    INTERVIEW_STAGE_KEY,
    JOB_ROLE_KEY,
    REQUIRES_CODING_KEY,
    InterviewStage,
    DEFAULT_TEMPERATURE,
    DEFAULT_TOP_P,
    DEFAULT_MAX_TOKENS,
    ERROR_NO_MESSAGES,
    ERROR_EMPTY_RESPONSE
)

# Import tools
from ai_interviewer.tools.coding_tools import (
    start_coding_challenge,
    submit_code_for_challenge,
    get_coding_hint
)
from ai_interviewer.tools.pair_programming import (
    suggest_code_improvements,
    complete_code,
    review_code_section
)
from ai_interviewer.tools.question_tools import (
    generate_interview_question,
    analyze_candidate_response
)
from ai_interviewer.tools.problem_generation_tool import (
    generate_coding_challenge_from_jd,
    submit_code_for_generated_challenge,
    get_hint_for_generated_challenge
)

# Import custom modules
from ai_interviewer.utils.session_manager import SessionManager
from ai_interviewer.utils.memory_manager import InterviewMemoryManager
from ai_interviewer.utils.config import get_db_config, get_llm_config, log_config
from ai_interviewer.utils.transcript import extract_messages_from_transcript, safe_extract_content

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Interview stage tracking
class InterviewStage(Enum):
    """Enum for tracking the current stage of the interview."""
    INTRODUCTION = "introduction"  # Getting candidate's name and introductions
    TECHNICAL_QUESTIONS = "technical_questions"  # Technical questions phase
    CODING_CHALLENGE = "coding_challenge"  # Coding challenge phase
    CODING_CHALLENGE_WAITING = "coding_challenge_waiting" # New stage for human-in-the-loop
    FEEDBACK = "feedback"  # Providing feedback on performance
    CONCLUSION = "conclusion"  # Wrapping up the interview
    BEHAVIORAL_QUESTIONS = "behavioral_questions"  # Behavioral questions phase

# Define state keys to be used with MessagesState
STAGE_KEY = "interview_stage"  # Key for storing interview stage in the state
CANDIDATE_NAME_KEY = "candidate_name"  # Key for storing candidate name in the state
METADATA_KEY = "metadata"  # Key for storing all metadata in the state

# System prompt template
INTERVIEW_SYSTEM_PROMPT = """
You are {system_name}, an AI technical interviewer conducting a {job_role} interview for a {seniority_level} position.

Interview ID: {interview_id}
Candidate: {candidate_name}
Current stage: {current_stage}

Required skills: {required_skills}
Job description: {job_description}
Requires coding: {requires_coding}

CONVERSATION STYLE GUIDELINES:
1. Be warm, personable, and empathetic while maintaining professionalism
2. Use natural conversational transitions rather than formulaic responses
3. Address the candidate by name occasionally but naturally
4. Acknowledge and validate the candidate's feelings or concerns when expressed
5. Vary your response style and length to create a more dynamic conversation
6. Use appropriate conversational connectors (e.g., "That's interesting," "I see," "Thanks for sharing that")
7. Occasionally refer to yourself by name and your role (e.g., "I'm {system_name}, and I'll be conducting your interview for the {job_role} position today")

INTERVIEW APPROACH:
1. Assess the candidate's technical skills and experience level
2. Ask relevant technical questions based on the job requirements
3. Provide a coding challenge if appropriate for the position. Only suggest coding challenges if the "Requires coding" flag is set to "True". If set to "False", focus on conceptual questions instead.
4. Evaluate both technical knowledge and problem-solving approach
5. Give constructive feedback on responses when appropriate

CONTEXT MANAGEMENT:
If a conversation summary is provided below, use it to understand previous parts of the interview that are no longer in the recent messages.

{conversation_summary}

HANDLING SPECIAL SITUATIONS:
- When the candidate asks for clarification: Provide helpful context without giving away answers
- When the candidate struggles: Show patience and offer gentle prompts or hints
- When the candidate digresses: Acknowledge their point and guide them back to relevant topics
- When the candidate shares personal experiences: Show interest and connect it back to the role
- When the candidate asks about the company/role: Provide encouraging, realistic information

ADAPTING TO INTERVIEW STAGES:
- Introduction: Start by introducing yourself (as {system_name}) and clearly state that you are conducting the interview for the **{job_role}** position at the **{seniority_level}** level. Then, focus on building rapport and understanding the candidate's background. Keep this initial part brief, just 2-3 exchanges before moving to technical questions.
- Technical Questions: Assess depth of knowledge with progressive difficulty. Ask 3-4 technical questions before moving on. If the candidate explicitly requests to move to the coding challenge, and the role requires coding, you should honor this request even if you haven't asked 3-4 questions yet.
- Coding Challenge: IMPORTANT - When you decide to use the `generate_coding_challenge_from_jd` tool, your response should *only* contain the tool call. This means you must output a valid JSON object that represents the tool call, structured like this: `{{"name": "tool_name", "args": {{"arg1": "value1", ...}}, "id": "unique_tool_call_id"}}`. For the `generate_coding_challenge_from_jd` tool specifically, the JSON would be: `{{"name": "generate_coding_challenge_from_jd", "args": {{"job_description": "<full job description text>", "skills_required": ["Skill1", "Skill2"], "difficulty_level": "<level>"}}, "id": "call_xyz"}}`. Replace `<full job description text>` with the actual job description from your context, `["Skill1", "Skill2"]` with the actual list of skills, `<level>` with the chosen difficulty, and `"call_xyz"` with a unique ID for this specific tool call. Do not wrap this JSON in any other keys like "tool_code". Provide the `job_description` from your context, and ensure `skills_required` is a LIST of strings. `difficulty_level` is optional but can be "beginner", "intermediate", or "advanced".
- Behavioral Questions: Look for evidence of soft skills and experience. Ask 2-3 behavioral questions.
- Feedback: Be constructive, balanced, and specific
- Conclusion: End on a positive note with clear next steps

TOOLS USAGE:
- generate_coding_challenge_from_jd: When you reach the `coding_challenge` stage and need to generate a problem, invoke this tool. To do this, your *entire response* should be a single JSON object representing the tool call. The JSON should look like: `{{"name": "generate_coding_challenge_from_jd", "args": {{"job_description": "...full job description...", "skills_required": ["Python", "APIs"], "difficulty_level": "intermediate"}}, "id": "call_123"}}`. Ensure `skills_required` is a JSON list of strings. You MUST include a unique `id` field for each tool call.
- analyze_candidate_response: To use this tool, your response should be a JSON tool call: `{{"name": "analyze_candidate_response", "args": {{...arguments...}}, "id": "call_456"}}`.
- generate_interview_question: To use this tool, your response should be a JSON tool call: `{{"name": "generate_interview_question", "args": {{...arguments...}}, "id": "call_789"}}`.

If unsure how to respond to something unusual, stay professional and steer the conversation back to relevant technical topics.
"""

# Custom state that extends MessagesState to add interview-specific context
class InterviewState(MessagesState):
    """
    Custom state for the interview process that extends MessagesState to include
    interview-specific context that persists across the conversation.
    """
    # Candidate information
    candidate_name: str = ""
    
    # Job details
    job_role: str = ""
    seniority_level: str = ""
    required_skills: List[str] = []
    job_description: str = ""
    requires_coding: bool = True
    
    # Interview progress
    interview_stage: str = InterviewStage.INTRODUCTION.value
    
    # Session information
    session_id: str = ""
    user_id: str = ""
    
    # Context management
    conversation_summary: str = ""
    message_count: int = 0
    max_messages_before_summary: int = 20
    
    def __init__(self, 
                messages: Optional[List[BaseMessage]] = None,
                candidate_name: str = "",
                job_role: str = "",
                seniority_level: str = "",
                required_skills: Optional[List[str]] = None,
                job_description: str = "",
                requires_coding: bool = True,
                interview_stage: str = "",
                session_id: str = "",
                user_id: str = "",
                conversation_summary: str = "",
                message_count: int = 0,
                max_messages_before_summary: int = 20):
        """
        Initialize the InterviewState with the provided values.
        
        Args:
            messages: List of conversation messages
            candidate_name: Name of the candidate
            job_role: Job role for the interview
            seniority_level: Seniority level for the position
            required_skills: List of required skills
            job_description: Job description text
            requires_coding: Whether this role requires coding challenges
            interview_stage: Current interview stage
            session_id: Session identifier
            user_id: User identifier
            conversation_summary: Summary of earlier conversation parts
            message_count: Total message count for context management
            max_messages_before_summary: Threshold to trigger summarization
        """
        # Initialize MessagesState
        super().__init__(messages=messages or [])
        
        # Initialize the rest of the state
        self.candidate_name = candidate_name
        self.job_role = job_role
        self.seniority_level = seniority_level
        self.required_skills = required_skills or []
        self.job_description = job_description
        self.requires_coding = requires_coding
        self.interview_stage = interview_stage or InterviewStage.INTRODUCTION.value
        self.session_id = session_id
        self.user_id = user_id
        self.conversation_summary = conversation_summary
        self.message_count = message_count
        self.max_messages_before_summary = max_messages_before_summary
    
    # Add dictionary-style access for compatibility
    def __getitem__(self, key):
        if key == "messages":
            return self.messages
        elif key == "candidate_name":
            return self.candidate_name
        elif key == "job_role":
            return self.job_role
        elif key == "seniority_level":
            return self.seniority_level
        elif key == "required_skills":
            return self.required_skills
        elif key == "job_description":
            return self.job_description
        elif key == "requires_coding":
            return self.requires_coding
        elif key == "interview_stage":
            return self.interview_stage
        elif key == "session_id":
            return self.session_id
        elif key == "user_id":
            return self.user_id
        elif key == "conversation_summary":
            return self.conversation_summary
        elif key == "message_count":
            return self.message_count
        elif key == "max_messages_before_summary":
            return self.max_messages_before_summary
        else:
            raise KeyError(f"Key '{key}' not found in InterviewState")
    
    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

# Add safe_extract_content function before the AIInterviewer class definition

# Import for resume_interview method
import asyncio

def safe_extract_content(message: AIMessage) -> str:
    """
    Safely extract the content from an AI message.
    
    Args:
        message: AIMessage object
        
    Returns:
        Content string or default error message
    """
    try:
        return message.content or "I apologize, but I encountered an issue. Please try again."
    except Exception:
        return "I apologize, but I encountered an issue. Please try again."

class AIInterviewer:
    """Main class that encapsulates the AI Interviewer functionality."""
    
    def __init__(self, 
                use_mongodb: bool = True, 
                connection_uri: Optional[str] = None,
                job_role: str = "Software Engineering",
                seniority_level: str = "Mid-level",
                required_skills: List[str] = None,
                job_description: str = "",
                auto_migrate: bool = True,
                memory_manager_instance: Optional[InterviewMemoryManager] = None):
        """
        Initialize the AI Interviewer with the necessary components.
        
        Args:
            use_mongodb: Whether to use MongoDB for persistence
            connection_uri: Optional MongoDB connection URI
            job_role: Default job role for interviews
            seniority_level: Default seniority level
            required_skills: Default required skills
            job_description: Default job description
            auto_migrate: Whether to automatically migrate old tool call formats
            memory_manager_instance: Optional pre-initialized InterviewMemoryManager instance
        """
        log_config()
        
        # Store default job parameters
        self.job_role = job_role
        self.seniority_level = seniority_level
        self.required_skills = required_skills or ["Programming", "Problem-solving", "Communication"]
        self.job_description = job_description or f"A {seniority_level} {job_role} position requiring skills in {', '.join(self.required_skills or [])}"
        
        # Set up LLM and tools
        self._setup_tools()
        
        # Get LLM configuration
        llm_config = get_llm_config()
        
        # Initialize LLM with tools
        self.model = ChatGoogleGenerativeAI(
            model=llm_config["model"],
            temperature=llm_config["temperature"]
        ).bind_tools(self.tools)
        
        # Initialize a raw LLM for summarization tasks
        self.summarization_model = ChatGoogleGenerativeAI(
            model=llm_config["model"],
            temperature=0.1
        )
        
        # Set up persistence and session management
        db_config = get_db_config()
        self.use_mongodb = use_mongodb
        
        if memory_manager_instance:
            logger.info(f"Using provided InterviewMemoryManager instance: {memory_manager_instance}")
            self.memory_manager = memory_manager_instance
            # Ensure the provided instance is set up if it has async_setup
            if hasattr(self.memory_manager, 'async_setup') and not (hasattr(self.memory_manager, 'db') and self.memory_manager.db is not None):
                logger.info("Provided memory_manager_instance needs async_setup. Running it.")
                # This might be an issue if called outside an event loop context directly
                # For now, assume it's handled if called from lifespan
                # Consider a flag or state in memory_manager to know if it's already setup
                # For simplicity, we'll assume it's either fully ready or setup_ai_interviewer_async handles this call correctly.
                pass # The setup_memory_manager_async in server.py should have already run this.

        elif self.use_mongodb:
            # Initialize InterviewMemoryManager
            # Use connection_uri if provided, otherwise use db_config
            resolved_connection_uri = connection_uri or db_config["uri"]
            logger.info(f"Initializing Memory Manager with URI {resolved_connection_uri}")
            self.memory_manager = InterviewMemoryManager(
                connection_uri=resolved_connection_uri,
                db_name=db_config["database"],
                checkpoint_collection=db_config["sessions_collection"],
                store_collection=db_config["store_collection"],
                use_async=True  # AIInterviewer primarily uses async operations
            )
            # The async_setup for memory_manager is typically called by the server's lifespan manager.
            # If AIInterviewer is used standalone, it might need to handle this.
            # For now, we assume it's handled externally if self.memory_manager is created here.
            logger.info("MongoDB memory manager initialized. Ensure async_setup is called if used in async context.")
        else:
            self.memory_manager = None
            logger.info("MongoDB persistence is disabled. Using in-memory for some features.")

        # Initialize SessionManager (depends on memory_manager)
        if self.memory_manager:
            self.session_manager = SessionManager(
                connection_uri=self.memory_manager.connection_uri,
                database_name=self.memory_manager.db_name,
                collection_name=db_config["metadata_collection"] # Using the specific metadata collection name from config
            )
            self.store = self.memory_manager.get_store() # Get the store from memory_manager
            logger.info(f"SessionManager initialized with memory manager. Store type: {type(self.store)}")
            
            # Set up LangGraph checkpointer
            self.checkpointer = self.memory_manager.get_checkpointer()
            if self.checkpointer:
                 logger.info(f"Using MongoDB checkpointer: {type(self.checkpointer)}")
            else:
                logger.warning("Failed to get checkpointer from MongoDB memory_manager. Falling back to InMemorySaver.")
                self.checkpointer = InMemorySaver() # Fallback
        else:
            # Use in-memory persistence for checkpointer and no session/memory manager
            self.checkpointer = InMemorySaver()
            self.session_manager = None
            self.store = None # No persistent store
            logger.info("Using in-memory persistence for LangGraph checkpointer. Session and memory management disabled.")
        
        # Initialize workflow
        self.workflow = self._initialize_workflow()
        
        # Session tracking
        self.active_sessions = {}
    
    def _setup_tools(self):
        """Set up the tools for the interviewer."""
        # Define tools
        self.tools = [
            # Prioritize problem generation tools
            generate_coding_challenge_from_jd,
            submit_code_for_generated_challenge,
            get_hint_for_generated_challenge,
            
            # Include original tools for backward compatibility
            start_coding_challenge,
            submit_code_for_challenge,
            get_coding_hint,
            
            # Other tools
            suggest_code_improvements,
            complete_code,
            review_code_section,
            generate_interview_question,
            analyze_candidate_response
        ]
        for tool_instance in self.tools:
            logger.info(f"[AIInterviewer._setup_tools] Tool: {tool_instance.name}, Type: {type(tool_instance)}, Is async: {asyncio.iscoroutinefunction(getattr(tool_instance, 'func', tool_instance))}")
            if hasattr(tool_instance, 'description'):
                 logger.info(f"[AIInterviewer._setup_tools] Description for {tool_instance.name}: {tool_instance.description}")
    
    def _initialize_workflow(self) -> StateGraph:
        """
        Initialize the LangGraph workflow with the model and tools.
        
        Returns:
            StateGraph instance configured with the model and tools
        """
        logger.info("Initializing LangGraph workflow")
        
        # Use our custom InterviewState instead of MessagesState
        workflow = StateGraph(InterviewState)
        
        # Initialize the tool node first
        self.tool_node = ToolNode(self.tools)
        
        # Define custom wrapper for the tool node to ensure proper state handling
        async def tools_node(state: Union[Dict, InterviewState]) -> Union[Dict, InterviewState]: # MODIFIED to async def
            """
            Wrapper for ToolNode that ensures proper state handling.
            
            Args:
                state: Current state (dict or InterviewState)
                
            Returns:
                Updated state with tool results
            """
            try:
                # Check if state is a dictionary or InterviewState object
                if isinstance(state, dict):
                    # Extract messages from dictionary
                    messages = state.get("messages", [])
                    candidate_name = state.get("candidate_name", "")
                    interview_stage = state.get("interview_stage", InterviewStage.INTRODUCTION.value)
                    job_role = state.get("job_role", "")
                    requires_coding = state.get("requires_coding", True)
                    
                    # Get additional info for coding challenge generation
                    seniority_level = state.get("seniority_level", "Mid-level")
                    required_skills = state.get("required_skills", ["Programming", "Problem-solving"])
                    job_description = state.get("job_description", f"A {seniority_level} {job_role} position")
                    
                    # Special handling for coding challenge stage
                    last_msg = messages[-1] if messages else None
                    if (interview_stage == InterviewStage.CODING_CHALLENGE.value and 
                        isinstance(last_msg, AIMessage) and 
                        (not hasattr(last_msg, 'tool_calls') or 
                         not any(call.get('name') in ['start_coding_challenge', 'generate_coding_challenge_from_jd'] 
                                for call in (last_msg.tool_calls or [])))):
                        
                        # No coding challenge tool was called, but we're in the coding stage
                        # Let's add a special message to force the tool usage
                        logger.info("In coding_challenge stage but no tool used - forcing generate_coding_challenge_from_jd tool")
                        
                        # Create a fake tool call for generate_coding_challenge_from_jd
                        if requires_coding:
                            difficulty_level = "intermediate" 
                            if seniority_level.lower() == "junior":
                                difficulty_level = "beginner"
                            elif seniority_level.lower() in ["senior", "lead", "principal"]:
                                difficulty_level = "advanced"
                                
                            fake_tool_call = {
                                "name": "generate_coding_challenge_from_jd",
                                "args": {
                                    "job_description": job_description,
                                    "skills_required": required_skills,
                                    "difficulty_level": difficulty_level
                                },
                                "id": f"tool_{uuid.uuid4().hex[:8]}"
                            }
                            
                            # If the last message is an AI message, add the tool call to it
                            if isinstance(last_msg, AIMessage):
                                if not hasattr(last_msg, 'tool_calls'):
                                    last_msg.tool_calls = []
                                last_msg.tool_calls.append(fake_tool_call)
                                messages[-1] = last_msg
                    
                    # Ensure tool_calls are in the correct format before executing
                    # This helps with backward compatibility
                    if messages and isinstance(messages[-1], AIMessage) and hasattr(messages[-1], 'tool_calls'):
                        self._normalize_tool_calls(messages[-1].tool_calls)
                    
                    logger.info(f"[TOOLS_NODE] About to invoke self.tool_node with messages: {messages}") # ADDED LOG
                    # Log the specific tool calls being processed if they exist
                    if messages and isinstance(messages[-1], AIMessage) and hasattr(messages[-1], 'tool_calls') and messages[-1].tool_calls:
                        logger.info(f"[TOOLS_NODE] Last AI message has tool_calls: {messages[-1].tool_calls}")
                        for tc in messages[-1].tool_calls:
                            logger.info(f"[TOOLS_NODE] Processing tool_call: Name: {tc.get('name')}, Args: {tc.get('args')}, ID: {tc.get('id')}")
                    else:
                        logger.info("[TOOLS_NODE] Last AI message has no tool_calls or tool_calls list is empty.")

                    # Execute tools using the ToolNode with messages
                    tool_result = await self.tool_node.ainvoke({"messages": messages}) # MODIFIED to await self.tool_node.ainvoke
                    logger.info(f"[TOOLS_NODE] self.tool_node.ainvoke completed. Result: {tool_result}") # ADDED LOG
                    
                    # Create a new dictionary with updated values
                    updated_state = dict(state)
                    if "messages" in tool_result:
                        updated_state["messages"] = messages + tool_result["messages"]
                    
                    # Check for extracted name in new messages
                    if not candidate_name and "messages" in tool_result:
                        combined_messages = messages + tool_result.get("messages", [])
                        name_match = self._extract_candidate_name(combined_messages)
                        if name_match:
                            updated_state["candidate_name"] = name_match
                            logger.info(f"Extracted candidate name during tool call: {name_match}")
                    
                    # Update message count for context management
                    updated_state["message_count"] = state.get("message_count", 0) + len(tool_result.get("messages", []))
                    
                    return updated_state
                else:
                    # Extract messages from InterviewState
                    messages = state.messages
                    candidate_name = state.candidate_name
                    interview_stage = state.interview_stage
                    job_role = state.job_role
                    requires_coding = state.requires_coding
                    
                    # Get additional info for coding challenge generation
                    seniority_level = state.seniority_level
                    required_skills = state.required_skills
                    job_description = state.job_description
                    
                    # Special handling for coding challenge stage
                    last_msg = messages[-1] if messages else None
                    if (interview_stage == InterviewStage.CODING_CHALLENGE.value and 
                        isinstance(last_msg, AIMessage) and 
                        (not hasattr(last_msg, 'tool_calls') or 
                         not any(call.get('name') in ['start_coding_challenge', 'generate_coding_challenge_from_jd'] 
                                for call in (last_msg.tool_calls or [])))):
                        
                        # No coding challenge tool was called, but we're in the coding stage
                        # Let's add a special message to force the tool usage
                        logger.info("In coding_challenge stage but no tool used - forcing generate_coding_challenge_from_jd tool")
                        
                        # Create a fake tool call for generate_coding_challenge_from_jd
                        if requires_coding:
                            difficulty_level = "intermediate" 
                            if seniority_level.lower() == "junior":
                                difficulty_level = "beginner"
                            elif seniority_level.lower() in ["senior", "lead", "principal"]:
                                difficulty_level = "advanced"
                                
                            fake_tool_call = {
                                "name": "generate_coding_challenge_from_jd",
                                "args": {
                                    "job_description": job_description,
                                    "skills_required": required_skills,
                                    "difficulty_level": difficulty_level
                                },
                                "id": f"tool_{uuid.uuid4().hex[:8]}"
                            }
                            
                            # If the last message is an AI message, add the tool call to it
                            if isinstance(last_msg, AIMessage):
                                if not hasattr(last_msg, 'tool_calls'):
                                    last_msg.tool_calls = []
                                last_msg.tool_calls.append(fake_tool_call)
                                messages[-1] = last_msg
                    
                    # Ensure tool_calls are in the correct format before executing
                    # This helps with backward compatibility
                    if messages and isinstance(messages[-1], AIMessage) and hasattr(messages[-1], 'tool_calls'):
                        self._normalize_tool_calls(messages[-1].tool_calls)
                    
                    logger.info(f"[TOOLS_NODE] About to invoke self.tool_node with messages (InterviewState path): {state.messages}") # ADDED LOG
                    # Log the specific tool calls being processed if they exist (InterviewState path)
                    if state.messages and isinstance(state.messages[-1], AIMessage) and hasattr(state.messages[-1], 'tool_calls') and state.messages[-1].tool_calls:
                        logger.info(f"[TOOLS_NODE] (InterviewState path) Last AI message has tool_calls: {state.messages[-1].tool_calls}")
                        for tc in state.messages[-1].tool_calls:
                            logger.info(f"[TOOLS_NODE] (InterviewState path) Processing tool_call: Name: {tc.get('name')}, Args: {tc.get('args')}, ID: {tc.get('id')}")
                    else:
                        logger.info("[TOOLS_NODE] (InterviewState path) Last AI message has no tool_calls or tool_calls list is empty.")
                        
                    # Execute tools using the ToolNode with messages
                    tool_result = await self.tool_node.ainvoke({"messages": messages}) # MODIFIED to await self.tool_node.ainvoke
                    logger.info(f"[TOOLS_NODE] self.tool_node.ainvoke completed (InterviewState path). Result: {tool_result}") # ADDED LOG
                    
                    # Get updated messages
                    updated_messages = state.messages + tool_result.get("messages", [])
                    
                    # Check for extracted name in new messages
                    if not candidate_name and "messages" in tool_result:
                        name_match = self._extract_candidate_name(updated_messages)
                        if name_match:
                            candidate_name = name_match
                            logger.info(f"Extracted candidate name during tool call: {name_match}")
                    
                    # Update message count
                    new_message_count = state.message_count + len(tool_result.get("messages", []))
                    
                    # Create a new InterviewState with updated values
                    return InterviewState(
                        messages=updated_messages,
                        candidate_name=candidate_name,
                        job_role=state.job_role,
                        seniority_level=state.seniority_level,
                        required_skills=state.required_skills,
                        job_description=state.job_description,
                        requires_coding=state.requires_coding,
                        interview_stage=state.interview_stage,
                        session_id=state.session_id,
                        user_id=state.user_id,
                        conversation_summary=state.conversation_summary,
                        message_count=new_message_count,
                        max_messages_before_summary=state.max_messages_before_summary
                    )
            except Exception as e:
                logger.error(f"Error in tools_node: {e}")
                # Return original state on error
                return state
        
        # Define context management node
        def manage_context(state: Union[Dict, InterviewState]) -> Union[Dict, InterviewState]:
            """
            Manages conversation context by summarizing older messages when needed.
            
            Args:
                state: Current state with messages
                
            Returns:
                Updated state with managed context
            """
            try:
                # Extract values from state based on type
                if isinstance(state, dict):
                    messages = state.get("messages", [])
                    message_count = state.get("message_count", 0)
                    max_messages = state.get("max_messages_before_summary", 20)
                    current_summary = state.get("conversation_summary", "")
                    session_id = state.get("session_id", "")
                else:
                    messages = state.messages
                    message_count = state.message_count
                    max_messages = state.max_messages_before_summary
                    current_summary = state.conversation_summary
                    session_id = state.session_id
                
                # Check if we need to summarize
                if len(messages) <= max_messages:
                    # No need to summarize yet
                    if isinstance(state, dict):
                        return state
                    else:
                        return state
                
                # We need to summarize older portions of the conversation
                messages_to_keep = max_messages // 2  # Keep half of the max messages
                messages_to_summarize = messages[:-messages_to_keep]
                
                # First, extract structured insights from the conversation
                # These insights will be preserved even as we reduce the conversation history
                current_insights = None
                
                # Try to get current insights from session metadata if available
                if session_id and self.session_manager:
                    session = self.session_manager.get_session(session_id)
                    if session and "metadata" in session:
                        metadata = session.get("metadata", {})
                        current_insights = metadata.get("interview_insights", None)
                
                # Extract insights from all messages, updating current insights
                insights = self._extract_interview_insights(messages, current_insights)
                
                # If we have a session manager and session ID, update the insights in metadata
                if session_id and self.session_manager:
                    try:
                        session = self.session_manager.get_session(session_id)
                        if session and "metadata" in session:
                            metadata = session.get("metadata", {})
                            metadata["interview_insights"] = insights
                            self.session_manager.update_session_metadata(session_id, metadata)
                            logger.info(f"Updated interview insights in session metadata for session {session_id}")
                    except Exception as e:
                        logger.error(f"Failed to update interview insights in session metadata: {e}")
                
                # Now generate the conversation summary
                # Include insights in the prompt to assist with better summarization
                insights_text = ""
                if insights and "candidate_details" in insights:
                    details = insights["candidate_details"]
                    skills = insights.get("key_skills", [])
                    experiences = insights.get("notable_experiences", [])
                    
                    insights_text = "CANDIDATE INSIGHTS EXTRACTED SO FAR:\n"
                    
                    if details.get("name"):
                        insights_text += f"Name: {details['name']}\n"
                    
                    if details.get("current_role"):
                        insights_text += f"Current Role: {details['current_role']}\n"
                    
                    if details.get("years_of_experience"):
                        insights_text += f"Experience: {details['years_of_experience']}\n"
                    
                    if skills:
                        insights_text += f"Key Skills: {', '.join(skills[:10])}\n"
                    
                    if experiences:
                        insights_text += f"Notable Experiences: {'; '.join(experiences[:3])}\n"
                    
                    coding = insights.get("coding_ability", {})
                    if coding.get("languages"):
                        insights_text += f"Coding Languages: {', '.join(coding['languages'])}\n"
                
                # Prompt to generate summary
                if current_summary:
                    summary_prompt = [
                        SystemMessage(content=f"""You are a helpful assistant that summarizes technical interview conversations while retaining all key information.
                        
                        Below is an existing summary, extracted candidate insights, and new conversation parts to integrate.
                        Create a comprehensive summary that includes all important details about the candidate, their skills,
                        experiences, and responses to interview questions.
                        
                        Focus on preserving technical details, specific examples, and insights about the candidate's abilities
                        and experiences. Be concise but thorough, ensuring no important technical details are lost.
                        """),
                        HumanMessage(content=f"EXISTING SUMMARY:\n{current_summary}\n\n{insights_text}\n\nNEW CONVERSATION TO INTEGRATE:\n" + "\n".join([f"{m.type}: {m.content}" for m in messages_to_summarize if hasattr(m, 'content')]))
                    ]
                else:
                    summary_prompt = [
                        SystemMessage(content=f"""You are a helpful assistant that summarizes technical interview conversations while retaining all key information.
                        
                        Create a comprehensive summary of this interview conversation that includes all important details about
                        the candidate, their skills, experiences, and responses to interview questions.
                        
                        Focus on preserving technical details, specific examples, and insights about the candidate's abilities
                        and experiences. Be concise but thorough, ensuring no important technical details are lost.
                        """),
                        HumanMessage(content=f"{insights_text}\n\nCONVERSATION TO SUMMARIZE:\n" + "\n".join([f"{m.type}: {m.content}" for m in messages_to_summarize if hasattr(m, 'content')]))
                    ]
                
                # Generate the summary
                summary_response = self.summarization_model.invoke(summary_prompt)
                new_summary = summary_response.content if hasattr(summary_response, 'content') else ""
                
                # Create list of messages to remove from state
                messages_to_remove = [RemoveMessage(id=m.id) for m in messages_to_summarize]
                
                # Return the appropriate state type based on input
                if isinstance(state, dict):
                    updated_state = dict(state)
                    updated_state["conversation_summary"] = new_summary
                    updated_state["messages"] = messages_to_remove + messages[-messages_to_keep:]
                    updated_state["message_count"] = message_count - len(messages_to_summarize) + 1  # +1 for the summary itself
                    return updated_state
                else:
                    # Get the messages to keep
                    kept_messages = messages[-messages_to_keep:]
                    
                    # Create new state with updated values
                    return InterviewState(
                        messages=messages_to_remove + kept_messages,
                        candidate_name=state.candidate_name,
                        job_role=state.job_role,
                        seniority_level=state.seniority_level,
                        required_skills=state.required_skills,
                        job_description=state.job_description,
                        interview_stage=state.interview_stage,
                        session_id=state.session_id,
                        user_id=state.user_id,
                        conversation_summary=new_summary,
                        message_count=state.message_count - len(messages_to_summarize) + 1,  # +1 for the summary
                        max_messages_before_summary=state.max_messages_before_summary
                    )
            except Exception as e:
                logger.error(f"Error in manage_context: {e}")
                # Return original state on error
                return state
        
        # Define nodes
        workflow.add_node("model", self.call_model)
        workflow.add_node("tools", tools_node)
        workflow.add_node("manage_context", manage_context)
        
        # Define edges with context management
        workflow.add_conditional_edges(
            "model",
            self.should_continue,
            {
                "tools": "tools",
                "manage_context": "manage_context",
                "end": END
            }
        )
        
        # Add edge from tools to context management
        workflow.add_edge("tools", "manage_context")
        
        # Add edge from context management to model or end
        # workflow.add_conditional_edges(
        #     "manage_context",
        #     lambda state: "model" if self.should_continue(state) == "tools" else "end", # Original problematic line
        #     {
        #         "model": "model",
        #         "end": END
        #     }
        # )
        # Always go from manage_context back to model so the model can process tool outputs or summarize results
        workflow.add_edge("manage_context", "model")
        
        # Define starting node
        workflow.set_entry_point("model")
        
        # Compile workflow
        logger.info("Compiling workflow")
        compiled_workflow = workflow.compile(checkpointer=self.checkpointer)
        
        return compiled_workflow
        
    @staticmethod
    def should_continue(state: Union[Dict, InterviewState]) -> Literal["tools", "manage_context", "end"]:
        """
        Determine whether to continue to tools, manage context, or end the workflow.
        
        Args:
            state: Current state with messages (dict or InterviewState)
            
        Returns:
            Next node to execute ("tools", "manage_context", or "end")
        """
        # Get the most recent assistant message
        # Check if state is a dictionary or MessagesState object
        if isinstance(state, dict):
            if "messages" not in state or not state["messages"]:
                # No messages yet
                return "end"
            messages = state["messages"]
            # message_count = state.get("message_count", 0) # Not used in this function's logic directly
            # max_messages = state.get("max_messages_before_summary", 20) # Not used
            interview_stage = state.get("interview_stage", "introduction")
        else:
            # Assume it's a MessagesState or InterviewState object
            if not hasattr(state, "messages") or not state.messages:
                # No messages yet
                return "end"
            messages = state.messages
            interview_stage = getattr(state, "interview_stage", "introduction")
        
        last_message = messages[-1] if messages else None

        # If the absolute last message is a ToolMessage, a tool just ran. Model needs to process this.
        if isinstance(last_message, BaseMessage) and last_message.type == "tool": # Langchain ToolMessage type
            logger.info("[should_continue] Last message is a ToolMessage. Routing to manage_context (then model) to process tool output.")
            return "manage_context" 
        
        last_ai_message = None
        for i in range(len(messages) -1, -1, -1):
            if isinstance(messages[i], AIMessage):
                last_ai_message = messages[i]
                break
        
        if not last_ai_message:
            logger.info("[should_continue] No AI message found and last message wasn't a ToolMessage. Ending turn.")
            return "end" 

        # If the AI's last message has any tool calls, route to tools.
        # This takes precedence over stage-specific logic if the AI is actively trying to use a tool.
        if hasattr(last_ai_message, "tool_calls") and last_ai_message.tool_calls:
            logger.info(f"[should_continue] AI message has tool_calls: {last_ai_message.tool_calls}. Routing to tools.")
            return "tools"

        # Specific stage logic if no tool calls are pending from the last AI message
        if interview_stage == InterviewStage.CODING_CHALLENGE.value:
            # If in coding challenge stage AND the AI is not trying to call a tool (checked above),
            # it means the AI is likely presenting the problem or waiting for the user.
            # The AI's turn should end here. The frontend will then show the coding panel.
            # The stage should transition to CODING_CHALLENGE_WAITING after the AI presents the problem.
            logger.info("[should_continue] In CODING_CHALLENGE stage, AI has no active tool calls. Ending AI turn to present problem.")
            return "end"
        elif interview_stage == InterviewStage.CODING_CHALLENGE_WAITING.value:
            # If the AI is waiting for the user to submit code, its turn should always end.
            logger.info("[should_continue] In CODING_CHALLENGE_WAITING stage. Ending AI turn, awaiting user code submission.")
            return "end"
            
        # Default for other stages if no tool calls from AI: end the turn.
        logger.info(f"[should_continue] No tool calls in last AI message and not in a special waiting stage (current_stage: {interview_stage}). Ending turn.")
        return "end"
    
    async def call_model(self, state: Union[Dict, InterviewState]) -> Union[Dict, InterviewState]:
        """Call the LLM model to generate a response based on the current state."""
        logger.info(f"[CORE] call_model invoked. Initial state interview_stage: {state.get('interview_stage')}, candidate_name: {state.get('candidate_name')}") # Added log
        messages = []  # Initialize messages to an empty list for safety in except block
        try:
            # Extract messages and context from state
            messages = state.get("messages", [])
            if not messages:
                raise ValueError(ERROR_NO_MESSAGES)

            # Check if the last message contains audio data
            last_message = messages[-1] if messages else None
            audio_data = None
            if last_message and hasattr(last_message, 'content') and isinstance(last_message.content, dict):
                audio_data = last_message.content.get('audio_data')
                if audio_data:
                    # Transcribe audio using Gemini
                    transcription = await transcribe_audio_gemini(audio_data)
                    if transcription:
                        # Replace audio message with transcription
                        messages[-1] = HumanMessage(content=transcription)
                    else:
                        raise ValueError("Failed to transcribe audio")

            # Extract context information
            candidate_name = state.get("candidate_name", "")
            job_role = state.get("job_role", self.job_role)
            seniority_level = state.get("seniority_level", self.seniority_level)
            required_skills = state.get("required_skills", self.required_skills)
            job_description = state.get("job_description", self.job_description)
            interview_stage = state.get("interview_stage", InterviewStage.INTRODUCTION.value)
            session_id = state.get("session_id", "")
            conversation_summary = state.get("conversation_summary", "")
            requires_coding = state.get("requires_coding", True)

            logger.info(f"[CORE] call_model: Formatting system prompt with job_role='{job_role}', seniority_level='{seniority_level}', system_name='{get_llm_config()['system_name']}'")

            # Create system prompt with context
            system_prompt = INTERVIEW_SYSTEM_PROMPT.format(
                system_name=get_llm_config()["system_name"],
                candidate_name=candidate_name or "[Not provided yet]",
                interview_id=session_id,
                current_stage=interview_stage,
                job_role=job_role,
                seniority_level=seniority_level,
                required_skills=", ".join(required_skills) if isinstance(required_skills, list) else str(required_skills),
                job_description=job_description,
                requires_coding=requires_coding,
                conversation_summary=conversation_summary if conversation_summary else "No summary available yet."
            )
            
            # Add extra instructions for specific stages
            if interview_stage == InterviewStage.CODING_CHALLENGE.value:
                # Check if the last message is a ToolMessage (output from generate_coding_challenge_from_jd)
                last_message_is_tool_output = isinstance(messages[-1], BaseMessage) and messages[-1].type == "tool"
                
                if last_message_is_tool_output:
                    system_prompt += "\n\nIMPORTANT: You are in the CODING_CHALLENGE stage. A coding challenge has just been generated for you (it's in the last ToolMessage in the history). Your task is to present this coding challenge to the candidate. Introduce it clearly, explain what is expected, and provide the problem statement and any other relevant details from the tool's output. Do NOT try to generate another challenge or call the tool again."
                else:
                    # This case is when AI is deciding to initiate the challenge
                    system_prompt += "\n\nIMPORTANT: You are now in the CODING_CHALLENGE stage. You MUST use the generate_coding_challenge_from_jd tool to generate a coding challenge for the candidate. Your *entire response* must be the JSON tool call for `generate_coding_challenge_from_jd`. DO NOT create your own coding challenge description or add any conversational text."
            elif interview_stage == InterviewStage.TECHNICAL_QUESTIONS.value:
                system_prompt += "\n\nIMPORTANT: You are now in the TECHNICAL_QUESTIONS stage. Ask relevant technical questions based on the required skills and job description. Use the generate_interview_question tool if needed."
            elif interview_stage == InterviewStage.BEHAVIORAL_QUESTIONS.value:
                system_prompt += "\n\nIMPORTANT: You are now in the BEHAVIORAL_QUESTIONS stage. Ask behavioral questions to assess soft skills and past experiences relevant to the role."
            
            # Build the full prompt with system message and conversation history
            prompt_parts = [f"System: {system_prompt}"]
            for msg in messages:
                role = "Assistant" if isinstance(msg, AIMessage) else "User"
                content = safe_extract_content(msg) if isinstance(msg, AIMessage) else msg.content
                prompt_parts.append(f"{role}: {content}")
            
            full_prompt = "\n".join(prompt_parts)
            
            # Get response using Gemini with configured parameters
            response_text = ""
            async for chunk in generate_response_stream(
                prompt=full_prompt,
                temperature=DEFAULT_TEMPERATURE,
                max_tokens=DEFAULT_MAX_TOKENS
            ):
                response_text += chunk
            
            if not response_text.strip():
                raise ValueError(ERROR_EMPTY_RESPONSE)
            
            # Create AIMessage from response
            ai_message = AIMessage(content=response_text)

            # Attempt to parse content as a tool call if it looks like JSON
            parsed_tool_call_data = None
            try:
                # First, try to find and extract content within ```json ... ``` fences
                json_block_match = re.search(r"```json\s*(.*?)\s*```", response_text, re.DOTALL)
                text_to_parse = ""

                if json_block_match:
                    text_to_parse = json_block_match.group(1).strip()
                    logger.debug(f"Extracted JSON block from markdown fences: '{text_to_parse[:100]}...'")
                else:
                    # If no ```json ... ```, try to see if the entire response is just ``` ... ```
                    # This is less specific but a fallback.
                    generic_block_match = re.search(r"```\s*(.*?)\s*```", response_text, re.DOTALL)
                    if generic_block_match:
                        text_to_parse = generic_block_match.group(1).strip()
                        logger.debug(f"Extracted content from generic markdown fences: '{text_to_parse[:100]}...'")
                    else:
                        # If no fences found, assume the entire response_text might be raw JSON
                        text_to_parse = response_text.strip()
                        logger.debug(f"No markdown fences found, attempting to parse entire response_text: '{text_to_parse[:100]}...'")
                
                if text_to_parse: # Proceed only if we have something to parse
                    parsed_tool_call_data = json.loads(text_to_parse)
                else:
                    logger.debug("After attempting to strip fences, no text remains to parse.")

                if parsed_tool_call_data:
                    if isinstance(parsed_tool_call_data, dict) and \
                       "name" in parsed_tool_call_data and \
                       "args" in parsed_tool_call_data and \
                       "id" in parsed_tool_call_data:
                        logger.info(f"Detected single tool call JSON: {parsed_tool_call_data.get('name')}")
                        ai_message.tool_calls = [parsed_tool_call_data]
                    elif isinstance(parsed_tool_call_data, list):
                        processed_tool_calls = []
                        all_are_valid_tool_calls = True
                        for item in parsed_tool_call_data:
                            if isinstance(item, dict) and \
                               "name" in item and \
                               "args" in item and \
                               "id" in item:
                                processed_tool_calls.append(item)
                            else:
                                all_are_valid_tool_calls = False
                                break 
                        if all_are_valid_tool_calls and processed_tool_calls:
                            logger.info(f"Detected list of tool call JSONs. Count: {len(processed_tool_calls)}")
                            ai_message.tool_calls = processed_tool_calls
                        else:
                            logger.debug(f"Parsed JSON list did not conform to tool call structure. Data: {parsed_tool_call_data}")
                    else:
                        logger.debug(f"Parsed JSON did not conform to expected tool call structure. Data: {parsed_tool_call_data}")
            except (json.JSONDecodeError, TypeError) as e:
                logger.debug(f"AI message content not a direct JSON tool call (or parsing error: {e}). Content: '{response_text[:100]}...'")
                # ai_message.tool_calls will remain empty or its default value (None or empty list)
            
            logger.info(f"[call_model] After JSON parsing, ai_message.tool_calls: {ai_message.tool_calls}")

            # Generate audio response using Gemini TTS if input was audio
            if audio_data:  # Only generate audio if input was audio
                try:
                    # Initialize VoiceHandler (does not require API key directly if utils handle it)
                    voice_handler = VoiceHandler()
                    # The voice parameter in speak will be used by synthesize_speech_gemini
                    # It can be overridden by gemini_live_config if set there.
                    synthesized_audio_bytes = await voice_handler.speak(
                        text=response_text,
                        voice="Aoede", # Default voice, can be configured in gemini_live_config
                        play_audio=False, # Do not play audio here, server will handle it
                        output_file=None  # No need to save to file here
                    )
                    if synthesized_audio_bytes:
                        # Attach the audio data directly to the AIMessage
                        ai_message.additional_kwargs['audio_data'] = synthesized_audio_bytes
                        logger.info("Successfully attached synthesized audio to AIMessage")
                    else:
                        logger.warning("TTS synthesis returned no audio data.")
                except Exception as e:
                    logger.error(f"Gemini TTS error in call_model: {str(e)}", exc_info=True)
                    # Continue without audio if TTS fails
            
            # Update interview stage if needed
            current_stage_val = state.get("interview_stage", InterviewStage.INTRODUCTION.value)
            new_stage = self._determine_interview_stage(messages, ai_message, current_stage_val)
            
            # Update state
            state["messages"] = messages + [ai_message]
            state["interview_stage"] = new_stage
            
            # Log stage transition if it occurred
            if new_stage != current_stage_val:
                logger.info(f"Interview stage transitioned from {current_stage_val} to {new_stage}")
            
            # Update message count
            state["message_count"] = state.get("message_count", 0) + 1
            
            return state
            
        except Exception as e:
            logger.error(f"Error in call_model: {str(e)}", exc_info=True)
            # Return a graceful error message
            error_message = AIMessage(content="I apologize, but I encountered an error. Could you please rephrase your question?")
            # Ensure state[\"messages\"] is accessible and append error_message
            if isinstance(state, dict):
                if "messages" not in state or not isinstance(state["messages"], list):
                    state["messages"] = [] # Initialize if not present or not a list
                state["messages"].append(error_message)
            # If state is an InterviewState object, it should inherently handle messages
            elif hasattr(state, 'messages') and isinstance(state.messages, list):
                 state.messages.append(error_message)
            # Fallback if state is unexpected, though less likely with type hints
            else:
                return {"messages": [error_message]} # Or handle as appropriate

            return state
    
    def _detect_digression(self, user_message: str, messages: List[BaseMessage], current_stage: str) -> bool:
        """
        Detect if the user message is digressing from the interview context.
        
        Args:
            user_message: The user's message
            messages: Previous messages in the conversation
            current_stage: Current interview stage
            
        Returns:
            Boolean indicating if the message appears to be a digression
        """
        # Ignore digressions during introduction - people are just getting to know each other
        if current_stage == InterviewStage.INTRODUCTION.value:
            return False
            
        # If we have few messages, don't worry about digressions yet
        if len(messages) < 4:
            return False
            
        # Common interview-related terms that indicate the message is on-topic
        interview_terms = [
            "experience", "project", "skill", "work", "challenge", "problem", "solution",
            "develop", "implement", "design", "code", "algorithm", "data", "system",
            "architecture", "test", "debug", "optimize", "improve", "performance",
            "team", "collaborate", "communicate", "learn", "technology", "framework",
            "language", "database", "frontend", "backend", "api", "cloud", "devops"
        ]
        
        # Personal context digressions
        personal_digression = [
            "family", "kids", "child", "vacation", "hobby", "weather", "traffic",
            "lunch", "dinner", "breakfast", "weekend", "movie", "show", "music",
            "sick", "illness", "sorry for", "apologies for", "excuse"
        ]
        
        # Meta-interview digressions 
        meta_interview = [
            "interview process", "next steps", "salary", "compensation", "benefits",
            "work hours", "remote work", "location", "when will I hear back",
            "how many rounds", "dress code", "company culture", "team size"
        ]
        
        # Lower-case the message for comparison
        message_lower = user_message.lower()
        
        # Check for job-related content - this is expected and not a digression
        has_interview_terms = any(term in message_lower for term in interview_terms)
        
        
        # Check for personal digressions
        has_personal_digression = any(term in message_lower for term in personal_digression)
        
        # Check for meta-interview questions
        has_meta_interview = any(term in message_lower for term in meta_interview)
        
        # Analyze message length - very short responses during technical questions 
        # might indicate lack of engagement
        is_very_short = len(message_lower.split()) < 5 and current_stage == InterviewStage.TECHNICAL_QUESTIONS.value
        
        # Get the last AI message to check context
        last_ai_message = next((m.content.lower() for m in reversed(messages) 
                               if isinstance(m, AIMessage) and hasattr(m, 'content')), "")
        
        # Check if the AI asked a question that the candidate isn't answering
        ai_asked_question = any(q in last_ai_message for q in ["?", "explain", "describe", "tell me", "how would you"])
        
        # Only consider it a digression if it lacks interview terms AND has either
        # personal digression markers or meta-interview questions
        is_off_topic = (not has_interview_terms and (has_personal_digression or has_meta_interview))
        
        # Also consider it a digression if it's very short and doesn't address a question
        is_non_responsive = is_very_short and ai_asked_question and not has_interview_terms
        
        return is_off_topic or is_non_responsive

    async def run_interview(self, user_id: str, user_message: str, session_id: Optional[str] = None, 
                           job_role: Optional[str] = None, seniority_level: Optional[str] = None, 
                           required_skills: Optional[List[str]] = None, job_description: Optional[str] = None,
                           requires_coding: Optional[bool] = None, handle_digression: bool = True) -> Tuple[str, str]:
        """
        Run an interview session with the given user message.
        
        Args:
            user_id: User identifier
            user_message: User's message text
            session_id: Optional session ID for continuing a session
            job_role: Optional job role for the interview
            seniority_level: Optional seniority level
            required_skills: Optional list of required skills
            job_description: Optional job description
            requires_coding: Whether this role requires coding challenges
            handle_digression: Whether to handle topic digressions
            
        Returns:
            Tuple of (AI response, session ID)
        """
        logger.info(f"[CORE] run_interview called. user_id: {user_id}, session_id: {session_id}")
        logger.info(f"[CORE] run_interview initial params: job_role='{job_role}', seniority_level='{seniority_level}', requires_coding='{requires_coding}'")

        # Determine initial job role and seniority from passed arguments or instance defaults
        # These will be used if creating a new session or if not found in existing session metadata.
        # Fallback to instance default if job_role/seniority_level is None or an empty string.
        effective_job_role = job_role if job_role else self.job_role
        effective_seniority_level = seniority_level if seniority_level else self.seniority_level
        # For skills and description, None means use default; empty list/string is a valid override.
        effective_required_skills = required_skills if required_skills is not None else self.required_skills
        effective_job_description = job_description if job_description is not None else self.job_description
        # For requires_coding, respect False if passed, otherwise default to True if None.
        effective_requires_coding = requires_coding if requires_coding is not None else True

        logger.info(f"[CORE] run_interview effective values: job_role='{effective_job_role}', seniority_level='{effective_seniority_level}', skills='{effective_required_skills}', desc='{effective_job_description}', coding='{effective_requires_coding}'")

        # Create a new session if one doesn't exist, passing job details
        if not session_id:
            session_id = self._get_or_create_session(
                user_id,
                job_role=effective_job_role,
                seniority_level=effective_seniority_level,
                required_skills=effective_required_skills,
                job_description=effective_job_description,
                requires_coding=effective_requires_coding
            )
            logger.info(f"New session {session_id} for user {user_id} will be used/created by _get_or_create_session with specific job details.")
        
        # Ensure session_id is definitely created/retrieved before proceeding
        # Pass job details here as well, in case the session_id was provided but didn't exist
        # and _get_or_create_session needs to create it.
        session_id = self._get_or_create_session(
            user_id, 
            session_id,
            job_role=effective_job_role,
            seniority_level=effective_seniority_level,
            required_skills=effective_required_skills,
            job_description=effective_job_description,
            requires_coding=effective_requires_coding
        )

        # Initialize state with default values that will be potentially overridden by loaded session data
        messages = []
        candidate_name = ""
        interview_stage = InterviewStage.INTRODUCTION.value
        # Use effective values as initial fallback before loading from session
        job_role_value = effective_job_role
        seniority_level_value = effective_seniority_level
        required_skills_value = effective_required_skills
        job_description_value = effective_job_description
        requires_coding_value = effective_requires_coding
        conversation_summary = ""
        message_count = 0
        max_messages_before_summary = 20  # Default value
        metadata = {} # Initialize metadata

        # Try to load existing session if available
        try:
            # Check if the session exists
            current_session_data = None # Use a different variable name
            if self.session_manager:
                current_session_data = self.session_manager.get_session(session_id)
            else:
                # Use in-memory storage
                current_session_data = self.active_sessions.get(session_id)
                
            # If session_id was provided but session doesn't exist, _get_or_create_session handles creation.
            # Here, we assume session_id now points to a valid (possibly new) session.

            # Extract messages and metadata
            if current_session_data:
                if self.session_manager:
                    # MongoDB session structure
                    messages = current_session_data.get("messages", [])
                    metadata = current_session_data.get("metadata", {})
                else:
                    # In-memory session structure
                    messages = current_session_data.get("messages", [])
                    metadata = current_session_data # In-memory stores metadata at the top level of session object
                
                # Extract metadata values
                candidate_name = metadata.get(CANDIDATE_NAME_KEY, "")
                interview_stage = metadata.get(STAGE_KEY, InterviewStage.INTRODUCTION.value)
                conversation_summary = metadata.get("conversation_summary", "")
                message_count = metadata.get("message_count", len(messages)) # Recalculate if not present
                max_messages_before_summary = metadata.get("max_messages_before_summary", 20)
                
                logger.debug(f"Loaded existing session {session_id} with candidate_name: '{candidate_name}'")
                
                # Set job role info if not in session but provided in this call
                job_role_value = metadata.get("job_role", job_role_value)
                seniority_level_value = metadata.get("seniority_level", seniority_level_value)
                required_skills_value = metadata.get("required_skills", required_skills_value)
                job_description_value = metadata.get("job_description", job_description_value)
                requires_coding_value = metadata.get("requires_coding", requires_coding_value)

                # If new job details are provided for an existing session, update metadata
                if job_role and job_role != job_role_value:
                    metadata["job_role"] = job_role
                    job_role_value = job_role
                if seniority_level and seniority_level != seniority_level_value:
                    metadata["seniority_level"] = seniority_level
                    seniority_level_value = seniority_level
                if required_skills and required_skills != required_skills_value:
                    metadata["required_skills"] = required_skills
                    required_skills_value = required_skills
                if job_description and job_description != job_description_value:
                    metadata["job_description"] = job_description
                    job_description_value = job_description
                if requires_coding is not None and requires_coding != requires_coding_value:
                    metadata["requires_coding"] = requires_coding
                    requires_coding_value = requires_coding

                if self.session_manager:
                    self.session_manager.update_session_metadata(session_id, metadata)
                elif session_id in self.active_sessions: # Update in-memory session metadata
                    self.active_sessions[session_id].update(metadata)

                messages = extract_messages_from_transcript(messages)
                logger.debug(f"Loaded session {session_id} with {len(messages)} messages")
            else: # Should not happen if _get_or_create_session works correctly
                logger.warning(f"Session {session_id} data not found after _get_or_create_session. Initializing defaults.")
                metadata = {
                    "job_role": job_role_value,
                    "seniority_level": seniority_level_value,
                    "required_skills": required_skills_value,
                    "job_description": job_description_value,
                    "requires_coding": requires_coding_value,
                    STAGE_KEY: InterviewStage.INTRODUCTION.value,
                    "conversation_summary": "",
                    "message_count": 0,
                    "max_messages_before_summary": 20
                }
                if self.session_manager:
                    self.session_manager.update_session_metadata(session_id, metadata)
                elif session_id in self.active_sessions: # Update in-memory session metadata
                    self.active_sessions[session_id].update(metadata)

                messages = extract_messages_from_transcript(messages)
                logger.debug(f"Loaded session {session_id} with {len(messages)} messages")
        
        except Exception as e:
            logger.error(f"Error loading session {session_id}: {e}", exc_info=True)
            # Fallback to ensure essential metadata keys exist
            metadata.setdefault("job_role", job_role_value)
            metadata.setdefault("seniority_level", seniority_level_value)
            metadata.setdefault("required_skills", required_skills_value)
            metadata.setdefault("job_description", job_description_value)
            metadata.setdefault("requires_coding", requires_coding_value)
            metadata.setdefault(STAGE_KEY, InterviewStage.INTRODUCTION.value)
            metadata.setdefault("conversation_summary", "")
            metadata.setdefault("message_count", 0)
            metadata.setdefault("max_messages_before_summary", 20)

        # Detect potential digression if enabled
        if handle_digression and len(messages) > 2: # Ensure there are enough messages for context
            is_digression = self._detect_digression(user_message, messages, interview_stage)
            if is_digression:
                logger.info(f"Detected potential digression: '{user_message}'")
                if not any(isinstance(m, AIMessage) and hasattr(m, 'content') and "CONTEXT: Candidate is digressing" in m.content for m in messages[-3:]):
                    digression_note = AIMessage(content="CONTEXT: Candidate is digressing from the interview topic. I'll acknowledge their point and gently guide the conversation back to relevant technical topics.")
                    messages.append(digression_note)
                    logger.info("Added digression context note to message history")
                metadata["handling_digression"] = True
            elif metadata.get("handling_digression"): # If not a digression, clear flag
                metadata.pop("handling_digression", None)
        
        # Add the user message
        human_msg = HumanMessage(content=user_message)
        messages.append(human_msg)
        message_count = len(messages) # Recalculate message_count after adding new message

        # Check for candidate name in the user message if not already known
        if not candidate_name:
            name_match = self._extract_candidate_name([human_msg])
            if name_match:
                candidate_name = name_match
                logger.info(f"Extracted candidate name from new message: {candidate_name}")
                metadata[CANDIDATE_NAME_KEY] = candidate_name
                if self.session_manager:
                    self.session_manager.update_session_metadata(session_id, metadata)
                elif session_id in self.active_sessions:
                    self.active_sessions[session_id][CANDIDATE_NAME_KEY] = candidate_name

        # Update metadata before graph call
        metadata[STAGE_KEY] = interview_stage # Ensure stage is current
        metadata["message_count"] = message_count
        metadata["conversation_summary"] = conversation_summary # Ensure summary is current
        if self.session_manager:
            self.session_manager.update_session_metadata(session_id, metadata)
        elif session_id in self.active_sessions:
             self.active_sessions[session_id].update(metadata)


        # Create or update system message with context including conversation summary
        system_prompt_text = INTERVIEW_SYSTEM_PROMPT.format(
            system_name=get_llm_config()["system_name"],
            candidate_name=candidate_name or "[Not provided yet]",
            interview_id=session_id,
            current_stage=interview_stage,
            job_role=job_role_value,
            seniority_level=seniority_level_value,
            required_skills=", ".join(required_skills_value) if isinstance(required_skills_value, list) else str(required_skills_value),
            job_description=job_description_value,
            requires_coding=requires_coding_value,
            conversation_summary=conversation_summary if conversation_summary else "No summary available yet."
        )
        logger.info(f"[CORE] run_interview: System prompt being assembled with: job_role='{job_role_value}', seniority_level='{seniority_level_value}'")
        
        # Prepend system message if not already present or update existing one
        current_messages_for_graph = list(messages) # Operate on a copy
        if not current_messages_for_graph or not isinstance(current_messages_for_graph[0], SystemMessage):
            current_messages_for_graph.insert(0, SystemMessage(content=system_prompt_text))
        else:
            current_messages_for_graph[0] = SystemMessage(content=system_prompt_text)
        
        # Properly initialize our InterviewState class for the graph
        # The graph itself will manage appending its own AI responses to the message list.
        # We pass the current human message as the primary input to the graph.
        # The full history (including the system prompt) will be loaded by the checkpointer.
        
        graph_input = {
            "messages": [human_msg], # Graph expects a list of messages to process
            "candidate_name": candidate_name,
            "job_role": job_role_value,
            "seniority_level": seniority_level_value,
            "required_skills": required_skills_value,
            "job_description": job_description_value,
            "requires_coding": requires_coding_value,
            "interview_stage": interview_stage,
            "session_id": session_id, # Also pass session_id and user_id into the state
            "user_id": user_id,
            "conversation_summary": conversation_summary,
            "message_count": message_count,
            "max_messages_before_summary": max_messages_before_summary 
            # Ensure all relevant fields from InterviewState are populated
        }

        config = {
            "configurable": {
                "thread_id": session_id, # LangGraph uses thread_id for persistence
                # Pass other relevant info if your graph uses it directly in config
                "session_id": session_id, 
                "user_id": user_id,
                # Persisted state will be loaded by the checkpointer using thread_id
                # Initial values for a new thread can be passed if checkpointer doesn't have it.
                # However, for subsequent calls, checkpointer state takes precedence.
            }
        }
        
        final_graph_state = None
        try:
            is_async_checkpointer = hasattr(self.checkpointer, 'aget_tuple')
            logger.info(f"Running graph for session {session_id}. Async checkpointer: {is_async_checkpointer}")

            if is_async_checkpointer:
                async for chunk in self.workflow.astream(
                    input=graph_input, # Pass only the new message(s)
                    config=config,
                    # stream_mode="values", # stream_mode="updates" or "values" or "messages"
                ):
                    # Process chunks if necessary, e.g., for streaming to client
                    # The final state will be in the last chunk if stream_mode="values"
                    # Or you can inspect specific keys like chunk.get('model')
                    logger.debug(f"Graph async chunk for session {session_id}: {chunk}")
                    final_graph_state = chunk # The last chunk IS the final state with astream
            else:
                for chunk in self.workflow.stream(
                    input=graph_input,
                    config=config,
                    # stream_mode="values",
                ):
                    logger.debug(f"Graph sync chunk for session {session_id}: {chunk}")
                    final_graph_state = chunk # The last chunk IS the final state with stream
        
        except NotImplementedError as e:
            logger.error(f"NotImplementedError with checkpointer type for session {session_id}: {str(e)}", exc_info=True)
            # Fallback logic or re-raise
            return f"I apologize, an error occurred with session persistence. Error: {str(e)}", session_id
        except Exception as e:
            import traceback
            error_tb = traceback.format_exc()
            logger.error(f"Error running interview graph for session {session_id}: {str(e)}", exc_info=True)
            logger.error(f"Traceback: {error_tb}")
            return f"I apologize, but there was an error processing your request. Please try again. Error: {str(e)}", session_id
        
        extracted_challenge_details = None # Initialize here

        if final_graph_state:
            logger.info(f"[CORE run_interview] Processing final_graph_state. Type: {type(final_graph_state)}")
            if isinstance(final_graph_state, dict):
                logger.info(f"[CORE run_interview] final_graph_state top-level keys: {list(final_graph_state.keys())}")
            
            all_messages_from_state = []
            latest_stage_from_graph = graph_input.get("interview_stage", InterviewStage.INTRODUCTION.value) # Default to input stage

            if isinstance(final_graph_state, dict):
                model_output = final_graph_state.get("model")
                if isinstance(model_output, dict):
                    all_messages_from_state = model_output.get("messages", [])
                    if "interview_stage" in model_output: # Check if stage is in model output
                        latest_stage_from_graph = model_output["interview_stage"]
                elif "messages" in final_graph_state:
                    all_messages_from_state = final_graph_state.get("messages", [])
                
                # Check top-level for stage if not in model output
                if "interview_stage" in final_graph_state and latest_stage_from_graph == graph_input.get("interview_stage"):
                    latest_stage_from_graph = final_graph_state["interview_stage"]
            elif hasattr(final_graph_state, 'messages'):
                all_messages_from_state = final_graph_state.messages
                if hasattr(final_graph_state, 'interview_stage'):
                    latest_stage_from_graph = final_graph_state.interview_stage
            
            logger.info(f"[CORE run_interview] Determined latest_stage_from_graph: {latest_stage_from_graph}")

            # --- Start: Synthetic Challenge Generation Logic ---
            if latest_stage_from_graph == InterviewStage.CODING_CHALLENGE.value:
                challenge_already_generated_by_graph = False
                if all_messages_from_state:
                    for msg_content_item_check in all_messages_from_state:
                        if hasattr(msg_content_item_check, 'type') and msg_content_item_check.type == "tool" and \
                           hasattr(msg_content_item_check, 'name') and msg_content_item_check.name == "generate_coding_challenge_from_jd":
                            parsed_content_check = None
                            if hasattr(msg_content_item_check, 'content'):
                                if isinstance(msg_content_item_check.content, dict):
                                    parsed_content_check = msg_content_item_check.content
                                elif isinstance(msg_content_item_check.content, str):
                                    try:
                                        parsed_content_check = json.loads(msg_content_item_check.content)
                                    except json.JSONDecodeError:
                                        logger.warning(f"Synthetic check: JSONDecodeError for tool message content: {msg_content_item_check.content[:100]}")
                                    except Exception as e_json:
                                        logger.error(f"Synthetic check: Unexpected JSON error {e_json} for: {msg_content_item_check.content[:100]}")


                            if parsed_content_check and isinstance(parsed_content_check, dict) and "problem_statement" in parsed_content_check:
                                challenge_already_generated_by_graph = True
                                logger.info(f"Synthetic check: Challenge details found in graph output for session {session_id}.")
                                break
                
                if not challenge_already_generated_by_graph:
                    logger.warning(f"Graph did not produce 'generate_coding_challenge_from_jd' output in CODING_CHALLENGE stage for session {session_id}. Attempting synthetic generation.")
                    jd = graph_input.get("job_description", self.job_description)
                    skills = graph_input.get("required_skills", self.required_skills)
                    difficulty = "intermediate" # Default
                    seniority = graph_input.get("seniority_level", self.seniority_level)
                    if seniority.lower() == "junior": difficulty = "beginner"
                    elif seniority.lower() in ["senior", "lead", "principal"]: difficulty = "advanced"

                    try:
                        # generate_coding_challenge_from_jd is already imported at class level
                        tool_input_args_synth = {
                            "job_description": jd, "skills_required": skills, "difficulty_level": difficulty
                        }
                        synthetic_details = await generate_coding_challenge_from_jd.ainvoke(tool_input_args_synth)
                        
                        if synthetic_details and isinstance(synthetic_details, dict) and synthetic_details.get("status") == "success":
                            extracted_challenge_details = synthetic_details
                            logger.info(f"Successfully generated coding challenge synthetically for session {session_id}.")
                        else:
                            logger.error(f"Synthetic generation of coding challenge failed or returned non-success. Details: {synthetic_details}")
                    except Exception as e_synth:
                        logger.error(f"Exception during synthetic 'generate_coding_challenge_from_jd': {e_synth}", exc_info=True)
            # --- End: Synthetic Challenge Generation Logic ---

            # Extract coding challenge details from ToolMessage (if not synthetically generated)
            if not extracted_challenge_details and all_messages_from_state:
                logger.info(f"[run_interview] Iterating {len(all_messages_from_state)} messages to find coding challenge (post-synthetic check)...")
                for idx, msg_content_item in enumerate(all_messages_from_state):
                    if not hasattr(msg_content_item, 'type'):
                        logger.debug(f"[run_interview] Msg {idx} has no 'type' attribute, skipping.")
                        continue

                    is_tool = msg_content_item.type == "tool"
                    name_is_correct = hasattr(msg_content_item, 'name') and msg_content_item.name == "generate_coding_challenge_from_jd"
                    content_is_dict = hasattr(msg_content_item, 'content') and isinstance(msg_content_item.content, dict)
                    content_is_str = hasattr(msg_content_item, 'content') and isinstance(msg_content_item.content, str)
                    
                    if is_tool:
                        logger.info(f"[run_interview] Encountered ToolMessage: Name='{getattr(msg_content_item, 'name', 'N/A')}', Content Type='{type(getattr(msg_content_item, 'content', None))}', Is Dict='{content_is_dict}', Is Str='{content_is_str}', Content Preview='{str(getattr(msg_content_item, 'content', 'N/A'))[:100]}...'")

                    if is_tool and name_is_correct:
                        parsed_content = None
                        if content_is_dict:
                            logger.info(f"[run_interview] ToolMessage content is already a dict for challenge extraction at index {idx}: Name='{msg_content_item.name}'")
                            parsed_content = msg_content_item.content
                        elif content_is_str:
                            logger.info(f"[run_interview] ToolMessage content is a string, attempting JSON parse for challenge extraction at index {idx}: Name='{msg_content_item.name}'")
                            try:
                                parsed_content = json.loads(msg_content_item.content)
                            except json.JSONDecodeError as e:
                                logger.warning(f"Failed to parse ToolMessage string content for generate_coding_challenge_from_jd: {e}. Content: {msg_content_item.content[:200]}")
                            except Exception as e_json_inner: # Catch other parsing errors
                                logger.error(f"Unexpected error parsing ToolMessage string content: {e_json_inner}", exc_info=True)
                        
                        if parsed_content and isinstance(parsed_content, dict) and \
                           "problem_statement" in parsed_content and \
                           "test_cases" in parsed_content and \
                           "reference_solution" in parsed_content:
                           extracted_challenge_details = parsed_content
                           logger.info(f"Extracted coding challenge details from ToolMessage ID {getattr(msg_content_item, 'id', 'N/A')} named '{msg_content_item.name}'")
                           break 
                        elif parsed_content: 
                            logger.warning(f"ToolMessage for '{msg_content_item.name}' parsed, but did not contain expected challenge keys. Parsed content: {str(parsed_content)[:200]}...")
            
            if extracted_challenge_details:
                logger.info(f"[CORE run_interview] Successfully extracted coding_challenge_detail for session {session_id}")
                # Store it in session metadata for the /submit endpoint
                if self.session_manager:
                    session_data_for_saving_challenge = self.session_manager.get_session(session_id)
                    if session_data_for_saving_challenge:
                        metadata_to_save = session_data_for_saving_challenge.get("metadata", {})
                        logger.info(f"[CORE run_interview] BEFORE saving to session metadata: existing metadata keys for {session_id}: {list(metadata_to_save.keys())}") # ADDED LOG
                        logger.info(f"[CORE run_interview] Attempting to save the following extracted_challenge_details: {json.dumps(extracted_challenge_details, indent=2)[:500]}...") # ADDED LOG
                        
                        metadata_to_save["current_coding_challenge_details_for_submission"] = extracted_challenge_details # Store the whole dict
                        self.session_manager.update_session_metadata(session_id, metadata_to_save)
                        logger.info(f"[CORE run_interview] Stored full challenge details in session metadata for {session_id} under 'current_coding_challenge_details_for_submission'")
                        
                        # VERIFY what was saved by re-fetching (for debugging)
                        updated_session_data_after_save = self.session_manager.get_session(session_id)
                        if updated_session_data_after_save and updated_session_data_after_save.get("metadata"):
                            retrieved_challenge_for_verification = updated_session_data_after_save["metadata"].get("current_coding_challenge_details_for_submission")
                            logger.info(f"[CORE run_interview] AFTER saving, VERIFIED 'current_coding_challenge_details_for_submission' in session {session_id} (first 100 chars): {str(retrieved_challenge_for_verification)[:100]}...") # ADDED LOG
                        else:
                            logger.warning(f"[CORE run_interview] AFTER saving, failed to re-fetch session metadata for verification for {session_id}.")
                    else:
                        logger.warning(f"[CORE run_interview] Could not retrieve session {session_id} to store full challenge details in metadata.")
                elif session_id in self.active_sessions: # For in-memory
                    if "metadata" not in self.active_sessions[session_id]: # Ensure metadata dict exists for in-memory
                        self.active_sessions[session_id]["metadata"] = {}
                    self.active_sessions[session_id]["metadata"]["current_coding_challenge_details_for_submission"] = extracted_challenge_details
                    logger.info(f"[CORE run_interview] Stored full challenge details in IN-MEMORY session for {session_id} under 'current_coding_challenge_details_for_submission'")
            else:
                logger.info(f"[CORE run_interview] No coding_challenge_detail extracted from ToolMessages for session {session_id} in final graph state.")

            # Now, find the AI response (AIMessage)
            # final_messages_for_ai_response = all_messages_from_state # Use the same list
            if all_messages_from_state: # Renamed for clarity from final_messages_for_ai_response
                for msg in reversed(all_messages_from_state): # Iterate to find the last AIMessage that is not a tool call itself
                    if isinstance(msg, AIMessage):
                        # If this AIMessage is a tool call, skip it, 
                        # as we want the subsequent AI message that responds to the tool's output.
                        # We also check if the content itself is JSON, as per the prompt,
                        # the AI's response *is* the tool call JSON.
                        is_tool_call_message = False
                        if getattr(msg, 'tool_calls', None) and msg.tool_calls:
                            is_tool_call_message = True
                        else:
                            # Check if content is JSON (a common way to represent a tool call directly)
                            try:
                                if msg.content and isinstance(msg.content, str) and msg.content.strip().startswith('{') and msg.content.strip().endswith('}'):
                                    json.loads(msg.content) # Try to parse
                                    # If it parses and has 'name' and 'args', it's likely a tool call
                                    parsed_content = json.loads(msg.content)
                                    if isinstance(parsed_content, dict) and 'name' in parsed_content and 'args' in parsed_content:
                                        # Check if this tool call ID was recently executed if we have tool messages
                                        # This is a more robust check but harder to do without full history access here
                                        is_tool_call_message = True 
                                        logger.debug(f"Identified AIMessage content as a potential tool call JSON: {msg.content[:100]}")
                            except json.JSONDecodeError:
                                pass # Not a JSON string
                            except Exception: # Catch other parsing errors
                                pass

                        if is_tool_call_message:
                            logger.debug(f"Skipping AIMessage that appears to be a tool call: ID {msg.id}, Content: {msg.content[:100]}...")
                            continue

                        ai_response_content = safe_extract_content(msg)
                        logger.info(f"AI response generated for session {session_id}: '{ai_response_content}'")
                        
                        # Update cross-thread memory if needed
                        if self.memory_manager:
                            try:
                                insights = self._extract_interview_insights(all_messages_from_state)
                                if insights and "candidate_details" in insights:
                                    self.memory_manager.save_candidate_profile(user_id, insights)
                                self.memory_manager.save_interview_memory(
                                    session_id=session_id,
                                    memory_type="insights",
                                    memory_data={"insights": insights}
                                )
                            except Exception as e:
                                logger.error(f"Error updating memory for session {session_id}: {e}", exc_info=True)
                        
                        # Update session metadata with the latest stage from the graph if available
                        if isinstance(final_graph_state, dict) and final_graph_state.get(STAGE_KEY):
                            metadata[STAGE_KEY] = final_graph_state.get(STAGE_KEY)
                        elif hasattr(final_graph_state, INTERVIEW_STAGE_KEY): # Check actual key used in InterviewState
                            metadata[STAGE_KEY] = getattr(final_graph_state, INTERVIEW_STAGE_KEY)

                        if self.session_manager:
                            self.session_manager.update_session_metadata(session_id, metadata)
                        elif session_id in self.active_sessions:
                            self.active_sessions[session_id].update(metadata)

                        current_stage_after_turn = InterviewStage.INTRODUCTION.value # Default
                        if final_graph_state: # Ensure it's not None
                            if isinstance(final_graph_state, dict):
                                # Check if interview_stage is at the top level of the final state
                                if "interview_stage" in final_graph_state:
                                    current_stage_after_turn = final_graph_state["interview_stage"]
                                    logger.info(f"Extracted stage '{current_stage_after_turn}' from final_graph_state top level")
                                # Check if it's nested under a 'model' key (if the graph outputs like that)
                                elif "model" in final_graph_state and isinstance(final_graph_state["model"], dict) and "interview_stage" in final_graph_state["model"]:
                                    current_stage_after_turn = final_graph_state["model"]["interview_stage"]
                                    logger.info(f"Extracted stage '{current_stage_after_turn}' from final_graph_state['model']")
                                else:
                                    logger.warning(f"Could not find 'interview_stage' in final_graph_state dict: {final_graph_state}")
                            elif hasattr(final_graph_state, 'interview_stage'): # If it's an InterviewState object
                                current_stage_after_turn = final_graph_state.interview_stage
                                logger.info(f"Extracted stage '{current_stage_after_turn}' from final_graph_state object attribute")
                            else:
                                logger.warning(f"final_graph_state is not a dict and has no 'interview_stage' attribute: {type(final_graph_state)}")
                        else:
                            logger.warning("final_graph_state was None in run_interview when trying to determine stage.")
                        
                        # Update session metadata with the final, correct stage for the next turn
                        # Also, if challenge details were extracted, save them now.
                        # CRITICAL: Fetch the LATEST metadata from SessionManager before updating
                        # to avoid working with a stale metadata object.
                        
                        current_stage_after_turn = InterviewStage.INTRODUCTION.value # Default
                        if final_graph_state: # Ensure it's not None
                            if isinstance(final_graph_state, dict):
                                # Check 'model' key or top level of final_graph_state
                                model_output_for_stage = final_graph_state.get("model", final_graph_state) 
                                if isinstance(model_output_for_stage, dict) and "interview_stage" in model_output_for_stage:
                                    current_stage_after_turn = model_output_for_stage["interview_stage"]
                                    logger.info(f"Extracted stage '{current_stage_after_turn}' from final_graph_state for metadata update")
                                # else: current_stage_after_turn remains default or from existing metadata
                            elif hasattr(final_graph_state, 'interview_stage'): # If final_graph_state is an InterviewState object
                                current_stage_after_turn = final_graph_state.interview_stage
                                logger.info(f"Extracted stage '{current_stage_after_turn}' from final_graph_state object attribute for metadata update")
                            # If stage couldn't be determined, it remains default, or could be loaded from existing metadata below.
                        
                        if self.session_manager:
                            # CRITICAL: Fetch the LATEST metadata from SessionManager before updating
                            fresh_session_data = self.session_manager.get_session(session_id)
                            
                            metadata_to_save = {} # Initialize as an empty dict
                            if fresh_session_data and "metadata" in fresh_session_data:
                                metadata_to_save = fresh_session_data["metadata"] # Work with the latest
                                logger.info(f"[CORE run_interview] Fetched fresh metadata for session {session_id} before final update. Existing keys: {list(metadata_to_save.keys())}")
                            else:
                                logger.warning(f"[CORE run_interview] Could not re-fetch session {session_id} or it had no metadata. Starting with fresh metadata for save.")
                                # Populate essential knowns if creating metadata from scratch (should be rare if session exists)
                                metadata_to_save["job_role"] = job_role_value # from earlier in run_interview
                                metadata_to_save["seniority_level"] = seniority_level_value # from earlier
                                metadata_to_save["required_skills"] = required_skills_value # from earlier
                                metadata_to_save["job_description"] = job_description_value # from earlier
                                metadata_to_save["requires_coding"] = requires_coding_value # from earlier
                                if candidate_name: # from earlier in run_interview
                                    metadata_to_save[CANDIDATE_NAME_KEY] = candidate_name

                            # Update with the latest stage determined from the graph
                            metadata_to_save[STAGE_KEY] = current_stage_after_turn
                            
                            # If coding challenge details were extracted, add/update them
                            if extracted_challenge_details:
                                metadata_to_save["current_coding_challenge_details_for_submission"] = extracted_challenge_details
                                logger.info(f"[CORE run_interview] Adding/updating 'current_coding_challenge_details_for_submission' in metadata for session {session_id}")
                            
                            # Update message_count from the graph's final state if available
                            if hasattr(final_graph_state, 'message_count'):
                                 metadata_to_save["message_count"] = final_graph_state.message_count
                            elif isinstance(final_graph_state, dict):
                                 graph_model_state = final_graph_state.get("model", final_graph_state)
                                 if isinstance(graph_model_state, dict) and graph_model_state.get("message_count") is not None:
                                    metadata_to_save["message_count"] = graph_model_state["message_count"]
                            # If not found in graph state, it keeps what was in fresh_session_data or remains unset if metadata was new

                            self.session_manager.update_session_metadata(session_id, metadata_to_save)
                            logger.info(f"Final metadata update for session {session_id} with stage: {current_stage_after_turn}, details_present: {extracted_challenge_details is not None}, message_count: {metadata_to_save.get('message_count', 'N/A')}")
                            
                            # Optional: Verification re-read (as was in logs)
                            verified_data = self.session_manager.get_session(session_id)
                            if verified_data and "metadata" in verified_data:
                                verified_metadata = verified_data["metadata"]
                                logger.info(f"[CORE run_interview] Verification read after final save: challenge_details_present={verified_metadata.get('current_coding_challenge_details_for_submission') is not None}, stage='{verified_metadata.get(STAGE_KEY)}', message_count='{verified_metadata.get('message_count')}'")
                            else:
                                logger.warning(f"[CORE run_interview] Verification read failed or no metadata after final save for session {session_id}")


                        elif session_id in self.active_sessions: # In-memory handling
                            # Ensure metadata sub-dictionary exists if that's the structure for in-memory
                            if "metadata" not in self.active_sessions[session_id] or not isinstance(self.active_sessions[session_id].get("metadata"), dict):
                                # If top-level keys are directly on active_sessions[session_id]
                                if STAGE_KEY not in self.active_sessions[session_id]: # or other check
                                     # This indicates active_sessions[session_id] itself is the metadata dict
                                     target_metadata_dict = self.active_sessions[session_id]
                                else: # Assume it should have a metadata sub-dict
                                    self.active_sessions[session_id]["metadata"] = {}
                                    target_metadata_dict = self.active_sessions[session_id]["metadata"]
                            else:
                                target_metadata_dict = self.active_sessions[session_id]["metadata"]

                            target_metadata_dict[STAGE_KEY] = current_stage_after_turn
                            if extracted_challenge_details:
                                target_metadata_dict["current_coding_challenge_details_for_submission"] = extracted_challenge_details
                            
                            # Update message_count for in-memory as well
                            if hasattr(final_graph_state, 'message_count'):
                                 target_metadata_dict["message_count"] = final_graph_state.message_count
                            elif isinstance(final_graph_state, dict):
                                 graph_model_state = final_graph_state.get("model", final_graph_state)
                                 if isinstance(graph_model_state, dict) and graph_model_state.get("message_count") is not None:
                                    target_metadata_dict["message_count"] = graph_model_state["message_count"]

                            logger.info(f"Final in-memory metadata update for session {session_id} with stage: {current_stage_after_turn}, details_present: {extracted_challenge_details is not None}, message_count: {target_metadata_dict.get('message_count')}")

                        logger.info(f"[CORE] run_interview RETURN: ai_response='{ai_response_content[:50]}...', session_id='{session_id}', interview_stage='{current_stage_after_turn}', challenge_detail_present={extracted_challenge_details is not None}") # MODIFIED LOG
                        return {
                            "ai_response": ai_response_content,
                            "session_id": session_id,
                            "interview_stage": current_stage_after_turn, # Return the determined stage
                            "coding_challenge_detail": extracted_challenge_details # ADDED
                        }
        
        logger.warning(f"No AI message found in final graph state for session {session_id}. State: {final_graph_state}")
        
        # Attempt to get the most up-to-date stage from the final_graph_state, even in error cases.
        current_stage_at_turn_start = graph_input.get("interview_stage", InterviewStage.INTRODUCTION.value) # Keep this for comparison/logging
        latest_stage_from_graph = current_stage_at_turn_start # Fallback to stage at turn start
        if final_graph_state:
            if isinstance(final_graph_state, dict):
                # Check if interview_stage is at the top level of the final state
                if "interview_stage" in final_graph_state:
                    latest_stage_from_graph = final_graph_state["interview_stage"]
                # Check if it's nested under a 'model' key (if the graph outputs like that)
                elif "model" in final_graph_state and isinstance(final_graph_state["model"], dict) and "interview_stage" in final_graph_state["model"]:
                    latest_stage_from_graph = final_graph_state["model"]["interview_stage"]
            elif hasattr(final_graph_state, 'interview_stage'): # If it's an InterviewState object
                latest_stage_from_graph = final_graph_state.interview_stage
        
        logger.info(f"[CORE] run_interview ERROR RETURN: session_id='{session_id}', determined_latest_stage='{latest_stage_from_graph}' (was '{current_stage_at_turn_start}' at turn start), challenge_detail_present={extracted_challenge_details is not None}") # MODIFIED LOG
        return {
            "ai_response": "I'm sorry, I couldn't generate a proper response. Please try again.",
            "session_id": session_id,
            "interview_stage": latest_stage_from_graph, 
            "coding_challenge_detail": extracted_challenge_details 
        }

    def _get_or_create_session(self, user_id: str, session_id: Optional[str] = None,
                               job_role: Optional[str] = None,
                               seniority_level: Optional[str] = None,
                               required_skills: Optional[List[str]] = None,
                               job_description: Optional[str] = None,
                               requires_coding: Optional[bool] = None
                               ) -> str:
        """Get an existing session ID or create a new one.
        
        If job_role, seniority_level, etc., are provided, they are used for new sessions.
        Otherwise, instance defaults are used.
        """
        logger.info(f"[CORE] _get_or_create_session called with session_id='{session_id}', job_role='{job_role}', seniority_level='{seniority_level}'")

        if session_id:
            # Check if session exists
            if self.session_manager and self.session_manager.get_session(session_id):
                logger.info(f"Using existing session {session_id} for user {user_id}")
                # Verify user_id matches if session exists, or handle appropriately
                # For now, assume session_id is authoritative if provided.
                return session_id
            if not self.session_manager and session_id in self.active_sessions:
                 logger.info(f"Using existing in-memory session {session_id} for user {user_id}")
                 return session_id
            # If session_id was provided but not found, we'll create it below with this ID.
            logger.info(f"Provided session_id {session_id} not found, will create.")
        
        # Create new session ID if not provided or if provided one wasn't found
        effective_session_id = session_id or f"sess-{uuid.uuid4()}"
        
        logger.info(f"[CORE] _get_or_create_session: effective_session_id='{effective_session_id}'")
        # Use provided job details or fall back to instance defaults for the new session metadata
        # Fallback to instance default if job_role/seniority_level is None or an empty string.
        session_job_role = job_role if job_role else self.job_role
        session_seniority_level = seniority_level if seniority_level else self.seniority_level
        # For skills and description, None means use default; empty list/string is a valid override.
        session_required_skills = required_skills if required_skills is not None else self.required_skills
        session_job_description = job_description if job_description is not None else self.job_description
        # For requires_coding, if None is passed, use instance default (True), otherwise use the passed boolean.
        session_requires_coding = requires_coding if requires_coding is not None else True

        logger.info(f"[CORE] _get_or_create_session: determined session metadata values: job_role='{session_job_role}', seniority_level='{session_seniority_level}', coding='{session_requires_coding}'")

        if self.session_manager:
            # If session_manager is available, check again if it was created by another request
            # or if the provided session_id now exists.
            existing_session = self.session_manager.get_session(effective_session_id)
            if not existing_session:
                new_session_id = self.session_manager.create_session(
                    user_id,
                    metadata={
                        CANDIDATE_NAME_KEY: "",
                        STAGE_KEY: InterviewStage.INTRODUCTION.value,
                        "job_role": session_job_role,
                        "seniority_level": session_seniority_level,
                        "required_skills": session_required_skills,
                        "job_description": session_job_description,
                        "requires_coding": session_requires_coding,
                        "conversation_summary": "",
                        "message_count": 0,
                        "max_messages_before_summary": 20
                    }
                )
                logger.info(f"Created new session {new_session_id} for user {user_id} via SessionManager with job: {session_job_role}, seniority: {session_seniority_level}")
                effective_session_id = new_session_id
            else:
                logger.info(f"Session {effective_session_id} already exists for user {user_id} via SessionManager")

        elif effective_session_id not in self.active_sessions: # Only create if not already in active_sessions
            self.active_sessions[effective_session_id] = {
                "user_id": user_id,
                "messages": [], # messages will be loaded/populated by run_interview
                "created_at": datetime.now().isoformat(),
                "last_active": datetime.now().isoformat(),
                CANDIDATE_NAME_KEY: "",
                STAGE_KEY: InterviewStage.INTRODUCTION.value,
                "job_role": session_job_role,
                "seniority_level": session_seniority_level,
                "required_skills": session_required_skills,
                "job_description": session_job_description,
                "requires_coding": session_requires_coding,
                "conversation_summary": "",
                "message_count": 0,
                "max_messages_before_summary": 20
                # Ensure all keys accessed in run_interview's metadata section are initialized
            }
            logger.info(f"Created new in-memory session {effective_session_id} for user {user_id} with job: {session_job_role}, seniority: {session_seniority_level}")
        else:
            logger.info(f"In-memory session {effective_session_id} already exists for user {user_id}")
            
        return effective_session_id

    def _extract_candidate_name(self, messages):
        """
        Try to extract a candidate name from a list of messages.
        Looks for patterns like 'My name is ...' or 'I'm ...'
        """
        import re
        name_patterns = [
            r"my name is ([A-Za-z ]+)",
            r"i am ([A-Za-z ]+)",
            r"i'm ([A-Za-z ]+)",
            r"this is ([A-Za-z ]+)",
        ]
        for msg in messages:
            content = getattr(msg, "content", "")
            if not isinstance(content, str):
                continue
            for pat in name_patterns:
                match = re.search(pat, content, re.IGNORECASE)
                if match:
                    name = match.group(1).strip()
                    if len(name.split()) >= 1:
                        return name
        return None

    def _extract_interview_insights(self, messages, current_insights=None):
        """
        Stub for extracting interview insights from messages.
        You should implement this for your use case.
        """
        return current_insights or {}

    def _is_introduction_complete(self, human_messages: List[BaseMessage]) -> bool:
        """
        Determine if the introduction phase is complete based on message content.
        
        Args:
            human_messages: List of human messages in the conversation
            
        Returns:
            Boolean indicating if introduction is complete
        """
        logger.info(f"[_is_introduction_complete] Checking. Number of human messages: {len(human_messages)}")
        # If we have less than 2 exchanges, introduction is not complete
        if len(human_messages) < 2:
            logger.info("[_is_introduction_complete] Returning False (less than 2 human messages)")
            return False
        
        # Check if candidate has shared their name, background, or experience
        introduction_markers = [
            "experience with", "background in", "worked with", "my name is",
            "years of experience", "worked as", "skills in", "specialized in",
            "i am a", "i'm a", "i am", "i'm", "currently working", "previously worked",
            "my background is", "i focus on", "my expertise is", "i have experience",
            "role at", "position as", "studied at", "degree in", "graduated with"
        ]
        
        # Combine all human messages and check for introduction markers
        all_content = " ".join([m.content.lower() for m in human_messages if hasattr(m, 'content')])
        logger.info(f"[_is_introduction_complete] Combined human content: '{all_content[:200]}...'") # Log first 200 chars
        
        has_introduction_info = any(marker in all_content for marker in introduction_markers)
        logger.info(f"[_is_introduction_complete] Has introduction markers: {has_introduction_info}")
        
        logger.info(f"[_is_introduction_complete] Returning: {has_introduction_info}")
        return has_introduction_info
    
    def _count_substantive_exchanges(self, messages: List[BaseMessage]) -> int:
        """
        Count the number of substantive question-answer exchanges in the conversation.
        
        Args:
            messages: List of all messages in the conversation
            
        Returns:
            Count of substantive Q&A exchanges
        """
        count = 0
        
        # Look for pairs of messages (AI question followed by human response)
        for i in range(len(messages) - 1):
            if isinstance(messages[i], AIMessage) and isinstance(messages[i+1], HumanMessage):
                ai_content = messages[i].content.lower() if hasattr(messages[i], 'content') else ""
                human_response = messages[i+1].content.lower() if hasattr(messages[i+1], 'content') else ""
                
                # Check if this is a substantive technical exchange
                is_technical_question = any(kw in ai_content for kw in ["how", "what", "why", "explain", "describe"])
                is_substantive_answer = len(human_response.split()) > 15  # Reasonable length for a substantive answer
                
                if is_technical_question and is_substantive_answer:
                    count += 1
        
        return count
    
    def _is_ready_for_conclusion(self, messages: List[BaseMessage]) -> bool:
        """
        Determine if the interview is ready to conclude based on conversation flow.
        
        Args:
            messages: List of all messages in the conversation
            
        Returns:
            Boolean indicating if ready for conclusion
        """
        # Check if we've had sufficient conversation overall
        if len(messages) < 10:  # Need a reasonable conversation length
            return False
        
        # Check for signals that all question areas have been covered
        ai_messages = [m.content.lower() for m in messages if isinstance(m, AIMessage) and hasattr(m, 'content')]
        
        # Look for phrases that suggest interview completeness
        conclusion_signals = [
            "covered all", "thank you for your time", "appreciate your answers",
            "that concludes", "wrapping up", "final question", "is there anything else",
            "do you have any questions"
        ]
        
        # Check the last 3 AI messages for conclusion signals
        recent_ai_content = " ".join(ai_messages[-3:]) if len(ai_messages) >= 3 else " ".join(ai_messages)
        has_conclusion_signal = any(signal in recent_ai_content for signal in conclusion_signals)
        
        return has_conclusion_signal

    def _determine_interview_stage(self, messages: List[BaseMessage], ai_message: AIMessage, current_stage: str) -> str:
        """
        Determine the next interview stage based on the conversation context.
        
        Args:
            messages: List of all messages in the conversation
            ai_message: The latest AI message
            current_stage: Current interview stage
            
        Returns:
            New interview stage or current stage if no change
        """
        # Get human messages for better analysis
        human_messages = [m for m in messages if isinstance(m, HumanMessage)]
        human_message_count = len(human_messages) # RE-ADD THIS LINE
        
        # Get the latest human message (if any)
        latest_human_message = human_messages[-1].content.lower() if human_messages else ""
        
        # Extract AI message content
        ai_content = ai_message.content.lower() if hasattr(ai_message, 'content') else ""

        # --- START NEW HIGH-PRIORITY CHECK ---
        # If AI is calling the tool to generate a coding challenge, ensure stage is CODING_CHALLENGE.
        if getattr(ai_message, 'tool_calls', None):
            for tool_call in ai_message.tool_calls:
                if tool_call.get('name') == 'generate_coding_challenge_from_jd':
                    job_role_requires_coding = self._get_coding_requirement_from_state(messages + [ai_message])
                    if job_role_requires_coding:
                        if current_stage != InterviewStage.CODING_CHALLENGE.value:
                            logger.info(f"AI initiated 'generate_coding_challenge_from_jd'. Transitioning from {current_stage} to {InterviewStage.CODING_CHALLENGE.value} stage.")
                            return InterviewStage.CODING_CHALLENGE.value
                        else:
                            # Already in coding challenge, AI might be retrying or confirming.
                            return current_stage 
                    else:
                        logger.warning(f"AI initiated 'generate_coding_challenge_from_jd' for a role not requiring coding. Current stage: {current_stage}. Stage will not be forced to CODING_CHALLENGE here.")
                        # Allow subsequent logic to determine the stage; it might go to behavioral, etc.
                        break # Exit loop, let other logic handle stage if coding not required.
        # --- END NEW HIGH-PRIORITY CHECK ---

        # Define typical stage progression and keywords for user requests
        # This can be expanded based on observed user phrasing
        stage_transition_triggers = {
            InterviewStage.INTRODUCTION.value: {
                "next_stage": InterviewStage.TECHNICAL_QUESTIONS.value,
                "keywords": [
                    "move to technical", "start technical questions", "technical round",
                    "ask me technical questions", "let's do technical"
                ]
            },
            InterviewStage.TECHNICAL_QUESTIONS.value: {
                "next_stage_coding": InterviewStage.CODING_CHALLENGE.value,
                "keywords_coding": [
                    "move to coding", "start coding challenge", "coding round",
                    "give me a coding problem", "let's do coding"
                ],
                "next_stage_behavioral": InterviewStage.BEHAVIORAL_QUESTIONS.value,
                "keywords_behavioral": [
                    "move to behavioral", "start behavioral questions", "behavioral round",
                    "ask behavioral questions", "let's do behavioral"
                ]
            },
            InterviewStage.CODING_CHALLENGE.value: {
                "next_stage": InterviewStage.FEEDBACK.value, # Or CODING_CHALLENGE_WAITING then FEEDBACK
                "keywords": [
                    "finished coding", "submitted my code", "done with challenge", 
                    "evaluate my solution", "coding done", "completed the challenge"
                ] 
            },
            InterviewStage.CODING_CHALLENGE_WAITING.value: { 
                "next_stage": InterviewStage.FEEDBACK.value,
                "keywords": ["what's the feedback", "review my code now", "ready for feedback"]
            },
            InterviewStage.FEEDBACK.value: {
                "next_stage": InterviewStage.BEHAVIORAL_QUESTIONS.value,
                "keywords": [
                    "next question", "move on", "what else", "behavioral questions now"
                ]
            },
            InterviewStage.BEHAVIORAL_QUESTIONS.value: {
                "next_stage": InterviewStage.CONCLUSION.value,
                "keywords": [
                    "wrap up", "conclude interview", "that's all for behavioral", 
                    "any final questions", "end the interview"
                ]
            }
        }

        # Check for explicit user requests to change stage first
        if current_stage in stage_transition_triggers:
            triggers = stage_transition_triggers[current_stage]
            
            # Handle stages like TECHNICAL_QUESTIONS that might go to coding or behavioral
            if "next_stage_coding" in triggers and any(kw in latest_human_message for kw in triggers["keywords_coding"]):
                # Before transitioning to coding, check if the role requires it
                job_role_requires_coding = self._get_coding_requirement_from_state(messages)
                if job_role_requires_coding:
                    logger.info(f"User requested move from {current_stage} to {triggers['next_stage_coding']}")
                    return triggers['next_stage_coding']
                else:
                    logger.info(f"User requested coding, but role does not require it. Moving to behavioral instead from {current_stage}.")
                    return triggers.get('next_stage_behavioral', InterviewStage.BEHAVIORAL_QUESTIONS.value) # Fallback

            if "next_stage_behavioral" in triggers and any(kw in latest_human_message for kw in triggers["keywords_behavioral"]):
                logger.info(f"User requested move from {current_stage} to {triggers['next_stage_behavioral']}")
                return triggers['next_stage_behavioral']
            
            # Handle stages with a single typical next stage
            if "next_stage" in triggers and any(kw in latest_human_message for kw in triggers["keywords"]):
                logger.info(f"User requested move from {current_stage} to {triggers['next_stage']}")
                return triggers['next_stage']

        # Original logic if no direct user request matches or if stage isn't in triggers for explicit requests
        
        # Check for digression or clarification patterns (remains important)
        clarification_patterns = [
            "could you explain", "what do you mean", "can you clarify", 
            "i\\'m not sure", "don\\'t understand", "please explain", 
            "what is", "how does", "could you elaborate"
        ]
        
        # Is this a clarification or digression?
        is_clarification = any(pattern in latest_human_message for pattern in clarification_patterns)
        
        # If this is a clarification, usually we don't want to change stages
        if is_clarification and current_stage != InterviewStage.INTRODUCTION.value:
            logger.info(f"Detected clarification request, maintaining {current_stage} stage")
            return current_stage
        
        # Check for coding challenge triggers in AI message
        coding_keywords = [
            "coding challenge", "programming challenge", "write code", 
            "implement a function", "solve this problem", "coding exercise",
            "write a program", "implement an algorithm"
        ]
        has_coding_trigger = any(keyword in ai_content for keyword in coding_keywords)
        
        # Check for readiness to conclude the interview
        conclusion_keywords = [
            "conclude the interview", "conclude our interview", 
            "finishing up", "wrapping up", "end of our interview",
            "thank you for your time today"
        ]
        has_conclusion_trigger = any(keyword in ai_content for keyword in conclusion_keywords)
        
        if has_conclusion_trigger and current_stage not in [InterviewStage.INTRODUCTION.value, InterviewStage.CONCLUSION.value]:
            logger.info(f"Transitioning from {current_stage} to CONCLUSION stage")
            return InterviewStage.CONCLUSION.value
        
        # Handle stage-specific transitions
        if current_stage == InterviewStage.INTRODUCTION.value:
            # Start technical questions after introduction is complete
            # More dynamic transition based on interaction quality, not just count
            introduction_complete = self._is_introduction_complete(human_messages)
            if introduction_complete:
                logger.info("Transitioning from INTRODUCTION to TECHNICAL_QUESTIONS stage")
                return InterviewStage.TECHNICAL_QUESTIONS.value
        
        elif current_stage == InterviewStage.TECHNICAL_QUESTIONS.value:
            # Check if we should transition to coding challenge based on AI suggestion
            if has_coding_trigger:
                # Get state information to check if job role requires coding
                job_role_from_state = None
                requires_coding_flag_from_state = None

                # Attempt to extract job_role and requires_coding from the system message.
                # This is less ideal than having it directly in state (e.g. from InterviewState.requires_coding)
                # but serves as a fallback if the direct state attribute isn't easily accessible here.
                for msg in messages:
                    if isinstance(msg, SystemMessage) and hasattr(msg, 'content'):
                        sys_content_lower = msg.content.lower()
                        # Try to find requires_coding boolean first
                        coding_flag_match = re.search(r"requires coding: (true|false)", sys_content_lower)
                        if coding_flag_match:
                            requires_coding_flag_from_state = (coding_flag_match.group(1) == "true")
                        
                        # Try to find job_role for logging/context
                        role_match = re.search(r"job role: (.+?)[\n\.]", sys_content_lower, re.IGNORECASE)
                        if role_match:
                            job_role_from_state = role_match.group(1).strip()
                        
                        if coding_flag_match: # If we found the flag, we can stop searching this message
                            break
                
                job_role_requires_coding = True # Default if not found
                if requires_coding_flag_from_state is not None:
                    job_role_requires_coding = requires_coding_flag_from_state
                elif job_role_from_state: # Fallback to inferring from role name if flag isn't explicit
                    coding_required_roles = [
                        "software engineer", "developer", "programmer", "frontend developer", 
                        "backend developer", "full stack developer", "web developer",
                        "mobile developer", "app developer", "data scientist", "devops engineer"
                    ]
                    job_role_lower = job_role_from_state.lower()
                    job_role_requires_coding = any(role in job_role_lower for role in coding_required_roles)
                
                if job_role_requires_coding:
                    logger.info(f"Transitioning from TECHNICAL_QUESTIONS to CODING_CHALLENGE stage for job role: {job_role_from_state if job_role_from_state else '[Undetermined]'}")
                    return InterviewStage.CODING_CHALLENGE.value
                else:
                    logger.info(f"Skipping coding challenge for job role: {job_role_from_state if job_role_from_state else '[Undetermined]'} (coding not required)")
            
            # If we've had enough substantive technical exchanges, move to behavioral questions
            # Use a combination of count and content analysis
            if human_message_count >= 5 and not has_coding_trigger:
                # Check if we've asked enough substantive technical questions
                substantive_qa = self._count_substantive_exchanges(messages)
                if substantive_qa >= 3: # Restored to >= 3
                    logger.info("Transitioning from TECHNICAL_QUESTIONS to BEHAVIORAL_QUESTIONS stage after substantive technical discussion")
                    return InterviewStage.BEHAVIORAL_QUESTIONS.value
        
        elif current_stage == InterviewStage.CODING_CHALLENGE.value:
            # Check if the candidate has submitted a solution and we should transition
            submission_keywords = [
                "submitted my solution", "finished the challenge", "completed the exercise",
                "here\\'s my solution", "my code is ready", "implemented the solution",
                "done with the challenge", "finished coding", "completed the task"
            ]
            has_submission = any(keyword in ' '.join([m.content.lower() for m in messages[-3:] if hasattr(m, 'content')]) for keyword in submission_keywords)
            
            # Also check metadata for manual transition triggered by frontend submission
            # This typically happens via the continue_after_challenge API endpoint
            metadata_transition = False
            for msg in messages:
                if isinstance(msg, SystemMessage) and hasattr(msg, 'content'):
                    if "resuming_from_challenge: true" in msg.content.lower():
                        metadata_transition = True
                        break
            
            if has_submission or metadata_transition:
                logger.info(f"Transitioning from CODING_CHALLENGE to CODING_CHALLENGE_WAITING stage (triggered by{'metadata' if metadata_transition else 'message content'})")
                return InterviewStage.CODING_CHALLENGE_WAITING.value
        
        elif current_stage == InterviewStage.CODING_CHALLENGE_WAITING.value:
            # This stage is primarily a UI-driven state that indicates we're waiting for the frontend
            # to complete the coding challenge submission flow and call the challenge-complete endpoint.
            # The actual transition to FEEDBACK is typically handled by the continue_after_challenge method.
            
            # However, we provide a backup detection mechanism here for text-based interfaces
            # by checking for evaluation language in the AI's response
            evaluation_keywords = [
                "your solution was", "feedback on your code", "your implementation", 
                "code review", "assessment of your solution", "evaluation of your code"
            ]
            has_evaluation = any(keyword in ai_content for keyword in evaluation_keywords)
            
            # Also check recent history for coding evaluation data in the metadata
            has_evaluation_data = False
            for msg in messages[-5:]:
                if isinstance(msg, SystemMessage) and hasattr(msg, 'content'):
                    if "coding_evaluation:" in msg.content.lower():
                        has_evaluation_data = True
                        break
            
            if has_evaluation or has_evaluation_data:
                logger.info(f"Transitioning from CODING_CHALLENGE_WAITING to FEEDBACK stage (triggered by{'evaluation data' if has_evaluation_data else 'evaluation keywords'})")
                return InterviewStage.FEEDBACK.value
        
        elif current_stage == InterviewStage.FEEDBACK.value:
            # After providing feedback, transition to behavioral questions if not already done
            behavioral_transition = any(keyword in ai_content for keyword in [
                "let\\'s talk about your experience", "tell me about a time", 
                "describe a situation", "how do you handle", "what would you do if"
            ])
            
            if behavioral_transition or human_message_count > 2: # human_message_count refers to total human messages in interview
                logger.info("Transitioning from FEEDBACK to BEHAVIORAL_QUESTIONS stage")
                return InterviewStage.BEHAVIORAL_QUESTIONS.value
        
        elif current_stage == InterviewStage.BEHAVIORAL_QUESTIONS.value:
            # After enough behavioral questions, move to conclusion
            # Check if we have enough substantive behavioral exchanges or AI is ready to conclude
            if has_conclusion_trigger or human_message_count >= 4: # human_message_count refers to total human messages
                conclusion_ready = self._is_ready_for_conclusion(messages)
                if conclusion_ready:
                    logger.info("Transitioning from BEHAVIORAL_QUESTIONS to CONCLUSION stage")
                    return InterviewStage.CONCLUSION.value
        
        # By default, stay in the current stage
        return current_stage

    def _get_coding_requirement_from_state(self, messages: List[BaseMessage]) -> bool:
        """Helper to determine if coding is required based on system message in conversation history."""
        job_role_from_state = None
        requires_coding_flag_from_state = None
        for msg in messages:
            if isinstance(msg, SystemMessage) and hasattr(msg, 'content'):
                sys_content_lower = msg.content.lower()
                coding_flag_match = re.search(r"requires coding: (true|false)", sys_content_lower)
                if coding_flag_match:
                    requires_coding_flag_from_state = (coding_flag_match.group(1) == "true")
                
                role_match = re.search(r"job role: (.+?)[\n\.]", sys_content_lower, re.IGNORECASE)
                if role_match:
                    job_role_from_state = role_match.group(1).strip()
                
                if coding_flag_match: # If we found the flag, we can stop searching
                    break
        
        if requires_coding_flag_from_state is not None:
            return requires_coding_flag_from_state
        elif job_role_from_state:
            coding_required_roles = [
                "software engineer", "developer", "programmer", "frontend developer", 
                "backend developer", "full stack developer", "web developer",
                "mobile developer", "app developer", "data scientist", "devops engineer"
            ]
            job_role_lower = job_role_from_state.lower()
            return any(role in job_role_lower for role in coding_required_roles)
        return True # Default to true if not determinable from context

    async def resume_interview(self, session_id: str, user_id: str) -> Tuple[Optional[InterviewState], str]:
        # Implementation of resume_interview method
        pass

    def _migrate_tool_calls(self, mongodb_uri: str, db_name: str, collection_name: str) -> None:
        """
        Migrate tool calls from 'arguments' to 'args' format to prevent deserialization errors.
        
        Args:
            mongodb_uri: MongoDB connection URI
            db_name: Database name
            collection_name: Collection name for checkpoints
        """
        try:
            # Import the migration utility function
            from ai_interviewer.utils.db_utils import migrate_tool_call_format
            from pymongo import MongoClient
            
            # Connect to MongoDB
            client = MongoClient(mongodb_uri)
            
            # Run migration
            logger.info("Running quick tool call format migration to prevent deserialization errors")
            result = migrate_tool_call_format(client, db_name, collection_name)
            
            if "error" not in result:
                logger.info(f"Tool call migration complete: {result}")
            else:
                logger.warning(f"Tool call migration failed: {result['error']}")
                
            client.close()
        except Exception as e:
            logger.warning(f"Error during tool call migration: {e}")
            logger.warning("Continuing without migration - some sessions may experience errors")

    def _normalize_tool_calls(self, tool_calls):
        """
        Normalize tool calls to ensure they use 'args' instead of 'arguments'.
        This helps with backward compatibility and prevents deserialization errors.
        
        Args:
            tool_calls: List of tool calls to normalize
        """
        if not tool_calls:
            return
            
        for tool_call in tool_calls:
            # Convert 'arguments' to 'args' if present
            if "arguments" in tool_call and "args" not in tool_call:
                tool_call["args"] = tool_call.pop("arguments")
                
            # Ensure each tool call has an ID
            if "id" not in tool_call:
                tool_call["id"] = f"tool_{uuid.uuid4().hex[:8]}"
