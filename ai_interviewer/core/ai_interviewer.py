"""
Core AI Interviewer class that encapsulates all LangGraph components.

This module follows the architecture pattern from gizomobot, providing a unified
class that handles the entire interview process.
"""
import logging
import os
import uuid
from typing import Dict, List, Optional, Any, Literal, Union
from datetime import datetime

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# System prompt template
INTERVIEW_SYSTEM_PROMPT = """You are an AI Technical Interviewer for a software engineering position.

Your goal is to conduct a professional, thorough interview that assesses the candidate's technical skills, problem-solving abilities, and communication style.

During this interview, you should:
1. Begin with a friendly introduction and make the candidate comfortable.
2. Ask technical questions related to software engineering, gradually increasing in difficulty.
3. Follow up on answers to probe deeper into the candidate's understanding.
4. If you present a coding challenge, explain the requirements clearly.
5. Provide constructive feedback on the candidate's solutions.
6. Be respectful, professional, and unbiased at all times.
7. Keep your responses concise and clear.

The interview will typically follow this flow:
1. Greeting and introduction
2. Technical questions
3. Coding challenge
4. Feedback and conclusion

AVAILABLE TOOLS:
- start_coding_challenge: Presents a coding challenge to the candidate
- submit_code_for_challenge: Evaluates the candidate's solution
- get_coding_hint: Provides hints if the candidate is stuck
- suggest_code_improvements: Offers ways to improve code
- complete_code: Helps complete partial code
- review_code_section: Reviews specific parts of code

IMPORTANT:
- Present one question at a time and wait for a response.
- Use tools only when appropriate for the interview stage.
- Do not fabricate or assume information about the candidate's background.

Current Context:
Candidate name: {candidate_name}
Interview ID: {interview_id}
"""

class AIInterviewer:
    """Main class that encapsulates the AI Interviewer functionality."""
    
    def __init__(self):
        """Initialize the AI Interviewer with tools, model, and workflow."""
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
        self.model = ChatGoogleGenerativeAI(
            model="gemini-1.5-pro-latest",
            temperature=0.2
        ).bind_tools(self.tools)
        
        # Set up memory for session persistence
        self.memory = InMemorySaver()
        
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
        
        # Compile with memory saver
        return workflow.compile(checkpointer=self.memory)
    
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
        logger.info(f"should_continue received state of type: {type(state)}")
        
        # Check if state has messages key
        if isinstance(state, dict) and "messages" in state:
            logger.info(f"State has messages key with {len(state['messages'])} messages")
        else:
            # If state doesn't have messages or is not a dict, log and end
            logger.error(f"Invalid state format in should_continue: {state}")
            return "end"
            
        # Get the last message
        if not state["messages"]:
            logger.info("No messages in state, ending")
            return "end"
            
        last_message = state["messages"][-1]
        logger.info(f"Last message type: {type(last_message)}")
        
        # Check for tool calls
        if isinstance(last_message, AIMessage) and hasattr(last_message, "tool_calls") and last_message.tool_calls:
            logger.info(f"Found tool calls: {[tc.get('name') for tc in last_message.tool_calls]}")
            return "tools"
        
        # End if no tool calls found
        logger.info("No tool calls found, ending")
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
        logger.info(f"call_model received state of type: {type(state)}")
        
        # Safely access messages
        if not isinstance(state, dict) or "messages" not in state:
            logger.error(f"Invalid state format in call_model: {state}")
            # Return a minimal valid state
            return {"messages": [AIMessage(content="I apologize, but I'm experiencing a technical issue.")]}
            
        messages = state["messages"]
        logger.info(f"State has {len(messages)} messages")
        
        # Get session info from thread_id
        config = {}
        thread_id = ""
        
        # Try to get config from different possible locations
        if hasattr(state, "__config__"):
            config = state.__config__
            logger.info("Found __config__ as attribute")
        elif isinstance(state, dict) and "__config__" in state:
            config = state["__config__"]
            logger.info("Found __config__ in dict")
        
        # Get thread_id from config
        if isinstance(config, dict) and "thread_id" in config:
            thread_id = config["thread_id"]
            logger.info(f"Using thread_id: {thread_id}")
        
        # Fallback for missing thread_id
        if not thread_id:
            logger.warning("No thread_id found in config, using default context")
            
        # Get session data
        session_data = self.active_sessions.get(thread_id, {})
        candidate_name = session_data.get("candidate_name", "")
        interview_id = session_data.get("interview_id", "")
        
        # Create system message with context
        system_prompt = INTERVIEW_SYSTEM_PROMPT.format(
            candidate_name=candidate_name or "Candidate",
            interview_id=interview_id or "New Interview"
        )
        
        # Prepend system message if not already present
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=system_prompt)] + messages
        
        # Call the model
        try:
            response = self.model.invoke(messages)
            
            # Return updated state
            return {"messages": messages + [response]}
            
        except Exception as e:
            logger.error(f"Error generating model response: {e}")
            # Return error message
            error_msg = AIMessage(content=f"I apologize, but I'm experiencing a technical issue. Let's continue our conversation.")
            return {"messages": messages + [error_msg]}
    
    async def run_interview(self, user_id: str, query: str) -> str:
        """
        Process a user query within an interview session.
        
        Args:
            user_id: User identifier
            query: User's message
            
        Returns:
            AI response as string
        """
        try:
            # Get or create session
            session_id = self._get_or_create_session(user_id)
            logger.info(f"Using session {session_id} for user {user_id}")
            
            # Create a fresh state with the user message
            state = {"messages": [HumanMessage(content=query)]}
            logger.info(f"Created fresh state with 1 message")
                        
            # Run workflow with thread_id to maintain persistence
            config = {
                "thread_id": session_id,
                "checkpoint_ns": "ai_interviewer",
                "checkpoint_id": session_id
            }
            logger.info(f"Invoking workflow with config: {config}")
            
            # Invoke workflow
            result = self.workflow.invoke(state, config)
            logger.info(f"Workflow result type: {type(result)}")
            
            if isinstance(result, dict):
                logger.info(f"Result keys: {result.keys()}")
                if "messages" in result:
                    logger.info(f"Result has {len(result['messages'])} messages")
            
            # Update last active timestamp
            if session_id in self.active_sessions:
                self.active_sessions[session_id]["last_active"] = datetime.now().isoformat()
                logger.info(f"Updated session last_active timestamp")
            
            # Extract AI response
            if isinstance(result, dict) and "messages" in result:
                messages = result["messages"]
                if messages and isinstance(messages[-1], AIMessage):
                    logger.info("Successfully extracted AI response")
                    return messages[-1].content
                else:
                    logger.warning("No AI message found in result")
            else:
                logger.warning(f"Unexpected result format: {type(result)}")
            
            # Fallback response
            return "I apologize, but I couldn't generate a proper response. Let's continue our conversation."
                
        except Exception as e:
            logger.error(f"Error processing interview for user {user_id}: {e}")
            # Get more details about the exception
            import traceback
            logger.error(f"Exception traceback: {traceback.format_exc()}")
            return "I apologize, but I'm experiencing a technical issue. Please try again."
    
    def _get_or_create_session(self, user_id: str) -> str:
        """
        Get an existing session or create a new one.
        
        Args:
            user_id: User identifier
            
        Returns:
            Session ID
        """
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
            "last_active": datetime.now().isoformat()
        }
        
        logger.info(f"Created new session {session_id} for user {user_id}")
        return session_id
    
    def list_active_sessions(self) -> Dict[str, Dict[str, Any]]:
        """
        List all active interview sessions.
        
        Returns:
            Dictionary of active sessions
        """
        # Filter out expired sessions
        now = datetime.now()
        active_sessions = {}
        
        for session_id, session_data in self.active_sessions.items():
            last_active = datetime.fromisoformat(session_data.get("last_active", ""))
            time_diff = (now - last_active).total_seconds() / 60
            
            if time_diff < 60:  # 1 hour timeout
                active_sessions[session_id] = session_data
        
        return active_sessions 