"""
SSML utilities for {SYSTEM_NAME} platform.

This module provides utilities for working with Speech Synthesis Markup Language (SSML)
to enhance text-to-speech output.
"""
import re
from typing import Dict, List, Optional, Any, Union
import logging
from xml.etree import ElementTree as ET

# Configure logging
logger = logging.getLogger(__name__)

class SSMLBuilder:
    """Helper class for building valid SSML markup."""
    
    def __init__(self, text: str = ""):
        """
        Initialize the SSML builder.
        
        Args:
            text: Optional initial text
        """
        self.text = text
        self._validate_text()
    
    def _validate_text(self):
        """Ensure text doesn't contain invalid characters for SSML."""
        # Replace problematic characters
        self.text = (
            self.text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("'", "&apos;")
            .replace('"', "&quot;")
        )
    
    def add_break(self, time: str = "500ms") -> 'SSMLBuilder':
        """
        Add a pause in speech.
        
        Args:
            time: Duration of pause (e.g., "500ms", "1s")
            
        Returns:
            Self for chaining
        """
        self.text += f'<break time="{time}"/>'
        return self
    
    def add_emphasis(self, text: str, level: str = "moderate") -> 'SSMLBuilder':
        """
        Add emphasized text.
        
        Args:
            text: Text to emphasize
            level: Emphasis level ("strong", "moderate", "reduced")
            
        Returns:
            Self for chaining
        """
        if level not in ["strong", "moderate", "reduced"]:
            level = "moderate"
        self._validate_text()
        self.text += f'<emphasis level="{level}">{text}</emphasis>'
        return self
    
    def add_prosody(self, text: str, rate: Optional[str] = None, 
                    pitch: Optional[str] = None, volume: Optional[str] = None) -> 'SSMLBuilder':
        """
        Add text with modified prosody.
        
        Args:
            text: Text to modify
            rate: Speech rate (e.g., "slow", "medium", "fast", "80%", "120%")
            pitch: Voice pitch (e.g., "low", "medium", "high", "-10%", "+20%")
            volume: Volume (e.g., "silent", "soft", "medium", "loud")
            
        Returns:
            Self for chaining
        """
        attrs = []
        if rate:
            attrs.append(f'rate="{rate}"')
        if pitch:
            attrs.append(f'pitch="{pitch}"')
        if volume:
            attrs.append(f'volume="{volume}"')
            
        attrs_str = " ".join(attrs)
        self._validate_text()
        self.text += f'<prosody {attrs_str}>{text}</prosody>'
        return self
    
    def add_say_as(self, text: str, interpret_as: str) -> 'SSMLBuilder':
        """
        Add text with specific interpretation.
        
        Args:
            text: Text to interpret
            interpret_as: Interpretation type (e.g., "characters", "cardinal", "ordinal")
            
        Returns:
            Self for chaining
        """
        self._validate_text()
        self.text += f'<say-as interpret-as="{interpret_as}">{text}</say-as>'
        return self
    
    def add_text(self, text: str) -> 'SSMLBuilder':
        """
        Add plain text.
        
        Args:
            text: Text to add
            
        Returns:
            Self for chaining
        """
        self.text += text
        return self
    
    def build(self) -> str:
        """
        Build the final SSML string.
        
        Returns:
            Complete SSML markup
        """
        return f'<speak>{self.text}</speak>'

def add_automatic_ssml(text: str) -> str:
    """
    Automatically add SSML tags to improve speech naturalness.
    
    This function analyzes the text and adds appropriate SSML tags based on
    punctuation, sentence structure, and common patterns.
    
    Args:
        text: Plain text to enhance
        
    Returns:
        Text with SSML markup
    """
    builder = SSMLBuilder()
    
    # Split into sentences
    sentences = re.split(r'([.!?]+)', text)
    
    for i, part in enumerate(sentences):
        if not part.strip():
            continue
            
        # Check if this is punctuation
        if re.match(r'[.!?]+', part):
            # Add longer pause for question marks and exclamation points
            if '?' in part or '!' in part:
                builder.add_break("750ms")
            else:
                builder.add_break("500ms")
            continue
            
        # Handle emphasis for important phrases
        emphasis_patterns = [
            (r'\b(must|never|always|critical|important)\b', 'strong'),
            (r'\b(should|could|would|might)\b', 'moderate'),
            (r'\b(maybe|perhaps|possibly)\b', 'reduced')
        ]
        
        current_text = part
        for pattern, level in emphasis_patterns:
            current_text = re.sub(
                pattern,
                lambda m: f'<emphasis level="{level}">{m.group()}</emphasis>',
                current_text,
                flags=re.IGNORECASE
            )
        
        # Add the processed sentence
        builder.add_text(current_text)
    
    return builder.build()

def validate_ssml(ssml: str) -> bool:
    """
    Validate SSML markup.
    
    Args:
        ssml: SSML string to validate
        
    Returns:
        True if valid, False otherwise
    """
    try:
        # Parse XML
        root = ET.fromstring(ssml)
        
        # Check root element is <speak>
        if root.tag != 'speak':
            logger.error("Root element must be <speak>")
            return False
        
        # Validate allowed tags and attributes
        allowed_tags = {
            'break': {'time', 'strength'},
            'emphasis': {'level'},
            'prosody': {'rate', 'pitch', 'volume'},
            'say-as': {'interpret-as'},
            'speak': set()
        }
        
        def validate_element(elem):
            if elem.tag not in allowed_tags:
                logger.error(f"Invalid tag: {elem.tag}")
                return False
                
            # Check attributes
            allowed_attrs = allowed_tags[elem.tag]
            for attr in elem.attrib:
                if attr not in allowed_attrs:
                    logger.error(f"Invalid attribute '{attr}' for tag '{elem.tag}'")
                    return False
            
            # Recursively validate children
            return all(validate_element(child) for child in elem)
        
        return validate_element(root)
    except ET.ParseError as e:
        logger.error(f"Invalid SSML syntax: {e}")
        return False
    except Exception as e:
        logger.error(f"Error validating SSML: {e}")
        return False 