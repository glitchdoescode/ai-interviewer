"""
Command Line Interface for the AI Interviewer platform.

This module provides a CLI for interacting with the AI Interviewer.
"""
import os
import sys
import asyncio
import logging
import argparse
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Import the AIInterviewer class
from ai_interviewer.core.ai_interviewer import AIInterviewer

class InterviewCLI:
    """Command Line Interface for interacting with the AI Interviewer."""
    
    def __init__(self):
        """Initialize the CLI with an AIInterviewer instance."""
        self.interviewer = AIInterviewer()
        self.user_id = f"cli-user-{uuid.uuid4()}"
        self.interview_history = []
    
    async def start_interview(self):
        """Start an interactive interview session."""
        print("\n🤖 AI Interviewer - Technical Interview Simulator 🤖\n")
        print("Welcome to your technical interview simulation!")
        print("Type your responses after each question. Type 'exit' to end the interview.\n")
        
        while True:
            # Get user input
            user_input = input("\n👤 You: ")
            
            # Check for exit command
            if user_input.lower() in ["exit", "quit", "bye"]:
                print("\nThank you for participating in this interview simulation. Goodbye!")
                break
            
            # Process user input and get response
            response = await self.interviewer.run_interview(self.user_id, user_input)
            
            # Display AI response
            print(f"\n🤖 Interviewer: {response}")
            
            # Store in history
            timestamp = datetime.now().isoformat()
            self.interview_history.append({
                "timestamp": timestamp,
                "user": user_input,
                "ai": response
            })
    
    def save_interview_transcript(self, filename: Optional[str] = None):
        """
        Save the interview transcript to a file.
        
        Args:
            filename: Optional filename to save to
        """
        if not self.interview_history:
            print("No interview history to save.")
            return
            
        # Generate default filename if none provided
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"interview_transcript_{timestamp}.txt"
        
        try:
            with open(filename, "w") as f:
                f.write("AI INTERVIEW TRANSCRIPT\n")
                f.write("======================\n\n")
                
                for entry in self.interview_history:
                    time_str = datetime.fromisoformat(entry["timestamp"]).strftime("%H:%M:%S")
                    f.write(f"[{time_str}] You: {entry['user']}\n")
                    f.write(f"[{time_str}] Interviewer: {entry['ai']}\n\n")
                
            print(f"\nInterview transcript saved to {filename}")
        except Exception as e:
            logger.error(f"Error saving transcript: {e}")
            print(f"Failed to save transcript: {str(e)}")

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="AI Technical Interviewer CLI")
    parser.add_argument("--save", type=str, help="Save interview transcript to the specified file")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    return parser.parse_args()

async def _main():
    """Async main function."""
    args = parse_args()
    
    # Set logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create and start CLI
    cli = InterviewCLI()
    try:
        await cli.start_interview()
    except KeyboardInterrupt:
        print("\nInterview ended by user.")
    
    # Save transcript if requested
    if args.save:
        cli.save_interview_transcript(args.save)
    else:
        # Ask if user wants to save the transcript
        save_response = input("\nDo you want to save the interview transcript? (y/n): ")
        if save_response.lower() in ["y", "yes"]:
            filename = input("Enter filename (leave blank for auto-generated name): ")
            cli.save_interview_transcript(filename if filename else None)

def main():
    """Main entry point for the CLI, used by setup.py entry_points."""
    asyncio.run(_main())

if __name__ == "__main__":
    main() 