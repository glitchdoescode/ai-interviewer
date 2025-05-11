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

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage

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

def extract_messages_from_transcript(transcript: List[Dict[str, Any]], 
                                    system_prompt: Optional[str] = None) -> List[BaseMessage]:
    """
    Convert a transcript (list of message exchanges) to LangChain message objects.
    
    Args:
        transcript: List of message exchanges with 'user' and 'ai' keys
        system_prompt: Optional system prompt to prepend to the messages
        
    Returns:
        List of LangChain message objects
    """
    messages = []
    
    # Add system message if provided
    if system_prompt:
        messages.append(SystemMessage(content=system_prompt))
    
    # Convert transcript entries to messages
    for entry in transcript:
        try:
            # Add user message
            if "user" in entry and entry["user"]:
                messages.append(HumanMessage(content=entry["user"]))
            
            # Add AI message
            if "ai" in entry and entry["ai"]:
                messages.append(AIMessage(content=entry["ai"]))
        except Exception as e:
            logger.error(f"Error converting transcript entry to messages: {e}")
            # Continue with other entries
    
    return messages

def messages_to_transcript(messages: List[BaseMessage]) -> List[Dict[str, Any]]:
    """
    Convert LangChain message objects to transcript format.
    
    Args:
        messages: List of LangChain message objects
        
    Returns:
        List of message exchanges in transcript format
    """
    transcript = []
    timestamp = datetime.now().isoformat()
    
    # Skip system messages at the beginning
    start_idx = 0
    if messages and isinstance(messages[0], SystemMessage):
        start_idx = 1
    
    # Process message pairs
    for i in range(start_idx, len(messages) - 1, 2):
        try:
            # Check if we have a human-AI message pair
            if i+1 < len(messages) and isinstance(messages[i], HumanMessage) and isinstance(messages[i+1], AIMessage):
                entry = {
                    "timestamp": timestamp,
                    "user": messages[i].content,
                    "ai": messages[i+1].content
                }
                transcript.append(entry)
        except Exception as e:
            logger.error(f"Error converting messages to transcript: {e}")
            # Continue with other messages
    
    # Handle last message if it's unpaired
    if len(messages) > start_idx and (len(messages) - start_idx) % 2 == 1:
        if isinstance(messages[-1], HumanMessage):
            transcript.append({
                "timestamp": timestamp,
                "user": messages[-1].content,
                "ai": ""
            })
    
    return transcript

def serialize_message(message: BaseMessage) -> Dict[str, Any]:
    """
    Serialize a LangChain message object to a dictionary.
    
    Args:
        message: LangChain message object
        
    Returns:
        Dictionary representation of the message
    """
    message_type = message.__class__.__name__
    result = {
        "type": message_type,
        "content": message.content,
        "additional_kwargs": message.additional_kwargs,
    }
    
    # Add special handling for tool calls
    if hasattr(message, "tool_calls") and message.tool_calls:
        result["tool_calls"] = message.tool_calls
        
    return result

def deserialize_message(data: Dict[str, Any]) -> BaseMessage:
    """
    Deserialize a dictionary to a LangChain message object.
    
    Args:
        data: Dictionary representation of a message
        
    Returns:
        LangChain message object
    """
    message_type = data.get("type")
    content = data.get("content", "")
    additional_kwargs = data.get("additional_kwargs", {})
    
    # Create the appropriate message type
    if message_type == "HumanMessage":
        return HumanMessage(content=content, additional_kwargs=additional_kwargs)
    elif message_type == "AIMessage":
        message = AIMessage(content=content, additional_kwargs=additional_kwargs)
        # Handle tool calls if present
        if "tool_calls" in data:
            message.tool_calls = data["tool_calls"]
        return message
    elif message_type == "SystemMessage":
        return SystemMessage(content=content, additional_kwargs=additional_kwargs)
    
    # Default to base message if type not recognized
    return BaseMessage(content=content, additional_kwargs=additional_kwargs)

def safe_extract_content(message) -> str:
    """
    Safely extract content from message objects of various types.
    
    Args:
        message: A message object that could have content in different formats
        
    Returns:
        Extracted content as a string
    """
    # If the message is None, return empty string
    if message is None:
        return ""
    
    try:
        # If there's a content attribute
        if hasattr(message, "content"):
            content = message.content
            
            # Handle different content types
            if isinstance(content, str):
                return content
            elif isinstance(content, list):
                # Join list elements, handling non-string elements
                return " ".join([str(item) if item is not None else "" for item in content])
            elif content is None:
                return ""
            else:
                # Try to convert other types to string
                return str(content)
                
        # If there's no content attribute but the object is string-like
        elif isinstance(message, (str, bytes)):
            return str(message)
            
        # If it's a dict with a content key
        elif isinstance(message, dict) and "content" in message:
            content = message["content"]
            if isinstance(content, str):
                return content
            elif isinstance(content, list):
                return " ".join([str(item) if item is not None else "" for item in content])
            elif content is None:
                return ""
            else:
                return str(content)
                
        # If it's some other object, try to convert to string
        else:
            return str(message)
            
    except Exception as e:
        # If anything goes wrong, log and return empty string
        logging.error(f"Error extracting content from message: {e}")
        return ""

def format_conversation_for_llm(messages, max_messages=10):
    """
    Format a list of messages into a readable conversation format for an LLM.
    
    Args:
        messages: List of messages (can be BaseMessage objects or dicts)
        max_messages: Maximum number of recent messages to include
        
    Returns:
        Formatted conversation string
    """
    if not messages:
        return ""
    
    # Take only the most recent messages if we have too many
    messages = messages[-min(len(messages), max_messages):]
    
    formatted_lines = []
    for msg in messages:
        # Extract content safely
        content = safe_extract_content(msg)
        
        # Determine speaker
        if isinstance(msg, HumanMessage) or (isinstance(msg, dict) and msg.get("type") == "human"):
            speaker = "User"
        elif isinstance(msg, AIMessage) or (isinstance(msg, dict) and msg.get("type") == "ai"):
            speaker = "Interviewer"
        elif isinstance(msg, SystemMessage) or (isinstance(msg, dict) and msg.get("type") == "system"):
            speaker = "System"
        else:
            speaker = "Unknown"
        
        # Add to formatted lines
        formatted_lines.append(f"{speaker}: {content}")
    
    return "\n".join(formatted_lines) 