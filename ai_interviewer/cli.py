"""
Command-line interface for the AI Interviewer platform.

This module provides a simple command-line interface for interacting with
the AI Interviewer.
"""
import argparse
import logging
import os
import sys
import uuid
from typing import List, Optional, Dict, Any, Union

from langchain_core.messages import HumanMessage

from ai_interviewer.core.workflow import create_interview_workflow, create_checkpointer

# Create logs directory if needed
if not os.path.exists("logs"):
    os.makedirs("logs")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger(__name__)


def run_interview(thread_id: Optional[str] = None, topic: str = "general", skill_level: str = "general") -> None:
    """
    Run the AI interviewer in an interactive command-line session.
    
    Args:
        thread_id: Optional thread ID for persistent state (for resuming interviews)
        topic: The topic of the interview (e.g., python, javascript)
        skill_level: The skill level to target (e.g., junior, mid, senior)
    """
    # Create or use thread ID
    if not thread_id:
        thread_id = str(uuid.uuid4())
    
    logger.info(f"Interview session ID: {thread_id}")
    
    # Set up the interview workflow with a memory-based checkpointer
    checkpointer = create_checkpointer()
    logger.info(f"Created checkpointer: {id(checkpointer)}")
    
    workflow = create_interview_workflow(checkpointer)
    logger.info(f"Created workflow graph with checkpointer")
    
    # Create config with thread_id for persistence
    config: Dict[str, Any] = {
        "configurable": {"topic": topic, "skill_level": skill_level},
        "thread_id": thread_id
    }
    logger.info(f"Using config: thread_id={thread_id}, topic={topic}, skill_level={skill_level}")
    
    # Initial greeting to start the interview
    initial_message = "Hello, I'm here for the interview."
    
    # Start the interview with an initial greeting
    logger.info("Starting interview with initial greeting")
    result = workflow.invoke(
        {"messages": [HumanMessage(content=initial_message)]},
        config=config
    )
    
    # Print interview information
    print("\n" + "=" * 50)
    print("  AI INTERVIEWER - Interactive Technical Interview")
    print("=" * 50)
    print(f"* Session ID: {thread_id}")
    print(f"* Topic: {topic}")
    print(f"* Skill Level: {skill_level}")
    print(f"* Type 'exit' or 'quit' to end the interview")
    print("=" * 50 + "\n")
    
    # Process the first response
    ai_response = result.get("messages", [])[-1].content
    print("AI:", ai_response)
    
    # Store current state for context preservation
    current_state = result
    
    # Main interview loop
    while True:
        # Get user input
        user_input = input("\nYou: ")
        
        # Check for exit command
        if user_input.lower() in ["exit", "quit", "q"]:
            print("\n\nInterview terminated by user.\n")
            print("Thank you for using AI Interviewer!")
            break
        
        # Process user input
        try:
            # Preserve important state information like candidate_id across invocations
            if current_state and current_state.get("candidate_id"):
                logger.info(f"Preserving candidate_id in next request: {current_state.get('candidate_id')}")
                
            # Process user input
            logger.info(f"Using thread_id: {thread_id} for state persistence")
            logger.info(f"Sending new human message: {user_input[:50]}...")
            
            # Send only the new message - the checkpointer will handle state persistence
            result = workflow.invoke(
                {"messages": [HumanMessage(content=user_input)]},
                config=config
            )
            
            # Update our current state
            current_state = result
            if "candidate_id" in result:
                logger.info(f"Updated current_state with candidate_id: {result['candidate_id']}")
            
            # Extract AI response and print it
            messages = result.get("messages", [])
            if messages:
                # Print interview progress information
                interview_stage = result.get("interview_stage", "unknown")
                questions = len(result.get("question_history", []))
                logger.info(f"Interview progress: stage={interview_stage}, questions={questions}")
                
                # Get the latest AI message
                ai_response = messages[-1].content
                print("\nAI:", ai_response)
        
        except KeyboardInterrupt:
            print("\n\nInterview terminated by user.\n")
            print("Thank you for using AI Interviewer!")
            break
        
        except Exception as e:
            logger.error(f"Error during interview: {e}", exc_info=True)
            print(f"\nAn error occurred: {e}")
            print("Let's continue the interview...")


def main() -> None:
    """
    Main entry point for the AI Interviewer CLI.
    """
    logger.info("Starting AI Interviewer CLI")
    
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="AI Interviewer CLI")
    parser.add_argument("--thread-id", type=str, help="Thread ID for resuming an interview")
    parser.add_argument(
        "--topic", 
        type=str, 
        choices=["general", "python", "javascript", "data_structures"],
        default="general",
        help="Topic for the interview"
    )
    parser.add_argument(
        "--skill-level", 
        type=str, 
        choices=["junior", "mid", "senior", "general"],
        default="general",
        help="Target skill level for the interview"
    )
    
    args = parser.parse_args()
    
    # Run the interview
    run_interview(args.thread_id, args.topic, args.skill_level)


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
    
    # Enter main function
    main() 