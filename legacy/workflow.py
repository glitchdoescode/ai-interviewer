"""
Core workflow module for the AI Interviewer platform.
"""
import logging
from typing import Dict, Union, Literal, List, Optional
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langgraph.graph import MessagesState

from ai_interviewer.models.state import InterviewState
from ai_interviewer.core.agent import interview_agent
from ai_interviewer.tools.coding_tools import start_coding_challenge, submit_code_for_challenge, get_coding_hint
from ai_interviewer.tools.pair_programming import suggest_code_improvements, complete_code, review_code_section

# Configure logging
logger = logging.getLogger(__name__)

# Define available tools
INTERVIEW_TOOLS = [
    start_coding_challenge,
    submit_code_for_challenge,
    get_coding_hint,
    suggest_code_improvements,
    complete_code,
    review_code_section
]

# Create tool node
tool_node = ToolNode(INTERVIEW_TOOLS)

def should_continue_or_end_interview(state: Union[Dict, InterviewState]) -> Literal["tools", "end"]:
    """
    Determine if the interview should process tools or end.
    
    Args:
        state: Current interview state
        
    Returns:
        "tools" - Process tool calls
        "end" - End interview
    """
    # Normalize the state to work with either a dict or InterviewState
    if isinstance(state, dict):
        normalized_state = state
    else:
        normalized_state = {
            "messages": state.messages,
            "interview_stage": state.interview_stage
        }
    
    # Log state check
    logger.info(f"Checking interview state continuation - current stage: {normalized_state['interview_stage']}, messages: {len(normalized_state.get('messages', []))}")
    
    # End if interview is finished
    if normalized_state["interview_stage"] == "finished":
            logger.info("Interview stage is 'finished', ending interview")
            return "end"
    
    # Get messages
    messages = normalized_state.get("messages", [])
    
    # End if no messages
    if not messages:
        logger.info("No messages in state, ending interview")
        return "end"
    
    # Get last message
    last_message = messages[-1]
    
    # Check for tool calls
    if isinstance(last_message, AIMessage) and hasattr(last_message, "tool_calls") and last_message.tool_calls:
        logger.info("Found tool calls, processing tools")
        return "tools"
    
    # End if no tool calls
    logger.info("No tool calls found, ending interview")
    return "end"

def create_interview_workflow() -> StateGraph:
    """
    Create the interview workflow graph.
        
    Returns:
        A compiled workflow graph
    """
    # Create workflow graph with MessagesState schema
    workflow = StateGraph(MessagesState)
    
    # Add nodes
    workflow.add_node("agent", interview_agent)
    workflow.add_node("tools", tool_node)
    
    # Add conditional edges
    workflow.add_conditional_edges(
        "agent",
        should_continue_or_end_interview,
        {
            "tools": "tools",
            "end": END
        }
    )
    
    # Add edge from tools back to agent
    workflow.add_edge("tools", "agent")
    
    # Set entry point
    workflow.set_entry_point("agent")
    
    # Compile graph
    try:
        return workflow.compile()
    except Exception as e:
        logger.error(f"Error compiling workflow graph: {e}")
        raise