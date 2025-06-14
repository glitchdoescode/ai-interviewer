"""
Gemini Live API Audio Stream Adapter for AI Interviewer

This module provides real-time audio streaming capabilities using Gemini Live API,
replacing the sequential STT->LLM->TTS flow with low-latency bidirectional audio.
"""

import asyncio
import os
import pyaudio
import logging
from typing import Dict, Any, Callable, Optional, List
from google import genai
from ai_interviewer.utils.config import get_gemini_live_config

logger = logging.getLogger(__name__)

# Audio configuration constants
FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE = 1024

# Gemini Live API configuration
MODEL = "gemini-2.5-flash-preview-native-audio-dialog"
CONFIG = {"response_modalities": ["AUDIO"]}


class GeminiLiveAudioAdapter:
    """
    Real-time audio streaming adapter using Gemini Live API.
    
    This adapter manages bidirectional audio streaming and context injection
    for the AI interviewer, replacing the traditional STT->LLM->TTS pipeline.
    """
    
    def __init__(self, api_key: Optional[str] = None, interview_context: Optional[Dict[str, Any]] = None):
        """
        Initialize the Gemini Live Audio Adapter.
        
        Args:
            api_key: Gemini API key (defaults to environment variable)
            interview_context: Initial interview context for the session
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable must be set")
        
        self.client = genai.Client(api_key=self.api_key)
        self.interview_context = interview_context or {}
        
        # Session state
        self.session = None
        self.running = False
        self.audio_stream = None
        
        # Audio queues for bidirectional streaming
        self.audio_in_queue = None
        self.out_queue = None
        
        # PyAudio instance
        self.pya = pyaudio.PyAudio()
        
        # Callback systems
        self.audio_callbacks: List[Callable] = []
        self.text_callbacks: List[Callable] = []
        self.stage_transition_callbacks: List[Callable] = []
        
        # Context management
        self.context_buffer = []
        self.context_batch_size = 5
        
        logger.info("GeminiLiveAudioAdapter initialized")
    
    async def start_session(self, initial_prompt: str = None) -> bool:
        """
        Start a new Gemini Live API session with audio streaming.
        
        Args:
            initial_prompt: Initial context or prompt for the session
            
        Returns:
            bool: True if session started successfully, False otherwise
        """
        try:
            logger.info("Starting Gemini Live API session...")
            
            # Initialize audio queues
            self.audio_in_queue = asyncio.Queue()
            self.out_queue = asyncio.Queue(maxsize=10)
            
            # Connect to Gemini Live API
            self.session = await self.client.aio.live.connect(model=MODEL, config=CONFIG)
            self.running = True
            
            # Send initial context if provided
            if initial_prompt:
                await self._send_initial_context(initial_prompt)
            
            # Start audio processing tasks
            await self._start_audio_tasks()
            
            logger.info("Gemini Live API session started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start Gemini Live API session: {e}")
            await self.stop_session()
            return False
    
    async def stop_session(self):
        """Clean shutdown of the audio session."""
        logger.info("Stopping Gemini Live API session...")
        
        self.running = False
        
        # Stop audio stream
        if self.audio_stream:
            try:
                self.audio_stream.stop_stream()
                self.audio_stream.close()
            except Exception as e:
                logger.warning(f"Error closing audio stream: {e}")
        
        # Close session
        if self.session:
            try:
                await self.session.close()
            except Exception as e:
                logger.warning(f"Error closing Gemini session: {e}")
        
        logger.info("Gemini Live API session stopped")
    
    async def inject_context(self, context_update: Dict[str, Any], silent: bool = True):
        """
        Inject context into the conversation stream.
        
        Args:
            context_update: Dictionary containing context information
            silent: If True, inject as silent context that doesn't trigger responses
        """
        try:
            context_text = self._format_context_update(context_update)
            
            if silent:
                # Use silent context injection pattern from geminicode1.py
                silent_context = f"[SYSTEM CONTEXT - DO NOT RESPOND OR ACKNOWLEDGE - ABSORB SILENTLY]: {context_text}"
                await self.out_queue.put({"type": "silent_context", "data": silent_context})
            else:
                await self.out_queue.put({"type": "text", "data": context_text})
            
            logger.debug(f"Context injected: {context_text[:100]}...")
            
        except Exception as e:
            logger.error(f"Error injecting context: {e}")
    
    async def inject_stage_transition(self, from_stage: str, to_stage: str, context: Dict[str, Any]):
        """
        Inject interview stage transition as context.
        
        Args:
            from_stage: Previous interview stage
            to_stage: New interview stage
            context: Additional context for the transition
        """
        stage_context = {
            "type": "stage_transition",
            "from_stage": from_stage,
            "to_stage": to_stage,
            "context": context
        }
        
        await self.inject_context(stage_context, silent=True)
        
        # Notify stage transition callbacks
        for callback in self.stage_transition_callbacks:
            try:
                await callback(from_stage, to_stage, context)
            except Exception as e:
                logger.warning(f"Stage transition callback error: {e}")
    
    def add_audio_callback(self, callback: Callable):
        """Register callback for audio responses."""
        self.audio_callbacks.append(callback)
    
    def add_text_callback(self, callback: Callable):
        """Register callback for text responses."""
        self.text_callbacks.append(callback)
    
    def add_stage_transition_callback(self, callback: Callable):
        """Register callback for stage transitions."""
        self.stage_transition_callbacks.append(callback)
    
    async def _start_audio_tasks(self):
        """Start all audio processing tasks."""
        task_group = asyncio.create_task(self._create_audio_task_group())
        return task_group
    
    async def _create_audio_task_group(self):
        """Create and manage audio processing task group."""
        async with asyncio.TaskGroup() as tg:
            tg.create_task(self._listen_audio())
            tg.create_task(self._send_realtime())
            tg.create_task(self._receive_audio())
            tg.create_task(self._play_audio())
    
    async def _listen_audio(self):
        """Capture audio from microphone and queue for sending."""
        try:
            mic_info = self.pya.get_default_input_device_info()
            self.audio_stream = await asyncio.to_thread(
                self.pya.open,
                format=FORMAT,
                channels=CHANNELS,
                rate=SEND_SAMPLE_RATE,
                input=True,
                input_device_index=mic_info["index"],
                frames_per_buffer=CHUNK_SIZE,
            )
            
            kwargs = {"exception_on_overflow": False} if __debug__ else {}
            
            while self.running:
                try:
                    data = await asyncio.to_thread(self.audio_stream.read, CHUNK_SIZE, **kwargs)
                    await self.out_queue.put({"type": "audio", "data": data, "mime_type": "audio/pcm"})
                except Exception as e:
                    if self.running:
                        logger.error(f"Audio capture error: {e}")
                    break
                    
        except Exception as e:
            logger.error(f"Error initializing audio capture: {e}")
    
    async def _send_realtime(self):
        """Send audio and context messages to Gemini Live API."""
        while self.running:
            try:
                msg = await self.out_queue.get()
                
                if msg["type"] == "audio":
                    await self.session.send_realtime_input(
                        audio={"data": msg["data"], "mime_type": msg["mime_type"]}
                    )
                elif msg["type"] == "text":
                    await self.session.send_realtime_input(text=msg["data"])
                elif msg["type"] == "silent_context":
                    # Send silent context without triggering response
                    await self.session.send_realtime_input(text=msg["data"])
                    
            except Exception as e:
                if self.running:
                    logger.error(f"Send error: {e}")
                break
    
    async def _receive_audio(self):
        """Receive audio and text responses from Gemini Live API."""
        while self.running:
            try:
                turn = self.session.receive()
                async for response in turn:
                    if data := response.data:
                        # Audio response received
                        self.audio_in_queue.put_nowait(data)
                        
                        # Notify audio callbacks
                        for callback in self.audio_callbacks:
                            try:
                                await callback(data)
                            except Exception as e:
                                logger.warning(f"Audio callback error: {e}")
                        continue
                        
                    if text := response.text:
                        logger.info(f"🤖 AI Interviewer: {text}")
                        
                        # Notify text callbacks
                        for callback in self.text_callbacks:
                            try:
                                await callback(text)
                            except Exception as e:
                                logger.warning(f"Text callback error: {e}")
                
                # Clear audio queue on turn complete (for interruptions)
                while not self.audio_in_queue.empty():
                    self.audio_in_queue.get_nowait()
                    
            except Exception as e:
                if self.running:
                    logger.error(f"Receive error: {e}")
                break
    
    async def _play_audio(self):
        """Play audio responses from Gemini Live API."""
        try:
            stream = await asyncio.to_thread(
                self.pya.open,
                format=FORMAT,
                channels=CHANNELS,
                rate=RECEIVE_SAMPLE_RATE,
                output=True,
            )
            
            while self.running:
                try:
                    bytestream = await self.audio_in_queue.get()
                    await asyncio.to_thread(stream.write, bytestream)
                except Exception as e:
                    if self.running:
                        logger.error(f"Audio playback error: {e}")
                    break
            
            stream.close()
            
        except Exception as e:
            logger.error(f"Error initializing audio playback: {e}")
    
    async def _send_initial_context(self, initial_prompt: str):
        """Send initial context to the session."""
        if initial_prompt:
            await self.session.send_realtime_input(text=initial_prompt)
    
    def _format_context_update(self, context_update: Dict[str, Any]) -> str:
        """
        Format context update dictionary into a readable string.
        
        Args:
            context_update: Dictionary containing context information
            
        Returns:
            str: Formatted context string
        """
        if context_update.get("type") == "stage_transition":
            return (f"Interview stage transition: {context_update['from_stage']} -> "
                   f"{context_update['to_stage']}. Context: {context_update.get('context', {})}")
        
        # General context formatting
        formatted_parts = []
        for key, value in context_update.items():
            if isinstance(value, (list, tuple)):
                value = ", ".join(str(v) for v in value)
            formatted_parts.append(f"{key}: {value}")
        
        return "; ".join(formatted_parts)
    
    def __del__(self):
        """Cleanup on object destruction."""
        if hasattr(self, 'pya') and self.pya:
            try:
                self.pya.terminate()
            except:
                pass 