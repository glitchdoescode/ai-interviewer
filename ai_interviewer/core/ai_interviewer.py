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

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END, MessagesState
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.prebuilt import ToolNode

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
from ai_interviewer.utils.mongodb_checkpointer import MongoDBCheckpointer
from ai_interviewer.utils.session_manager import SessionManager
from ai_interviewer.utils.config import get_db_config, get_llm_config, log_config
from ai_interviewer.utils.transcript import extract_messages_from_transcript

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
    FEEDBACK = "feedback"  # Providing feedback on performance
    CONCLUSION = "conclusion"  # Wrapping up the interview

# System prompt template
INTERVIEW_SYSTEM_PROMPT = """You are an AI Technical Interviewer for a software engineering position.

Your goal is to conduct a professional, thorough interview that assesses the candidate's technical skills, problem-solving abilities, and communication style.

INTERVIEW STRUCTURE:
1. If the candidate's name is not provided (or is blank/empty), your FIRST message must ask for their name and wait for a response.
2. Once you have the name, start with a friendly introduction, introduce yourself, and make the candidate comfortable.
3. Ask a series of technical questions related to software engineering, gradually increasing in difficulty.
4. Follow up on answers to probe deeper into the candidate's understanding.
5. Present a coding challenge when appropriate.
6. Provide constructive feedback on the candidate's solutions.
7. Conclude with a summary and next steps.

INTERACTION GUIDELINES:
- Always be respectful, professional, and unbiased.
- Keep your responses concise and clear.
- Present one question at a time and wait for a response.
- Use tools only when appropriate for the interview stage.
- Do not fabricate or assume information about the candidate's background.

AVAILABLE TOOLS:
- start_coding_challenge: Presents a coding challenge to the candidate
- submit_code_for_challenge: Evaluates the candidate's solution
- get_coding_hint: Provides hints if the candidate is stuck
- suggest_code_improvements: Offers ways to improve code
- complete_code: Helps complete partial code
- review_code_section: Reviews specific parts of code

Current Context:
Candidate name: {candidate_name}
Interview ID: {interview_id}
Current Stage: {current_stage}
"""

class AIInterviewer:
    """Main class that encapsulates the AI Interviewer functionality."""
    
    def __init__(self, use_mongodb: bool = True, connection_uri: Optional[str] = None):
        """
        Initialize the AI Interviewer with tools, model, and workflow.
        
        Args:
            use_mongodb: Whether to use MongoDB for persistence
            connection_uri: MongoDB connection URI (if None, uses config)
        """
        # Log configuration
        log_config()
        
        # Set up tools
        self.tools = [
            start_coding_challenge,
            submit_code_for_challenge,
            get_coding_hint,
            suggest_code_improvements,
            complete_code,
            review_code_section
        ]
        
        # Create tool node
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
                
                # Initialize MongoDB checkpointer
                logger.info(f"Initializing MongoDB checkpointer with database {db_config['database']}")
                self.checkpointer = MongoDBCheckpointer(
                    connection_uri=mongodb_uri,
                    database_name=db_config["database"],
                    collection_name=db_config["sessions_collection"],
                )
                
                # Test MongoDB connection with a small write/read
                test_config = {
                    "configurable": {
                        "thread_id": "test-connection",
                    }
                }
                test_data = {"test": "connection"}
                test_config = self.checkpointer.put(test_config, test_data, {"source": "test"}, {})
                result = self.checkpointer.get_tuple(test_config)
                if result and result[1].get("test") == "connection":
                    logger.info("MongoDB connection successful!")
                else:
                    raise ValueError("MongoDB connection test failed")
                
                # Initialize session manager
                self.session_manager = SessionManager(
                    connection_uri=mongodb_uri,
                    database_name=db_config["database"],
                    collection_name=db_config["metadata_collection"],
                )
                
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
        Initialize the LangGraph workflow.
        
        Returns:
            StateGraph: Compiled workflow graph
        """
        # Create workflow with MessagesState
        workflow = StateGraph(MessagesState)
        
        # Add nodes
        workflow.add_node("agent", self.call_model)
        workflow.add_node("tools", self.tool_node)
        
        # Add conditional edges
        workflow.add_conditional_edges(
            "agent",
            self.should_continue,
            {
                "tools": "tools",
                "end": END
            }
        )
        
        # Add edge from tools back to agent
        workflow.add_edge("tools", "agent")
        
        # Set entry point
        workflow.set_entry_point("agent")
        
        # Compile with checkpointer
        compiled_graph = workflow.compile(checkpointer=self.checkpointer)
        logger.info("Workflow compiled successfully with checkpointer")
        return compiled_graph
    
    @staticmethod
    def should_continue(state: MessagesState) -> Literal["tools", "end"]:
        """
        Determine if the workflow should continue to tools or end.
        
        Args:
            state: Current state with messages
            
        Returns:
            "tools" if tool calls are present, otherwise "end"
        """
        # Debug state type
        logger.debug(f"should_continue received state of type: {type(state)}")
        
        # Extract messages from state, handling different state formats
        messages = []
        try:
            # Handle different types of state objects
            if hasattr(state, "messages"):
                # MessagesState or object with messages attribute
                messages = state.messages
                logger.debug(f"Extracted messages from state.messages attribute, found {len(messages)} messages")
            elif isinstance(state, dict) and "messages" in state:
                # Dictionary with messages key
                messages = state["messages"]
                logger.debug(f"Extracted messages from state['messages'], found {len(messages)} messages")
            elif hasattr(state, "__getitem__") and "messages" in state:
                # Dict-like object with messages key
                messages = state["messages"]
                logger.debug(f"Extracted messages from state['messages'] using __getitem__, found {len(messages)} messages")
            else:
                logger.error(f"Unable to extract messages from state of type {type(state)}")
                return "end"
        except Exception as e:
            logger.error(f"Error extracting messages from state: {e}")
            return "end"
            
        # Check if we have any messages
        if not messages:
            logger.debug("No messages found in state, ending")
            return "end"
            
        # Get the last message
        try:
            last_message = messages[-1]
            logger.debug(f"Last message type: {type(last_message)}")
        except (IndexError, TypeError) as e:
            logger.error(f"Error accessing last message: {e}")
            return "end"
        
        # Check for tool calls
        try:
            if isinstance(last_message, AIMessage) and hasattr(last_message, "tool_calls") and last_message.tool_calls:
                tool_names = [tc.get('name') for tc in last_message.tool_calls]
                logger.debug(f"Found tool calls: {tool_names}")
                return "tools"
        except Exception as e:
            logger.error(f"Error checking for tool calls: {e}")
            
        # End if no tool calls found
        logger.debug("No tool calls found, ending")
        return "end"
    
    def call_model(self, state: MessagesState) -> Dict:
        """
        Call the model to generate a response based on the current state.
        
        Args:
            state: Current state with messages
            
        Returns:
            Updated state with new AI message
        """
        # Debug state type
        logger.debug(f"call_model received state of type: {type(state)}")
        
        # Extract messages from state, handling different state formats
        messages = []
        try:
            # Handle different types of state objects
            if hasattr(state, "messages"):
                # MessagesState or object with messages attribute
                messages = state.messages
                logger.debug(f"Extracted messages from state.messages attribute, found {len(messages)} messages")
            elif isinstance(state, dict) and "messages" in state:
                # Dictionary with messages key
                messages = state["messages"]
                logger.debug(f"Extracted messages from state['messages'], found {len(messages)} messages")
            elif hasattr(state, "__getitem__") and "messages" in state:
                # Dict-like object with messages key
                messages = state["messages"]
                logger.debug(f"Extracted messages from state['messages'] using __getitem__, found {len(messages)} messages")
            else:
                logger.error(f"Unable to extract messages from state of type {type(state)}")
                # Return a minimal valid state with error message
                return {"messages": [AIMessage(content="I apologize, but I'm experiencing a technical issue.")]}
        except Exception as e:
            logger.error(f"Error extracting messages from state: {e}")
            # Return a minimal valid state with error message
            return {"messages": [AIMessage(content="I apologize, but I'm experiencing a technical issue.")]}
            
        logger.debug(f"State has {len(messages)} messages")
        
        # Get session info from thread_id
        config = {}
        thread_id = ""
        
        # Try to get config from different possible locations
        try:
            if hasattr(state, "__config__"):
                config = state.__config__
                logger.debug("Found __config__ as attribute")
            elif isinstance(state, dict) and "__config__" in state:
                config = state["__config__"]
                logger.debug("Found __config__ in dict")
            elif hasattr(state, "__getitem__") and "__config__" in state:
                config = state["__config__"]
                logger.debug("Found __config__ using __getitem__")
        except Exception as e:
            logger.error(f"Error retrieving config from state: {e}")
        
        # Get thread_id from config
        try:
            if isinstance(config, dict) and "configurable" in config:
                configurable = config["configurable"]
                thread_id = configurable.get("thread_id", "")
                logger.debug(f"Using thread_id: {thread_id}")
        except Exception as e:
            logger.error(f"Error retrieving thread_id from config: {e}")
        
        # Fallback for missing thread_id
        if not thread_id:
            logger.warning("No thread_id found in config, using default context")
            
        # Get session data from MongoDB if available
        session_data = {}
        try:
            if thread_id and self.session_manager:
                session = self.session_manager.get_session(thread_id)
                if session:
                    session_data = session.get("metadata", {})
                    # Update last active timestamp
                    self.session_manager.update_session_activity(thread_id)
            else:
                # Fallback to in-memory storage
                session_data = self.active_sessions.get(thread_id, {})
        except Exception as e:
            logger.error(f"Error retrieving session data: {e}")
            # Continue with empty session data
        
        candidate_name = session_data.get("candidate_name", "")
        interview_id = thread_id or "New Interview"
        current_stage = session_data.get("interview_stage", InterviewStage.INTRODUCTION.value)
        
        # Determine the interview stage if it's not set
        if not current_stage or current_stage == InterviewStage.INTRODUCTION.value:
            if not candidate_name:
                # Still in introduction stage, need to get name
                current_stage = InterviewStage.INTRODUCTION.value
            else:
                # Check conversation length to determine stage
                if len(messages) < 5:  # Arbitrary threshold for introduction
                    current_stage = InterviewStage.INTRODUCTION.value
                else:
                    # Check if any coding tools have been used
                    has_coding = any(
                        isinstance(m, AIMessage) and hasattr(m, "tool_calls") and 
                        any(tc.get("name") in ["start_coding_challenge", "submit_code_for_challenge"] 
                            for tc in (m.tool_calls or []))
                        for m in messages
                    )
                    
                    if has_coding:
                        current_stage = InterviewStage.CODING_CHALLENGE.value
                    else:
                        current_stage = InterviewStage.TECHNICAL_QUESTIONS.value
        
        # Create system message with context
        system_prompt = INTERVIEW_SYSTEM_PROMPT.format(
            candidate_name=candidate_name or "[Not provided yet]",
            interview_id=interview_id,
            current_stage=current_stage
        )
        
        # Prepend system message if not already present
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=system_prompt)] + messages
        
        # Call the model
        try:
            logger.debug(f"Calling model with {len(messages)} messages")
            response = self.model.invoke(messages)
            logger.debug(f"Received response from model: {type(response)}")
            
            # Extract candidate name if not already known
            if not candidate_name:
                candidate_name = self._extract_candidate_name(messages)
                if candidate_name:
                    logger.info(f"Extracted candidate name: {candidate_name}")
                    # Update session metadata with candidate name
                    try:
                        if thread_id and self.session_manager:
                            session_data["candidate_name"] = candidate_name
                            session_data["interview_stage"] = current_stage
                            self.session_manager.update_session_metadata(thread_id, session_data)
                        elif thread_id:
                            # Use in-memory session storage
                            if thread_id in self.active_sessions:
                                self.active_sessions[thread_id]["candidate_name"] = candidate_name
                                self.active_sessions[thread_id]["interview_stage"] = current_stage
                    except Exception as e:
                        logger.error(f"Error updating candidate name: {e}")
            
            # Update interview stage based on conversation content
            new_stage = self._determine_interview_stage(messages, response, current_stage)
            if new_stage != current_stage and thread_id:
                logger.info(f"Updating interview stage from {current_stage} to {new_stage}")
                try:
                    if self.session_manager:
                        session_data["interview_stage"] = new_stage
                        self.session_manager.update_session_metadata(thread_id, session_data)
                    else:
                        if thread_id in self.active_sessions:
                            self.active_sessions[thread_id]["interview_stage"] = new_stage
                except Exception as e:
                    logger.error(f"Error updating interview stage: {e}")
            
            # Return updated state
            return {"messages": messages + [response]}
            
        except Exception as e:
            logger.error(f"Error generating model response: {e}")
            # Return error message
            error_msg = AIMessage(content=f"I apologize, but I'm experiencing a technical issue. Let's continue our conversation.")
            return {"messages": messages + [error_msg]}
    
    def _determine_interview_stage(self, messages: List[BaseMessage], new_response: AIMessage, current_stage: str) -> str:
        """
        Determine the current interview stage based on conversation context.
        
        Args:
            messages: List of messages in the conversation
            new_response: Latest AI response
            current_stage: Current interview stage
            
        Returns:
            Updated interview stage
        """
        # Default to current stage if we can't determine
        if not messages:
            return current_stage
            
        # Extract the content from the latest response
        response_content = new_response.content.lower() if hasattr(new_response, "content") else ""
        
        # Check if we just initiated a coding challenge
        if hasattr(new_response, "tool_calls") and new_response.tool_calls:
            for tool_call in new_response.tool_calls:
                if tool_call.get("name") == "start_coding_challenge":
                    return InterviewStage.CODING_CHALLENGE.value
        
        # Check for stage transitions based on content
        if current_stage == InterviewStage.INTRODUCTION.value:
            # Look for transitions to technical questions
            technical_indicators = [
                "first question",
                "let's start with",
                "let's begin with",
                "technical question",
                "experience with",
                "tell me about your experience",
                "how would you",
                "let's move on to"
            ]
            
            if any(indicator in response_content for indicator in technical_indicators):
                return InterviewStage.TECHNICAL_QUESTIONS.value
        
        elif current_stage == InterviewStage.TECHNICAL_QUESTIONS.value:
            # Check for transitions to coding challenge
            coding_indicators = [
                "coding challenge",
                "programming task",
                "implement a function",
                "write a program",
                "solve this problem",
                "let's move to a practical exercise"
            ]
            
            if any(indicator in response_content for indicator in coding_indicators):
                return InterviewStage.CODING_CHALLENGE.value
        
        elif current_stage == InterviewStage.CODING_CHALLENGE.value:
            # Check for transitions to feedback
            feedback_indicators = [
                "overall, your solution",
                "your performance",
                "you've done well",
                "thank you for completing",
                "your approach to the problem",
                "based on your solution",
                "to summarize your performance"
            ]
            
            if any(indicator in response_content for indicator in feedback_indicators):
                return InterviewStage.FEEDBACK.value
        
        elif current_stage == InterviewStage.FEEDBACK.value:
            # Check for transitions to conclusion
            conclusion_indicators = [
                "thank you for your time",
                "that concludes",
                "this concludes",
                "wrap up",
                "end of our interview",
                "it was a pleasure",
                "next steps in the process"
            ]
            
            if any(indicator in response_content for indicator in conclusion_indicators):
                return InterviewStage.CONCLUSION.value
                
        return current_stage
    
    async def run_interview(self, user_id: str, query: str, session_id: Optional[str] = None) -> Tuple[str, str]:
        """
        Process a user query within an interview session.
        
        Args:
            user_id: User identifier
            query: User's message
            session_id: Optional session ID (if None, most recent or new session used)
            
        Returns:
            Tuple of (AI response as string, session_id)
        """
        try:
            # Get or create session
            if session_id:
                # Validate session exists and belongs to user
                if self.session_manager:
                    try:
                        session = self.session_manager.get_session(session_id)
                        if not session or session.get("user_id") != user_id:
                            logger.warning(f"Invalid session ID {session_id} for user {user_id}")
                            session_id = self._get_or_create_session(user_id)
                    except Exception as e:
                        logger.error(f"Error validating session: {e}")
                        session_id = self._get_or_create_session(user_id)
                else:
                    # When using in-memory storage
                    if session_id not in self.active_sessions or self.active_sessions[session_id].get("user_id") != user_id:
                        logger.warning(f"Invalid session ID {session_id} for user {user_id}")
                        session_id = self._get_or_create_session(user_id)
            else:
                # Get most recent or create new session
                session_id = self._get_or_create_session(user_id)
                
            logger.info(f"Using session {session_id} for user {user_id}")
            
            # Create config for retrieving existing state
            config = {
                "configurable": {
                    "thread_id": session_id,
                    "checkpoint_ns": "ai_interviewer",
                }
            }
            
            # For a new session, initialize the interview stage
            try:
                if self.session_manager:
                    session = self.session_manager.get_session(session_id)
                    if session and "metadata" in session:
                        metadata = session["metadata"]
                        if "interview_stage" not in metadata:
                            metadata["interview_stage"] = InterviewStage.INTRODUCTION.value
                            self.session_manager.update_session_metadata(session_id, metadata)
                else:
                    # In-memory session initialization
                    if session_id in self.active_sessions and "interview_stage" not in self.active_sessions[session_id]:
                        self.active_sessions[session_id]["interview_stage"] = InterviewStage.INTRODUCTION.value
            except Exception as e:
                logger.error(f"Error initializing interview stage: {e}")
            
            # Check for existing messages in the checkpoint
            existing_messages = []
            try:
                # Try to get the existing checkpoint
                checkpoint = self.checkpointer.get_tuple(config)
                if checkpoint and checkpoint[1] and "messages" in checkpoint[1]:
                    existing_messages = checkpoint[1]["messages"]
                    logger.info(f"Retrieved {len(existing_messages)} existing messages from checkpoint")
            except Exception as e:
                logger.error(f"Error retrieving existing messages: {e}")
                # Continue with empty messages list

            # Create the state with existing messages plus new message
            human_message = HumanMessage(content=query)
            state = {"messages": existing_messages + [human_message]} if existing_messages else {"messages": [human_message]}
            logger.info(f"Created state with {len(state['messages'])} messages")
            
            # Invoke workflow
            logger.info(f"Invoking workflow with config: {config}")
            try:
                # Use a timeout to prevent hanging if the invoke takes too long
                import asyncio
                if asyncio.iscoroutinefunction(self.workflow.invoke):
                    # For async workflow
                    result = await self.workflow.invoke(state, config)
                else:
                    # For sync workflow
                    result = self.workflow.invoke(state, config)
                
                logger.info(f"Workflow result type: {type(result)}")
                
                if isinstance(result, dict):
                    logger.debug(f"Result keys: {result.keys()}")
                    if "messages" in result:
                        logger.debug(f"Result has {len(result['messages'])} messages")
                    else:
                        logger.warning(f"Result missing 'messages' key. Keys present: {list(result.keys())}")
                else:
                    logger.warning(f"Result is not a dict, but {type(result)}")
            except Exception as e:
                logger.error(f"Error invoking workflow: {e}")
                import traceback
                logger.error(f"Full traceback: {traceback.format_exc()}")
                # Return error message
                return "I apologize, but I'm experiencing a technical issue with the interview system. Please try again.", session_id
            
            # Update last active timestamp and store transcript
            timestamp = datetime.now().isoformat()
            
            # Extract AI response
            ai_response = ""
            if isinstance(result, dict) and "messages" in result:
                messages = result["messages"]
                if messages and isinstance(messages[-1], AIMessage):
                    ai_response = messages[-1].content
                    logger.info("Successfully extracted AI response")
            
            # Update session data
            try:
                if self.session_manager:
                    # Update session activity
                    self.session_manager.update_session_activity(session_id)
                    
                    # Get and update session metadata
                    session = self.session_manager.get_session(session_id)
                    if session:
                        metadata = session.get("metadata", {})
                        
                        # Initialize or append to transcript
                        transcript = metadata.get("transcript", [])
                        
                        # Add to transcript
                        transcript.append({
                            "timestamp": timestamp,
                            "user": query,
                            "ai": ai_response
                        })
                        
                        # Update metadata
                        metadata["transcript"] = transcript
                        metadata["last_response"] = ai_response
                        
                        # Save updated metadata
                        self.session_manager.update_session_metadata(session_id, metadata)
                else:
                    # In-memory storage
                    if session_id in self.active_sessions:
                        # Initialize transcript if needed
                        if "transcript" not in self.active_sessions[session_id]:
                            self.active_sessions[session_id]["transcript"] = []
                        
                        # Update transcript
                        self.active_sessions[session_id]["transcript"].append({
                            "timestamp": timestamp,
                            "user": query,
                            "ai": ai_response
                        })
                        
                        # Update last active timestamp
                        self.active_sessions[session_id]["last_active"] = timestamp
            except Exception as e:
                logger.error(f"Error updating session data: {e}")
            
            # Return AI response if we have it, otherwise return a fallback message
            if ai_response:
                return ai_response, session_id
            else:
                logger.warning("No AI response found in result")
                return "I apologize, but I couldn't generate a proper response. Let's continue our conversation.", session_id
                
        except Exception as e:
            logger.error(f"Error processing interview for user {user_id}: {e}")
            # Get more details about the exception
            import traceback
            logger.error(f"Exception traceback: {traceback.format_exc()}")
            return "I apologize, but I'm experiencing a technical issue. Please try again.", session_id
    
    def resume_interview(self, user_id: str, session_id: str, query: Optional[str] = None) -> Tuple[str, Dict[str, Any]]:
        """
        Resume an existing interview session.
        
        Args:
            user_id: User identifier
            session_id: Session identifier
            query: Optional new query to process
            
        Returns:
            Tuple of (summary message, session data)
        """
        # Get session data
        session_data = None
        
        try:
            if self.session_manager:
                # Get session from MongoDB
                session = self.session_manager.get_session(session_id)
                if session and session.get("user_id") == user_id:
                    session_data = session
            else:
                # Get session from in-memory storage
                if session_id in self.active_sessions and self.active_sessions[session_id].get("user_id") == user_id:
                    session_data = self.active_sessions[session_id]
        except Exception as e:
            logger.error(f"Error retrieving session for resume: {e}")
        
        if not session_data:
            return "Session not found or invalid. Starting a new interview session.", {}
        
        # Process query if provided
        if query:
            response, _ = asyncio.run(self.run_interview(user_id, query, session_id))
            return response, session_data
        
        # Get session metadata
        try:
            if self.session_manager:
                metadata = session_data.get("metadata", {})
                transcript = metadata.get("transcript", [])
                current_stage = metadata.get("interview_stage", InterviewStage.INTRODUCTION.value)
            else:
                transcript = session_data.get("transcript", [])
                current_stage = session_data.get("interview_stage", InterviewStage.INTRODUCTION.value)
        except Exception as e:
            logger.error(f"Error getting session metadata: {e}")
            transcript = []
            current_stage = InterviewStage.INTRODUCTION.value
        
        # Build summary message
        candidate_name = session_data.get("metadata", {}).get("candidate_name", "") if self.session_manager else session_data.get("candidate_name", "")
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
                    {"interview_stage": InterviewStage.INTRODUCTION.value}
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
        if hasattr(self, 'checkpointer') and hasattr(self.checkpointer, 'close'):
            try:
                self.checkpointer.close()
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