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
9. Never repeat questions that have already been asked.
10. Remember previous responses from the candidate and build on them.
11. DO NOT ask for the candidate's background more than once.

The interview progresses through several stages:
- greeting: Initial welcome and introduction
- qa: Question and answer technical assessment
- coding: Interactive coding challenge 
- feedback: Summarizing the interview
- finished: End of interview

Your current stage in the interview is: {interview_stage}

STAGE-SPECIFIC INSTRUCTIONS:
- If in greeting stage: Introduce yourself and ask ONCE about the candidate's background.
- If in qa stage: Use the generate_interview_question tool to create relevant technical questions. DO NOT repeat your introduction.
- If in coding stage: Use start_coding_challenge to present a coding challenge.
- If in feedback stage: Summarize the candidate's performance.
- If in finished stage: Thank the candidate for their time and end the interview.

TOOLS:
You have access to several tools to help guide the interview:
- generate_interview_question: Use this to generate a relevant interview question based on topic and context
- evaluate_candidate_response: Use this to analyze the candidate's answers (only use after they've provided a substantial response)
- get_next_question: Use this for predefined questions (use generate_interview_question instead for more adaptive questions)
- submit_answer: Use this to record candidate responses
- start_coding_challenge: Use this to start a coding challenge during the interview
- submit_code_for_challenge: Use this to submit and evaluate the candidate's coding solution
- get_coding_hint: Use this to provide a hint for the current coding challenge

IMPORTANT: When in the qa stage, ALWAYS use generate_interview_question tool to create relevant technical questions.
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
    # Count all human messages in the conversation history
    human_messages = [msg for msg in messages if isinstance(msg, HumanMessage)]
    ai_messages = [msg for msg in messages if isinstance(msg, AIMessage)]
    exchange_count = len(human_messages)
    
    logger.info(f"Stage transition check: current_stage={current_stage}, exchanges={exchange_count}, questions={question_count}")
    logger.info(f"Total messages: {len(messages)}, Human messages: {len(human_messages)}, AI messages: {len(ai_messages)}")
    
    # Dump message content for debugging
    for i, msg in enumerate(messages):
        msg_type = type(msg).__name__
        content_preview = msg.content[:30] + "..." if len(msg.content) > 30 else msg.content
        logger.info(f"Message {i}: {msg_type} - {content_preview}")

    # Stage transition logic with more reliable triggers
    if current_stage == "greeting" and exchange_count >= 2:
        # After 2 human messages, transition to Q&A
        logger.info(f"TRANSITIONING from greeting to qa after {exchange_count} human messages")
        return "qa"
    elif current_stage == "qa" and question_count >= 3:
        # After at least 3 questions, move to coding
        logger.info(f"TRANSITIONING from qa to coding after {question_count} questions")
        return "coding" 
    elif current_stage == "coding" and has_completed_coding:
        # After coding challenge is completed, move to feedback
        logger.info("TRANSITIONING from coding to feedback after challenge completion")
        return "feedback"
    elif current_stage == "feedback" and exchange_count >= question_count + 2:
        # After feedback exchange, conclude
        logger.info("TRANSITIONING from feedback to finished")
        return "finished"
    
    # Default: remain in the current stage
    logger.info(f"Remaining in {current_stage} stage")
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
    # Log the entire input state for debugging
    logger.info(f"RECEIVED STATE: {type(state)}")
    
    # Normalize the state to work with either a dict or InterviewState
    if isinstance(state, dict):
        # Convert dict to a normalized working format
        normalized_state = {
            "messages": state.get("messages", []),
            "interview_id": state.get("interview_id"),
            "candidate_id": state.get("candidate_id"),
            "interview_stage": state.get("interview_stage", "greeting"),
            "question_history": state.get("question_history", []),
            "candidate_responses": state.get("candidate_responses", []),
            "current_topic": state.get("current_topic", "general"),
            "coding_challenge_state": state.get("coding_challenge_state")
        }
        
        # Log the message count in incoming state
        logger.info(f"Input state messages count: {len(normalized_state['messages'])}")
        if normalized_state['messages']:
            logger.info(f"First message type: {type(normalized_state['messages'][0]).__name__}")
            logger.info(f"Last message type: {type(normalized_state['messages'][-1]).__name__}")
    else:
        # Convert InterviewState to a normalized working format
        normalized_state = {
            "messages": state.messages,
            "interview_id": state.interview_id,
            "candidate_id": state.candidate_id,
            "interview_stage": state.interview_stage,
            "question_history": state.question_history,
            "candidate_responses": state.candidate_responses,
            "current_topic": state.current_topic or "general",
            "coding_challenge_state": state.coding_challenge_state
        }
        
        # Log the message count in incoming state
        logger.info(f"Input state messages count: {len(normalized_state['messages'])}")
        if normalized_state['messages']:
            logger.info(f"First message type: {type(normalized_state['messages'][0]).__name__}")
            logger.info(f"Last message type: {type(normalized_state['messages'][-1]).__name__}")
    
    # Debug checkpoint retrieval - this is critical for message persistence
    if config and "thread_id" in config:
        try:
            from langgraph.checkpoint import get_checkpointer
            checkpointer = get_checkpointer()
            
            # For newer versions of LangGraph, the config is passed directly
            # Check if the thread_id is already in the right format
            thread_id = config["thread_id"]
            
            # Try to retrieve any existing state for this thread
            existing_state = checkpointer.get(thread_id)
            
            if existing_state:
                # Log the checkpointed state information
                logger.info(f"Retrieved checkpointed state for thread: {thread_id}")
                if "messages" in existing_state:
                    logger.info(f"Checkpointed messages count: {len(existing_state['messages'])}")
                
                # CRITICAL FIX: Make sure we accumulate messages from checkpointed state
                # Update normalized state with checkpointed values if they exist
                for key in normalized_state:
                    if key in existing_state and existing_state[key]:
                        # Special handling for messages to ensure they accumulate correctly
                        if key == "messages" and normalized_state[key]:
                            # If the latest human message is not yet in the checkpointed messages
                            # Only add the new human message, otherwise use checkpointed messages as is
                            last_human_msg = normalized_state[key][-1] if normalized_state[key] else None
                            checkpoint_msg_contents = [msg.content for msg in existing_state[key]] if existing_state[key] else []
                            
                            if last_human_msg and isinstance(last_human_msg, HumanMessage) and last_human_msg.content not in checkpoint_msg_contents:
                                # We have a new human message that's not in the checkpoint
                                logger.info("Adding new human message to checkpointed messages")
                                normalized_state[key] = existing_state[key] + [last_human_msg]
                            else:
                                # Use checkpointed messages as is
                                normalized_state[key] = existing_state[key]
                        else:
                            # For other state fields, just use the checkpointed values
                            normalized_state[key] = existing_state[key]
                
                logger.info(f"After merging with checkpoint, messages count: {len(normalized_state['messages'])}")
        except Exception as e:
            logger.error(f"Error retrieving state: {e}")
    
    logger.info(f"Processing interview in stage: {normalized_state['interview_stage']}")
    
    # Get user's message (if any)
    user_message = None
    if normalized_state["messages"] and isinstance(normalized_state["messages"][-1], HumanMessage):
        user_message = normalized_state["messages"][-1].content
        logger.info(f"Received user message: {user_message[:50]}...")
        
        # Try to extract candidate name from introduction messages in greeting stage
        if normalized_state["interview_stage"] == "greeting" and not normalized_state["candidate_id"] and user_message:
            normalized_state["candidate_id"] = extract_name_with_llm(user_message)
    
    # Determine if coding challenge has been completed (if in coding stage)
    has_completed_coding = False
    if (normalized_state["interview_stage"] == "coding" and
        normalized_state["coding_challenge_state"] and
        normalized_state["coding_challenge_state"].get("status") == "evaluated"):
        has_completed_coding = True
    
    # Check if we should advance to the next stage based on the conversation flow
    next_stage = should_transition_stage(
        normalized_state["interview_stage"], 
        normalized_state["messages"], 
        len(normalized_state["question_history"]),
        has_completed_coding
    )
    
    # Important! Make sure stage transitions are applied to the state
    if next_stage != normalized_state["interview_stage"]:
        logger.info(f"Updating interview stage: {normalized_state['interview_stage']} -> {next_stage}")
        normalized_state["interview_stage"] = next_stage
    
    # Prepare system message with current context
    system_prompt = INTERVIEWER_SYSTEM_PROMPT.format(
        interview_stage=normalized_state["interview_stage"]
    )
    
    # Add candidate name to the system prompt if available
    if normalized_state["candidate_id"]:
        # Add it explicitly in the beginning of the prompt
        system_prompt = f"Candidate name: {normalized_state['candidate_id']}\n\n" + system_prompt
        
        # For clarity in transitions, explicitly tell the model about the current stage
        stage_message = ""
        if normalized_state["interview_stage"] == "qa":
            stage_message = "\n\nWe are now in the technical Q&A stage. Ask technical questions without repeating the introduction."
        elif normalized_state["interview_stage"] == "coding":
            stage_message = "\n\nWe are now in the coding challenge stage. Present a coding challenge."
        elif normalized_state["interview_stage"] == "feedback":
            stage_message = "\n\nWe are now in the feedback stage. Provide feedback on the interview."
        elif normalized_state["interview_stage"] == "finished":
            stage_message = "\n\nWe are now in the final stage. Conclude the interview."
            
        system_prompt += stage_message
    
    # Add context about previous questions and topics
    if normalized_state["question_history"]:
        system_prompt += f"\n\nPrevious questions asked: {normalized_state['question_history']}"
        system_prompt += f"\nCurrent topic focus: {normalized_state['current_topic']}"
    
    # Add previous responses context
    if normalized_state["candidate_responses"]:
        system_prompt += "\n\nPrevious candidate responses:"
        for i, response in enumerate(normalized_state["candidate_responses"][-3:]):  # Last 3 responses
            if "answer" in response:
                system_prompt += f"\nResponse {i+1}: {response['answer'][:100]}..."
    
    # Add coding challenge context if we have it
    if normalized_state["coding_challenge_state"]:
        challenge_id = normalized_state["coding_challenge_state"].get("challenge_id")
        submission_status = normalized_state["coding_challenge_state"].get("status", "not_started")
        
        system_prompt += f"\n\nActive coding challenge: {challenge_id}"
        system_prompt += f"\nChallenge status: {submission_status}"
        
        # If a challenge is active but not evaluated, include extra context
        if submission_status not in ["evaluated", "not_started"]:
            system_prompt += "\n\nThe candidate is working on a coding challenge. Encourage them to submit their solution or ask for a hint if needed."
    
    system_message = SystemMessage(content=system_prompt)
    
    # Create the complete message history for the LLM
    all_messages = normalized_state["messages"]
    
    # Include the system message at the beginning
    llm_messages = [system_message] + all_messages
    
    # Get the LLM
    llm = get_llm()
    
    # Generate a response from the LLM
    try:
        ai_message = llm.invoke(llm_messages)
        logger.info(f"Generated AI response: {ai_message.content[:50]}...")
        
        # If this is the first message in greeting stage, assign an interview ID if needed
        if normalized_state["interview_stage"] == "greeting" and not normalized_state["interview_id"]:
            normalized_state["interview_id"] = str(uuid.uuid4())
        
        # Update the messages in the normalized state - IMPORTANT: we don't add stage marker to the actual message
        normalized_state["messages"] = all_messages + [ai_message]
        
        # Log the message count in the output state
        logger.info(f"Output state messages count: {len(normalized_state['messages'])}")
        
        # Log the current stage for debugging but don't modify the AI response
        logger.info(f"Current interview stage after response: {normalized_state['interview_stage']}")
        
        # Return the updated state
        return normalized_state
    
    except Exception as e:
        logger.error(f"Error generating AI response: {e}")
        # Return original normalized state on error to prevent data loss
        return normalized_state 