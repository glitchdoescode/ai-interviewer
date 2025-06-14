# -- coding: utf-8 --
# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
## Setup

To install the dependencies for this script, run:


brew install portaudio
pip install -U google-genai pyaudio


## API key

Ensure the GOOGLE_API_KEY environment variable is set to the api-key
you obtained from Google AI Studio.

## Run

To run the script:


python Get_started_LiveAPI_NativeAudio.py


Start talking to Gemini. You can also type text commands:
- Type any text and press Enter to send context
- Type 'quit' or 'exit' to end the conversation
- Type 'help' for available commands
"""

import asyncio
import sys
import traceback
import os
import pyaudio
import threading
from queue import Queue
import aioconsole
from dotenv import load_dotenv
from google import genai


load_dotenv()
if sys.version_info < (3, 11, 0):
    import taskgroup, exceptiongroup
    asyncio.TaskGroup = taskgroup.TaskGroup
    asyncio.ExceptionGroup = exceptiongroup.ExceptionGroup

FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE = 1024

pya = pyaudio.PyAudio()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))  # GOOGLE_API_KEY must be set as env variable

MODEL = "gemini-2.5-flash-preview-native-audio-dialog"
CONFIG = {"response_modalities": ["AUDIO"]}


class AudioLoop:
    def __init__(self, text_prompt=None):
        self.audio_in_queue = None
        self.out_queue = None
        self.text_queue = None
        self.session = None
        self.audio_stream = None
        self.receive_audio_task = None
        self.play_audio_task = None
        self.text_prompt = text_prompt
        self.running = True

    async def listen_audio(self):
        """Capture audio from microphone and send to Gemini"""
        mic_info = pya.get_default_input_device_info()
        self.audio_stream = await asyncio.to_thread(
            pya.open,
            format=FORMAT,
            channels=CHANNELS,
            rate=SEND_SAMPLE_RATE,
            input=True,
            input_device_index=mic_info["index"],
            frames_per_buffer=CHUNK_SIZE,
        )
        if __debug__:
            kwargs = {"exception_on_overflow": False}
        else:
            kwargs = {}
        
        while self.running:
            try:
                data = await asyncio.to_thread(self.audio_stream.read, CHUNK_SIZE, **kwargs)
                await self.out_queue.put({"type": "audio", "data": data, "mime_type": "audio/pcm"})
            except Exception as e:
                if self.running:  # Only print error if we're still supposed to be running
                    print(f"Audio capture error: {e}")
                break

    async def listen_text(self):
        """Listen for text input from user"""
        print("\n" + "="*50)
        print("🎤 Audio conversation started!")
        print("💬 Type text and press Enter to send context")
        print("📝 Available commands:")
        print("   - 'quit' or 'exit': End conversation")
        print("   - 'help': Show this help")
        print("   - Any other text: Send as context to Gemini")
        print("="*50 + "\n")
        
        while self.running:
            try:
                # Use aioconsole for async input
                text_input = await aioconsole.ainput()
                
                if text_input.lower() in ['quit', 'exit']:
                    print("👋 Ending conversation...")
                    self.running = False
                    break
                elif text_input.lower() == 'help':
                    print("\n📝 Available commands:")
                    print("   - 'quit' or 'exit': End conversation")
                    print("   - 'help': Show this help")
                    print("   - Any other text: Send as context to Gemini")
                    continue
                elif text_input.strip():
                    print(f"📤 Sending text context: {text_input}")
                    await self.out_queue.put({"type": "text", "data": text_input})
                    
            except Exception as e:
                if self.running:
                    print(f"Text input error: {e}")
                break

    async def send_realtime(self):
        """Send audio and text messages to Gemini"""
        while self.running:
            try:
                msg = await self.out_queue.get()
                
                if msg["type"] == "audio":
                    await self.session.send_realtime_input(audio={"data": msg["data"], "mime_type": msg["mime_type"]})
                elif msg["type"] == "text":
                    await self.session.send_realtime_input(text=msg["data"])
                    
            except Exception as e:
                if self.running:
                    print(f"Send error: {e}")
                break

    async def receive_audio(self):
        """Background task to read from the websocket and write pcm chunks to the output queue"""
        while self.running:
            try:
                turn = self.session.receive()
                async for response in turn:
                    if data := response.data:
                        self.audio_in_queue.put_nowait(data)
                        continue
                    if text := response.text:
                        print(f"🤖 Gemini: {text}")

                # If you interrupt the model, it sends a turn_complete.
                # For interruptions to work, we need to stop playback.
                # So empty out the audio queue because it may have loaded
                # much more audio than has played yet.
                while not self.audio_in_queue.empty():
                    self.audio_in_queue.get_nowait()
                    
            except Exception as e:
                if self.running:
                    print(f"Receive error: {e}")
                break

    async def play_audio(self):
        """Play audio responses from Gemini"""
        stream = await asyncio.to_thread(
            pya.open,
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
                    print(f"Audio playback error: {e}")
                break
        
        stream.close()

    async def run(self):
        try:
            async with (
                client.aio.live.connect(model=MODEL, config=CONFIG) as session,
                asyncio.TaskGroup() as tg,
            ):
                self.session = session

                # Send initial text prompt if provided
                if self.text_prompt:
                    await self.session.send_realtime_input(text=self.text_prompt)

                self.audio_in_queue = asyncio.Queue()
                self.out_queue = asyncio.Queue(maxsize=10)  # Increased size for text messages

                # Start all tasks
                tg.create_task(self.send_realtime())
                tg.create_task(self.listen_audio())
                tg.create_task(self.receive_audio())
                tg.create_task(self.play_audio())
                tg.create_task(self.listen_text())  # New text input task
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Main loop error: {e}")
            traceback.print_exc()
        finally:
            self.running = False
            if self.audio_stream:
                self.audio_stream.close()


# Alternative implementation using threading for text input
class AudioLoopWithThreading:
    def __init__(self, text_prompt=None):
        self.audio_in_queue = None
        self.out_queue = None
        self.session = None
        self.audio_stream = None
        self.text_prompt = text_prompt
        self.running = True
        self.text_thread = None

    def text_input_thread(self):
        """Thread function to handle text input"""
        print("\n" + "="*50)
        print("🎤 Audio conversation started!")
        print("💬 Type text and press Enter to send context")
        print("📝 Available commands:")
        print("   - 'quit' or 'exit': End conversation")
        print("   - 'help': Show this help")
        print("   - Any other text: Send as context to Gemini")
        print("="*50 + "\n")
        
        while self.running:
            try:
                text_input = input()
                
                if text_input.lower() in ['quit', 'exit']:
                    print("👋 Ending conversation...")
                    self.running = False
                    break
                elif text_input.lower() == 'help':
                    print("\n📝 Available commands:")
                    print("   - 'quit' or 'exit': End conversation")
                    print("   - 'help': Show this help")
                    print("   - Any other text: Send as context to Gemini")
                    continue
                elif text_input.strip():
                    print(f"📤 Sending text context: {text_input}")
                    # Use asyncio.create_task to add to queue from thread
                    asyncio.run_coroutine_threadsafe(
                        self.out_queue.put({"type": "text", "data": text_input}),
                        asyncio.get_event_loop()
                    )
                    
            except (EOFError, KeyboardInterrupt):
                self.running = False
                break
            except Exception as e:
                if self.running:
                    print(f"Text input error: {e}")

    async def listen_audio(self):
        """Capture audio from microphone and send to Gemini"""
        mic_info = pya.get_default_input_device_info()
        self.audio_stream = await asyncio.to_thread(
            pya.open,
            format=FORMAT,
            channels=CHANNELS,
            rate=SEND_SAMPLE_RATE,
            input=True,
            input_device_index=mic_info["index"],
            frames_per_buffer=CHUNK_SIZE,
        )
        if _debug_:
            kwargs = {"exception_on_overflow": False}
        else:
            kwargs = {}
        
        while self.running:
            try:
                data = await asyncio.to_thread(self.audio_stream.read, CHUNK_SIZE, **kwargs)
                await self.out_queue.put({"type": "audio", "data": data, "mime_type": "audio/pcm"})
            except Exception as e:
                if self.running:
                    print(f"Audio capture error: {e}")
                break

    async def send_realtime(self):
        """Send audio and text messages to Gemini"""
        while self.running:
            try:
                msg = await self.out_queue.get()
                
                if msg["type"] == "audio":
                    await self.session.send_realtime_input(audio={"data": msg["data"], "mime_type": msg["mime_type"]})
                elif msg["type"] == "text":
                    await self.session.send_realtime_input(text=msg["data"])
                    
            except Exception as e:
                if self.running:
                    print(f"Send error: {e}")
                break

    async def receive_audio(self):
        """Background task to read from the websocket and write pcm chunks to the output queue"""
        while self.running:
            try:
                turn = self.session.receive()
                async for response in turn:
                    if data := response.data:
                        self.audio_in_queue.put_nowait(data)
                        continue
                    if text := response.text:
                        print(f"🤖 Gemini: {text}")

                while not self.audio_in_queue.empty():
                    self.audio_in_queue.get_nowait()
                    
            except Exception as e:
                if self.running:
                    print(f"Receive error: {e}")
                break

    async def play_audio(self):
        """Play audio responses from Gemini"""
        stream = await asyncio.to_thread(
            pya.open,
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
                    print(f"Audio playback error: {e}")
                break
        
        stream.close()

    async def run(self):
        try:
            # Start text input thread
            self.text_thread = threading.Thread(target=self.text_input_thread, daemon=True)
            self.text_thread.start()
            
            async with (
                client.aio.live.connect(model=MODEL, config=CONFIG) as session,
                asyncio.TaskGroup() as tg,
            ):
                self.session = session

                if self.text_prompt:
                    await self.session.send_realtime_input(text=self.text_prompt)

                self.audio_in_queue = asyncio.Queue()
                self.out_queue = asyncio.Queue(maxsize=10)

                tg.create_task(self.send_realtime())
                tg.create_task(self.listen_audio())
                tg.create_task(self.receive_audio())
                tg.create_task(self.play_audio())
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Main loop error: {e}")
            traceback.print_exc()
        finally:
            self.running = False
            if self.audio_stream:
                self.audio_stream.close()


if __name__ == "__main__":
    # Choose which implementation to use
    USE_ASYNC_INPUT = True  # Set to False to use threading version
    
    # Example usage with custom prompt
    text_prompt = "Please speak in Indian English with Mumbai accent"
    
    if USE_ASYNC_INPUT:
        print("Using async input version (requires aioconsole: pip install aioconsole)")
        loop = AudioLoop(text_prompt=text_prompt)
    else:
        print("Using threading version")
        loop = AudioLoopWithThreading(text_prompt=text_prompt)
    
    try:
        asyncio.run(loop.run())
    except KeyboardInterrupt:
        print("\n👋 Conversation ended by user")
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()