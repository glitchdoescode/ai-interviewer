"""
Voice-enabled CLI for the AI Interviewer platform.

This module provides a voice interface for interacting with the AI Interviewer
using speech-to-text and text-to-speech capabilities.
"""
import os
import sys
import asyncio
import logging
import argparse
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Import the AIInterviewer class and speech utilities
from ai_interviewer.core.ai_interviewer import AIInterviewer
from ai_interviewer.utils.speech_utils import VoiceHandler
from ai_interviewer.utils.config import get_speech_config


class VoiceInterviewCLI:
    """Voice-enabled CLI for interacting with the AI Interviewer."""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the CLI with an AIInterviewer instance and VoiceHandler.
        
        Args:
            api_key: Optional Deepgram API key
        """
        # Get speech configuration
        speech_config = get_speech_config()
        self.api_key = api_key or speech_config["api_key"]
        
        if not self.api_key:
            logger.error("Deepgram API key is required. Set DEEPGRAM_API_KEY environment variable or pass as parameter.")
            raise ValueError("Deepgram API key is required")
        
        # Initialize voice handler
        self.voice_handler = VoiceHandler(api_key=self.api_key)
        
        # Initialize AI Interviewer
        self.interviewer = AIInterviewer()
        
        # Generate a random user ID
        self.user_id = f"voice-user-{uuid.uuid4()}"
        
        # Keep track of session ID
        self.session_id = None
        
        # Interview history
        self.interview_history = []
        
        # Speech configuration
        self.recording_duration = speech_config["recording_duration"]
        self.sample_rate = speech_config["sample_rate"]
        self.tts_voice = speech_config["tts_voice"]
        self.silence_threshold = speech_config["silence_threshold"]
        self.silence_duration = speech_config["silence_duration"]
        
        logger.info(f"Voice CLI initialized with max recording: {self.recording_duration}s, "
                   f"sample rate: {self.sample_rate}Hz, voice: {self.tts_voice}, "
                   f"silence detection: {self.silence_duration}s pause at threshold {self.silence_threshold}")
    
    async def start_interview(self):
        """Start an interactive voice-based interview session."""
        print("\n🔊 AI Voice Interviewer - Technical Interview Simulator 🎙️\n")
        print("Welcome to your voice-based technical interview simulation!")
        print("Speak after each prompt. Say 'exit' to end the interview.\n")
        
        # Initial greeting from the AI
        print("\n🤖 AI Interviewer is introducing itself...")
        
        # Get first response without user input (this starts the interview)
        ai_response, self.session_id = await self.interviewer.run_interview(
            self.user_id, "Hello, I'm ready for my interview."
        )
        
        # Speak the initial response
        print(f"🤖 Interviewer: {ai_response}")
        await self.voice_handler.speak(
            text=ai_response,
            voice=self.tts_voice,
            play_audio=True
        )
        
        # Store in history
        timestamp = datetime.now().isoformat()
        self.interview_history.append({
            "timestamp": timestamp,
            "user": "Hello, I'm ready for my interview.",
            "ai": ai_response
        })
        
        # Interview loop
        while True:
            # Listen for user input with silence detection
            print("\n🎙️ Listening... (speak now, pause for 2s to finish)")
            user_input = await self.voice_handler.listen(
                duration_seconds=self.recording_duration,
                sample_rate=self.sample_rate,
                channels=1,
                silence_threshold=self.silence_threshold,
                silence_duration=self.silence_duration
            )
            
            # If empty transcription or error, retry
            if not user_input:
                print("❌ Nothing heard or transcription failed. Please try again.")
                continue
            
            # Add debug logging of transcription
            logger.debug(f"Transcribed text: {user_input[:100]}{'...' if len(user_input) > 100 else ''}")
                
            print(f"👤 You: {user_input}")
            
            # Check for exit command
            if user_input.lower() in ["exit", "quit", "bye", "goodbye", "end interview"]:
                print("\nThank you for participating in this interview simulation. Goodbye!")
                break
            
            # Process user input and get response
            print("🤖 AI Interviewer is thinking...")
            ai_response, self.session_id = await self.interviewer.run_interview(
                self.user_id, user_input, self.session_id
            )
            
            # Display and speak AI response
            print(f"🤖 Interviewer: {ai_response}")
            await self.voice_handler.speak(
                text=ai_response,
                voice=self.tts_voice,
                play_audio=True
            )
            
            # Store in history
            timestamp = datetime.now().isoformat()
            self.interview_history.append({
                "timestamp": timestamp,
                "user": user_input,
                "ai": ai_response
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
            filename = f"voice_interview_transcript_{timestamp}.txt"
        
        try:
            with open(filename, "w") as f:
                f.write("AI VOICE INTERVIEW TRANSCRIPT\n")
                f.write("===========================\n\n")
                
                for entry in self.interview_history:
                    time_str = datetime.fromisoformat(entry["timestamp"]).strftime("%H:%M:%S")
                    f.write(f"[{time_str}] You: {entry['user']}\n")
                    f.write(f"[{time_str}] Interviewer: {entry['ai']}\n\n")
                
            print(f"\nInterview transcript saved to {filename}")
        except Exception as e:
            logger.error(f"Error saving transcript: {e}")
            print(f"Failed to save transcript: {str(e)}")
    
    async def cleanup(self):
        """Clean up resources."""
        try:
            if hasattr(self.interviewer, 'cleanup'):
                self.interviewer.cleanup()
            logger.info("Resources cleaned up")
        except Exception as e:
            logger.error(f"Error cleaning up resources: {e}")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="AI Voice Interviewer CLI")
    parser.add_argument(
        "--api-key", 
        type=str, 
        help="Deepgram API key (overrides environment variable)"
    )
    parser.add_argument(
        "--save", 
        type=str, 
        help="Save interview transcript to the specified file"
    )
    parser.add_argument(
        "--max-duration", 
        type=float, 
        default=30.0,
        help="Maximum recording duration in seconds (default: 30.0)"
    )
    parser.add_argument(
        "--silence-duration", 
        type=float, 
        default=2.0,
        help="How long of a pause (in seconds) before ending recording (default: 2.0)"
    )
    parser.add_argument(
        "--silence-threshold", 
        type=float, 
        default=0.03,
        help="Volume threshold to detect silence (0.0-1.0) (default: 0.03)"
    )
    parser.add_argument(
        "--voice", 
        type=str, 
        default="nova",
        help="Voice to use for text-to-speech (default: nova)"
    )
    parser.add_argument(
        "--debug", 
        action="store_true", 
        help="Enable debug logging"
    )
    return parser.parse_args()


async def _main():
    """Async main function."""
    args = parse_args()
    
    # Set logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Get API key from arguments or environment
    api_key = args.api_key or os.environ.get("DEEPGRAM_API_KEY")
    
    if not api_key:
        print("❌ Error: Deepgram API key is required. Set DEEPGRAM_API_KEY environment variable or use --api-key.")
        return
    
    # Create and start CLI
    try:
        cli = VoiceInterviewCLI(api_key=api_key)
        
        # Override defaults with command line arguments
        if args.max_duration:
            cli.recording_duration = args.max_duration
        if args.silence_duration:
            cli.silence_duration = args.silence_duration
        if args.silence_threshold:
            cli.silence_threshold = args.silence_threshold
        if args.voice:
            cli.tts_voice = args.voice
        
        # Start interview
        await cli.start_interview()
    except KeyboardInterrupt:
        print("\nInterview ended by user.")
    except Exception as e:
        logger.error(f"Error in voice interview: {e}")
        print(f"❌ Error: {str(e)}")
    finally:
        if 'cli' in locals():
            await cli.cleanup()
    
    # Save transcript if requested
    if 'cli' in locals():
        if args.save:
            cli.save_interview_transcript(args.save)
        else:
            # Ask if user wants to save the transcript
            save_response = input("\nDo you want to save the interview transcript? (y/n): ")
            if save_response.lower() in ["y", "yes"]:
                filename = input("Enter filename (leave blank for auto-generated name): ")
                cli.save_interview_transcript(filename if filename else None)


def main():
    """Main entry point for the voice CLI."""
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        print("\nInterview ended by user.")


if __name__ == "__main__":
    main() 