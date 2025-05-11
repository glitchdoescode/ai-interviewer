"""
Tests for the workflow module.
"""
import pytest
from unittest.mock import patch, MagicMock

from langchain_core.messages import HumanMessage, AIMessage

from ai_interviewer.core.workflow import build_interview_graph, should_continue_or_end_interview
from ai_interviewer.models.state import InterviewState


def test_should_continue_or_end_interview_finished_stage():
    """Test that workflow ends when interview stage is 'finished'"""
    # Create a mock state with 'finished' stage
    state = InterviewState(
        messages=[],
        interview_id="test_id",
        interview_stage="finished"
    )
    
    result = should_continue_or_end_interview(state)
    assert result == "end"


def test_should_continue_or_end_interview_with_tool_calls():
    """Test that workflow continues to tools when tool calls are present"""
    # Create a mock AI message with tool calls
    ai_message = AIMessage(content="Let me think about that.")
    ai_message.tool_calls = [{"name": "get_next_question", "args": {"topic": "python"}}]
    
    # Create a mock state with the AI message
    state = InterviewState(
        messages=[HumanMessage(content="Hi"), ai_message],
        interview_id="test_id",
        interview_stage="qa"
    )
    
    result = should_continue_or_end_interview(state)
    assert result == "tools"


def test_should_continue_or_end_interview_no_tool_calls():
    """Test that workflow ends when no tool calls are present"""
    # Create a mock AI message without tool calls
    ai_message = AIMessage(content="Thank you for your answer.")
    
    # Create a mock state with the AI message
    state = InterviewState(
        messages=[HumanMessage(content="Hi"), ai_message],
        interview_id="test_id",
        interview_stage="qa"
    )
    
    result = should_continue_or_end_interview(state)
    assert result == "end"


@patch('ai_interviewer.core.workflow.interview_agent')
@patch('ai_interviewer.core.workflow.ToolNode')
def test_build_interview_graph(mock_tool_node, mock_interview_agent):
    """Test that the workflow graph is built correctly"""
    # Setup mocks
    mock_tool_node_instance = MagicMock()
    mock_tool_node.return_value = mock_tool_node_instance
    
    # Build the graph
    graph = build_interview_graph()
    
    # Assert the graph was compiled
    assert graph is not None
    
    # Verify the nodes were added correctly
    mock_tool_node.assert_called_once()
    
    # Since we're mocking most of the internals, we're primarily testing
    # that the function runs without errors and returns something 