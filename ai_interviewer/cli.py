"""
Command-line interface for the AI Interviewer platform.

This module provides a command-line interface for testing the interview process.
"""
import os
import sys
import logging
import argparse
import uuid
from typing import Dict, Any, Optional
from dotenv import load_dotenv

from langchain_core.messages import HumanMessage

from ai_interviewer.core.workflow import create_interview_workflow
from ai_interviewer.models.state import InterviewState
from ai_interviewer.utils.logging_utils import setup_logging

# Load environment variables
load_dotenv()

# Configure logging
setup_logging(log_level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="AI Interviewer CLI")
    parser.add_argument(
        "--thread-id", 
        type=str, 
        help="Thread ID for continuing an existing interview"
    )
    parser.add_argument(
        "--topic", 
        type=str, 
        default="general",
        choices=["general", "python", "javascript", "data_structures"],
        help="Topic for the interview questions"
    )
    parser.add_argument(
        "--skill-level",
        type=str,
        default="general",
        choices=["junior", "mid", "senior", "general"],
        help="Skill level for the interview"
    )
    return parser.parse_args()


def run_interview_cli():
    """
    Run the AI Interviewer in an interactive CLI loop.
    """
    args = parse_args()
    logger.info("Starting AI Interviewer CLI")
    
    # Get the interview app
    interview_app = create_interview_workflow()
    
    # Generate or use thread ID
    thread_id = args.thread_id or str(uuid.uuid4())
    logger.info(f"Interview session ID: {thread_id}")
    
    # Create a properly initialized InterviewState with all required fields
    state = {
        "messages": [],
        "interview_id": thread_id,
        "candidate_id": None,
        "current_question_id": None,
        "current_question_text": None,
        "candidate_responses": [],
        "coding_challenge_state": None,
        "evaluation_notes": [],
        "interview_stage": "greeting",
        "current_topic": args.topic,
        "question_history": []
    }
    
    # Config with thread_id for continuity
    config = {
        "configurable": {
            "topic": args.topic,
            "skill_level": args.skill_level
        },
        "thread_id": thread_id,
        "checkpoint_id": thread_id
    }
    
    print("\n" + "=" * 50)
    print("  AI INTERVIEWER - Interactive Technical Interview")
    print("=" * 50)
    print(f"* Session ID: {thread_id}")
    print(f"* Topic: {args.topic}")
    print(f"* Skill Level: {args.skill_level}")
    print("* Type 'exit' or 'quit' to end the interview")
    print("=" * 50 + "\n")
    
    # Send an empty message to start the interview
    # Add a system message first to ensure we have a valid message
    greeting_state = {
        "messages": [HumanMessage(content="Hello, I'm here for the interview.")],
        "interview_id": thread_id,
        "candidate_id": None,
        "current_question_id": None,
        "current_question_text": None,
        "candidate_responses": [],
        "coding_challenge_state": None,
        "evaluation_notes": [],
        "interview_stage": "greeting",
        "current_topic": args.topic,
        "question_history": []
    }
    
    result = interview_app.invoke(greeting_state, config)
    
    # Display the AI's first message
    if result and result.get("messages"):
        first_message = result["messages"][-1]
        print(f"AI: {first_message.content}\n")
    
    # Main interview loop
    try:
        # Keep track of the latest complete state
        current_state = result if result else greeting_state
        
        while True:
            # Get user input
            user_input = input("You: ").strip()
            
            # Check for exit command
            if user_input.lower() in ["exit", "quit", "bye"]:
                print("\nAI: Thank you for participating in this interview. Goodbye!\n")
                break
            
            # Add user message to the state
            user_message = HumanMessage(content=user_input)
            
            # Create next state with the new message but preserve all critical state
            next_state = {
                "messages": [user_message],
            }
            
            # Preserve critical state fields
            preserve_fields = [
                "candidate_id", "interview_stage", "current_topic", 
                "question_history", "candidate_responses", "evaluation_notes",
                "current_question_id", "current_question_text"
            ]
            
            for field in preserve_fields:
                if field in current_state and current_state[field] is not None:
                    next_state[field] = current_state[field]
                    
            # Always provide the interview_id
            next_state["interview_id"] = thread_id
            
            # Invoke the interview app
            try:
                result = interview_app.invoke(next_state, config)
                
                # Update our tracking of the complete state
                if result:
                    # Update the current state with all fields from result
                    for key, value in result.items():
                        current_state[key] = value
                    
                    # Log the current stage and question count
                    stage = current_state.get("interview_stage", "unknown")
                    questions = len(current_state.get("question_history", []))
                    logger.info(f"Interview progress: stage={stage}, questions={questions}")
                
                # Display the AI's response
                if result and result.get("messages"):
                    ai_response = result["messages"][-1]
                    print(f"\nAI: {ai_response.content}\n")
            except Exception as e:
                logger.error(f"Error during interview: {e}")
                print(f"\nAI: I apologize, but I encountered an error. Let's continue.\n")
    
    except KeyboardInterrupt:
        print("\n\nInterview terminated by user.")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print(f"\nUnexpected error: {e}")
    
    print("\nThank you for using AI Interviewer!\n")


if __name__ == "__main__":
    run_interview_cli() 