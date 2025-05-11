"""
Agent module for the AI Interviewer platform.

This module implements the core interview agent that interacts with candidates.
"""
import logging
import uuid
from typing import Dict, Any, Optional, Union, cast, List

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI

from ai_interviewer.models.state import InterviewState

# Configure logging
logger = logging.getLogger(__name__)

# System prompt template for the interviewer persona
INTERVIEWER_SYSTEM_PROMPT = """You are an AI Technical Interviewer for a software engineering position.

Your goal is to conduct a professional, thorough interview that assesses the candidate's technical skills, problem-solving abilities, and communication style.

During this interview, you should:
1. Begin with a friendly introduction and greeting to make the candidate comfortable.
2. Always address the candidate by their name when it's provided.
3. Ask technical questions related to software engineering, starting with simpler concepts and gradually increasing in difficulty.
4. Follow up on answers to probe deeper into the candidate's understanding.
5. If a candidate provides a vague or incorrect answer, ask clarifying questions.
6. Be respectful, professional, and unbiased at all times.
7. Do not provide the answers to questions even if the candidate struggles.
8. Keep your responses concise and clear.

The interview progresses through several stages:
- greeting: Initial welcome and introduction
- qa: Question and answer technical assessment
- coding: Interactive coding challenge 
- feedback: Summarizing the interview
- finished: End of interview

Your current stage in the interview is: {interview_stage}

TOOLS:
You have access to several tools to help guide the interview:
- generate_interview_question: Use this to generate a relevant interview question based on topic and context
- evaluate_candidate_response: Use this to analyze the candidate's answers (only use after they've provided a substantial response)
- get_next_question: Use this for predefined questions (use generate_interview_question instead for more adaptive questions)
- submit_answer: Use this to record candidate responses
- start_coding_challenge: Use this to start a coding challenge during the interview
- submit_code_for_challenge: Use this to submit and evaluate the candidate's coding solution
- get_coding_hint: Use this to provide a hint for the current coding challenge

STAGE TRANSITIONS:
- When starting, use the greeting stage to introduce yourself and understand the candidate's background
- After greeting, transition to qa stage for technical assessment by asking questions on relevant topics
- After several questions in the qa stage, transition to coding stage and use start_coding_challenge
- When concluding, transition to feedback stage to summarize the interview
- Finally, transition to finished stage when the interview is complete

CODING CHALLENGE GUIDANCE:
When in the coding stage:
1. Explain to the candidate that you'll be presenting a coding challenge
2. Use the start_coding_challenge tool to retrieve a challenge
3. Clearly present the problem, requirements, and starter code to the candidate
4. Encourage the candidate to think aloud as they work on the solution
5. When they provide code, use submit_code_for_challenge to evaluate it
6. If they get stuck, offer encouragement and the option to use get_coding_hint
7. After evaluating their solution, provide constructive feedback
"""


def get_llm(model_name: str = "gemini-1.5-pro-latest", temperature: float = 0.2):
    """
    Initialize and return the language model.
    
    Args:
        model_name: The name of the Google Generative AI model to use
        temperature: Controls randomness in responses (0.0 to 1.0)
        
    Returns:
        A ChatGoogleGenerativeAI instance
    """
    # Import the tools
    from ai_interviewer.tools.basic_tools import get_next_question, submit_answer
    from ai_interviewer.tools.dynamic_tools import generate_interview_question, evaluate_candidate_response
    from ai_interviewer.tools.coding_tools import start_coding_challenge, submit_code_for_challenge, get_coding_hint
    from langchain.tools.render import format_tool_to_openai_tool
    
    # Create OpenAI-compatible tool descriptions
    tools = [
        format_tool_to_openai_tool(get_next_question),
        format_tool_to_openai_tool(submit_answer),
        format_tool_to_openai_tool(generate_interview_question),
        format_tool_to_openai_tool(evaluate_candidate_response),
        format_tool_to_openai_tool(start_coding_challenge),
        format_tool_to_openai_tool(submit_code_for_challenge),
        format_tool_to_openai_tool(get_coding_hint)
    ]
    
    return ChatGoogleGenerativeAI(
        model=model_name,
        temperature=temperature,
        convert_system_message_to_human=True,  # For compatibility with Gemini
        tools=tools
    )


def extract_name_with_llm(message: str) -> Optional[str]:
    """
    Use the LLM to extract a name from a message if present.
    
    Args:
        message: The message to extract a name from
        
    Returns:
        The extracted name or None if no name is found
    """
    # Use a simplified system prompt specific for name extraction
    system_prompt = """Extract the person's name from the message if it exists. 
If no name is present, respond with "None". 
If a name is present, respond with only the name, nothing else."""

    # Create a simple LLM for name extraction with lower temperature
    name_llm = ChatGoogleGenerativeAI(
        model="gemini-1.5-flash-latest",
        temperature=0.1,
        convert_system_message_to_human=True
    )
    
    try:
        # Create minimal messages just for name extraction
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Message: {message}\nExtract name:")
        ]
        
        # Get the response and clean it
        response = name_llm.invoke(messages)
        extracted_name = response.content.strip()
        
        # Check if the response is "None" or empty
        if extracted_name.lower() == "none" or not extracted_name:
            return None
            
        logger.info(f"LLM extracted candidate name: {extracted_name}")
        return extracted_name
    except Exception as e:
        logger.error(f"Error extracting name with LLM: {e}")
        return None


def should_transition_stage(current_stage: str, messages: List, question_count: int, has_completed_coding: bool = False) -> str:
    """
    Determine if the interview should transition to a new stage.
    
    Args:
        current_stage: The current interview stage
        messages: The message history
        question_count: The number of questions asked so far
        has_completed_coding: Whether the candidate has completed a coding challenge
        
    Returns:
        The suggested next stage, or current stage if no transition needed
    """
    # Simple transition logic based on stages and question count
    if current_stage == "greeting" and len(messages) >= 4:
        # After initial greeting exchange (2 turns), move to Q&A
        return "qa"
    elif current_stage == "qa" and question_count >= 3:
        # After 3 questions, move to coding challenge
        return "coding" 
    elif current_stage == "coding" and has_completed_coding:
        # After coding challenge is completed, move to feedback
        return "feedback"
    elif current_stage == "feedback" and len(messages) >= question_count + 4:
        # After feedback exchange, conclude the interview
        return "finished"
    
    # Default: remain in the current stage
    return current_stage


def interview_agent(state: Union[Dict, InterviewState], config: Optional[Dict[str, Any]] = None) -> Dict:
    """
    Main LangGraph node function that processes the current state and generates 
    a response from the interviewer.
    
    Args:
        state: The current InterviewState or dict
        config: Optional configuration parameters
        
    Returns:
        Updated state information
    """
    # Get the existing state from the checkpointer if this isn't the initial call
    existing_state = None
    if config and "thread_id" in config:
        thread_id = config["thread_id"]
        if hasattr(config, "get") and config.get("checkpoint_id"):
            from langgraph.checkpoint import get_checkpointer
            checkpointer = get_checkpointer()
            try:
                existing_state = checkpointer.get(config["checkpoint_id"], thread_id)
                logger.debug(f"Retrieved existing state with checkpoint_id={config['checkpoint_id']}, thread_id={thread_id}")
            except Exception as e:
                logger.error(f"Error retrieving state: {e}")
    
    # Handle case where state is a dict instead of an InterviewState object
    interview_stage = "greeting"
    candidate_id = None
    question_history = []
    candidate_responses = []
    current_topic = "general"
    coding_challenge_state = None
    
    # Use existing state values if available
    if existing_state:
        interview_stage = existing_state.get("interview_stage", "greeting") 
        candidate_id = existing_state.get("candidate_id")
        question_history = existing_state.get("question_history", [])
        candidate_responses = existing_state.get("candidate_responses", [])
        current_topic = existing_state.get("current_topic", "general")
        coding_challenge_state = existing_state.get("coding_challenge_state")
        logger.info(f"Retrieved existing state: stage={interview_stage}, candidate={candidate_id}, questions={len(question_history)}")
    
    if isinstance(state, dict):
        # We're dealing with a dict, so access attributes as dictionary keys
        # If 'interview_stage' is not in the dict, use existing or default to 'greeting'
        if "interview_stage" in state:
            interview_stage = state["interview_stage"]
        if "candidate_id" in state and state["candidate_id"]:
            candidate_id = state["candidate_id"]
        if "question_history" in state:
            question_history = state["question_history"]
        if "candidate_responses" in state:
            candidate_responses = state["candidate_responses"]
        if "current_topic" in state:
            current_topic = state["current_topic"]
        if "coding_challenge_state" in state:
            coding_challenge_state = state["coding_challenge_state"]
        # Get messages from dict
        messages = state.get("messages", [])
    else:
        # We're dealing with an InterviewState object
        interview_stage = state.interview_stage
        if state.candidate_id:
            candidate_id = state.candidate_id
        question_history = state.question_history
        candidate_responses = state.candidate_responses
        if state.current_topic:
            current_topic = state.current_topic
        coding_challenge_state = state.coding_challenge_state
        messages = state.messages
    
    logger.info(f"Processing interview in stage: {interview_stage}")
    
    # Get user's message (if any)
    user_message = None
    if messages and len(messages) > 0 and isinstance(messages[-1], HumanMessage):
        user_message = messages[-1].content
        logger.info(f"Received user message: {user_message[:50]}...")
        
        # Try to extract candidate name from introduction messages in greeting stage
        if interview_stage == "greeting" and not candidate_id and user_message:
            # Use LLM to extract name instead of regex patterns
            candidate_id = extract_name_with_llm(user_message)
    
    # Determine if coding challenge has been completed (if in coding stage)
    has_completed_coding = False
    if interview_stage == "coding" and coding_challenge_state and coding_challenge_state.get("status") == "evaluated":
        has_completed_coding = True
    
    # Check if we should advance to the next stage based on the conversation flow
    next_stage = should_transition_stage(
        interview_stage, 
        messages, 
        len(question_history),
        has_completed_coding
    )
    
    if next_stage != interview_stage:
        logger.info(f"Transitioning interview stage: {interview_stage} -> {next_stage}")
        interview_stage = next_stage
    
    # Prepare system message with current context
    system_prompt = INTERVIEWER_SYSTEM_PROMPT.format(
        interview_stage=interview_stage
    )
    
    # Add candidate name to the system prompt if available
    if candidate_id:
        # Replace all instances of [Candidate Name] with the actual name
        system_prompt = system_prompt.replace("[Candidate Name]", candidate_id)
        
        # Also add it explicitly in the beginning
        system_prompt = f"Candidate name: {candidate_id}\n\n" + system_prompt
    
    # Add context about previous questions and topics
    if question_history:
        system_prompt += f"\n\nPrevious questions asked: {len(question_history)}"
        system_prompt += f"\nCurrent topic focus: {current_topic}"
    
    # Add coding challenge context if we have it
    if coding_challenge_state:
        challenge_id = coding_challenge_state.get("challenge_id")
        submission_status = coding_challenge_state.get("status", "not_started")
        
        system_prompt += f"\n\nActive coding challenge: {challenge_id}"
        system_prompt += f"\nChallenge status: {submission_status}"
        
        # If a challenge is active but not evaluated, include extra context
        if submission_status not in ["evaluated", "not_started"]:
            system_prompt += "\n\nThe candidate is working on a coding challenge. Encourage them to submit their solution or ask for a hint if needed."
    
    system_message = SystemMessage(content=system_prompt)
    
    # Create the message history for the LLM
    # Include saved messages from the existing state if available
    all_messages = []
    if existing_state and "messages" in existing_state:
        saved_messages = existing_state.get("messages", [])
        if saved_messages:
            all_messages.extend(saved_messages)
            
    # Add the new message from the current state
    if messages:
        all_messages.extend(messages)
    
    # If we don't have messages yet, create a default history
    if not all_messages:
        all_messages = messages
    
    # Include the system message at the beginning
    llm_messages = [system_message] + all_messages
    
    # Get the LLM
    llm = get_llm()
    
    # Generate a response from the LLM
    try:
        ai_message = llm.invoke(llm_messages)
        logger.info(f"Generated AI response: {ai_message.content[:50]}...")
        
        # If this is the first message in greeting stage, assign an interview ID
        if interview_stage == "greeting" and (isinstance(state, dict) and not state.get("interview_id")):
            interview_id = str(uuid.uuid4())
            return {
                "messages": all_messages + [ai_message],
                "interview_id": interview_id,
                "candidate_id": candidate_id,
                "interview_stage": interview_stage
            }
        
        # Build the result with all the updated state information
        result = {
            "messages": all_messages + [ai_message],
            "interview_stage": interview_stage
        }
        
        # Include other state fields that we're tracking
        if candidate_id:
            result["candidate_id"] = candidate_id
        
        result["question_history"] = question_history
        result["candidate_responses"] = candidate_responses
        result["current_topic"] = current_topic
        
        if coding_challenge_state:
            result["coding_challenge_state"] = coding_challenge_state
            
        return result
    
    except Exception as e:
        logger.error(f"Error generating AI response: {e}")
        # Return original state on error to prevent data loss
        if isinstance(state, dict):
            return state
        else:
            # Convert InterviewState to dict
            return {
                "messages": state.messages,
                "interview_id": state.interview_id,
                "candidate_id": state.candidate_id,
                "interview_stage": state.interview_stage,
                "current_question_id": state.current_question_id,
                "current_question_text": state.current_question_text,
                "question_history": state.question_history,
                "candidate_responses": state.candidate_responses,
                "coding_challenge_state": state.coding_challenge_state,
                "evaluation_notes": state.evaluation_notes,
                "current_topic": state.current_topic
            } 