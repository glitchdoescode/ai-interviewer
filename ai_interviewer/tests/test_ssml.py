"""
Tests for SSML functionality in the {SYSTEM_NAME} platform.

This module tests the SSML utilities and TTS integration with SSML.
"""
import pytest
import os
from pathlib import Path
import asyncio
from ai_interviewer.utils.ssml_utils import SSMLBuilder, add_automatic_ssml, validate_ssml
from ai_interviewer.utils.speech_utils import DeepgramTTS

# Test data
TEST_TEXT = "Hello, this is a test of the text-to-speech system."
TEST_OUTPUT_DIR = Path("test_output")

@pytest.fixture(autouse=True)
def setup_test_env():
    """Set up test environment."""
    # Create test output directory
    TEST_OUTPUT_DIR.mkdir(exist_ok=True)
    
    # Clean up any existing test files
    for file in TEST_OUTPUT_DIR.glob("*.wav"):
        file.unlink()
    
    yield
    
    # Clean up after tests
    for file in TEST_OUTPUT_DIR.glob("*.wav"):
        file.unlink()
    
    try:
        TEST_OUTPUT_DIR.rmdir()
    except:
        pass

def test_ssml_builder():
    """Test SSMLBuilder functionality."""
    # Test basic text
    builder = SSMLBuilder("Hello")
    assert builder.build() == "<speak>Hello</speak>"
    
    # Test break
    builder = SSMLBuilder("Hello")
    builder.add_break("500ms")
    assert builder.build() == "<speak>Hello<break time=\"500ms\"/></speak>"
    
    # Test emphasis
    builder = SSMLBuilder()
    builder.add_emphasis("important", "strong")
    assert builder.build() == "<speak><emphasis level=\"strong\">important</emphasis></speak>"
    
    # Test prosody
    builder = SSMLBuilder()
    builder.add_prosody("faster", rate="fast")
    assert builder.build() == "<speak><prosody rate=\"fast\">faster</prosody></speak>"
    
    # Test say-as
    builder = SSMLBuilder()
    builder.add_say_as("123", "cardinal")
    assert builder.build() == "<speak><say-as interpret-as=\"cardinal\">123</say-as></speak>"
    
    # Test chaining
    builder = SSMLBuilder("Start")
    result = (
        builder
        .add_break("500ms")
        .add_emphasis("important", "strong")
        .add_text(" end")
        .build()
    )
    assert result == "<speak>Start<break time=\"500ms\"/><emphasis level=\"strong\">important</emphasis> end</speak>"

def test_automatic_ssml():
    """Test automatic SSML tag insertion."""
    # Test basic sentence
    text = "This is a test."
    ssml = add_automatic_ssml(text)
    assert "<speak>" in ssml and "</speak>" in ssml
    
    # Test question mark
    text = "How are you?"
    ssml = add_automatic_ssml(text)
    assert "<break time=\"750ms\"/>" in ssml
    
    # Test emphasis
    text = "This is very important!"
    ssml = add_automatic_ssml(text)
    assert "<emphasis level=\"strong\">important</emphasis>" in ssml
    
    # Test multiple sentences
    text = "First sentence. Second sentence! Third sentence?"
    ssml = add_automatic_ssml(text)
    assert ssml.count("<break") >= 2

def test_ssml_validation():
    """Test SSML validation."""
    # Test valid SSML
    valid_ssml = "<speak>Hello<break time=\"500ms\"/>World</speak>"
    assert validate_ssml(valid_ssml) is True
    
    # Test invalid root element
    invalid_root = "<wrong>Hello</wrong>"
    assert validate_ssml(invalid_root) is False
    
    # Test invalid tag
    invalid_tag = "<speak><invalid>Hello</invalid></speak>"
    assert validate_ssml(invalid_tag) is False
    
    # Test invalid attribute
    invalid_attr = "<speak><break invalid=\"true\"/></speak>"
    assert validate_ssml(invalid_attr) is False
    
    # Test malformed XML
    malformed = "<speak>Hello<break></speak>"
    assert validate_ssml(malformed) is False

@pytest.mark.asyncio
async def test_tts_with_ssml():
    """Test TTS with SSML input."""
    # Skip if no API key
    if not os.environ.get("DEEPGRAM_API_KEY"):
        pytest.skip("Deepgram API key not available")
    
    tts = DeepgramTTS()
    output_file = TEST_OUTPUT_DIR / "test_ssml.wav"
    
    # Test with explicit SSML
    ssml = (
        SSMLBuilder("Hello")
        .add_break("500ms")
        .add_emphasis("important test", "strong")
        .build()
    )
    
    result = await tts.synthesize_speech(
        ssml,
        output_file=output_file,
        params={"use_ssml": True}
    )
    
    assert result["success"] is True
    assert result["used_ssml"] is True
    assert output_file.exists()
    
    # Test with automatic SSML
    output_file = TEST_OUTPUT_DIR / "test_auto_ssml.wav"
    result = await tts.synthesize_speech(
        "Hello! This is an important test.",
        output_file=output_file,
        auto_ssml=True
    )
    
    assert result["success"] is True
    assert result["used_ssml"] is True
    assert output_file.exists()
    
    # Test with invalid SSML
    invalid_ssml = "<speak><invalid>test</invalid></speak>"
    result = await tts.synthesize_speech(
        invalid_ssml,
        params={"use_ssml": True}
    )
    
    assert result["success"] is False
    assert "Invalid SSML markup" in result["error"] 