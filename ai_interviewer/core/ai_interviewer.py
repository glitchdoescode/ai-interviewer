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
from langgraph.checkpoint.mongodb import MongoDBSaver

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
- For voice interactions, use natural, conversational language suitable for spoken dialogue.
- When in voice mode, use brief pauses in your responses (represented by commas or periods) to make your speech more natural.
- For voice interactions, clearly indicate when you're waiting for the candidate to speak, e.g., "Please go ahead and answer now."

AVAILABLE TOOLS:
- start_coding_challenge: Presents a coding challenge to the candidate
- submit_code_for_challenge: Evaluates the candidate's solution
- get_coding_hint: Provides context-aware hints if the candidate is stuck
- suggest_code_improvements: Offers ways to improve code based on analysis
- complete_code: Helps complete partial code with AI assistance
- review_code_section: Reviews specific parts of code for improvement

PAIR PROGRAMMING ASSISTANCE:
During coding challenges, you can offer pair programming assistance to help the candidate learn and succeed:
- If the candidate seems stuck, offer a hint using get_coding_hint
- If they've completed part of a solution but aren't sure how to continue, offer to help complete it with complete_code
- If their solution works but could be improved, use suggest_code_improvements to guide them
- For specific code sections they're uncertain about, use review_code_section to provide focused feedback

VOICE INTERACTION GUIDELINES:
- For voice interactions, keep responses under 30 seconds of speaking time.
- Use natural breaks in your speech to allow for better text-to-speech synthesis.
- Avoid using special characters or symbols that don't read well in speech.
- When asking technical questions, be clear and specific to avoid misunderstandings in voice format.
- For coding challenges in voice mode, describe the problem clearly and concisely.

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
            # Coding challenge tools
            start_coding_challenge,
            submit_code_for_challenge,
            get_coding_hint,
            
            # Pair programming tools
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
            # Check for tool_calls in different potential formats
            if isinstance(last_message, AIMessage):
                if hasattr(last_message, "tool_calls"):
                    tool_calls = last_message.tool_calls
                    
                    # Handle different tool_calls formats
                    if tool_calls:
                        if isinstance(tool_calls, list):
                            # Check if any tool in the list has a 'name' attribute
                            tool_names = []
                            for tc in tool_calls:
                                if isinstance(tc, dict) and "name" in tc:
                                    tool_names.append(tc.get('name'))
                            
                            if tool_names:
                                logger.debug(f"Found tool calls: {tool_names}")
                                return "tools"
                        elif isinstance(tool_calls, dict) and "name" in tool_calls:
                            # Single tool as dict
                            logger.debug(f"Found single tool call: {tool_calls.get('name')}")
                            return "tools"
                
                # Alternative format: tool_call_id in additional_kwargs
                elif hasattr(last_message, "additional_kwargs") and last_message.additional_kwargs:
                    if "tool_call_id" in last_message.additional_kwargs:
                        logger.debug(f"Found tool call in additional_kwargs")
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
        # Import the safe_extract_content utility
        from ai_interviewer.utils.transcript import safe_extract_content
        
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
                        any(tc.get("name") in ["start_coding_challenge", "submit_code_for_challenge", "get_coding_hint",
                                              "suggest_code_improvements", "complete_code", "review_code_section"] 
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
        Determine the current interview stage based on conversation context using an LLM.
        
        Args:
            messages: List of messages in the conversation
            new_response: Latest AI response
            current_stage: Current interview stage
            
        Returns:
            Updated interview stage
        """
        # Import helper functions
        from ai_interviewer.utils.transcript import format_conversation_for_llm
        
        # If there are no messages, return the current stage
        if not messages or len(messages) < 2:
            return current_stage
            
        # Check for explicit tool call first (fast path for coding challenge initiation)
        if hasattr(new_response, "tool_calls") and new_response.tool_calls:
            for tool_call in new_response.tool_calls:
                if isinstance(tool_call, dict) and tool_call.get("name") == "start_coding_challenge":
                    logger.info("Detected coding challenge tool call, setting stage to CODING_CHALLENGE")
                    return InterviewStage.CODING_CHALLENGE.value
        
        try:
            # Create a focused prompt for stage determination
            # Extract just the last few exchanges to keep the context manageable
            recent_exchanges = messages[-min(len(messages), 8):] + [new_response]
            
            # Format the conversation for the LLM using our helper function
            conversation_text = format_conversation_for_llm(recent_exchanges)
            
            # Create a system prompt explaining the interview stages
            system_prompt = """You are an assistant helping to determine the current stage of a technical interview.
The interview has the following stages:
1. INTRODUCTION - Getting candidate's name and introductions
2. TECHNICAL_QUESTIONS - Asking technical knowledge questions
3. CODING_CHALLENGE - Presenting and discussing coding tasks
4. FEEDBACK - Providing feedback on performance
5. CONCLUSION - Wrapping up the interview

Based only on the conversation provided, determine which stage the interview is currently in.
Return ONLY the stage name, nothing else."""

            # Create a prompt for the LLM
            prompt = f"""
Current stage: {current_stage}

Recent conversation:
{conversation_text}

Based on this conversation, what stage is the interview in now? 
Respond with only one of: INTRODUCTION, TECHNICAL_QUESTIONS, CODING_CHALLENGE, FEEDBACK, or CONCLUSION."""

            # Use a lightweight model call with low temperature for deterministic results
            llm_config = get_llm_config()
            simple_model = ChatGoogleGenerativeAI(
                model=llm_config["model"],
                temperature=0.0
            )
            
            # Create messages for the LLM
            llm_messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=prompt)
            ]
            
            # Get the response
            response = simple_model.invoke(llm_messages)
            response_text = response.content.strip().upper()
            
            logger.debug(f"LLM stage determination response: {response_text}")
            
            # Map the response to our stage enum
            stage_mapping = {
                "INTRODUCTION": InterviewStage.INTRODUCTION.value,
                "TECHNICAL_QUESTIONS": InterviewStage.TECHNICAL_QUESTIONS.value,
                "CODING_CHALLENGE": InterviewStage.CODING_CHALLENGE.value,
                "FEEDBACK": InterviewStage.FEEDBACK.value,
                "CONCLUSION": InterviewStage.CONCLUSION.value
            }
            
            # Get the new stage, defaulting to current stage if not recognized
            new_stage = stage_mapping.get(response_text, current_stage)
            
            # Only log if there's a change in stage
            if new_stage != current_stage:
                logger.info(f"Interview stage changed from {current_stage} to {new_stage} based on LLM determination")
            
            return new_stage
            
        except Exception as e:
            logger.error(f"Error determining interview stage with LLM: {e}")
            # Fallback to current stage if there's an error
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
            
            # Create config for LangGraph checkpointer
            # The format expected by LangGraph MongoDBSaver
            config = {
                "configurable": {
                    "thread_id": session_id,
                    # Don't need to set checkpoint_ns or metadata
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
            
            # Create human message from the query
            human_message = HumanMessage(content=query)
            
            # Create a state with or without previous messages
            state = None
            
            try:
                # Try to get the existing state from the checkpoint
                # MongoDBSaver needs a different approach to retrieve the checkpoint
                existing_state = None
                
                # The workflow will automatically load the previous state based on thread_id
                # Just initialize with the new message
                state = {"messages": [human_message]}
                
            except Exception as e:
                logger.error(f"Error retrieving existing messages: {e}")
                # Start with just the new message
                state = {"messages": [human_message]}
            
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