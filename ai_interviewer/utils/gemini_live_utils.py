"""
Utilities for interacting with Google's Gemini Live API for STT and TTS.
"""
import asyncio
import logging
import os
import numpy as np
from google.genai import types as genai_types
from google.genai.types import (
    Content,
    GenerateContentConfig,
    SafetySetting,
    LiveConnectConfig, 
    SpeechConfig,
    VoiceConfig,
    PrebuiltVoiceConfig,
    Part
)
from ai_interviewer.utils.config import get_gemini_live_config
from google import genai
import base64

logger = logging.getLogger(__name__)

MODEL_NAME = "gemini-2.5-flash-preview-05-20"

async def generate_response_stream(prompt: str, temperature: float = 1.0, max_tokens: int = 65535):
    """
    Generate streaming responses from Gemini 2.5 Flash Preview model.
    
    Args:
        prompt (str): The input prompt text
        temperature (float): Sampling temperature (0.0 to 1.0)
        max_tokens (int): Maximum number of tokens to generate
        
    Yields:
        str: Generated text chunks
    """
    try:
        config = get_gemini_live_config()
        api_key = config.get("api_key")
        
        if not api_key:
            logger.error("Gemini API key not configured")
            yield ""
            return

        # Initialize client with just the API key
        client = genai.Client(api_key=api_key)

        contents = [
            genai_types.Content(
                role="user",
                parts=[{"text": prompt}]
            )
        ]

        generate_content_config = genai_types.GenerateContentConfig(
            temperature=temperature,
            top_p=1,
            seed=0,
            max_output_tokens=max_tokens,
            safety_settings=[
                genai_types.SafetySetting(
                    category="HARM_CATEGORY_HATE_SPEECH",
                    threshold="OFF"
                ),
                genai_types.SafetySetting(
                    category="HARM_CATEGORY_DANGEROUS_CONTENT",
                    threshold="OFF"
                ),
                genai_types.SafetySetting(
                    category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    threshold="OFF"
                ),
                genai_types.SafetySetting(
                    category="HARM_CATEGORY_HARASSMENT",
                    threshold="OFF"
                )
            ],
        )

        response_stream = client.models.generate_content_stream(
            model=MODEL_NAME,
            contents=contents,
            config=generate_content_config,
        )

        for chunk in response_stream:
            if chunk.text:
                yield chunk.text

    except Exception as e:
        logger.error(f"Error in Gemini response generation: {str(e)}")
        yield ""

async def transcribe_audio_gemini(audio_bytes: bytes) -> str:
    """
    Transcribe audio using Gemini 2.5 Flash Preview model.
    
    Args:
        audio_bytes (bytes): Raw audio data in WAV format
        
    Returns:
        str: Transcribed text
    """
    try:
        config = get_gemini_live_config()
        api_key = config.get("api_key")
        
        if not api_key:
            logger.error("Gemini API key not configured")
            return ""
            
        # Initialize client with just the API key
        client = genai.Client(api_key=api_key)
        
        # Convert audio bytes to base64
        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')
        
        # Create the content with audio data
        content = genai_types.Content(
            role="user",
            parts=[{
                    "inline_data": {
                        "mime_type": "audio/wav",
                        "data": audio_base64
                    }
                }]
        )
        
        logger.info("Sending audio to Gemini for transcription")
        
        # Use models.generate_content with proper parameters
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[content]
        )
        
        if response and hasattr(response, 'text'):
            transcription = response.text
            logger.info(f"Transcription completed successfully: {transcription}")
            return transcription.strip()
        
        logger.warning("No transcription received from Gemini")
        return ""
        
    except Exception as e:
        logger.error(f"Error in Gemini transcription: {str(e)}")
        return ""

async def synthesize_speech_gemini(text_input: str, voice_name: str = "Aoede") -> bytes:
    """
    Synthesizes speech from text using Gemini TTS API and returns audio data.

    Args:
        text_input: The text to synthesize.
        voice_name: The prebuilt voice name to use. Must be one of the allowed voices:
                   achernar, achird, algenib, algieba, alnilam, aoede, autonoe, callirrhoe, 
                   charon, despina, enceladus, erinome, fenrir, gacrux, iapetus, kore, 
                   laomedeia, leda, orus, puck, pulcherrima, rasalgethi, sadachbia, 
                   sadaltager, schedar, sulafat, umbriel, vindemiatrix, zephyr, zubenelgenubi

    Returns:
        The synthesized audio data in bytes, or empty bytes if synthesis fails.
    """
    gem_config = get_gemini_live_config()
    api_key = gem_config.get("api_key")

    if not api_key:
        logger.error("Gemini API key not configured for TTS.")
        return b""

    # Ensure voice_name is one of the allowed voices
    allowed_voices = [
        "achernar", "achird", "algenib", "algieba", "alnilam", "aoede", "autonoe", 
        "callirrhoe", "charon", "despina", "enceladus", "erinome", "fenrir", "gacrux", 
        "iapetus", "kore", "laomedeia", "leda", "orus", "puck", "pulcherrima", 
        "rasalgethi", "sadachbia", "sadaltager", "schedar", "sulafat", "umbriel", 
        "vindemiatrix", "zephyr", "zubenelgenubi"
    ]
    
    if voice_name.lower() not in [v.lower() for v in allowed_voices]:
        logger.warning(f"Voice '{voice_name}' not in allowed list. Using 'Aoede' instead.")
        voice_name = "Aoede"  # Default to a known working voice

    try:
        client = genai.Client(api_key=api_key)
        
        logger.info(f"Generating TTS with model: gemini-2.5-flash-preview-tts, voice: {voice_name}")
        
        response = client.models.generate_content(
            model="gemini-2.5-flash-preview-tts",
            contents=text_input,
            config=genai_types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=genai_types.SpeechConfig(
                    voice_config=genai_types.VoiceConfig(
                        prebuilt_voice_config=genai_types.PrebuiltVoiceConfig(
                            voice_name=voice_name,
                        )
                    )
                ),
            )
        )
        
        if response.candidates and response.candidates[0].content.parts:
            audio_data = response.candidates[0].content.parts[0].inline_data.data
            logger.info(f"Successfully generated {len(audio_data)} bytes of audio data.")
            return audio_data
        else:
            logger.warning("No audio data received from Gemini TTS.")
            return b""

    except Exception as e:
        logger.error(f"Error during Gemini TTS: {e}", exc_info=True)
        return b"" 