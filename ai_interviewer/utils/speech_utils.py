"""
Speech utilities for {SYSTEM_NAME} platform.

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
from ai_interviewer.utils.config import SYSTEM_NAME, get_speech_config
from ai_interviewer.utils.ssml_utils import validate_ssml, add_automatic_ssml

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
            "smart_format": "true",  # Use string values for boolean params
            "punctuate": "true",     # API expects "true"/"false" as strings
            "utterances": "true"     # Include utterance boundaries
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
        
        # Convert boolean parameters to string "true"/"false" for API compatibility
        for key, value in request_params.items():
            if isinstance(value, bool):
                request_params[key] = "true" if value else "false"
        
        # Construct query parameters
        query_params = "&".join([f"{k}={v}" for k, v in request_params.items()])
        url = f"{self.base_url}?{query_params}"
        
        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "audio/wav"  # Assuming WAV format - adjust as needed
        }
        
        # Log request details for debugging
        logger.debug(f"STT API request to: {url}")
        logger.debug(f"STT API headers: {headers}")
        logger.debug(f"STT API params: {request_params}")
        
        try:
            # Handle string/Path or file-like object
            if isinstance(audio_file, (str, Path)):
                with open(audio_file, 'rb') as f:
                    audio_data = f.read()
            else:
                # Assuming audio_file is a file-like object in binary mode
                audio_file.seek(0)
                audio_data = audio_file.read()
            
            logger.debug(f"Audio data size: {len(audio_data)} bytes")
            
            # Make API request
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.post(url, headers=headers, data=audio_data) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            logger.error(f"Deepgram STT API error: {response.status} - {error_text}")
                            logger.error(f"Request URL was: {url}")
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
                except aiohttp.ClientError as e:
                    logger.error(f"STT API request failed: {e}")
                    return {
                        "success": False,
                        "error": f"API request failed: {str(e)}"
                    }
        
        except Exception as e:
            logger.error(f"Error transcribing audio file: {e}")
            return {
                "success": False,
                "error": f"Error transcribing audio: {str(e)}"
            }
    
    async def transcribe_microphone(self, 
                                  duration_seconds: float = 30.0,
                                  sample_rate: int = 16000,
                                  channels: int = 1,
                                  chunk_size: int = 1024,
                                  silence_threshold: float = 0.03,
                                  silence_duration: float = 2.0,
                                  params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Record audio from microphone and transcribe using Deepgram's API.
        
        Args:
            duration_seconds: Maximum duration to record in seconds
            sample_rate: Audio sample rate
            channels: Number of audio channels
            chunk_size: Audio chunk size for recording
            silence_threshold: Volume threshold to detect silence (0.0-1.0)
            silence_duration: Duration of silence in seconds to stop recording
            params: Additional parameters to pass to Deepgram API
            
        Returns:
            Dictionary with transcription results
        """
        # Record audio from microphone with voice activity detection
        audio_data = await self._record_audio(
            duration_seconds=duration_seconds,
            sample_rate=sample_rate,
            channels=channels,
            chunk_size=chunk_size,
            silence_threshold=silence_threshold,
            silence_duration=silence_duration
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
                         duration_seconds: float = 30.0,
                         sample_rate: int = 16000,
                         channels: int = 1,
                         chunk_size: int = 1024,
                         silence_threshold: float = 0.03,
                         silence_duration: float = 2.0) -> Dict[str, Any]:
        """
        Record audio from microphone with voice activity detection.
        
        Args:
            duration_seconds: Maximum duration to record in seconds
            sample_rate: Audio sample rate
            channels: Number of audio channels
            chunk_size: Audio chunk size for recording
            silence_threshold: Volume threshold to detect silence (0.0-1.0)
            silence_duration: Duration of silence in seconds to stop recording
            
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
            
            print(f"Recording... (speak now, pause for {silence_duration:.1f}s to finish)")
            
            # Calculate parameters for silence detection
            frames = []
            silence_threshold_count = int(silence_duration * sample_rate / chunk_size)
            max_chunks = int(sample_rate / chunk_size * duration_seconds)
            silence_count = 0
            has_speech = False
            chunks_recorded = 0
            
            # Record audio with silence detection
            for i in range(max_chunks):
                data = stream.read(chunk_size, exception_on_overflow=False)
                frames.append(data)
                chunks_recorded += 1
                
                # Calculate audio level to detect silence
                audio_array = np.frombuffer(data, dtype=np.int16)
                audio_level = np.abs(audio_array).mean() / 32767.0  # Normalize to 0.0-1.0
                
                # If we detect speech, reset silence counter
                if audio_level > silence_threshold:
                    silence_count = 0
                    has_speech = True
                # If we detect silence, increment counter
                elif has_speech:
                    silence_count += 1
                
                # Show audio level visualization
                if i % 5 == 0:  # Update every ~0.3 seconds at 16kHz
                    bars = int(audio_level * 50)
                    # Only print if we have significant audio or every second
                    if audio_level > silence_threshold or i % (sample_rate // chunk_size) == 0:
                        seconds_passed = i / (sample_rate / chunk_size)
                        silence_count_display = silence_count if has_speech else 0
                        silence_progress = min(1.0, silence_count / silence_threshold_count) if has_speech else 0
                        silence_bar = f"[{'#' * int(silence_progress * 10)}{' ' * (10 - int(silence_progress * 10))}]"
                        
                        print(f"\rRecording: {seconds_passed:.1f}s {'|' * bars}{' ' * (50-bars)} "
                              f"{'🎙️ ACTIVE' if audio_level > silence_threshold else '⏸️ SILENT'} "
                              f"Pause: {silence_count_display}/{silence_threshold_count} {silence_bar}", end="")
                
                # Exit if we've had enough silence after speech
                if has_speech and silence_count >= silence_threshold_count:
                    print("\nDetected end of speech (pause).")
                    break
            
            # We got to the end of max duration without detecting silence
            if chunks_recorded >= max_chunks:
                print("\nReached maximum recording duration.")
            else:
                print(f"Recording complete after {chunks_recorded * chunk_size / sample_rate:.1f} seconds.")
            
            # Stop and close the stream
            stream.stop_stream()
            stream.close()
            p.terminate()
            
            # Combine all frames into a single audio buffer
            audio_data = b''.join(frames)
            
            # If we didn't record any meaningful audio, return an error
            if not has_speech or len(frames) < 5:  # Arbitrary minimum length
                logger.warning("No meaningful speech detected in recording")
                return {
                    "success": False,
                    "error": "No speech detected during recording"
                }
            
            return {
                "success": True,
                "audio_data": audio_data,
                "sample_rate": sample_rate,
                "channels": channels,
                "duration": chunks_recorded * chunk_size / sample_rate
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
    
    Available voices and models:
    - Models:
        - aura-asteria-en: High-quality English TTS
        - aura-zeus-en: Alternative English TTS model
    - Voices:
        - nova: Default female voice
        - stella: Alternative female voice
        - athena: Professional female voice
        - zeus: Male voice
        - hera: Alternative female voice
        - dave: Casual male voice
        - reed: Professional male voice
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
        
        # Get speech configuration
        speech_config = get_speech_config()
        
        # Default parameters for TTS
        self.default_params = {
            "model": speech_config.get("tts_model", "aura-asteria-en"),
            "voice": speech_config.get("tts_voice", "nova"),
            "encoding": "linear16", # WAV format
            "sample_rate": speech_config.get("sample_rate", 24000),
            "container": "wav",
            "rate": speech_config.get("tts_rate", 1.0),  # Speech rate (0.5 to 2.0)
            "pitch": speech_config.get("tts_pitch", 1.0),  # Voice pitch (0.5 to 2.0)
            "use_ssml": False  # Default to not using SSML
        }
        
        logger.debug("Deepgram TTS initialized with default parameters")
        logger.debug(f"TTS model: {self.default_params['model']}, voice: {self.default_params['voice']}")
        logger.debug(f"TTS rate: {self.default_params['rate']}, pitch: {self.default_params['pitch']}")
        
        logger.info("Initialized Deepgram TTS client")
    
    async def synthesize_speech(self, 
                             text: str, 
                             output_file: Optional[Union[str, Path]] = None,
                             play_audio: bool = False,
                             params: Optional[Dict[str, Any]] = None,
                             auto_ssml: bool = True) -> Dict[str, Any]:
        """
        Convert text to speech using Deepgram's API.
        
        Args:
            text: Text to convert to speech (can be plain text or SSML)
            output_file: Optional path to save audio file
            play_audio: Whether to play the audio immediately
            params: Additional parameters to pass to Deepgram API. Supported parameters:
                - model: TTS model to use (e.g. "aura-asteria-en", "aura-zeus-en")
                - voice: Voice to use (e.g. "nova", "stella", "zeus")
                - rate: Speech rate (0.5 to 2.0)
                - pitch: Voice pitch (0.5 to 2.0)
                - use_ssml: Whether the input text is SSML
            auto_ssml: Whether to automatically add SSML tags if text is not SSML
            
        Returns:
            Dictionary with synthesis results
        """
        # Combine default and custom parameters
        request_params = {**self.default_params, **(params or {})}
        
        # Check if text is SSML
        is_ssml = text.strip().startswith("<speak>") and text.strip().endswith("</speak>")
        
        # If text is not SSML but auto_ssml is True, add SSML tags
        if not is_ssml and auto_ssml:
            text = add_automatic_ssml(text)
            is_ssml = True
        
        # If text is SSML, validate it
        if is_ssml:
            if not validate_ssml(text):
                logger.error("Invalid SSML markup")
                return {
                    "success": False,
                    "error": "Invalid SSML markup"
                }
            request_params["use_ssml"] = True
        
        # Validate rate and pitch
        if "rate" in request_params:
            request_params["rate"] = max(0.5, min(2.0, float(request_params["rate"])))
        if "pitch" in request_params:
            request_params["pitch"] = max(0.5, min(2.0, float(request_params["pitch"])))
        
        # Convert boolean parameters to string "true"/"false" for API compatibility
        for key, value in request_params.items():
            if isinstance(value, bool):
                request_params[key] = "true" if value else "false"
        
        # Create base URL with query parameters
        query_params = []
        for key, value in request_params.items():
            if key != 'text':  # Don't include text in URL params
                query_params.append(f"{key}={value}")
        
        url = f"{self.base_url}?{'&'.join(query_params)}"
        
        # Prepare request payload
        payload = {
            "text": text
        }
        
        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            # Log API request details for debugging
            logger.debug(f"TTS API request to: {url}")
            logger.debug(f"TTS API headers: {headers}")
            logger.debug(f"TTS API payload: {json.dumps(payload, indent=2)}")
            logger.debug(f"TTS parameters: model={request_params.get('model')}, voice={request_params.get('voice')}, rate={request_params.get('rate')}, pitch={request_params.get('pitch')}, use_ssml={request_params.get('use_ssml')}")
            
            # Make API request
            async with aiohttp.ClientSession() as session:
                try:
                    async with session.post(url, headers=headers, json=payload) as response:
                        if response.status != 200:
                            error_text = await response.text()
                            logger.error(f"Deepgram TTS API error: {response.status} - {error_text}")
                            logger.error(f"Request URL was: {url}")
                            logger.error(f"Request payload was: {json.dumps(payload)}")
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
                            "output_file": str(output_file) if output_file else None,
                            "used_ssml": is_ssml
                        }
                except aiohttp.ClientError as e:
                    logger.error(f"TTS API request failed: {e}")
                    return {
                        "success": False,
                        "error": f"API request failed: {str(e)}"
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
                    
                    while data:
                        stream.write(data)
                        data = wf.readframes(chunk_size)
                    
                    # Clean up
                    stream.stop_stream()
                    stream.close()
                    p.terminate()
                    
                    print("Finished playing audio.")
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_path)
                except Exception as e:
                    logger.warning(f"Error cleaning up temporary file: {e}")
        except Exception as e:
            logger.error(f"Error playing audio: {e}")


class VoiceHandler:
    """
    Class that combines STT and TTS functionality for {SYSTEM_NAME}.
    
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
    
    async def transcribe_audio_bytes(self, audio_bytes: bytes, sample_rate: int = 16000, channels: int = 1) -> Dict[str, Any]:
        """
        Transcribe audio from bytes using Deepgram's API.
        
        Args:
            audio_bytes: Audio data as bytes
            sample_rate: Audio sample rate in Hz
            channels: Number of audio channels
            
        Returns:
            Dictionary with transcription results or the transcription text
        """
        try:
            # Create a temporary file to store the audio bytes
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_path = temp_file.name
                temp_file.write(audio_bytes)
            
            try:
                # Add sample rate and channels to params for the transcription
                params = {
                    "sample_rate": str(sample_rate),  # Convert to string for API
                    "channels": str(channels)
                }
                
                # Transcribe the temporary file
                result = await self.stt.transcribe_file(temp_path, params=params)
                
                # If the result contains a 'transcript' field, return it
                if isinstance(result, dict) and result.get('success', False) and 'transcript' in result:
                    return result['transcript']
                
                return result
            finally:
                # Clean up temporary file
                try:
                    os.unlink(temp_path)
                except Exception as e:
                    logger.warning(f"Failed to delete temporary file {temp_path}: {e}")
        
        except Exception as e:
            logger.error(f"Error transcribing audio bytes: {e}")
            return {
                "success": False,
                "error": f"Error transcribing audio bytes: {str(e)}"
            }
    
    async def listen(self, 
                  duration_seconds: float = 30.0,
                  sample_rate: int = 16000,
                  channels: int = 1,
                  silence_threshold: float = 0.03,
                  silence_duration: float = 2.0) -> str:
        """
        Record audio from microphone and convert to text.
        
        Args:
            duration_seconds: Maximum duration to record in seconds
            sample_rate: Audio sample rate
            channels: Number of audio channels
            silence_threshold: Volume threshold to detect silence (0.0-1.0)
            silence_duration: Duration of silence in seconds to stop recording
            
        Returns:
            Transcribed text (empty string if failed)
        """
        result = await self.stt.transcribe_microphone(
            duration_seconds=duration_seconds,
            sample_rate=sample_rate,
            channels=channels,
            silence_threshold=silence_threshold,
            silence_duration=silence_duration
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
                 output_file: Optional[str] = None,
                 params: Optional[Dict[str, Any]] = None) -> bool:
        """
        Convert text to speech and play/save.
        
        Args:
            text: Text to convert to speech
            voice: Voice to use for synthesis
            play_audio: Whether to play the audio immediately
            output_file: Optional path to save audio file
            params: Optional additional parameters for TTS
            
        Returns:
            True if successful, False otherwise
        """
        # Combine voice parameter with other params
        params = params or {}
        params["voice"] = voice
        
        result = await self.tts.synthesize_speech(
            text=text,
            output_file=output_file,
            play_audio=play_audio,
            params=params
        )
        
        return result.get("success", False) 