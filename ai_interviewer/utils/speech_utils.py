"""
Speech utilities for AI Interviewer platform.

This module provides speech-to-text (STT) and text-to-speech (TTS) 
functionality using Deepgram's API.
"""
import os
import asyncio
import logging
import tempfile
import wave
import pyaudio
import numpy as np
from typing import Optional, Tuple, Dict, Any, Union, List, BinaryIO
import aiohttp
import base64
from pathlib import Path
import json
import time

# Configure logging
logger = logging.getLogger(__name__)

class DeepgramSTT:
    """
    Speech-to-Text functionality using Deepgram's API.
    
    This class provides methods for transcribing audio from a file or microphone.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the DeepgramSTT class.
        
        Args:
            api_key: Deepgram API key (if None, uses environment variable)
        """
        self.api_key = api_key or os.environ.get("DEEPGRAM_API_KEY")
        if not self.api_key:
            raise ValueError("Deepgram API key is required. Set DEEPGRAM_API_KEY environment variable or pass as parameter.")
        
        # API endpoint for Deepgram Nova ASR
        self.base_url = "https://api.deepgram.com/v1/listen"
        
        # Default parameters for transcription
        self.default_params = {
            "model": "nova-2",
            "language": "en",
            "smart_format": True,
            "punctuate": True,
            "utterances": True  # Include utterance boundaries
        }
        
        logger.info("Initialized Deepgram STT client")
    
    async def transcribe_file(self, audio_file: Union[str, Path, BinaryIO], 
                             params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Transcribe audio from a file using Deepgram's API.
        
        Args:
            audio_file: Path to audio file or file-like object
            params: Additional parameters to pass to Deepgram API
            
        Returns:
            Dictionary with transcription results
        """
        # Combine default and custom parameters
        request_params = {**self.default_params, **(params or {})}
        
        # Construct query parameters
        query_params = "&".join([f"{k}={v}" for k, v in request_params.items()])
        url = f"{self.base_url}?{query_params}"
        
        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "audio/wav"  # Assuming WAV format - adjust as needed
        }
        
        try:
            # Handle string/Path or file-like object
            if isinstance(audio_file, (str, Path)):
                with open(audio_file, 'rb') as f:
                    audio_data = f.read()
            else:
                # Assuming audio_file is a file-like object in binary mode
                audio_file.seek(0)
                audio_data = audio_file.read()
            
            # Make API request
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, data=audio_data) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Deepgram API error: {response.status} - {error_text}")
                        return {
                            "success": False,
                            "error": f"API error: {response.status}",
                            "details": error_text
                        }
                    
                    result = await response.json()
                    
                    # Extract transcript text
                    transcript = result.get("results", {}).get("channels", [{}])[0].get("alternatives", [{}])[0].get("transcript", "")
                    
                    return {
                        "success": True,
                        "transcript": transcript,
                        "raw_response": result
                    }
        
        except Exception as e:
            logger.error(f"Error transcribing audio file: {e}")
            return {
                "success": False,
                "error": f"Error transcribing audio: {str(e)}"
            }
    
    async def transcribe_microphone(self, 
                                  duration_seconds: float = 10.0,
                                  sample_rate: int = 16000,
                                  channels: int = 1,
                                  chunk_size: int = 1024,
                                  params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Record audio from microphone and transcribe using Deepgram's API.
        
        Args:
            duration_seconds: Duration to record in seconds
            sample_rate: Audio sample rate
            channels: Number of audio channels
            chunk_size: Audio chunk size for recording
            params: Additional parameters to pass to Deepgram API
            
        Returns:
            Dictionary with transcription results
        """
        # Record audio from microphone
        audio_data = await self._record_audio(
            duration_seconds=duration_seconds,
            sample_rate=sample_rate,
            channels=channels,
            chunk_size=chunk_size
        )
        
        if not audio_data.get("success", False):
            return audio_data
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
            temp_path = temp_file.name
            
            try:
                # Write audio data to WAV file
                with wave.open(temp_path, 'wb') as wf:
                    wf.setnchannels(channels)
                    wf.setsampwidth(2)  # 16-bit audio
                    wf.setframerate(sample_rate)
                    wf.writeframes(audio_data["audio_data"])
                
                # Transcribe the audio file
                result = await self.transcribe_file(temp_path, params)
                return result
                
            except Exception as e:
                logger.error(f"Error in microphone transcription: {e}")
                return {
                    "success": False,
                    "error": f"Error in microphone transcription: {str(e)}"
                }
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_path)
                except Exception as e:
                    logger.warning(f"Failed to delete temporary file {temp_path}: {e}")
    
    async def _record_audio(self, 
                         duration_seconds: float = 10.0,
                         sample_rate: int = 16000,
                         channels: int = 1,
                         chunk_size: int = 1024) -> Dict[str, Any]:
        """
        Record audio from microphone.
        
        Args:
            duration_seconds: Duration to record in seconds
            sample_rate: Audio sample rate
            channels: Number of audio channels
            chunk_size: Audio chunk size for recording
            
        Returns:
            Dictionary with audio data
        """
        try:
            p = pyaudio.PyAudio()
            
            # Print available devices for debugging
            info = p.get_host_api_info_by_index(0)
            num_devices = info.get('deviceCount')
            
            logger.debug(f"Available audio input devices:")
            for i in range(0, num_devices):
                device_info = p.get_device_info_by_host_api_device_index(0, i)
                if device_info.get('maxInputChannels') > 0:
                    logger.debug(f"  Device {i}: {device_info.get('name')}")
            
            # Open stream
            stream = p.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=sample_rate,
                input=True,
                frames_per_buffer=chunk_size
            )
            
            print(f"Recording for {duration_seconds} seconds...")
            
            # Calculate number of frames to record
            frames = []
            total_chunks = int(sample_rate / chunk_size * duration_seconds)
            
            # Record audio
            for _ in range(total_chunks):
                data = stream.read(chunk_size)
                frames.append(data)
                # Show progress every second
                if _ % int(sample_rate / chunk_size) == 0:
                    seconds_passed = _ / (sample_rate / chunk_size)
                    print(f"Recording: {seconds_passed:.1f}s / {duration_seconds:.1f}s")
            
            print("Recording complete.")
            
            # Stop and close the stream
            stream.stop_stream()
            stream.close()
            p.terminate()
            
            # Combine all frames into a single audio buffer
            audio_data = b''.join(frames)
            
            return {
                "success": True,
                "audio_data": audio_data,
                "sample_rate": sample_rate,
                "channels": channels,
                "duration": duration_seconds
            }
            
        except Exception as e:
            logger.error(f"Error recording audio: {e}")
            return {
                "success": False,
                "error": f"Error recording audio: {str(e)}"
            }


class DeepgramTTS:
    """
    Text-to-Speech functionality using Deepgram's Aura API.
    
    This class provides methods for converting text to speech.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the DeepgramTTS class.
        
        Args:
            api_key: Deepgram API key (if None, uses environment variable)
        """
        self.api_key = api_key or os.environ.get("DEEPGRAM_API_KEY")
        if not self.api_key:
            raise ValueError("Deepgram API key is required. Set DEEPGRAM_API_KEY environment variable or pass as parameter.")
        
        # API endpoint for Deepgram Aura TTS
        self.base_url = "https://api.deepgram.com/v1/speak"
        
        # Default parameters for TTS
        self.default_params = {
            "model": "aura-asteria-en",
            "voice": "nova",  # Default voice
            "encoding": "linear16", # WAV format
            "sample_rate": 24000,
            "container": "wav"
        }
        
        logger.info("Initialized Deepgram TTS client")
    
    async def synthesize_speech(self, 
                             text: str, 
                             output_file: Optional[Union[str, Path]] = None,
                             play_audio: bool = False,
                             params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Convert text to speech using Deepgram's API.
        
        Args:
            text: Text to convert to speech
            output_file: Optional path to save audio file
            play_audio: Whether to play the audio immediately
            params: Additional parameters to pass to Deepgram API
            
        Returns:
            Dictionary with synthesis results
        """
        # Combine default and custom parameters
        request_params = {**self.default_params, **(params or {})}
        
        # Prepare request payload
        payload = {
            "text": text,
            **request_params
        }
        
        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            # Make API request
            async with aiohttp.ClientSession() as session:
                async with session.post(self.base_url, headers=headers, json=payload) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Deepgram API error: {response.status} - {error_text}")
                        return {
                            "success": False,
                            "error": f"API error: {response.status}",
                            "details": error_text
                        }
                    
                    # Get binary audio data
                    audio_data = await response.read()
                    
                    # Save to file if requested
                    if output_file:
                        with open(output_file, 'wb') as f:
                            f.write(audio_data)
                        logger.info(f"Saved audio to {output_file}")
                    
                    # Play audio if requested
                    if play_audio:
                        await self._play_audio(audio_data)
                    
                    return {
                        "success": True,
                        "audio_data": audio_data,
                        "output_file": str(output_file) if output_file else None
                    }
        
        except Exception as e:
            logger.error(f"Error synthesizing speech: {e}")
            return {
                "success": False,
                "error": f"Error synthesizing speech: {str(e)}"
            }
    
    async def _play_audio(self, audio_data: bytes) -> None:
        """
        Play audio data through speakers.
        
        Args:
            audio_data: WAV audio data to play
        """
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_path = temp_file.name
                temp_file.write(audio_data)
            
            try:
                # Initialize PyAudio
                p = pyaudio.PyAudio()
                
                # Open WAV file
                with wave.open(temp_path, 'rb') as wf:
                    # Get audio parameters
                    channels = wf.getnchannels()
                    sample_width = wf.getsampwidth()
                    sample_rate = wf.getframerate()
                    
                    # Open stream
                    stream = p.open(
                        format=p.get_format_from_width(sample_width),
                        channels=channels,
                        rate=sample_rate,
                        output=True
                    )
                    
                    # Read data in chunks and play
                    chunk_size = 1024
                    data = wf.readframes(chunk_size)
                    
                    print("Playing audio...")
                    while len(data) > 0:
                        stream.write(data)
                        data = wf.readframes(chunk_size)
                    
                    # Clean up
                    stream.stop_stream()
                    stream.close()
                    p.terminate()
                    
                    print("Audio playback complete.")
            
            except Exception as e:
                logger.error(f"Error playing audio: {e}")
            
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_path)
                except Exception as e:
                    logger.warning(f"Failed to delete temporary file {temp_path}: {e}")
                    
        except Exception as e:
            logger.error(f"Error preparing audio for playback: {e}")


class VoiceHandler:
    """
    Class that combines STT and TTS functionality for AI Interviewer.
    
    This class provides a unified interface for voice interactions.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the VoiceHandler class.
        
        Args:
            api_key: Deepgram API key (if None, uses environment variable)
        """
        self.api_key = api_key or os.environ.get("DEEPGRAM_API_KEY")
        if not self.api_key:
            raise ValueError("Deepgram API key is required. Set DEEPGRAM_API_KEY environment variable or pass as parameter.")
        
        # Initialize STT and TTS components
        self.stt = DeepgramSTT(api_key=self.api_key)
        self.tts = DeepgramTTS(api_key=self.api_key)
        
        logger.info("Initialized VoiceHandler")
    
    async def listen(self, 
                  duration_seconds: float = 10.0,
                  sample_rate: int = 16000,
                  channels: int = 1) -> str:
        """
        Record audio from microphone and convert to text.
        
        Args:
            duration_seconds: Duration to record in seconds
            sample_rate: Audio sample rate
            channels: Number of audio channels
            
        Returns:
            Transcribed text (empty string if failed)
        """
        result = await self.stt.transcribe_microphone(
            duration_seconds=duration_seconds,
            sample_rate=sample_rate,
            channels=channels
        )
        
        if result.get("success", False):
            return result.get("transcript", "")
        else:
            logger.error(f"STT error: {result.get('error', 'Unknown error')}")
            return ""
    
    async def speak(self, 
                 text: str, 
                 voice: str = "nova",
                 play_audio: bool = True,
                 output_file: Optional[str] = None) -> bool:
        """
        Convert text to speech and play/save.
        
        Args:
            text: Text to convert to speech
            voice: Voice to use for synthesis
            play_audio: Whether to play the audio immediately
            output_file: Optional path to save audio file
            
        Returns:
            True if successful, False otherwise
        """
        params = {"voice": voice}
        
        result = await self.tts.synthesize_speech(
            text=text,
            output_file=output_file,
            play_audio=play_audio,
            params=params
        )
        
        return result.get("success", False) 