"""
Command-line interface for the AI Interviewer platform.

This module provides a simple command-line interface for interacting with
the AI Interviewer.
"""
import logging
import click
from typing import Optional
from datetime import datetime

from langchain_core.messages import HumanMessage
from ai_interviewer.core.workflow import build_interview_graph
from ai_interviewer.core.session import SessionManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize session manager
session_manager = SessionManager()

@click.group()
def cli():
    """AI Interviewer - Technical Interview Platform"""
    pass

@cli.command()
@click.option('--session-id', help='Resume an existing interview session')
@click.option('--topic', default="general", help='Interview topic focus')
@click.option('--skill-level', default="general", help='Candidate skill level')
@click.option('--candidate-id', help='Optional candidate identifier')
def interview(session_id: Optional[str] = None, topic: str = "general", 
             skill_level: str = "general", candidate_id: Optional[str] = None) -> None:
    """
    Start or resume an AI-driven technical interview.
    """
    try:
        # Build the interview workflow
        workflow = build_interview_graph()
        
        # Create or resume session
        if session_id:
            # Try to resume existing session
            state = session_manager.get_session(session_id)
            if not state:
                logger.error(f"Session {session_id} not found or expired")
                return
            if not session_manager.is_session_active(session_id):
                logger.error(f"Session {session_id} has expired")
                return
                
            # Update session metadata
            if state.get("session_metadata"):
                state["session_metadata"]["pause_count"] = state["session_metadata"].get("pause_count", 0) + 1
                state["session_metadata"]["last_active"] = datetime.now().isoformat()
                
            print("\n" + "=" * 50)
            print("  RESUMING INTERVIEW SESSION")
            print("=" * 50)
            print(f"* Session ID: {session_id}")
            print(f"* Stage: {state.get('interview_stage', 'unknown')}")
            print(f"* Questions asked: {len(state.get('question_history', []))}")
            print("=" * 50 + "\n")
            
            # Resume from last state
            current_state = state
            
        else:
            # Create new session
            session_id = session_manager.create_session(candidate_id)
            initial_message = "Hello! I'm here for my technical interview."
            
            # Initialize session
            config = {
                "thread_id": session_id,
                "checkpoint_ns": "interview",
                "checkpoint_id": session_id
            }
            
            # Start the interview
            logger.info("Starting new interview session")
            result = workflow.invoke(
                {"messages": [HumanMessage(content=initial_message)]},
                config=config
            )
            
            # Print session information
            print("\n" + "=" * 50)
            print("  NEW INTERVIEW SESSION")
            print("=" * 50)
            print(f"* Session ID: {session_id}")
            print(f"* Topic: {topic}")
            print(f"* Skill Level: {skill_level}")
            print("=" * 50)
            print("\nCommands:")
            print("- Type 'exit' or 'quit' to end the interview")
            print("- Type 'pause' to pause the interview")
            print("- Type 'status' to see session status")
            print("=" * 50 + "\n")
            
            # Process first response
            ai_response = result.get("messages", [])[-1].content
            print("AI:", ai_response)
            
            current_state = result
        
        # Main interview loop
        while True:
            # Get user input
            user_input = input("\nYou: ").strip().lower()
            
            # Handle commands
            if user_input in ["exit", "quit", "q"]:
                # Complete the session
                session_manager.complete_session(session_id)
                print("\nInterview completed. Thank you for using AI Interviewer!")
                break
                
            elif user_input == "pause":
                # Update session metadata
                if isinstance(current_state, dict) and "session_metadata" in current_state:
                    current_state["session_metadata"]["paused_at"] = datetime.now().isoformat()
                    session_manager.update_session(session_id, current_state)
                print(f"\nInterview paused. To resume, use: --session-id {session_id}")
                break
                
            elif user_input == "status":
                # Show session status
                if isinstance(current_state, dict):
                    print("\nSession Status:")
                    print(f"* Stage: {current_state.get('interview_stage', 'unknown')}")
                    print(f"* Questions asked: {len(current_state.get('question_history', []))}")
                    if current_state.get("session_metadata"):
                        created = datetime.fromisoformat(current_state["session_metadata"].get("created_at", ""))
                        elapsed = datetime.now() - created
                        print(f"* Session duration: {elapsed.total_seconds():.0f} seconds")
                        print(f"* Pause count: {current_state['session_metadata'].get('pause_count', 0)}")
                continue
            
            # Process user input
            try:
                config = {
                    "thread_id": session_id,
                    "checkpoint_ns": "interview",
                    "checkpoint_id": session_id
                }
                
                # Send only the new message - checkpointer handles state
                result = workflow.invoke(
                    {"messages": [HumanMessage(content=user_input)]},
                    config=config
                )
                
                # Update current state
                current_state = result
                
                # Update session state
                session_manager.update_session(session_id, current_state)
                
                # Extract and print AI response
                messages = result.get("messages", [])
                if messages:
                    ai_response = messages[-1].content
                    print("\nAI:", ai_response)
                    
            except Exception as e:
                logger.error(f"Error processing input: {e}")
                print("\nSorry, there was an error processing your input. Please try again.")
                
    except Exception as e:
        logger.error(f"Interview session error: {e}")
        print("\nAn error occurred during the interview. Please try again.")

@cli.command()
def list_sessions():
    """List all active interview sessions."""
    active_sessions = session_manager.list_active_sessions()
    
    if not active_sessions:
        print("\nNo active sessions found.")
        return
        
    print("\nActive Interview Sessions:")
    print("=" * 50)
    for session_id, info in active_sessions.items():
        print(f"\nSession ID: {session_id}")
        print(f"Candidate ID: {info.get('candidate_id', 'Not provided')}")
        print(f"Stage: {info.get('interview_stage', 'unknown')}")
        
        metadata = info.get('metadata', {})
        if metadata:
            created = datetime.fromisoformat(metadata.get('created_at', ''))
            last_active = datetime.fromisoformat(metadata.get('last_active', ''))
            elapsed = datetime.now() - created
            idle = datetime.now() - last_active
            
            print(f"Created: {created.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Last active: {last_active.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Total duration: {elapsed.total_seconds():.0f} seconds")
            print(f"Idle time: {idle.total_seconds():.0f} seconds")
            print(f"Pause count: {metadata.get('pause_count', 0)}")
        print("-" * 30)

@cli.command()
def cleanup():
    """Clean up expired interview sessions."""
    count = session_manager.cleanup_expired_sessions()
    print(f"\nCleaned up {count} expired sessions.")

if __name__ == "__main__":
    cli() 