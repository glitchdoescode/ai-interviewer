"""
Tests for the AI Interviewer workflow.
"""
import pytest
from unittest.mock import patch, MagicMock
from typing import Literal

from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import MessagesState

from ai_interviewer.core.ai_interviewer import AIInterviewer


def test_should_continue_with_tool_calls():
    """Test that workflow continues to tools when tool calls are present."""
    # Create a mock AI message with tool calls
    ai_message = AIMessage(content="Let me think about that.")
    ai_message.tool_calls = [{"name": "start_coding_challenge", "args": {}}]
    
    # Create a mock state with the AI message
    state = {
        "messages": [HumanMessage(content="Hi"), ai_message]
    }
    
    # Call the should_continue method
    result = AIInterviewer.should_continue(state)
    assert result == "tools"


def test_should_continue_no_tool_calls():
    """Test that workflow ends when no tool calls are present."""
    # Create a mock AI message without tool calls
    ai_message = AIMessage(content="Thank you for your answer.")
    
    # Create a mock state with the AI message
    state = {
        "messages": [HumanMessage(content="Hi"), ai_message]
    }
    
    # Call the should_continue method
    result = AIInterviewer.should_continue(state)
    assert result == "end"


def test_should_continue_empty_messages():
    """Test that workflow ends when messages list is empty."""
    # Create an empty state
    state = {
        "messages": []
    }
    
    # Call the should_continue method
    result = AIInterviewer.should_continue(state)
    assert result == "end"


def test_interviewer_initialization():
    """Test that AIInterviewer initializes correctly."""
    # Initialize the interviewer
    interviewer = AIInterviewer()
    
    # Verify the important components are set up
    assert hasattr(interviewer, "tools")
    assert hasattr(interviewer, "tool_node")
    assert hasattr(interviewer, "model")
    assert hasattr(interviewer, "workflow")
    assert hasattr(interviewer, "memory")
    
    # Verify workflow was initialized
    assert interviewer.workflow is not None
    
    # Verify tools were initialized
    assert len(interviewer.tools) > 0 