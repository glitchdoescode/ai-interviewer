"""
Transcript utilities for AI Interviewer.

This module provides functionality for working with interview transcripts,
including saving, loading, and formatting.
"""
import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

def save_transcript_to_file(
    transcript: List[Dict[str, Any]],
    filename: Optional[str] = None,
    directory: str = "transcripts"
) -> str:
    """
    Save an interview transcript to a file.
    
    Args:
        transcript: List of transcript entries
        filename: Optional filename (auto-generated if None)
        directory: Directory to save the transcript in
        
    Returns:
        Path to the saved transcript file
    """
    # Create directory if it doesn't exist
    if not os.path.exists(directory):
        os.makedirs(directory)
        logger.info(f"Created directory {directory}")
    
    # Generate default filename if none provided
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"interview_transcript_{timestamp}.txt"
    
    # Full path to the transcript file
    filepath = os.path.join(directory, filename)
    
    try:
        with open(filepath, "w") as f:
            f.write("AI INTERVIEW TRANSCRIPT\n")
            f.write("======================\n\n")
            
            for entry in transcript:
                time_str = entry.get("timestamp", "")
                if time_str:
                    try:
                        # Format timestamp if it's ISO format
                        dt = datetime.fromisoformat(time_str)
                        time_str = dt.strftime("%H:%M:%S")
                    except (ValueError, TypeError):
                        # Use as is if it's not a valid ISO timestamp
                        pass
                    
                f.write(f"[{time_str}] You: {entry.get('user', '')}\n")
                f.write(f"[{time_str}] Interviewer: {entry.get('ai', '')}\n\n")
        
        logger.info(f"Saved transcript to {filepath}")
        return filepath
    except Exception as e:
        logger.error(f"Error saving transcript: {e}")
        raise

def save_transcript_to_json(
    transcript: List[Dict[str, Any]],
    metadata: Optional[Dict[str, Any]] = None,
    filename: Optional[str] = None,
    directory: str = "transcripts"
) -> str:
    """
    Save an interview transcript to a JSON file.
    
    Args:
        transcript: List of transcript entries
        metadata: Optional metadata to include
        filename: Optional filename (auto-generated if None)
        directory: Directory to save the transcript in
        
    Returns:
        Path to the saved JSON file
    """
    # Create directory if it doesn't exist
    if not os.path.exists(directory):
        os.makedirs(directory)
        logger.info(f"Created directory {directory}")
    
    # Generate default filename if none provided
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"interview_transcript_{timestamp}.json"
    
    # Full path to the transcript file
    filepath = os.path.join(directory, filename)
    
    # Prepare data
    data = {
        "metadata": metadata or {},
        "timestamp": datetime.now().isoformat(),
        "transcript": transcript
    }
    
    try:
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Saved transcript to {filepath}")
        return filepath
    except Exception as e:
        logger.error(f"Error saving transcript: {e}")
        raise

def load_transcript_from_json(filepath: str) -> Dict[str, Any]:
    """
    Load an interview transcript from a JSON file.
    
    Args:
        filepath: Path to the JSON file
        
    Returns:
        Dictionary with transcript data
    """
    try:
        with open(filepath, "r") as f:
            data = json.load(f)
        
        logger.info(f"Loaded transcript from {filepath}")
        return data
    except Exception as e:
        logger.error(f"Error loading transcript: {e}")
        raise

def format_transcript_for_display(transcript: List[Dict[str, Any]]) -> str:
    """
    Format a transcript for display.
    
    Args:
        transcript: List of transcript entries
        
    Returns:
        Formatted transcript as a string
    """
    formatted = "AI INTERVIEW TRANSCRIPT\n"
    formatted += "======================\n\n"
    
    for entry in transcript:
        time_str = entry.get("timestamp", "")
        if time_str:
            try:
                dt = datetime.fromisoformat(time_str)
                time_str = dt.strftime("%H:%M:%S")
            except (ValueError, TypeError):
                pass
        
        formatted += f"[{time_str}] You: {entry.get('user', '')}\n"
        formatted += f"[{time_str}] Interviewer: {entry.get('ai', '')}\n\n"
    
    return formatted

def extract_messages_from_transcript(transcript: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Extract messages from a transcript for use with the LLM.
    
    Args:
        transcript: List of transcript entries
        
    Returns:
        List of message dictionaries
    """
    messages = []
    
    for entry in transcript:
        # Add user message
        if "user" in entry and entry["user"]:
            messages.append({"role": "user", "content": entry["user"]})
        
        # Add AI message
        if "ai" in entry and entry["ai"]:
            messages.append({"role": "assistant", "content": entry["ai"]})
    
    return messages 