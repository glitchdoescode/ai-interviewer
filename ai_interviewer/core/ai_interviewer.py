"""
Core AI Interviewer class that encapsulates all LangGraph components.

This module follows the architecture pattern from gizomobot, providing a unified
class that handles the entire interview process.
"""
import logging
import os
import uuid
from typing import Dict, List, Optional, Any, Literal, Union, Tuple
from datetime import datetime
from enum import Enum
import re

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END, MessagesState
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.mongodb import MongoDBSaver
from langgraph.types import interrupt, Command

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

# Import custom modules
from ai_interviewer.utils.session_manager import SessionManager
from ai_interviewer.utils.config import get_db_config, get_llm_config, log_config
from ai_interviewer.utils.transcript import extract_messages_from_transcript, safe_extract_content, format_conversation_for_llm

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
You are an AI technical interviewer conducting a {job_role} interview for a {seniority_level} position.

Interview ID: {interview_id}
Candidate: {candidate_name}
Current stage: {current_stage}

Required skills: {required_skills}
Job description: {job_description}

Your role is to:
1. Assess the candidate's technical skills and experience level
2. Ask relevant technical questions based on the job requirements
3. Provide a coding challenge if appropriate for the position
4. Give the candidate feedback on their answers
5. Make the interview conversational, professional, and engaging

Remember the candidate's name and use it throughout the conversation.
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
    
    # Interview progress
    interview_stage: str = InterviewStage.INTRODUCTION.value
    
    # Session information
    session_id: str = ""
    user_id: str = ""
    
    def __init__(self, 
                messages: Optional[List[BaseMessage]] = None,
                candidate_name: str = "",
                job_role: str = "",
                seniority_level: str = "",
                required_skills: Optional[List[str]] = None,
                job_description: str = "",
                interview_stage: str = "",
                session_id: str = "",
                user_id: str = ""):
        """
        Initialize the InterviewState with the provided values.
        
        Args:
            messages: List of conversation messages
            candidate_name: Name of the candidate
            job_role: Job role for the interview
            seniority_level: Seniority level for the position
            required_skills: List of required skills
            job_description: Job description text
            interview_stage: Current interview stage
            session_id: Session identifier
            user_id: User identifier
        """
        # Initialize MessagesState
        super().__init__(messages=messages or [])
        
        # Initialize the rest of the state
        self.candidate_name = candidate_name
        self.job_role = job_role
        self.seniority_level = seniority_level
        self.required_skills = required_skills or []
        self.job_description = job_description
        self.interview_stage = interview_stage or InterviewStage.INTRODUCTION.value
        self.session_id = session_id
        self.user_id = user_id
    
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
        elif key == "interview_stage":
            return self.interview_stage
        elif key == "session_id":
            return self.session_id
        elif key == "user_id":
            return self.user_id
        else:
            raise KeyError(f"Key '{key}' not found in InterviewState")
    
    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

class AIInterviewer:
    """Main class that encapsulates the AI Interviewer functionality."""
    
    def __init__(self, 
                use_mongodb: bool = True, 
                connection_uri: Optional[str] = None,
                job_role: str = "Software Engineering",
                seniority_level: str = "Mid-level",
                required_skills: List[str] = None,
                job_description: str = ""):
        """
        Initialize the AI Interviewer with tools, model, and workflow.
        
        Args:
            use_mongodb: Whether to use MongoDB for persistence
            connection_uri: MongoDB connection URI (if None, uses config)
            job_role: The specific job role for the interview
            seniority_level: The seniority level for the position
            required_skills: List of required skills for the position
            job_description: Detailed job description for context
        """
        # Log configuration
        log_config()
        
        # Store job role configuration
        self.job_role = job_role
        self.seniority_level = seniority_level
        self.required_skills = required_skills or ["Programming", "Problem Solving", "Technical Knowledge"]
        self.job_description = job_description
        
        # Set up tools
        self.tools = [
            # Coding challenge tools
            start_coding_challenge,
            submit_code_for_challenge,
            get_coding_hint,
            
            # Pair programming tools
            suggest_code_improvements,
            complete_code,
            review_code_section
        ]
        
        # Create tool node with proper state handling
        self.tool_node = ToolNode(self.tools)
        
        # Initialize LLM with tools
        llm_config = get_llm_config()
        self.model = ChatGoogleGenerativeAI(
            model=llm_config["model"],
            temperature=llm_config["temperature"]
        ).bind_tools(self.tools)
        
        # Set up database connections if using MongoDB
        if use_mongodb:
            try:
                # Get database config
                db_config = get_db_config()
                mongodb_uri = connection_uri or db_config["uri"]
                
                # Define the checkpoint namespace
                checkpoint_namespace = "ai_interviewer"
                
                # Initialize MongoDB checkpointer using the official LangGraph implementation
                logger.info(f"Initializing MongoDB checkpointer with URI {mongodb_uri}")
                from pymongo import MongoClient
                
                # Create a MongoDB client
                client = MongoClient(mongodb_uri)
                
                # Create the checkpointer instance directly
                self.checkpointer = MongoDBSaver(
                    client=client,
                    db_name=db_config["database"], 
                    collection_name=db_config["sessions_collection"]
                )
                
                # Test MongoDB connection
                try:
                    # Simple connection test using the session manager
                    self.session_manager = SessionManager(
                        connection_uri=mongodb_uri,
                        database_name=db_config["database"],
                        collection_name=db_config["metadata_collection"],
                    )
                    logger.info("MongoDB connection successful!")
                except Exception as e:
                    raise ValueError(f"MongoDB connection test failed: {e}")
                
                logger.info("Using MongoDB for persistence")
            except Exception as e:
                # If there's an error with MongoDB, fall back to in-memory persistence
                logger.warning(f"Failed to connect to MongoDB: {e}. Falling back to in-memory persistence.")
                self.checkpointer = InMemorySaver()
                self.session_manager = None
                logger.info("Using in-memory persistence as fallback")
        else:
            # Use in-memory persistence
            self.checkpointer = InMemorySaver()
            self.session_manager = None
            logger.info("Using in-memory persistence")
        
        # Initialize workflow
        self.workflow = self._initialize_workflow()
        
        # Session tracking
        self.active_sessions = {}
    
    def _initialize_workflow(self) -> StateGraph:
        """
        Initialize the LangGraph workflow with the model and tools.
        
        Returns:
            StateGraph instance configured with the model and tools
        """
        logger.info("Initializing LangGraph workflow")
        
        # Use our custom InterviewState instead of MessagesState
        workflow = StateGraph(InterviewState)
        
        # Define custom wrapper for the tool node to ensure proper state handling
        def tools_node(state: Union[Dict, InterviewState]) -> Union[Dict, InterviewState]:
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
                    
                    # Execute tools using the ToolNode with messages
                    tool_result = self.tool_node.invoke({"messages": messages})
                    
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
                    
                    return updated_state
                else:
                    # Extract messages from InterviewState
                    messages = state.messages
                    candidate_name = state.candidate_name
                    
                    # Execute tools using the ToolNode with messages
                    tool_result = self.tool_node.invoke({"messages": messages})
                    
                    # Get updated messages
                    updated_messages = state.messages + tool_result.get("messages", [])
                    
                    # Check for extracted name in new messages
                    if not candidate_name and "messages" in tool_result:
                        name_match = self._extract_candidate_name(updated_messages)
                        if name_match:
                            candidate_name = name_match
                            logger.info(f"Extracted candidate name during tool call: {name_match}")
                    
                    # Create a new InterviewState with updated values
                    return InterviewState(
                        messages=updated_messages,
                        candidate_name=candidate_name,
                        job_role=state.job_role,
                        seniority_level=state.seniority_level,
                        required_skills=state.required_skills,
                        job_description=state.job_description,
                        interview_stage=state.interview_stage,
                        session_id=state.session_id,
                        user_id=state.user_id
                    )
            except Exception as e:
                logger.error(f"Error in tools_node: {e}")
                # Return original state on error
                return state
        
        # Define nodes
        workflow.add_node("model", self.call_model)
        workflow.add_node("tools", tools_node)
        
        # Define edges - model -> should_continue
        workflow.add_conditional_edges(
            "model",
            self.should_continue,
            {
                "tools": "tools",
                "end": END
            }
        )
        
        # Define edge - tools -> model
        workflow.add_edge("tools", "model")
        
        # Define starting node
        workflow.set_entry_point("model")
        
        # Compile workflow
        logger.info("Compiling workflow")
        compiled_workflow = workflow.compile()
        
        return compiled_workflow
        
    @staticmethod
    def should_continue(state: Union[Dict, InterviewState]) -> Literal["tools", "end"]:
        """
        Determine whether to continue to tools or end the workflow.
        
        Args:
            state: Current state with messages (dict or InterviewState)
            
        Returns:
            Next node to execute ("tools" or "end")
        """
        # Get the most recent assistant message
        # Check if state is a dictionary or MessagesState object
        if isinstance(state, dict):
            if "messages" not in state or not state["messages"]:
                # No messages yet
                return "end"
            messages = state["messages"]
        else:
            # Assume it's a MessagesState or InterviewState object
            if not hasattr(state, "messages") or not state.messages:
                # No messages yet
                return "end"
            messages = state.messages
        
        # Look for the last AI message
        for message in reversed(messages):
            if isinstance(message, AIMessage):
                # Check if it has tool calls
                if hasattr(message, "tool_calls") and message.tool_calls:
                    return "tools"
                # No tool calls
                return "end"
        
        # No AI messages found
        return "end"
    
    def call_model(self, state: Union[Dict, InterviewState]) -> Union[Dict, InterviewState]:
        """
        Call the model to generate a response based on the current state.
        
        Args:
            state: Current state with messages and interview context (dict or InterviewState)
            
        Returns:
            Updated state with new AI message
        """
        try:
            # Check if state is a dictionary or InterviewState object
            if isinstance(state, dict):
                # Extract data from dictionary
                messages = state.get("messages", [])
                candidate_name = state.get("candidate_name", "")
                job_role = state.get("job_role", self.job_role)
                seniority_level = state.get("seniority_level", self.seniority_level)
                required_skills = state.get("required_skills", self.required_skills)
                job_description = state.get("job_description", self.job_description)
                interview_stage = state.get("interview_stage", InterviewStage.INTRODUCTION.value)
                session_id = state.get("session_id", "")
                user_id = state.get("user_id", "")
            else:
                # Extract data from InterviewState object
                messages = state.messages
                candidate_name = state.candidate_name
                job_role = state.job_role
                seniority_level = state.seniority_level
                required_skills = state.required_skills
                job_description = state.job_description
                interview_stage = state.interview_stage
                session_id = state.session_id
                user_id = state.user_id
            
            # Create or update system message with context
            system_prompt = INTERVIEW_SYSTEM_PROMPT.format(
                candidate_name=candidate_name or "[Not provided yet]",
                interview_id=session_id,
                current_stage=interview_stage,
                job_role=job_role,
                seniority_level=seniority_level,
                required_skills=", ".join(required_skills) if isinstance(required_skills, list) else str(required_skills),
                job_description=job_description
            )
            
            # Update system message if present, otherwise add it
            if messages and isinstance(messages[0], SystemMessage):
                messages[0] = SystemMessage(content=system_prompt)
            else:
                messages = [SystemMessage(content=system_prompt)] + messages
            
            # Include metadata for model tracing/context
            model_config = {
                "metadata": {
                    "interview_id": session_id,
                    "candidate_name": candidate_name,
                    "interview_stage": interview_stage
                }
            }
            
            # Call the model
            logger.debug(f"Calling model with {len(messages)} messages")
            ai_message = self.model.invoke(messages, config=model_config)
            
            # Extract name from conversation if not already known
            if not candidate_name:
                name_match = self._extract_candidate_name(messages + [ai_message])
                if name_match:
                    candidate_name = name_match
                    logger.info(f"Extracted candidate name during model call: {candidate_name}")
                    
                    # Immediately update session metadata with the new candidate name
                    if session_id and self.session_manager:
                        session = self.session_manager.get_session(session_id)
                        if session and "metadata" in session:
                            metadata = session.get("metadata", {})
                            metadata[CANDIDATE_NAME_KEY] = candidate_name
                            self.session_manager.update_session_metadata(session_id, metadata)
                            logger.info(f"Updated session metadata with candidate name: {candidate_name}")
            
            # Determine if we need to update the interview stage
            new_stage = self._determine_interview_stage(messages, ai_message, interview_stage)
            
            # Return the appropriate state type based on input
            if isinstance(state, dict):
                # Return a dictionary with updated values
                updated_state = dict(state)
                updated_state["messages"] = messages + [ai_message]
                updated_state["candidate_name"] = candidate_name
                updated_state["interview_stage"] = new_stage if new_stage != interview_stage else interview_stage
                return updated_state
            else:
                # Return a new InterviewState object
                return InterviewState(
                    messages=messages + [ai_message],
                    candidate_name=candidate_name,
                    job_role=job_role,
                    seniority_level=seniority_level,
                    required_skills=required_skills,
                    job_description=job_description,
                    interview_stage=new_stage if new_stage != interview_stage else interview_stage,
                    session_id=session_id,
                    user_id=user_id
                )
            
        except Exception as e:
            logger.error(f"Error calling model: {e}")
            # Create error message
            error_message = AIMessage(content="I apologize, but I encountered an issue. Please try again.")
            
            # Return appropriate state type
            if isinstance(state, dict):
                updated_state = dict(state)
                if "messages" in updated_state:
                    updated_state["messages"] = updated_state["messages"] + [error_message]
                else:
                    updated_state["messages"] = [error_message]
                return updated_state
            else:
                return InterviewState(
                    messages=state.messages + [error_message] if hasattr(state, "messages") else [error_message],
                    candidate_name=state.candidate_name if hasattr(state, "candidate_name") else "",
                    job_role=state.job_role if hasattr(state, "job_role") else self.job_role,
                    seniority_level=state.seniority_level if hasattr(state, "seniority_level") else self.seniority_level,
                    required_skills=state.required_skills if hasattr(state, "required_skills") else self.required_skills,
                    job_description=state.job_description if hasattr(state, "job_description") else self.job_description,
                    interview_stage=state.interview_stage if hasattr(state, "interview_stage") else InterviewStage.INTRODUCTION.value,
                    session_id=state.session_id if hasattr(state, "session_id") else "",
                    user_id=state.user_id if hasattr(state, "user_id") else ""
                )
    
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
        # Check if we're in the introduction and have enough context to move on
        if current_stage == InterviewStage.INTRODUCTION.value:
            # After a few exchanges in the introduction, we can move to technical questions
            if len([m for m in messages if isinstance(m, HumanMessage)]) >= 2:
                return InterviewStage.TECHNICAL_QUESTIONS.value
                
        # If we're in technical questions and have had many exchanges, move to behavioral
        if current_stage == InterviewStage.TECHNICAL_QUESTIONS.value:
            if len([m for m in messages if isinstance(m, HumanMessage)]) >= 6:
                return InterviewStage.BEHAVIORAL_QUESTIONS.value
                
        # If we're in behavioral questions and have had enough exchanges, wrap up
        if current_stage == InterviewStage.BEHAVIORAL_QUESTIONS.value:
            if len([m for m in messages if isinstance(m, HumanMessage)]) >= 10:
                return InterviewStage.CONCLUSION.value
                
        # By default, stay in the current stage
        return current_stage
    
    async def run_interview(self, user_id: str, user_message: str, session_id: Optional[str] = None, 
                           job_role: Optional[str] = None, seniority_level: Optional[str] = None, 
                           required_skills: Optional[List[str]] = None, job_description: Optional[str] = None) -> Tuple[str, str]:
        """
        Run the interview with a user message, creating or continuing a session.
        
        Args:
            user_id: Unique identifier for the user
            user_message: Message from the user
            session_id: Optional session ID to continue an existing session
            job_role: Optional job role for the interview
            seniority_level: Optional seniority level
            required_skills: Optional list of required skills
            job_description: Optional job description text
            
        Returns:
            Tuple of (AI response, session_id)
        """
        # Create a new session if one doesn't exist
        if not session_id:
            session_id = self._get_or_create_session(user_id)
            logger.info(f"Created new session {session_id} for user {user_id}")
        
        # Initialize state with default values
        messages = []
        candidate_name = ""
        interview_stage = InterviewStage.INTRODUCTION.value
        job_role_value = job_role or self.job_role
        seniority_level_value = seniority_level or self.seniority_level
        required_skills_value = required_skills or self.required_skills
        job_description_value = job_description or self.job_description
        
        # Try to load existing session if available
        try:
            # Check if the session exists
            if self.session_manager:
                session = self.session_manager.get_session(session_id)
            else:
                # Use in-memory storage
                session = self.active_sessions.get(session_id)
                
            if not session and self.session_manager:
                # Create a new session if it doesn't exist but session_id was provided
                logger.warning(f"Session {session_id} not found, creating new")
                self.session_manager.create_session(user_id, session_id=session_id)
                session = self.session_manager.get_session(session_id)
                
                # Add default interview stage
                if session and self.session_manager:
                    metadata = session.get("metadata", {})
                    metadata[STAGE_KEY] = InterviewStage.INTRODUCTION.value
                    self.session_manager.update_session_metadata(session_id, metadata)
                
            # Extract messages and metadata
            if session:
                if self.session_manager:
                    # MongoDB session structure
                    messages = session.get("messages", [])
                    metadata = session.get("metadata", {})
                else:
                    # In-memory session structure
                    messages = session.get("messages", [])
                    metadata = session
                
                # Extract metadata values
                candidate_name = metadata.get(CANDIDATE_NAME_KEY, "")
                interview_stage = metadata.get(STAGE_KEY, InterviewStage.INTRODUCTION.value)
                
                logger.debug(f"Loaded existing session with candidate_name: '{candidate_name}'")
                
                # Set job role info if not in session but provided in this call
                if job_role and "job_role" not in metadata:
                    metadata["job_role"] = job_role
                    job_role_value = job_role
                else:
                    job_role_value = metadata.get("job_role", self.job_role)
                    
                if seniority_level and "seniority_level" not in metadata:
                    metadata["seniority_level"] = seniority_level
                    seniority_level_value = seniority_level
                else:
                    seniority_level_value = metadata.get("seniority_level", self.seniority_level)
                    
                if required_skills and "required_skills" not in metadata:
                    metadata["required_skills"] = required_skills
                    required_skills_value = required_skills
                else:
                    required_skills_value = metadata.get("required_skills", self.required_skills)
                    
                if job_description and "job_description" not in metadata:
                    metadata["job_description"] = job_description
                    job_description_value = job_description
                else:
                    job_description_value = metadata.get("job_description", self.job_description)
                
                # Convert list/dict messages to proper message objects if needed
                messages = extract_messages_from_transcript(messages)
                
                logger.debug(f"Loaded existing session with {len(messages)} messages")
            else:
                # Start a new session with empty messages
                metadata = {
                    "job_role": job_role or self.job_role,
                    "seniority_level": seniority_level or self.seniority_level,
                    "required_skills": required_skills or self.required_skills,
                    "job_description": job_description or self.job_description,
                    STAGE_KEY: InterviewStage.INTRODUCTION.value,
                }
                
                if self.session_manager:
                    self.session_manager.update_session_metadata(session_id, metadata)
                else:
                    # Store in memory
                    self.active_sessions[session_id] = metadata
                    self.active_sessions[session_id]["messages"] = []
                
                logger.debug(f"Starting new session with job role: {metadata.get('job_role')}")
        except Exception as e:
            # If there's an error loading the session, start with a clean state
            logger.error(f"Error loading session {session_id}: {e}")
            metadata = {
                "job_role": job_role or self.job_role,
                "seniority_level": seniority_level or self.seniority_level,
                "required_skills": required_skills or self.required_skills, 
                "job_description": job_description or self.job_description,
                STAGE_KEY: InterviewStage.INTRODUCTION.value,
            }
        
        # Add the user message
        human_msg = HumanMessage(content=user_message)
        messages.append(human_msg)
        
        # Check for candidate name in the user message if not already known
        if not candidate_name:
            # First try with simple name patterns
            name_match = self._extract_candidate_name([human_msg])
            if name_match:
                candidate_name = name_match
                logger.info(f"Extracted candidate name from new message: {candidate_name}")
                
                # Update metadata with the new name
                metadata[CANDIDATE_NAME_KEY] = candidate_name
                
                # Immediately update session metadata with the new name
                if self.session_manager:
                    self.session_manager.update_session_metadata(session_id, metadata)
                    logger.info(f"Updated session metadata with candidate name: {candidate_name}")
        
        # Add to transcript for later retrieval
        if "transcript" not in metadata:
            metadata["transcript"] = []
        
        # Create or update system message with context
        system_prompt = INTERVIEW_SYSTEM_PROMPT.format(
            candidate_name=candidate_name or "[Not provided yet]",
            interview_id=session_id,
            current_stage=interview_stage,
            job_role=job_role_value,
            seniority_level=seniority_level_value,
            required_skills=", ".join(required_skills_value) if isinstance(required_skills_value, list) else str(required_skills_value),
            job_description=job_description_value
        )
        
        # Prepend system message if not already present
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=system_prompt)] + messages
        else:
            # Update existing system message to reflect current stage
            messages[0] = SystemMessage(content=system_prompt)
        
        # Properly initialize our InterviewState class
        state = InterviewState(
            messages=messages,
            candidate_name=candidate_name,
            job_role=job_role_value,
            seniority_level=seniority_level_value,
            required_skills=required_skills_value,
            job_description=job_description_value,
            interview_stage=interview_stage,
            session_id=session_id,
            user_id=user_id
        )
        
        # Add the StateGraph config
        config = {
            "configurable": {
                "thread_id": session_id,
                "session_id": session_id,
                "user_id": user_id,
            }
        }
        
        # Call the workflow
        try:
            logger.info(f"Running workflow for session {session_id}")
            
            # Use runnable protocol with config
            output = self.workflow.invoke(state, config=config)
            
            # Extract response from output
            if not output:
                logger.error("No output returned from workflow")
                ai_message_content = "I apologize, but I encountered an issue. Please try again."
                tool_calls = []
            else:
                # Handle different output types (dict or InterviewState)
                if isinstance(output, dict):
                    # Extract messages from dictionary
                    all_messages = output.get("messages", [])
                    # Extract other state values
                    candidate_name = output.get("candidate_name", candidate_name)
                    interview_stage = output.get("interview_stage", interview_stage)
                else:
                    # Extract from InterviewState
                    all_messages = output.messages if hasattr(output, "messages") else []
                    # Extract other state values if available
                    candidate_name = output.candidate_name if hasattr(output, "candidate_name") else candidate_name
                    interview_stage = output.interview_stage if hasattr(output, "interview_stage") else interview_stage
                
                # Get AI messages
                ai_messages = [msg for msg in all_messages if isinstance(msg, AIMessage)]
                
                if not ai_messages:
                    logger.error("No AI messages found in response")
                    ai_message_content = "I apologize, but I encountered an issue. Please try again."
                    tool_calls = []
                else:
                    # Get the latest AI message content
                    response = ai_messages[-1]
                    ai_message_content = safe_extract_content(response)
                    tool_calls = getattr(response, "tool_calls", []) if hasattr(response, "tool_calls") else []
                    
                    # Update metadata with candidate name and stage
                    if candidate_name:
                        metadata[CANDIDATE_NAME_KEY] = candidate_name
                    
                    # Attempt to extract name from the conversation if not already set
                    if not candidate_name:
                        name_match = self._extract_candidate_name(all_messages)
                        if name_match:
                            candidate_name = name_match
                            metadata[CANDIDATE_NAME_KEY] = candidate_name
                            logger.info(f"Extracted candidate name from conversation: {candidate_name}")
                    
                    # Update stage in metadata
                    metadata[STAGE_KEY] = interview_stage
            
            # Save the updated session
            try:
                if self.session_manager:
                    # Update metadata including transcript
                    self.session_manager.update_session_metadata(session_id, metadata)
                    
                    # Update session with the updated messages
                    # Transcript includes all messages
                    if "transcript" in metadata:
                        # Add the user message to transcript
                        metadata["transcript"].append({
                            "role": "user",
                            "content": user_message,
                            "timestamp": datetime.now().isoformat()
                        })
                        
                        # Add the AI response to transcript
                        metadata["transcript"].append({
                            "role": "assistant",
                            "content": ai_message_content,
                            "timestamp": datetime.now().isoformat()
                        })
                        
                        self.session_manager.update_session_metadata(session_id, metadata)
                    
                    # Update activity timestamp
                    self.session_manager.update_session_activity(session_id)
                    
                    # Save all messages
                    self.session_manager.update_session_messages(session_id, all_messages)
                else:
                    # In-memory storage
                    self.active_sessions[session_id].update(metadata)
                    
                    # Update transcript
                    if "transcript" in self.active_sessions[session_id]:
                        self.active_sessions[session_id]["transcript"].append({
                            "role": "user",
                            "content": user_message,
                            "timestamp": datetime.now().isoformat()
                        })
                        self.active_sessions[session_id]["transcript"].append({
                            "role": "assistant",
                            "content": ai_message_content,
                            "timestamp": datetime.now().isoformat()
                        })
                    
                    # Update messages
                    self.active_sessions[session_id]["messages"] = all_messages
                    
                    # Update timestamp
                    self.active_sessions[session_id]["last_active"] = datetime.now().isoformat()
            except Exception as e:
                logger.error(f"Error saving session {session_id}: {e}")
            
            return ai_message_content, session_id
        except Exception as e:
            logger.error(f"Error in run_interview: {e}")
            return "I apologize, but I encountered an issue. Please try again.", session_id
    
    def resume_interview(self, user_id: str, session_id: str, query: Optional[str] = None) -> Tuple[str, Dict[str, Any]]:
        """
        Resume an existing interview session.
        
        Args:
            user_id: User identifier
            session_id: Session identifier
            query: Optional query string
            
        Returns:
            Tuple of (summary, session_data)
        """
        # Validate session exists
        try:
            if self.session_manager:
                session_data = self.session_manager.get_session(session_id)
                if not session_data:
                    return f"Session {session_id} not found.", {}
            else:
                # Use in-memory storage
                session_data = self.active_sessions.get(session_id)
                if not session_data:
                    return f"Session {session_id} not found.", {}
        except Exception as e:
            logger.error(f"Error retrieving session: {e}")
            return "Error retrieving session information.", {}
        
        # Get session metadata
        try:
            if self.session_manager:
                metadata = session_data.get("metadata", {})
                transcript = metadata.get("transcript", [])
                current_stage = metadata.get(STAGE_KEY, InterviewStage.INTRODUCTION.value)
            else:
                transcript = session_data.get("transcript", [])
                current_stage = session_data.get(STAGE_KEY, InterviewStage.INTRODUCTION.value)
        except Exception as e:
            logger.error(f"Error getting session metadata: {e}")
            transcript = []
            current_stage = InterviewStage.INTRODUCTION.value
        
        # Build summary message
        candidate_name = session_data.get("metadata", {}).get(CANDIDATE_NAME_KEY, "") if self.session_manager else session_data.get(CANDIDATE_NAME_KEY, "")
        created_at = session_data.get("created_at", "")
        
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at).strftime("%Y-%m-%d %H:%M:%S")
            except (ValueError, TypeError):
                pass
                
        # Get last few exchanges if available
        last_exchanges = ""
        if transcript:
            last_n = min(3, len(transcript))
            last_exchanges = "\n\n"
            for i in range(-last_n, 0):
                entry = transcript[i]
                last_exchanges += f"You: {entry.get('user', '')}\n"
                last_exchanges += f"Interviewer: {entry.get('ai', '')}\n\n"
        
        # Add stage information
        stage_info = f"Interview stage: {current_stage.capitalize()}"
        
        summary = f"Resuming interview session {session_id}"
        if candidate_name:
            summary += f" with {candidate_name}"
        if created_at:
            summary += f", started at {created_at}"
        summary += f". {stage_info}. This session has {len(transcript)} exchanges so far."
        summary += last_exchanges
        summary += "\nYou can continue the interview by typing your next response."
        
        return summary, session_data
    
    def _get_or_create_session(self, user_id: str) -> str:
        """
        Get an existing session or create a new one.
        
        Args:
            user_id: User identifier
            
        Returns:
            Session ID
        """
        try:
            if self.session_manager:
                # Try to get most recent active session for user
                session = self.session_manager.get_most_recent_session(user_id)
                if session:
                    return session["session_id"]
                
                # Create new session with initial interview stage
                session_id = self.session_manager.create_session(user_id)
                
                # Set initial interview stage
                self.session_manager.update_session_metadata(
                    session_id, 
                    {STAGE_KEY: InterviewStage.INTRODUCTION.value}
                )
                
                return session_id
            else:
                # In-memory session management
                # Check for existing active session
                for session_id, session_data in self.active_sessions.items():
                    if session_data.get("user_id") == user_id:
                        # Check if session is still active (not expired)
                        last_active = datetime.fromisoformat(session_data.get("last_active", ""))
                        time_diff = (datetime.now() - last_active).total_seconds() / 60
                        
                        if time_diff < 60:  # 1 hour timeout
                            logger.info(f"Using existing session {session_id} for user {user_id}")
                            return session_id
                
                # Create new session
                session_id = str(uuid.uuid4())
                self.active_sessions[session_id] = {
                    "user_id": user_id,
                    "interview_id": session_id,
                    "candidate_name": "",  # Will be populated during conversation
                    "created_at": datetime.now().isoformat(),
                    "last_active": datetime.now().isoformat(),
                    "interview_stage": InterviewStage.INTRODUCTION.value
                }
                
                logger.info(f"Created new session {session_id} for user {user_id}")
                return session_id
        except Exception as e:
            logger.error(f"Error in get_or_create_session: {e}")
            # Generate a fallback session ID
            session_id = str(uuid.uuid4())
            self.active_sessions[session_id] = {
                "user_id": user_id,
                "interview_id": session_id,
                "created_at": datetime.now().isoformat(),
                "last_active": datetime.now().isoformat(),
                "interview_stage": InterviewStage.INTRODUCTION.value
            }
            logger.info(f"Created fallback session {session_id} for user {user_id}")
            return session_id
    
    def list_active_sessions(self) -> Dict[str, Dict[str, Any]]:
        """
        List all active interview sessions.
        
        Returns:
            Dictionary of active sessions
        """
        try:
            if self.session_manager:
                # Get sessions from MongoDB
                sessions = self.session_manager.list_active_sessions()
                return {s["session_id"]: s for s in sessions}
            else:
                # Filter out expired sessions from in-memory storage
                now = datetime.now()
                active_sessions = {}
                
                for session_id, session_data in self.active_sessions.items():
                    last_active = datetime.fromisoformat(session_data.get("last_active", ""))
                    time_diff = (now - last_active).total_seconds() / 60
                    
                    if time_diff < 60:  # 1 hour timeout
                        active_sessions[session_id] = session_data
                
                return active_sessions
        except Exception as e:
            logger.error(f"Error listing active sessions: {e}")
            return {}
    
    def get_user_sessions(self, user_id: str, include_completed: bool = False) -> List[Dict[str, Any]]:
        """
        Get all sessions for a user.
        
        Args:
            user_id: User identifier
            include_completed: Whether to include completed sessions
            
        Returns:
            List of session details
        """
        try:
            if self.session_manager:
                # Get sessions from MongoDB
                return self.session_manager.get_user_sessions(user_id, include_completed)
            else:
                # Get sessions from in-memory storage
                sessions = []
                
                for session_id, session_data in self.active_sessions.items():
                    if session_data.get("user_id") == user_id:
                        sessions.append(session_data)
                
                return sessions
        except Exception as e:
            logger.error(f"Error getting user sessions: {e}")
            return []
    
    def cleanup(self):
        """Clean up resources."""
        if hasattr(self, 'checkpointer'):
            try:
                # Store a reference to the client before we potentially lose it
                mongo_client = None
                if hasattr(self.checkpointer, 'client'):
                    mongo_client = self.checkpointer.client
                
                # Close the checkpointer if it has a close method
                if hasattr(self.checkpointer, 'close'):
                    self.checkpointer.close()
                
                # Close the MongoDB client if we have it
                if mongo_client and hasattr(mongo_client, 'close'):
                    mongo_client.close()
                    logger.info("MongoDB client closed")
                    
                logger.info("Checkpointer resources cleaned up")
            except Exception as e:
                logger.error(f"Error closing checkpointer: {e}")
        
        if hasattr(self, 'session_manager') and hasattr(self.session_manager, 'close'):
            try:
                self.session_manager.close()
                logger.info("Session manager resources cleaned up")
            except Exception as e:
                logger.error(f"Error closing session manager: {e}")
    
    def _extract_candidate_name(self, messages: List[BaseMessage]) -> str:
        """
        Extract candidate name from conversation.
        
        Args:
            messages: List of conversation messages
            
        Returns:
            Candidate name or empty string if not found
        """
        # Skip if we have fewer than 3 messages
        if len(messages) < 3:
            return ""
        
        # Create a prompt for the model to extract the name
        extract_prompt = [
            SystemMessage(content="You are a helpful assistant. Your task is to extract the candidate's name from the conversation, if mentioned. Respond with just the name, or 'Unknown' if no name is found."),
            HumanMessage(content=f"Extract the candidate's name from this conversation: {', '.join([m.content for m in messages if hasattr(m, 'content')])}"),
        ]
        
        try:
            # Use the same model but with no tools
            raw_model = ChatGoogleGenerativeAI(
                model=get_llm_config()["model"],
                temperature=0.0
            )
            
            response = raw_model.invoke(extract_prompt)
            
            # Process response
            name = response.content.strip()
            if name.lower() in ["unknown", "not mentioned", "no name found", "none"]:
                return ""
                
            # Basic cleaning
            name = name.replace("Name:", "").replace("Candidate name:", "").strip()
            
            logger.info(f"Extracted candidate name: {name}")
            return name
        except Exception as e:
            logger.error(f"Error extracting candidate name: {e}")
            return ""
                
    def __enter__(self):
        """Context manager entry."""
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.cleanup()

# Import for resume_interview method
import asyncio 

async def continue_after_challenge(self, user_id: str, session_id: str, message: str, challenge_completed: bool = True) -> Tuple[str, Dict[str, Any]]:
    """
    Continue an interview after a coding challenge has been completed.
    
    Args:
        user_id: User identifier
        session_id: Session identifier
        message: Message to include as context
        challenge_completed: Whether the challenge was completed successfully
        
    Returns:
        Tuple of (AI response, session data)
    """
    try:
        # Get session data
        if self.session_manager:
            session = self.session_manager.get_session(session_id)
            if not session:
                return f"Session {session_id} not found.", {}
            
            metadata = session.get("metadata", {})
        else:
            # Use in-memory storage
            if session_id not in self.active_sessions:
                return f"Session {session_id} not found.", {}
            
            session = self.active_sessions[session_id]
            metadata = session
            
        # Update session with challenge result
        metadata["resuming_from_challenge"] = True
        metadata["challenge_completed"] = challenge_completed
        metadata[STAGE_KEY] = InterviewStage.TECHNICAL_QUESTIONS.value if challenge_completed else InterviewStage.CODING_CHALLENGE.value
        
        # Save metadata updates
        if self.session_manager:
            self.session_manager.update_session_metadata(session_id, metadata)
        
        # Run the interview with the challenge results message
        result = f"I've submitted my solution to the coding challenge. "
        if challenge_completed:
            result += "I believe I've completed it successfully."
        else:
            result += "I made some progress but couldn't fully complete it."
            
        # Add user's message if provided
        if message:
            result += f" {message}"
            
        # Run the interview with this context
        response, _ = await self.run_interview(user_id, result, session_id)
        
        return response, session
    except Exception as e:
        logger.error(f"Error continuing after challenge: {e}")
        return "I apologize, but I encountered an error processing your challenge submission. Let's continue with the interview.", {} 

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
