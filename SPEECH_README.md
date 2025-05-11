# AI Interviewer: Speech-to-Text and Text-to-Speech Features

This document explains how to set up and use the voice interaction features of the AI Interviewer platform.

## Overview

The AI Interviewer now supports voice interactions through speech-to-text (STT) and text-to-speech (TTS) capabilities powered by Deepgram's API. This allows for a more natural and engaging interview experience.

## Features

- **Speech-to-Text**: Record your voice responses and have them automatically transcribed
- **Text-to-Speech**: Listen to the interviewer's responses in a natural-sounding voice
- **Voice-Enabled CLI**: Conduct entire interviews using voice input/output
- **Voice Activity Detection**: Smart recording that automatically stops when you pause
- **Customizable Voice Settings**: Adjust silence detection parameters, sample rate, and TTS voice

## Prerequisites

1. **Deepgram API Key**: You'll need to sign up for a [Deepgram](https://deepgram.com/) account and obtain an API key.
2. **Audio Input/Output Hardware**: Working microphone and speakers or headphones.
3. **Python Dependencies**: See installation instructions below.

## Installation

1. **Install required system packages for PyAudio**:

   **For Ubuntu/Debian**:
   ```bash
   sudo apt-get install portaudio19-dev python3-pyaudio
   ```

   **For macOS**:
   ```bash
   brew install portaudio
   ```

2. **Install Python dependencies**:
   ```bash
   pip install -r speech_requirements.txt
   ```

## Configuration

1. **Set your Deepgram API Key** using one of these methods:

   - Environment variable:
     ```bash
     export DEEPGRAM_API_KEY="your_api_key_here"
     ```
   
   - Create a `.env` file in the project root:
     ```
     DEEPGRAM_API_KEY=your_api_key_here
     ```

2. **Customize speech settings** (optional) in `.env`:
   ```
   SPEECH_RECORDING_DURATION=30.0      # Maximum recording duration
   SPEECH_SAMPLE_RATE=16000           # Audio sample rate in Hz
   SPEECH_TTS_VOICE=nova              # Voice to use for TTS
   SPEECH_SILENCE_THRESHOLD=0.03      # Volume threshold for silence detection (0.0-1.0)
   SPEECH_SILENCE_DURATION=2.0        # Seconds of silence to end recording
   ```

## Usage

### Voice CLI

Run the voice-enabled CLI to conduct an interview through speech:

```bash
python -m ai_interviewer.voice_cli
```

Options:
- `--api-key KEY`: Manually provide a Deepgram API key
- `--max-duration SECONDS`: Set maximum recording duration (default: 30.0)
- `--silence-duration SECONDS`: Set pause duration to end recording (default: 2.0)
- `--silence-threshold VALUE`: Set volume threshold for silence (default: 0.03)
- `--voice VOICE`: Set TTS voice (default: nova)
- `--save FILENAME`: Automatically save transcript to specified file
- `--debug`: Enable debug logging

### Basic Interaction Flow

1. The CLI will greet you and begin the interview
2. When it's your turn to speak, the system will show "🎙️ Listening... (speak now, pause for 2s to finish)"
3. Speak clearly into your microphone
4. When you pause for the configured duration (default 2 seconds), recording will automatically stop
5. Your transcribed response will be shown, and the AI will respond
6. The AI's response will be both displayed and spoken aloud
7. To end the interview, simply say "exit" or "quit"

The recording will show audio levels in real-time, making it easy to see when your voice is being detected:

## Troubleshooting

- **No audio recording**: Check your microphone settings and permissions
- **API errors**: Verify your Deepgram API key is correct and has sufficient credits
- **PyAudio installation issues**: See the system package requirements above

## Advanced Usage

### Programmatic Use of Voice Features

You can integrate voice features into your own applications:

```python
from ai_interviewer.utils.speech_utils import VoiceHandler

async def example():
    voice_handler = VoiceHandler(api_key="your_api_key")
    
    # Speech-to-text
    transcript = await voice_handler.listen(duration_seconds=5.0)
    print(f"You said: {transcript}")
    
    # Text-to-speech
    await voice_handler.speak(
        text="This is a response from the AI.",
        voice="nova",
        play_audio=True
    )
```

### Available Voices

Deepgram offers several voices for TTS:
- nova (default)
- female
- male
- And more (check Deepgram's documentation for the latest options)

## Future Improvements

- Stream audio in real-time instead of fixed recording durations
- Add voice activity detection for automatic stopping of recording
- Support for additional languages
- Integrate with web interface for browser-based voice interviews 