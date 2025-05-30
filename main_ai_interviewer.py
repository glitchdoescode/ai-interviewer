"""
Core AI Interviewer class that encapsulates all LangGraph components.

This module follows the architecture pattern from gizomobot, providing a unified
class that handles the entire interview process.
"""
import logging
import os
import uuid
import asyncio
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
from langchain_core.messages import RemoveMessage

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
7. Occasionally refer to yourself by name (e.g., "I'm {system_name}, and I'll be conducting your interview today")

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
- Introduction: Focus on building rapport and understanding the candidate's background
- Technical Questions: Assess depth of knowledge with progressive difficulty
- Coding Challenge: Evaluate problem-solving process, not just the solution. Only move to this stage if the role requires coding.
- Behavioral Questions: Look for evidence of soft skills and experience
- Feedback: Be constructive, balanced, and specific
- Conclusion: End on a positive note with clear next steps

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
                job_description: str = ""):
        """
        Initialize the AI Interviewer with the necessary components.
        
        Args:
            use_mongodb: Whether to use MongoDB for persistence
            connection_uri: Optional MongoDB connection URI
            job_role: Default job role for interviews
            seniority_level: Default seniority level
            required_skills: Default required skills
            job_description: Default job description
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
        
        # Set up memory management
        if use_mongodb:
            try:
                # Get database config
                db_config = get_db_config()
                mongodb_uri = connection_uri or db_config["uri"]
                
                # Initialize the InterviewMemoryManager for both short-term and long-term memory
                logger.info(f"Initializing Memory Manager with URI {mongodb_uri}")
                self.memory_manager = InterviewMemoryManager(
                    connection_uri=mongodb_uri,
                    db_name=db_config["database"], 
                    checkpoint_collection=db_config["sessions_collection"],
                    store_collection="interview_memory_store",
                    use_async=True  # Default to async checkpointer
                )
                
                # Initialize the checkpointer by calling async_setup
                try:
                    # Create an event loop if necessary and call async_setup
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            # We're already in an event loop, create a task
                            asyncio.create_task(self.memory_manager.async_setup())
                            logger.info("Created task to initialize async memory manager")
                        else:
                            # We have an event loop but it's not running
                            loop.run_until_complete(self.memory_manager.async_setup())
                            logger.info("Initialized async memory manager in existing event loop")
                    except RuntimeError:
                        # No event loop exists, create one
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(self.memory_manager.async_setup())
                        logger.info("Initialized async memory manager in new event loop")
                    
                    # Mark setup as complete
                    self.memory_manager.async_setup_completed = True
                except Exception as setup_error:
                    logger.error(f"Error during memory manager async_setup: {setup_error}")
                
                # Get the checkpointer for thread-level memory
                self.checkpointer = self.memory_manager.get_checkpointer()
                
                # Log checkpointer type for better debugging
                if hasattr(self.checkpointer, 'aget_tuple'):
                    logger.info(f"Using async MongoDB checkpointer: {self.checkpointer.__class__.__name__}")
                else:
                    logger.warning(f"Using synchronous MongoDB checkpointer: {self.checkpointer.__class__.__name__}. This may cause issues with async operations.")
                
                # Get the store for cross-thread memory
                self.store = self.memory_manager.get_store()
                logger.info(f"Using MongoDB store: {self.store.__class__.__name__}")
                
                # Initialize the session manager for backward compatibility
                self.session_manager = SessionManager(
                    connection_uri=mongodb_uri,
                    database_name=db_config["database"],
                    collection_name=db_config["metadata_collection"],
                )
                
                logger.info("MongoDB memory manager initialized successfully")
            except Exception as e:
                # If there's an error with MongoDB, fall back to in-memory persistence
                logger.warning(f"Failed to connect to MongoDB: {e}. Falling back to in-memory persistence.")
                self.checkpointer = InMemorySaver()
                self.session_manager = None
                self.memory_manager = None
                self.store = None
                logger.info("Using in-memory persistence as fallback")
        else:
            # Use in-memory persistence
            self.checkpointer = InMemorySaver()
            self.session_manager = None
            self.memory_manager = None
            self.store = None
            logger.info("Using in-memory persistence")
        
        # Initialize workflow
        self.workflow = self._initialize_workflow()
        
        # Session tracking
        self.active_sessions = {}
    
    def _setup_tools(self):
        """Set up the tools for the interviewer."""
        # Define tools
        self.tools = [
            start_coding_challenge,
            submit_code_for_challenge,
            get_coding_hint,
            suggest_code_improvements,
            complete_code,
            review_code_section,
            generate_interview_question,
            analyze_candidate_response
        ]
    
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
                    
                    # Update message count for context management
                    updated_state["message_count"] = state.get("message_count", 0) + len(tool_result.get("messages", []))
                    
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
        workflow.add_conditional_edges(
            "manage_context",
            lambda state: "model" if self.should_continue(state) == "tools" else "end",
            {
                "model": "model",
                "end": END
            }
        )
        
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
            message_count = state.get("message_count", 0)
            max_messages = state.get("max_messages_before_summary", 20)
        else:
            # Assume it's a MessagesState or InterviewState object
            if not hasattr(state, "messages") or not state.messages:
                # No messages yet
                return "end"
            messages = state.messages
            message_count = getattr(state, "message_count", 0)
            max_messages = getattr(state, "max_messages_before_summary", 20)
        
        # Check if we need to manage context due to message length
        if len(messages) > max_messages:
            return "manage_context"
        
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
                conversation_summary = state.get("conversation_summary", "")
                message_count = state.get("message_count", len(messages))
                max_messages_before_summary = state.get("max_messages_before_summary", 20)
                # Default to True for requires_coding if not specified
                requires_coding = state.get("requires_coding", True)
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
                conversation_summary = state.conversation_summary
                message_count = state.message_count
                max_messages_before_summary = state.max_messages_before_summary
                # Default to True for requires_coding if not specified
                requires_coding = getattr(state, "requires_coding", True)
            
            # Create or update system message with context
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
            
            # Add cross-thread memory if available
            if self.memory_manager and candidate_name and user_id:
                try:
                    # Get candidate profile from memory store
                    candidate_profile = self.memory_manager.get_candidate_profile(user_id)
                    
                    if candidate_profile:
                        # Add profile information to the system prompt
                        profile_info = "\n\nCANDIDATE HISTORY FROM PREVIOUS SESSIONS:\n"
                        
                        if "key_skills" in candidate_profile and candidate_profile["key_skills"]:
                            skills = candidate_profile["key_skills"]
                            profile_info += f"- Previously demonstrated skills: {', '.join(skills[:5])}\n"
                        
                        if "notable_experiences" in candidate_profile and candidate_profile["notable_experiences"]:
                            experiences = candidate_profile["notable_experiences"]
                            profile_info += f"- Notable past experiences: {'; '.join(experiences[:3])}\n"
                        
                        if "strengths" in candidate_profile and candidate_profile["strengths"]:
                            strengths = candidate_profile["strengths"]
                            profile_info += f"- Previously identified strengths: {', '.join(strengths[:3])}\n"
                        
                        if "areas_for_improvement" in candidate_profile and candidate_profile["areas_for_improvement"]:
                            improvements = candidate_profile["areas_for_improvement"]
                            profile_info += f"- Areas for improvement: {', '.join(improvements[:3])}\n"
                        
                        if "coding_ability" in candidate_profile and candidate_profile["coding_ability"]:
                            coding = candidate_profile["coding_ability"]
                            if "languages" in coding and coding["languages"]:
                                profile_info += f"- Coding languages: {', '.join(coding['languages'])}\n"
                        
                        # Add the profile info to the system prompt
                        system_prompt += profile_info
                except Exception as e:
                    logger.error(f"Error retrieving candidate profile: {e}")
            
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
            
            # Increment message count for new message
            new_message_count = message_count + 1
            
            # Return the appropriate state type based on input
            if isinstance(state, dict):
                # Return a dictionary with updated values
                updated_state = dict(state)
                updated_state["messages"] = messages + [ai_message]
                updated_state["candidate_name"] = candidate_name
                updated_state["interview_stage"] = new_stage if new_stage != interview_stage else interview_stage
                updated_state["message_count"] = new_message_count
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
                    user_id=user_id,
                    conversation_summary=conversation_summary,
                    message_count=new_message_count,
                    max_messages_before_summary=max_messages_before_summary
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
                    user_id=state.user_id if hasattr(state, "user_id") else "",
                    conversation_summary=state.conversation_summary if hasattr(state, "conversation_summary") else "",
                    message_count=state.message_count if hasattr(state, "message_count") else 0,
                    max_messages_before_summary=state.max_messages_before_summary if hasattr(state, "max_messages_before_summary") else 20
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
        # Get human messages for better analysis
        human_messages = [m for m in messages if isinstance(m, HumanMessage)]
        human_message_count = len(human_messages)
        
        # Get the latest human message (if any)
        latest_human_message = human_messages[-1].content.lower() if human_messages else ""
        
        # Extract AI message content
        ai_content = ai_message.content.lower() if hasattr(ai_message, 'content') else ""
        
        # Check for digression or clarification patterns
        clarification_patterns = [
            "could you explain", "what do you mean", "can you clarify", 
            "i'm not sure", "don't understand", "please explain", 
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
                # Extract state from messages if available
                job_role = None
                for msg in messages:
                    if isinstance(msg, SystemMessage) and hasattr(msg, 'content'):
                        # Try to extract job role from system message
                        match = re.search(r"job role: (.+?)[\n\.]", msg.content, re.IGNORECASE)
                        if match:
                            job_role = match.group(1).strip()
                            break
                
                # Default job roles that should include coding challenges
                coding_required_roles = [
                    "software engineer", "developer", "programmer", "frontend developer", 
                    "backend developer", "full stack developer", "web developer",
                    "mobile developer", "app developer", "data scientist", "devops engineer"
                ]
                
                # Check if the job role requires coding
                job_role_requires_coding = False
                if job_role:
                    # Check if the job role contains any of our coding-required roles
                    job_role_lower = job_role.lower()
                    job_role_requires_coding = any(role in job_role_lower for role in coding_required_roles)
                    
                    # If we have a metadata field specifically for this, check that too
                    # This would be set if a JobRole.requires_coding field was provided
                    for msg in messages:
                        if isinstance(msg, SystemMessage) and hasattr(msg, 'content'):
                            if "requires coding: true" in msg.content.lower():
                                job_role_requires_coding = True
                                break
                            elif "requires coding: false" in msg.content.lower():
                                job_role_requires_coding = False
                                break
                else:
                    # Default to requiring coding if we can't determine the job role
                    job_role_requires_coding = True
                
                if job_role_requires_coding:
                    logger.info(f"Transitioning from TECHNICAL_QUESTIONS to CODING_CHALLENGE stage for job role: {job_role}")
                    return InterviewStage.CODING_CHALLENGE.value
                else:
                    logger.info(f"Skipping coding challenge for job role: {job_role} (coding not required)")
            
            # If we've had enough substantive technical exchanges, move to behavioral questions
            # Use a combination of count and content analysis
            if human_message_count >= 5 and not has_coding_trigger:
                # Check if we've asked enough substantive technical questions
                substantive_qa = self._count_substantive_exchanges(messages)
                if substantive_qa >= 3:
                    logger.info("Transitioning from TECHNICAL_QUESTIONS to BEHAVIORAL_QUESTIONS stage after substantive technical discussion")
                    return InterviewStage.BEHAVIORAL_QUESTIONS.value
        
        elif current_stage == InterviewStage.CODING_CHALLENGE.value:
            # Check if the candidate has submitted a solution and we should transition
            submission_keywords = [
                "submitted my solution", "finished the challenge", "completed the exercise",
                "here's my solution", "my code is ready", "implemented the solution",
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
                "let's talk about your experience", "tell me about a time", 
                "describe a situation", "how do you handle", "what would you do if"
            ])
            
            if behavioral_transition or human_message_count > 2:
                logger.info("Transitioning from FEEDBACK to BEHAVIORAL_QUESTIONS stage")
                return InterviewStage.BEHAVIORAL_QUESTIONS.value
        
        elif current_stage == InterviewStage.BEHAVIORAL_QUESTIONS.value:
            # After enough behavioral questions, move to conclusion
            # Check if we have enough substantive behavioral exchanges or AI is ready to conclude
            if has_conclusion_trigger or human_message_count >= 4:
                conclusion_ready = self._is_ready_for_conclusion(messages)
                if conclusion_ready:
                    logger.info("Transitioning from BEHAVIORAL_QUESTIONS to CONCLUSION stage")
                    return InterviewStage.CONCLUSION.value
        
        # By default, stay in the current stage
        return current_stage
    
    def _is_introduction_complete(self, human_messages: List[BaseMessage]) -> bool:
        """
        Determine if the introduction phase is complete based on message content.
        
        Args:
            human_messages: List of human messages in the conversation
            
        Returns:
            Boolean indicating if introduction is complete
        """
        # If we have less than 2 exchanges, introduction is not complete
        if len(human_messages) < 2:
            return False
        
        # Check if candidate has shared their name, background, or experience
        introduction_markers = [
            "experience with", "background in", "worked with", "my name is",
            "years of experience", "worked as", "skills in", "specialized in",
            "i am a", "i'm a", "currently working"
        ]
        
        # Combine all human messages and check for introduction markers
        all_content = " ".join([m.content.lower() for m in human_messages if hasattr(m, 'content')])
        has_introduction_info = any(marker in all_content for marker in introduction_markers)
        
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
        requires_coding_value = requires_coding if requires_coding is not None else True
        conversation_summary = ""
        message_count = 0
        max_messages_before_summary = 20  # Default value
        
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
                conversation_summary = metadata.get("conversation_summary", "")
                message_count = metadata.get("message_count", len(messages))
                max_messages_before_summary = metadata.get("max_messages_before_summary", 20)
                
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
                
                if requires_coding is not None and "requires_coding" not in metadata:
                    metadata["requires_coding"] = requires_coding
                    requires_coding_value = requires_coding
                else:
                    requires_coding_value = metadata.get("requires_coding", True)
                
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
                    "requires_coding": requires_coding if requires_coding is not None else True,
                    STAGE_KEY: InterviewStage.INTRODUCTION.value,
                    "conversation_summary": "",
                    "message_count": 0,
                    "max_messages_before_summary": 20
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
                "requires_coding": requires_coding if requires_coding is not None else True,
                STAGE_KEY: InterviewStage.INTRODUCTION.value,
                "conversation_summary": "",
                "message_count": 0,
                "max_messages_before_summary": 20
            }
        
        # Detect potential digression if enabled
        if handle_digression and len(messages) > 2:
            is_digression = self._detect_digression(user_message, messages, interview_stage)
            
            # If this is a digression, add a note in the message history for context
            if is_digression:
                logger.info(f"Detected potential digression: '{user_message}'")
                
                # Check if we've already marked this as a digression to avoid multiple markers
                if not any("CONTEXT: Candidate is digressing" in m.content for m in messages[-3:] if isinstance(m, AIMessage) and hasattr(m, 'content')):
                    # Add a system message noting the digression for better context
                    digression_note = AIMessage(content=f"CONTEXT: Candidate is digressing from the interview topic. I'll acknowledge their point and gently guide the conversation back to relevant technical topics.")
                    messages.append(digression_note)
                    logger.info("Added digression context note to message history")
                
                # No need to update the interview stage for digressions
                metadata["handling_digression"] = True
            else:
                # If previously handling a digression, clear the flag
                if metadata.get("handling_digression"):
                    metadata.pop("handling_digression")
                
        # Add the user message
        human_msg = HumanMessage(content=user_message)
        messages.append(human_msg)
        
        # Increment message count for context management
        message_count += 1
        
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
        
        # Create or update system message with context including conversation summary
        system_prompt = INTERVIEW_SYSTEM_PROMPT.format(
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
        
        # Prepend system message if not already present
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=system_prompt)] + messages
        else:
            # Update existing system message to reflect current stage and summary
            messages[0] = SystemMessage(content=system_prompt)
        
        # Properly initialize our InterviewState class
        state = InterviewState(
            messages=messages,
            candidate_name=candidate_name,
            job_role=job_role_value,
            seniority_level=seniority_level_value,
            required_skills=required_skills_value,
            job_description=job_description_value,
            requires_coding=requires_coding_value,
            interview_stage=interview_stage,
            session_id=session_id,
            user_id=user_id,
            conversation_summary=conversation_summary,
            message_count=message_count,
            max_messages_before_summary=max_messages_before_summary
        )
        
        # Add the StateGraph config
        config = {
            "configurable": {
                "thread_id": session_id,
                "session_id": session_id,
                "user_id": user_id,
            }
        }
        
        # Store a message for the graph to process
        human_message = HumanMessage(content=user_message)
        
        # Run the graph with appropriate method based on checkpointer type
        final_chunk = None
        try:
            # Check if we're using an async checkpointer
            is_async_checkpointer = hasattr(self.checkpointer, 'aget_tuple')
            
            # Use the appropriate streaming method based on the checkpointer type
            if is_async_checkpointer:
                # For async checkpointer
                logger.info(f"Using async streaming with thread_id: {session_id}")
                async for chunk in self.workflow.astream(
                    {"messages": [human_message]},
                    config=config,
                    stream_mode="values",
                ):
                    final_chunk = chunk
            else:
                # For sync checkpointer
                logger.info(f"Using synchronous streaming with thread_id: {session_id}")
                for chunk in self.workflow.stream(
                    {"messages": [human_message]},
                    config=config,
                    stream_mode="values",
                ):
                    final_chunk = chunk
        except NotImplementedError as e:
            # Handle the specific error when using wrong checkpointer type
            logger.error(f"NotImplementedError - likely mismatched checkpointer type: {str(e)}")
            error_message = str(e)
            
            # Give specific guidance based on the error
            if "astream" in error_message and not is_async_checkpointer:
                # Trying to use astream with a sync checkpointer
                logger.error("Async operation called with synchronous checkpointer. Use AsyncMongoDBSaver instead of MongoDBSaver")
                # Try fallback to sync method
                try:
                    logger.info("Attempting fallback to synchronous stream method")
                    for chunk in self.workflow.stream(
                        {"messages": [human_message]},
                        config=config,
                        stream_mode="values",
                    ):
                        final_chunk = chunk
                except Exception as fallback_error:
                    logger.error(f"Fallback to sync method failed: {fallback_error}")
                    return f"I apologize, but there was an error processing your request. The system is using an incompatible checkpoint configuration. Please contact support.", session_id
            elif "stream" in error_message and is_async_checkpointer:
                # Trying to use stream with an async checkpointer
                logger.error("Synchronous operation called with async checkpointer. Use MongoDBSaver instead of AsyncMongoDBSaver")
                # Try fallback to async method if we're in an event loop
                try:
                    logger.info("Attempting fallback to asynchronous stream method")
                    async for chunk in self.workflow.astream(
                        {"messages": [human_message]},
                        config=config,
                        stream_mode="values",
                    ):
                        final_chunk = chunk
                except Exception as fallback_error:
                    logger.error(f"Fallback to async method failed: {fallback_error}")
                    return f"I apologize, but there was an error processing your request. The system is using an incompatible checkpoint configuration. Please contact support.", session_id
            else:
                return f"I apologize, but there was an error processing your request. The system is using an incompatible checkpoint configuration. Please contact support. Error: {error_message}", session_id
        except Exception as e:
            import traceback
            error_tb = traceback.format_exc()
            logger.error(f"Error running interview graph: {str(e)}")
            logger.error(f"Traceback: {error_tb}")
            return f"I apologize, but there was an error processing your request. Please try again. Error: {str(e)}", session_id
        
        # Extract the AI response from the final chunk
        if final_chunk and "messages" in final_chunk and len(final_chunk["messages"]) > 0:
            for msg in reversed(final_chunk["messages"]):
                if isinstance(msg, AIMessage):
                    ai_response = msg.content
                    logger.info(f"AI response generated for session {session_id}")
                    
                    # Update cross-thread memory if needed
                    if self.memory_manager:
                        try:
                            # Extract candidate insights from the conversation
                            insights = self._extract_interview_insights(final_chunk["messages"])
                            
                            # Update candidate profile in long-term memory
                            if insights and "candidate_details" in insights:
                                self.memory_manager.save_candidate_profile(user_id, insights)
                            
                            # Save interview memory for this session
                            self.memory_manager.save_interview_memory(
                                session_id=session_id,
                                memory_type="insights",
                                memory_data={"insights": insights}
                            )
                        except Exception as e:
                            logger.error(f"Error updating memory: {e}")
                    
                    return ai_response, session_id
        
        # Fallback response if no AI message found
        return "I'm sorry, I couldn't generate a proper response. Please try again.", session_id
    
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
            user_id: User ID to get sessions for
            include_completed: Whether to include completed sessions
            
        Returns:
            List of sessions with metadata
        """
        return self.session_manager.get_user_sessions(user_id, include_completed)
        
    def get_code_snapshots(self, session_id: str, challenge_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get code evolution snapshots for a session.
        
        This method retrieves the code snapshots stored for a session, which track
        the evolution of code during coding challenges. Optionally filter by challenge ID.
        
        Args:
            session_id: Session ID to get snapshots for
            challenge_id: Optional challenge ID to filter by
            
        Returns:
            List of code snapshots with metadata, sorted by timestamp
        """
        if not self.session_manager:
            logger.error("Session manager not available")
            return []
            
        session = self.session_manager.get_session(session_id)
        if not session:
            logger.error(f"Session {session_id} not found")
            return []
            
        metadata = session.get("metadata", {})
        snapshots = metadata.get("code_snapshots", [])
        
        # Filter by challenge ID if provided
        if challenge_id:
            snapshots = [s for s in snapshots if s.get("challenge_id") == challenge_id]
            
        # Sort by timestamp
        snapshots.sort(key=lambda s: s.get("timestamp", ""))
        
        return snapshots

    def cleanup(self):
        """Clean up resources."""
        if hasattr(self, 'memory_manager') and self.memory_manager:
            try:
                # Check if we're using an async memory manager
                if hasattr(self.memory_manager, 'use_async') and self.memory_manager.use_async:
                    # Create a temporary event loop to run the async close
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            # If we're already in an event loop, create a task
                            asyncio.create_task(self.memory_manager.aclose())
                            logger.info("Created task to close async memory manager")
                        else:
                            # If not in an event loop, run the coroutine
                            loop.run_until_complete(self.memory_manager.aclose())
                            logger.info("Closed async memory manager")
                    except RuntimeError:
                        # If no event loop is available, create a new one
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(self.memory_manager.aclose())
                        loop.close()
                        logger.info("Closed async memory manager with new event loop")
                else:
                    # Use synchronous close
                    self.memory_manager.close()
                    logger.info("Memory manager resources cleaned up")
            except Exception as e:
                logger.error(f"Error closing memory manager: {e}")
        elif hasattr(self, 'checkpointer'):
            try:
                # Store a reference to the client before we potentially lose it
                mongo_client = None
                if hasattr(self.checkpointer, 'client'):
                    mongo_client = self.checkpointer.client
                elif hasattr(self.checkpointer, 'async_client'):
                    mongo_client = self.checkpointer.async_client
                
                # Check if it's an async checkpointer
                if hasattr(self.checkpointer, 'aclose'):
                    # Create a temporary event loop to run the async close
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            # If we're already in an event loop, create a task
                            asyncio.create_task(self.checkpointer.aclose())
                            logger.info("Created task to close async checkpointer")
                        else:
                            # If not in an event loop, run the coroutine
                            loop.run_until_complete(self.checkpointer.aclose())
                            logger.info("Closed async checkpointer")
                    except RuntimeError:
                        # If no event loop is available, create a new one
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(self.checkpointer.aclose())
                        loop.close()
                        logger.info("Closed async checkpointer with new event loop")
                # Close the checkpointer if it has a close method
                elif hasattr(self.checkpointer, 'close'):
                    self.checkpointer.close()
                
                # Close the MongoDB client if we have it
                if mongo_client:
                    if hasattr(mongo_client, 'close'):
                        mongo_client.close()
                        logger.info("MongoDB client closed")
                    
                logger.info("Checkpointer resources cleaned up")
            except Exception as e:
                logger.error(f"Error closing checkpointer: {e}")
        
        if hasattr(self, 'session_manager') and self.session_manager and hasattr(self.session_manager, 'close'):
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
    
    async def continue_after_challenge(self, user_id: str, session_id: str, message: str, challenge_completed: bool = True) -> Tuple[str, Dict[str, Any]]:
        """
        Continue an interview after a coding challenge has been completed.
        
        Args:
            user_id: User identifier
            session_id: Session identifier
            message: Message to include as context (should contain coding evaluation details)
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
                
            # Update session with challenge result and transition to appropriate stage
            metadata["resuming_from_challenge"] = True
            metadata["challenge_completed"] = challenge_completed
            
            # Extract coding evaluation data if available
            coding_evaluation = metadata.get("coding_evaluation", {})
            
            # Choose next stage based on challenge completion
            if challenge_completed:
                # If completed successfully, move to feedback stage
                next_stage = InterviewStage.FEEDBACK.value
                logger.info(f"Challenge completed successfully, moving to {next_stage} stage")
            else:
                # If not completed, remain in coding challenge stage
                next_stage = InterviewStage.CODING_CHALLENGE.value
                logger.info(f"Challenge not completed, staying in {next_stage} stage")
                
            metadata[STAGE_KEY] = next_stage
            
            # Save metadata updates
            if self.session_manager:
                self.session_manager.update_session_metadata(session_id, metadata)
            
            # Prepare context message for continuing the interview
            feedback_context = ""
            if coding_evaluation:
                # Add structured evaluation data to provide context for the AI
                test_results = coding_evaluation.get("test_results", {})
                passed = test_results.get("passed", 0) 
                total = test_results.get("total", 0)
                feedback = coding_evaluation.get("feedback", "")
                quality = coding_evaluation.get("quality_metrics", {})
                
                if passed and total:
                    feedback_context += f" My solution passed {passed} out of {total} test cases. "
                
                if feedback:
                    feedback_context += f"The feedback was: {feedback} "
                    
                if quality:
                    # Add any quality metrics highlights
                    if "complexity" in quality:
                        feedback_context += f"Code complexity was rated as {quality.get('complexity')}. "
                        
                    if "readability" in quality:
                        feedback_context += f"Readability was {quality.get('readability')}. "
                        
            # Combine message with generated feedback context
            result = f"I've submitted my solution to the coding challenge. "
            if challenge_completed:
                result += "I believe I've completed it successfully."
            else:
                result += "I made some progress but couldn't fully complete it."
            
            # Add feedback context if available and not redundant with message
            if feedback_context and not any(part in message.lower() for part in feedback_context.lower().split(". ")):
                result += feedback_context
                
            # Add user's message if provided and not already included
            if message and message not in result:
                result += f" {message}"
                
            # Run the interview with this context
            response, _ = await self.run_interview(user_id, result, session_id)
            
            return response, session
        except Exception as e:
            logger.error(f"Error continuing after challenge: {e}")
            return "I apologize, but I encountered an error processing your challenge submission. Let's continue with the interview.", {}
                
    def __enter__(self):
        """Context manager entry."""
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.cleanup()

    def _extract_interview_insights(self, messages: List[BaseMessage], current_insights: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Extract key interview insights from messages to retain critical information
        even when messages are summarized.
        
        Args:
            messages: List of messages to extract insights from
            current_insights: Current insights dictionary to update
            
        Returns:
            Dictionary of structured insights about the candidate
        """
        # Initialize insights with existing data or create new dict
        insights = current_insights or {
            "candidate_details": {
                "name": "",
                "years_of_experience": None,
                "current_role": "",
                "education": "",
                "location": "",
            },
            "key_skills": [],
            "notable_experiences": [],
            "strengths": [],
            "areas_for_improvement": [],
            "coding_ability": {
                "assessed": False,
                "languages": [],
                "frameworks": [],
                "level": "",
                "challenge_results": []
            },
            "communication_ability": "",
            "interview_progress": {
                "questions_asked": [],
                "completed_stages": []
            },
            "extracted_at": datetime.now().isoformat()
        }
        
        try:
            # If we have fewer than 5 messages, there's not much to extract yet
            if len(messages) < 5:
                return insights
                
            # Use the summarization model to extract structured insights
            # Build a prompt that asks for specific structured information
            extraction_prompt = [
                SystemMessage(content="""You are an expert at analyzing technical interviews and extracting structured information.
                Extract key information from this interview conversation into the following structured format.
                Only include information that was explicitly mentioned; don't infer or make up details.
                
                Format your response as a valid JSON object with these fields:
                {
                    "candidate_details": {
                        "name": "Candidate's name if mentioned",
                        "years_of_experience": "Years of experience in relevant fields (number or range)",
                        "current_role": "Current job title if mentioned",
                        "education": "Educational background if mentioned",
                        "location": "Location if mentioned"
                    },
                    "key_skills": ["List of skills the candidate mentioned having"],
                    "notable_experiences": ["Brief descriptions of notable projects or achievements mentioned"],
                    "strengths": ["Areas where the candidate demonstrated strength"],
                    "areas_for_improvement": ["Areas where the candidate could improve"],
                    "coding_ability": {
                        "assessed": true/false,
                        "languages": ["Programming languages mentioned"],
                        "frameworks": ["Frameworks mentioned"],
                        "level": "Assessment of coding ability if determined"
                    },
                    "communication_ability": "Assessment of communication skills if demonstrated"
                }
                """),
                HumanMessage(content="Here is the interview conversation to analyze:\n\n" + "\n".join([f"{m.type}: {m.content}" for m in messages if hasattr(m, 'content')]))
            ]
            
            # Call the model to extract insights
            extraction_response = self.summarization_model.invoke(extraction_prompt)
            extraction_text = extraction_response.content if hasattr(extraction_response, 'content') else ""
            
            # Parse the JSON response - handle potential JSON formatting issues
            import json
            import re
            
            # Look for JSON object in the response
            json_match = re.search(r'```json\s*(.*?)\s*```', extraction_text, re.DOTALL)
            if json_match:
                extraction_text = json_match.group(1)
            else:
                # Try to find JSON with curly braces
                json_match = re.search(r'({.*})', extraction_text, re.DOTALL)
                if json_match:
                    extraction_text = json_match.group(1)
            
            # Parse the JSON
            try:
                extracted_data = json.loads(extraction_text)
                
                # Update insights with extracted data, preserving existing data where appropriate
                if "candidate_details" in extracted_data:
                    for key, value in extracted_data["candidate_details"].items():
                        if value and (not insights["candidate_details"].get(key) or key == "name"):
                            insights["candidate_details"][key] = value
                
                # Update lists by adding new unique items
                for list_key in ["key_skills", "notable_experiences", "strengths", "areas_for_improvement"]:
                    if list_key in extracted_data and isinstance(extracted_data[list_key], list):
                        current_set = set(insights.get(list_key, []))
                        for item in extracted_data[list_key]:
                            if item and item not in current_set:
                                insights.setdefault(list_key, []).append(item)
                                current_set.add(item)
                
                # Update coding ability
                if "coding_ability" in extracted_data:
                    coding = extracted_data["coding_ability"]
                    insights_coding = insights["coding_ability"]
                    
                    # Only set assessed to True if it was previously False
                    if coding.get("assessed", False):
                        insights_coding["assessed"] = True
                    
                    # Add new programming languages
                    if "languages" in coding and isinstance(coding["languages"], list):
                        current_languages = set(insights_coding.get("languages", []))
                        for lang in coding["languages"]:
                            if lang and lang not in current_languages:
                                insights_coding.setdefault("languages", []).append(lang)
                                current_languages.add(lang)
                    
                    # Add new frameworks
                    if "frameworks" in coding and isinstance(coding["frameworks"], list):
                        current_frameworks = set(insights_coding.get("frameworks", []))
                        for framework in coding["frameworks"]:
                            if framework and framework not in current_frameworks:
                                insights_coding.setdefault("frameworks", []).append(framework)
                                current_frameworks.add(framework)
                    
                    # Update level if provided
                    if coding.get("level") and (not insights_coding.get("level") or len(coding["level"]) > len(insights_coding["level"])):
                        insights_coding["level"] = coding["level"]
                
                # Update communication ability if provided
                if extracted_data.get("communication_ability"):
                    insights["communication_ability"] = extracted_data["communication_ability"]
                
                # Update timestamp
                insights["extracted_at"] = datetime.now().isoformat()
                
                logger.info(f"Successfully extracted interview insights with {len(insights.get('key_skills', []))} skills and {len(insights.get('notable_experiences', []))} experiences")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON from extraction response: {e}")
                logger.debug(f"Raw extraction text: {extraction_text}")
        except Exception as e:
            logger.error(f"Error extracting interview insights: {e}")
        
        return insights

    async def extract_and_update_insights(self, session_id: str) -> Dict[str, Any]:
        """
        Manually extract and update insights for a session.
        
        This method can be called to extract structured insights from an interview session
        on demand, without having to wait for the automatic extraction during context management.
        
        Args:
            session_id: Session ID to extract insights for
            
        Returns:
            Dictionary of structured insights about the candidate
        """
        try:
            # Get session data
            if not self.session_manager:
                logger.error("Cannot extract insights: Session manager not available")
                return {}
                
            session = self.session_manager.get_session(session_id)
            if not session:
                logger.error(f"Cannot extract insights: Session {session_id} not found")
                return {}
                
            # Get messages and current insights
            messages = session.get("messages", [])
            metadata = session.get("metadata", {})
            current_insights = metadata.get("interview_insights", None)
            
            # Extract insights from messages
            logger.info(f"Manually extracting insights from session {session_id} with {len(messages)} messages")
            insights = self._extract_interview_insights(messages, current_insights)
            
            # Update metadata with new insights
            metadata["interview_insights"] = insights
            self.session_manager.update_session_metadata(session_id, metadata)
            
            logger.info(f"Successfully extracted and updated insights for session {session_id}")
            return insights
        except Exception as e:
            logger.error(f"Error in extract_and_update_insights: {e}")
            return {}
