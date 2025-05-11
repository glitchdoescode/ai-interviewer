"""
Integration tests for the AI Interviewer platform.

Tests the interaction between different components and end-to-end workflows.
"""
import unittest
import logging
from typing import Dict, Optional
from unittest.mock import patch, MagicMock

from ai_interviewer.tools.coding_tools import (
    start_coding_challenge,
    submit_code_for_challenge,
    get_coding_hint
)
from ai_interviewer.tools.pair_programming import (
    suggest_code_improvements,
    complete_code,
    review_code_section
)
from ai_interviewer.models.coding_challenge import CodingChallenge

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class TestPairProgrammingIntegration(unittest.TestCase):
    """Integration tests for pair programming features."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.sample_code = '''
def fibonacci(n):
    """Calculate the nth Fibonacci number."""
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)
'''

    def test_code_improvement_workflow(self):
        """Test the complete code improvement workflow."""
        # Get code improvement suggestions
        suggestions = suggest_code_improvements.invoke({"code": self.sample_code})
        self.assertEqual(suggestions["status"], "success")
        
        # Get code completion
        completion = complete_code.invoke({"code": self.sample_code, "context": "Add memoization"})
        self.assertEqual(completion["status"], "success")
        
        # Get code review
        review = review_code_section.invoke({"code": self.sample_code})
        self.assertEqual(review["status"], "success")

    def test_code_analysis_integration(self):
        """Test integration of code analysis features."""
        # Get suggestions
        suggestions = suggest_code_improvements.invoke({"code": self.sample_code})
        
        # Verify suggestions include quality metrics
        self.assertEqual(suggestions["status"], "success")
        self.assertIn("suggestions", suggestions)

class TestCodingChallengeIntegration(unittest.TestCase):
    """Integration tests for coding challenge features."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.challenge_response = start_coding_challenge.invoke({"challenge_id": None})
        self.sample_solution = '''
def solve_challenge(input_data):
    """Solution for the coding challenge."""
    # Process input
    result = input_data * 2
    
    # Return result
    return result
'''

    def test_challenge_evaluation_integration(self):
        """Test the challenge evaluation workflow."""
        # Submit solution
        evaluation = submit_code_for_challenge.invoke({
            "challenge_id": self.challenge_response["challenge_id"],
            "candidate_code": self.sample_solution
        })
        
        # Verify evaluation structure
        self.assertEqual(evaluation["status"], "submitted")
        self.assertIn("evaluation", evaluation)
        self.assertIn("test_results", evaluation["evaluation"])
        self.assertIn("quality_metrics", evaluation["evaluation"])

    def test_complete_challenge_workflow(self):
        """Test the complete challenge workflow."""
        # Start challenge
        self.assertIn("challenge_id", self.challenge_response)
        self.assertIn("starter_code", self.challenge_response)
        
        # Get hint
        hint = get_coding_hint.invoke({
            "challenge_id": self.challenge_response["challenge_id"],
            "current_code": self.sample_solution,
            "error_message": "Need optimization"
        })
        self.assertEqual(hint["status"], "success")
        self.assertIn("hints", hint)
        
        # Submit solution
        evaluation = submit_code_for_challenge.invoke({
            "challenge_id": self.challenge_response["challenge_id"],
            "candidate_code": self.sample_solution
        })
        self.assertEqual(evaluation["status"], "submitted")
        self.assertIn("evaluation", evaluation)

class TestEndToEndInterviewSession(unittest.TestCase):
    """End-to-end integration tests for interview sessions."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Start a coding challenge
        self.challenge_response = start_coding_challenge.invoke({"challenge_id": None})
        self.sample_solution = '''
def solve_challenge(input_data):
    """Solution for the coding challenge."""
    # Process input
    result = input_data * 2
    
    # Return result
    return result
'''

    def test_complete_interview_session(self):
        """Test a complete interview session flow."""
        # Verify challenge started successfully
        self.assertEqual(self.challenge_response["status"], "success")
        
        # Get a hint
        hint = get_coding_hint.invoke({
            "challenge_id": self.challenge_response["challenge_id"],
            "current_code": self.sample_solution
        })
        self.assertEqual(hint["status"], "success")
        self.assertIn("hints", hint)
        
        # Submit solution
        evaluation = submit_code_for_challenge.invoke({
            "challenge_id": self.challenge_response["challenge_id"],
            "candidate_code": self.sample_solution
        })
        self.assertEqual(evaluation["status"], "submitted")
        self.assertIn("evaluation", evaluation)
        self.assertIn("test_results", evaluation["evaluation"])
        
        # Get code improvements
        improvements = suggest_code_improvements.invoke({"code": self.sample_solution})
        self.assertEqual(improvements["status"], "success")
        self.assertIn("suggestions", improvements)

if __name__ == '__main__':
    unittest.main() 