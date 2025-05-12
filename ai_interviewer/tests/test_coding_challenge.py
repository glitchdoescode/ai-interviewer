import unittest
import asyncio
from unittest.mock import MagicMock, patch
import json

from ai_interviewer.core.ai_interviewer import AIInterviewer, InterviewStage
from ai_interviewer.tools.coding_tools import start_coding_challenge, submit_code_for_challenge
from ai_interviewer.models.coding_challenge import get_coding_challenge
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage


class TestCodingChallengeHumanInTheLoop(unittest.TestCase):
    """Test the human-in-the-loop functionality for coding challenges."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a mock session manager
        self.mock_session_manager = MagicMock()
        
        # Create a mock LLM that returns a predefined response with tool calls
        self.mock_llm = MagicMock()
        
        # Create an AI interviewer instance with mocks
        self.interviewer = AIInterviewer(
            llm=self.mock_llm,
            session_manager=self.mock_session_manager
        )
        
        # Sample challenge for testing
        self.challenge_id = "py_001"
        self.challenge = get_coding_challenge(self.challenge_id)
        self.sample_solution = """
def reverse_string(s: str) -> str:
    return s[::-1]
"""
    
    def test_coding_challenge_flow(self):
        """Test the complete coding challenge flow with human-in-the-loop."""
        # 1. Test initiating a coding challenge
        
        # Mock session data
        session_id = "test-session-123"
        user_id = "test-user-456"
        
        # Create mock AI message with tool call to start a coding challenge
        ai_message = AIMessage(content="Let's test your coding skills with a challenge.")
        ai_message.tool_calls = [{
            "name": "start_coding_challenge",
            "arguments": {"challenge_id": self.challenge_id},
            "result": start_coding_challenge(self.challenge_id)
        }]
        
        # Mock session data
        mock_session = {
            "session_id": session_id,
            "user_id": user_id,
            "messages": [
                SystemMessage(content="System prompt"),
                HumanMessage(content="I'm ready for a coding challenge"),
                ai_message
            ],
            "metadata": {
                "interview_stage": InterviewStage.CODING_CHALLENGE.value,
                "created_at": "2023-01-01T00:00:00",
                "last_active": "2023-01-01T00:00:00"
            }
        }
        
        # Configure session manager mock to return our mock session
        self.mock_session_manager.get_session.return_value = mock_session
        
        # Execute the interview function
        result = asyncio.run(self.interviewer.run_interview(
            user_id=user_id,
            user_message="I'll solve the challenge",
            session_id=session_id
        ))
        
        # Check if the interviewer detected the coding challenge waiting state
        self.assertIn("coding challenge", result[0].lower())
        self.assertIn("interface", result[0].lower())
        
        # 2. Test submitting code for the challenge
        
        # Now mock a coding challenge submission result
        submission_result = submit_code_for_challenge(
            challenge_id=self.challenge_id,
            candidate_code=self.sample_solution
        )
        
        # Update mock session to include the challenge completion indicator
        mock_session["metadata"]["resuming_from_challenge"] = True
        mock_session["metadata"]["challenge_completed"] = True
        
        # Configure mock LLM to return a response acknowledging completion
        self.mock_llm.ainvoke.return_value = AIMessage(
            content="Great job completing the coding challenge! Your solution was efficient and correct."
        )
        
        # Execute the interview function after challenge completion
        result_after_completion = asyncio.run(self.interviewer.run_interview(
            user_id=user_id,
            user_message="I've completed the challenge",
            session_id=session_id
        ))
        
        # Verify the response acknowledges completion
        self.assertIn("Great job", result_after_completion[0])
        
        # Verify session manager was called to update the session
        self.mock_session_manager.update_session.assert_called()
    
    def test_determine_interview_stage(self):
        """Test the _determine_interview_stage function for accurate detection."""
        # Test with coding challenge in messages
        messages = [
            SystemMessage(content="System prompt"),
            HumanMessage(content="I'm ready for a coding challenge"),
            AIMessage(content="Here's a challenge")
        ]
        
        # Add tool call for start_coding_challenge
        ai_message = messages[-1]
        ai_message.tool_calls = [{
            "name": "start_coding_challenge",
            "arguments": {"challenge_id": self.challenge_id}
        }]
        
        metadata = {"interview_stage": InterviewStage.TECHNICAL_QUESTIONS.value}
        
        # Should detect coding challenge stage
        stage = self.interviewer._determine_interview_stage_from_metadata(messages, metadata)
        self.assertEqual(stage, InterviewStage.CODING_CHALLENGE.value)
        
        # Test with resume from challenge
        metadata = {
            "interview_stage": InterviewStage.CODING_CHALLENGE.value,
            "resuming_from_challenge": True,
            "challenge_completed": True
        }
        
        # Should transition to technical questions after completed challenge
        stage = self.interviewer._determine_interview_stage_from_metadata(messages, metadata)
        self.assertEqual(stage, InterviewStage.TECHNICAL_QUESTIONS.value)
        
        # Test with resume but not completed
        metadata = {
            "interview_stage": InterviewStage.CODING_CHALLENGE.value,
            "resuming_from_challenge": True,
            "challenge_completed": False
        }
        
        # Should stay in coding challenge
        stage = self.interviewer._determine_interview_stage_from_metadata(messages, metadata)
        self.assertEqual(stage, InterviewStage.CODING_CHALLENGE.value)


if __name__ == "__main__":
    unittest.main() 