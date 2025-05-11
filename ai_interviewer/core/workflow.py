"""
Workflow module for the AI Interviewer platform.

This module implements the LangGraph workflow that orchestrates the interview process.
"""
import logging
import uuid
from typing import Dict, Any, Literal, Union, List, TypedDict, cast

from langchain_core.messages import AIMessage
from langgraph.graph import END, START, StateGraph
from langchain.tools.render import format_tool_to_openai_tool

from ai_interviewer.core.agent import interview_agent
from ai_interviewer.models.state import InterviewState
from ai_interviewer.tools.basic_tools import get_next_question, submit_answer
from ai_interviewer.tools.dynamic_tools import generate_interview_question, evaluate_candidate_response
from ai_interviewer.tools.coding_tools import start_coding_challenge, submit_code_for_challenge, get_coding_hint
from langgraph.checkpoint.memory import MemorySaver

# Configure logging
logger = logging.getLogger(__name__)


def tool_node(state: Union[Dict, InterviewState]) -> Union[Dict, InterviewState]:
    """
    Process tool calls from the agent and generate a new state.
    
    Args:
        state: Current interview state
        
    Returns:
        Updated state with results from tool execution
    """
    # Normalize the state to work with either a dict or InterviewState
    if isinstance(state, dict):
        normalized_state = state
    else:
        # Convert InterviewState to dict for easier handling
        normalized_state = {
            "messages": state.messages,
            "interview_id": state.interview_id,
            "candidate_id": state.candidate_id,
            "interview_stage": state.interview_stage,
            "current_question_id": state.current_question_id,
            "current_question_text": state.current_question_text,
            "question_history": state.question_history,
            "candidate_responses": state.candidate_responses,
            "current_topic": state.current_topic,
            "coding_challenge_state": state.coding_challenge_state,
            "evaluation_notes": state.evaluation_notes
        }
    
    # Get messages from the normalized state
    messages = normalized_state.get("messages", [])
    
    if not messages or len(messages) == 0:
        logger.warning("No messages in state, returning unmodified state")
        return state
    
    last_message = messages[-1]
    
    # If no tool calls in the last message, return the state unchanged
    if not isinstance(last_message, AIMessage) or not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        logger.warning("Last message has no tool calls, returning unmodified state")
        return state
    
    tool_calls = last_message.tool_calls
    
    # Execute each tool call and get the results
    for tool_call in tool_calls:
        tool_name = tool_call.get("name", "")
        tool_args = tool_call.get("args", {})
        
        logger.info(f"Processing tool call: {tool_name}")
        
        try:
            # Handle get_next_question
            if tool_name == "get_next_question":
                topic = tool_args.get("topic", "python")
                result = get_next_question(topic)
                
                # Update state with the new question
                normalized_state["current_question_id"] = result.get("question_id", "")
                normalized_state["current_question_text"] = result.get("question_text", "")
                
                # Add to question history
                if "question_history" not in normalized_state:
                    normalized_state["question_history"] = []
                normalized_state["question_history"].append(result.get("question_text", ""))
            
            # Handle submit_answer
            elif tool_name == "submit_answer":
                answer = tool_args.get("answer", "")
                question_id = tool_args.get("question_id", "")
                
                # If no question ID provided, try to get it from state
                if not question_id:
                    question_id = normalized_state.get("current_question_id", "unknown")
                
                result = submit_answer(question_id=question_id, answer=answer)
                
                # Store the response with the evaluation
                response_data = {
                    "question_id": question_id,
                    "answer": answer,
                    "evaluation": result.get("evaluation", {})
                }
                
                if "candidate_responses" not in normalized_state:
                    normalized_state["candidate_responses"] = []
                normalized_state["candidate_responses"].append(response_data)
                    
            # Handle generate_interview_question
            elif tool_name == "generate_interview_question":
                # Extract tool arguments
                current_topic = tool_args.get("current_topic", "general")
                candidate_skill_level = tool_args.get("candidate_skill_level", "general")
                
                # Get previous questions from state
                previous_questions = normalized_state.get("question_history", [])
                
                # Get previous responses text for context
                previous_responses = []
                for response in normalized_state.get("candidate_responses", []):
                    if "answer" in response:
                        previous_responses.append(response["answer"])
                
                # Generate the question
                result = generate_interview_question(
                    current_topic=current_topic,
                    previous_questions=previous_questions,
                    candidate_skill_level=candidate_skill_level,
                    previous_responses=previous_responses
                )
                
                # Update state with the new question
                normalized_state["current_question_id"] = result.get("question_id", "")
                normalized_state["current_question_text"] = result.get("question_text", "")
                
                # Add to question history
                if "question_history" not in normalized_state:
                    normalized_state["question_history"] = []
                normalized_state["question_history"].append(result.get("question_text", ""))
                
                # Store the topic
                normalized_state["current_topic"] = current_topic
            
            # Handle evaluate_candidate_response
            elif tool_name == "evaluate_candidate_response":
                # Extract tool arguments
                question = tool_args.get("question", "")
                candidate_answer = tool_args.get("candidate_answer", "")
                
                # Call the evaluation tool
                result = evaluate_candidate_response(
                    question=question,
                    candidate_answer=candidate_answer
                )
                
                # Store the evaluation in the state
                if "evaluation_notes" not in normalized_state:
                    normalized_state["evaluation_notes"] = []
                
                normalized_state["evaluation_notes"].append({
                    "question": question,
                    "answer": candidate_answer,
                    "evaluation": result
                })
                    
            # Handle start_coding_challenge
            elif tool_name == "start_coding_challenge":
                # Extract tool arguments
                challenge_id = tool_args.get("challenge_id")
                
                # Start the coding challenge
                result = start_coding_challenge(challenge_id=challenge_id)
                
                # Store coding challenge state
                coding_challenge_state = {
                    "challenge_id": result.get("challenge_id"),
                    "title": result.get("title"),
                    "description": result.get("description"),
                    "language": result.get("language"),
                    "starter_code": result.get("starter_code"),
                    "test_cases": result.get("visible_test_cases"),
                    "status": "started",
                    "code_submissions": []
                }
                
                # Update state with coding challenge information
                normalized_state["coding_challenge_state"] = coding_challenge_state
                
                # Ensure we're in the coding stage
                normalized_state["interview_stage"] = "coding"
                    
            # Handle submit_code_for_challenge
            elif tool_name == "submit_code_for_challenge":
                # Extract tool arguments
                challenge_id = tool_args.get("challenge_id", "")
                candidate_code = tool_args.get("candidate_code", "")
                
                # If no challenge ID provided, try to get it from state
                if not challenge_id and normalized_state.get("coding_challenge_state"):
                    challenge_id = normalized_state["coding_challenge_state"].get("challenge_id", "")
                
                # Submit the code
                result = submit_code_for_challenge(
                    challenge_id=challenge_id,
                    candidate_code=candidate_code
                )
                
                # Get the current coding challenge state
                coding_challenge_state = normalized_state.get("coding_challenge_state", {})
                
                # Add the submission to the code submissions history
                code_submission = {
                    "code": candidate_code,
                    "evaluation": result.get("evaluation", {})
                }
                
                if "code_submissions" not in coding_challenge_state:
                    coding_challenge_state["code_submissions"] = []
                
                coding_challenge_state["code_submissions"].append(code_submission)
                
                # Update the status
                if result.get("evaluation", {}).get("passed", False):
                    coding_challenge_state["status"] = "evaluated"
                else:
                    coding_challenge_state["status"] = "submitted"
                
                # Update the coding challenge state in the main state
                normalized_state["coding_challenge_state"] = coding_challenge_state
                
            # Handle get_coding_hint
            elif tool_name == "get_coding_hint":
                # Extract tool arguments
                challenge_id = tool_args.get("challenge_id", "")
                current_code = tool_args.get("current_code", "")
                
                # If no challenge ID provided, try to get it from state
                if not challenge_id and normalized_state.get("coding_challenge_state"):
                    challenge_id = normalized_state["coding_challenge_state"].get("challenge_id", "")
                
                # Get the hint
                result = get_coding_hint(
                    challenge_id=challenge_id,
                    current_code=current_code
                )
                
                # Get the current coding challenge state
                coding_challenge_state = normalized_state.get("coding_challenge_state", {})
                
                # Record that a hint was provided
                if "hints_provided" not in coding_challenge_state:
                    coding_challenge_state["hints_provided"] = []
                
                coding_challenge_state["hints_provided"].append(result.get("message", ""))
                
                # Update the coding challenge state in the main state
                normalized_state["coding_challenge_state"] = coding_challenge_state
                
            else:
                logger.warning(f"Unknown tool name: {tool_name}")
                
        except Exception as e:
            logger.error(f"Error processing tool call {tool_name}: {e}")
    
    # Convert back to the original state type
    if isinstance(state, InterviewState):
        # Convert the normalized state dict back to InterviewState fields
        for key, value in normalized_state.items():
            if hasattr(state, key):
                setattr(state, key, value)
        return state
    else:
        # Return the dict state
        return normalized_state


def should_continue_or_end_interview(state: Union[Dict, InterviewState]) -> Literal["continue", "end"]:
    """
    Determine if the interview should continue or end.
    
    Args:
        state: Current interview state
        
    Returns:
        'continue' if the interview should proceed, 'end' if it should end
    """
    # Check if we're in the final stage
    if isinstance(state, dict):
        interview_stage = state.get("interview_stage")
        messages_count = len(state.get("messages", []))
    else:
        interview_stage = state.interview_stage
        messages_count = len(state.messages)
        
    logger.info(f"Checking interview state continuation - current stage: {interview_stage}, messages: {messages_count}")
    
    if interview_stage == "finished":
        logger.info("Interview stage is 'finished', ending interview")
        return "end"
    
    # Otherwise, continue the interview
    logger.info(f"Continuing interview in {interview_stage} stage")
    return "continue"


def should_continue_with_agent_or_tools(state: Union[Dict, InterviewState]) -> Literal["agent", "tools"]:
    """
    Determine if the next step should involve the agent or tools.
    
    Args:
        state: Current interview state
        
    Returns:
        'agent' to proceed with the agent, 'tools' to proceed with tools
    """
    # Get messages from state
    if isinstance(state, dict):
        messages = state.get("messages", [])
        interview_stage = state.get("interview_stage", "greeting")
    else:
        messages = state.messages
        interview_stage = state.interview_stage
    
    logger.info(f"Checking for tool calls in {interview_stage} stage with {len(messages)} messages")
    
    # Check the most recent message
    if messages and len(messages) > 0:
        last_message = messages[-1]
        if isinstance(last_message, AIMessage) and hasattr(last_message, "tool_calls") and last_message.tool_calls:
            tool_calls_count = len(last_message.tool_calls)
            logger.info(f"Last message contains {tool_calls_count} tool calls")
            for tool_call in last_message.tool_calls:
                logger.info(f"Tool call detected: {tool_call.get('name', 'unknown')}")
            return "tools"
    
    # Default to continuing with the agent
    logger.info("No tool calls detected, continuing with agent")
    return "agent"


def create_interview_workflow(checkpoint_saver: Any = None) -> StateGraph:
    """
    Create the LangGraph workflow for the interview process.
    
    Args:
        checkpoint_saver: Optional checkpointer for state persistence
        
    Returns:
        A StateGraph representing the interview workflow
    """
    # Set up checkpointing if provided
    if checkpoint_saver:
        logger.info(f"Setting up checkpoint with saver type: {type(checkpoint_saver).__name__}")
    else:
        logger.warning("No checkpoint_saver provided! State won't persist between calls.")
    
    # Create the workflow graph with the checkpointer
    # In LangGraph 0.4.3, we need to pass the checkpointer directly
    builder = StateGraph(InterviewState)
    
    # For LangGraph 0.4.3, we need to create a checkpointer instance in a different way
    # Let's try passing it during compilation
    
    # Add the nodes
    builder.add_node("agent", interview_agent)
    builder.add_node("tools", tool_node)
    
    # Define the edges
    # Start -> Agent
    builder.add_edge(START, "agent")
    
    # Agent -> Tools or End
    builder.add_conditional_edges(
        "agent",
        should_continue_with_agent_or_tools,
        {
            "agent": END,
            "tools": "tools"
        }
    )
    
    # Tools -> Agent or End
    builder.add_conditional_edges(
        "tools",
        should_continue_or_end_interview,
        {
            "continue": "agent",
            "end": END
        }
    )
    
    # Create the graph with the checkpointer
    # In LangGraph 0.4.3, we pass checkpointer to compile()
    if checkpoint_saver:
        graph = builder.compile(checkpointer=checkpoint_saver)
    else:
        graph = builder.compile()
    
    return graph


def create_checkpointer() -> MemorySaver:
    """
    Create an in-memory checkpointer for saving state.
    
    Returns:
        MemorySaver instance
    """
    from langgraph.checkpoint.memory import MemorySaver
    saver = MemorySaver()
    logger.info(f"Created new MemorySaver instance: {id(saver)}")
    return saver


def get_interview_app(thread_id: str = None) -> Any:
    """
    Create and return the interview application with the workflow.
    
    Args:
        thread_id: Optional thread ID for state persistence
        
    Returns:
        A compiled workflow
    """
    # For backward compatibility
    logger.warning("get_interview_app is deprecated, use create_interview_workflow instead.")
    return create_interview_workflow(create_checkpointer())