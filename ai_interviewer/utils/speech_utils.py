"""
Speech utilities for AI Interviewer platform.

This module provides speech-to-text (STT) and text-to-speech (TTS) 
functionality using Google Gemini API.
"""
import os
import asyncio
import logging
import tempfile
import wave
import pyaudio
import numpy as np
from typing import Optional, Tuple, Dict, Any, Union, List, BinaryIO
import aiohttp # Keep for potential future HTTP needs, or remove if truly unused
import base64
from pathlib import Path
import json
import time

# Configure logging
logger = logging.getLogger(__name__)

from ai_interviewer.utils.config import get_gemini_live_config, get_speech_config
from ai_interviewer.utils.gemini_live_utils import transcribe_audio_gemini, synthesize_speech_gemini

class VoiceHandler:
    """
    Class that combines STT and TTS functionality for AI Interviewer using Gemini.
    """
    
    def __init__(self):
        """
        Initialize the VoiceHandler class.
        Gemini API key is typically handled by the gemini_live_utils.
        """
        # No specific API key needed here if gemini_live_utils handles it.
        # Deepgram specific initialization is removed.
        logger.info("Initialized VoiceHandler (using Gemini for STT/TTS via gemini_live_utils)")
    
    async def transcribe_audio_bytes(self, audio_bytes: bytes, sample_rate: int = 16000, channels: int = 1) -> Dict[str, Any]:
        """
        Transcribe audio from bytes using Gemini.
        
        Args:
            audio_bytes: Audio data as bytes
            sample_rate: Audio sample rate in Hz (Note: Gemini might have specific requirements)
            channels: Number of audio channels (Note: Gemini might have specific requirements)
            
        Returns:
            Dictionary with transcription results or an error message.
        """
        logger.info("Using Gemini for STT.")
        try:
            transcription = await transcribe_audio_gemini(audio_bytes)
            if transcription:
                return {"success": True, "transcript": transcription, "provider": "gemini"}
            else:
                logger.warning("Gemini STT failed to return a transcription.")
                return {"success": False, "error": "Gemini STT failed to return a transcription."}
        except Exception as e:
            logger.error(f"Error during Gemini STT in VoiceHandler: {e}", exc_info=True)
            return {"success": False, "error": f"Gemini STT error: {str(e)}"}
    
    async def listen(self, 
                                  duration_seconds: float = 30.0,
                                  sample_rate: int = 16000,
                                  channels: int = 1,
                                  silence_threshold: float = 0.03,
                  silence_duration: float = 2.0) -> str:
        """
        Record audio from microphone and convert to text using Gemini.
        
        Args:
            duration_seconds: Maximum duration to record in seconds
            sample_rate: Audio sample rate
            channels: Number of audio channels
            silence_threshold: Volume threshold to detect silence (0.0-1.0)
            silence_duration: Duration of silence in seconds to stop recording
            
        Returns:
            Transcribed text (empty string if failed)
        """
        # Record audio from microphone (this part remains using pyaudio)
        audio_record_result = await self._record_audio(
            duration_seconds=duration_seconds,
            sample_rate=sample_rate,
            channels=channels,
            silence_threshold=silence_threshold,
            silence_duration=silence_duration
        )
        
        if not audio_record_result.get("success", False):
            logger.error(f"Audio recording failed: {audio_record_result.get('error')}")
            return ""
        
        # Transcribe the recorded audio using Gemini
        stt_result = await self.transcribe_audio_bytes(audio_record_result["audio_data"], sample_rate, channels)
        
        if stt_result.get("success", False):
            return stt_result.get("transcript", "")
        else:
            logger.error(f"Gemini STT error after recording: {stt_result.get('error', 'Unknown error')}")
            return ""
    
    async def speak(self, 
                 text: str, 
                 voice: str = "Aoede", # Default Gemini voice, can be configured via gemini_live_config
                 play_audio: bool = True,
                 output_file: Optional[str] = None) -> Optional[bytes]:
        """
        Convert text to speech using Gemini and play/save.
        
        Args:
            text: Text to convert to speech
            voice: Voice to use for synthesis (specific to Gemini's prebuilt voices)
            play_audio: Whether to play the audio immediately
            output_file: Optional path to save audio file
            
        Returns:
            Audio data as bytes if successful, None otherwise.
        """
        logger.info(f"Using Gemini for TTS with voice: {voice}")
        try:
            # Voice parameter is now passed directly to synthesize_speech_gemini
            audio_data = await synthesize_speech_gemini(text, voice_name=voice)
            
            if audio_data:
                if output_file:
                    # Write a proper WAV file
                    try:
                        with wave.open(output_file, 'wb') as wf:
                            wf.setnchannels(1)  # Mono
                            wf.setsampwidth(2)  # 16-bit PCM
                            wf.setframerate(24000) # Gemini TTS standard rate
                            wf.writeframes(audio_data)
                        logger.info(f"Gemini TTS: Saved audio to {output_file} as proper WAV.")
                    except Exception as e:
                        logger.error(f"Error writing WAV file {output_file}: {e}")
                        # Fallback to writing raw bytes if wave writing fails, though less ideal
                        with open(output_file, 'wb') as f:
                            f.write(audio_data)
                        logger.warning(f"Gemini TTS: Saved raw audio to {output_file} due to WAV write error.")
                if play_audio:
                    await self._play_audio(audio_data) 
                return audio_data # Return the audio data bytes
            else:
                logger.warning("Gemini TTS failed to produce audio data.")
                return None
        except Exception as e:
            logger.error(f"Error during Gemini TTS in VoiceHandler: {e}", exc_info=True)
            return None

    # _record_audio and _play_audio methods remain as they are utility functions
    # for microphone interaction and audio playback, independent of the STT/TTS provider.
    # Ensure they are correctly handling bytes for playback.
    
    async def _record_audio(self, 
                         duration_seconds: float = 30.0,
                         sample_rate: int = 16000,
                         channels: int = 1,
                         chunk_size: int = 1024,
                         silence_threshold: float = 0.03,
                         silence_duration: float = 2.0) -> Dict[str, Any]:
        """
        Record audio from microphone with voice activity detection.
        (This method is kept from the original, assuming PyAudio is still desired for recording)
        """
        try:
            p = pyaudio.PyAudio()
            stream = p.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=sample_rate,
                input=True,
                frames_per_buffer=chunk_size
            )
            logger.info(f"Recording... (speak now, pause for {silence_duration:.1f}s to finish)")
            frames = []
            silence_threshold_count = int(silence_duration * sample_rate / chunk_size)
            max_chunks = int(sample_rate / chunk_size * duration_seconds)
            silence_count = 0
            has_speech = False
            chunks_recorded = 0
            
            for i in range(max_chunks):
                data = stream.read(chunk_size, exception_on_overflow=False)
                frames.append(data)
                chunks_recorded += 1
                audio_array = np.frombuffer(data, dtype=np.int16)
                audio_level = np.abs(audio_array).mean() / 32767.0
                if audio_level > silence_threshold:
                    silence_count = 0
                    has_speech = True
                elif has_speech:
                    silence_count += 1
                if i % 5 == 0: 
                    seconds_passed = i / (sample_rate / chunk_size)
                    silence_progress = min(1.0, silence_count / silence_threshold_count) if has_speech else 0
                    # Simplified print to avoid potential terminal rendering issues in some environments
                    print(f"\rRecording: {seconds_passed:.1f}s {'🎙️' if audio_level > silence_threshold else '⏸️'} Pause: {silence_progress*100:.0f}%", end="")
                if has_speech and silence_count >= silence_threshold_count:
                    print("\nDetected end of speech.")
                    break
            if chunks_recorded >= max_chunks:
                print("\nReached maximum recording duration.")
            else:
                print(f"\nRecording complete after {chunks_recorded * chunk_size / sample_rate:.1f} seconds.")
            
            stream.stop_stream()
            stream.close()
            p.terminate()
            audio_data_bytes = b''.join(frames)
            if not has_speech or len(frames) < 5:
                logger.warning("No meaningful speech detected in recording")
                return {"success": False, "error": "No speech detected"}
            return {"success": True, "audio_data": audio_data_bytes, "sample_rate": sample_rate, "channels": channels, "duration": chunks_recorded * chunk_size / sample_rate}
        except Exception as e:
            logger.error(f"Error recording audio: {e}", exc_info=True)
            return {"success": False, "error": f"Error recording audio: {str(e)}"}
    
    async def _play_audio(self, audio_data: bytes) -> None:
        """
        Play audio data through speakers.
        (This method is kept from the original, assuming PyAudio is still desired for playback)
        Args:
            audio_data: Raw audio data to play (should be WAV format or playable raw PCM)
        """
        try:
            # We assume audio_data from Gemini is raw PCM or directly playable as WAV content
            # If Gemini provides raw PCM, we need to know its sample rate and channels to play correctly.
            # For now, let's assume it's WAV content that PyAudio can handle via wave.open
            
            # Create a temporary WAV file with proper headers for playback
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_path = temp_file.name
                with wave.open(temp_path, 'wb') as wf_temp:
                    wf_temp.setnchannels(1)    # Mono - typical for Gemini TTS
                    wf_temp.setsampwidth(2)    # 16-bit PCM - typical for Gemini TTS
                    wf_temp.setframerate(24000) # Standard Gemini TTS output rate
                    wf_temp.writeframes(audio_data)
            
            wf = wave.open(temp_path, 'rb')
            p = pyaudio.PyAudio()
            stream = p.open(format=p.get_format_from_width(wf.getsampwidth()),
                            channels=wf.getnchannels(),
                            rate=wf.getframerate(),
                            output=True)
            data = wf.readframes(1024)
            logger.info("Playing audio...")
            while len(data) > 0:
                stream.write(data)
                data = wf.readframes(1024)
            stream.stop_stream()
            stream.close()
            wf.close()
            p.terminate()
            logger.info("Audio playback complete.")
            os.unlink(temp_path) # Clean up temp file
        except wave.Error as e:
            logger.error(f"Error opening WAV data for playback (is it valid WAV?): {e}. Attempting raw playback.")
            # Fallback: try to play as raw data if we know the format (e.g., 24000 Hz, 1 channel, 16-bit PCM for Gemini Live Audio)
            try:
                p_raw = pyaudio.PyAudio()
                stream_raw = p_raw.open(format=pyaudio.paInt16, # Assuming 16-bit PCM
                                    channels=1, # Assuming mono, Gemini Live default
                                    rate=24000, # Gemini Live Audio output rate
                                    output=True)
                logger.info("Playing audio (raw attempt)...")
                stream_raw.write(audio_data)
                stream_raw.stop_stream()
                stream_raw.close()
                p_raw.terminate()
                logger.info("Audio playback complete (raw attempt).")
            except Exception as raw_e:
                logger.error(f"Error playing raw audio: {raw_e}", exc_info=True)
        except Exception as e:
            logger.error(f"Error playing audio: {e}", exc_info=True)
            if 'temp_path' in locals() and os.path.exists(temp_path):
                 os.unlink(temp_path) # Ensure cleanup on other errors too