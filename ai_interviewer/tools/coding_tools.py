"""
Coding challenge tools for the AI Interviewer platform.

This module implements tools for starting, interacting with, and evaluating coding challenges.
"""
import logging
from typing import Dict, List, Optional, Any
import uuid

from langchain_core.tools import tool
from ai_interviewer.models.coding_challenge import get_coding_challenge, CodingChallenge

# Configure logging
logger = logging.getLogger(__name__)


@tool
def start_coding_challenge(challenge_id: Optional[str] = None) -> Dict:
    """
    Start a coding challenge for the candidate.
    
    Args:
        challenge_id: Optional ID of a specific challenge to start, or random if not provided
        
    Returns:
        A dictionary containing the challenge details and starter code
    """
    try:
        # Get a challenge (specific or random)
        challenge = get_coding_challenge(challenge_id)
        logger.info(f"Starting coding challenge: {challenge.id} - {challenge.title}")
        
        # Only expose non-hidden test cases to the candidate
        visible_test_cases = [
            {
                "input": tc.input,
                "expected_output": tc.expected_output,
                "explanation": tc.explanation
            }
            for tc in challenge.test_cases if not tc.is_hidden
        ]
        
        # Return the challenge details
        return {
            "status": "success",
            "challenge_id": challenge.id,
            "title": challenge.title,
            "description": challenge.description,
            "language": challenge.language,
            "difficulty": challenge.difficulty,
            "starter_code": challenge.starter_code,
            "visible_test_cases": visible_test_cases,
            "time_limit_mins": challenge.time_limit_mins
        }
    except Exception as e:
        logger.error(f"Error starting coding challenge: {e}")
        return {
            "status": "error",
            "message": "Failed to start coding challenge. Please try again."
        }


@tool
def submit_code_for_challenge(challenge_id: str, candidate_code: str) -> Dict:
    """
    Submit a candidate's code solution for evaluation.
    
    Args:
        challenge_id: ID of the challenge being solved
        candidate_code: The code solution provided by the candidate
        
    Returns:
        A dictionary containing the evaluation results
    """
    try:
        # For MVP, we'll implement a placeholder evaluation
        # In a real implementation, this would execute the code against test cases
        logger.info(f"Received code submission for challenge: {challenge_id}")
        
        # Simple validation check - does the code contain more than just comments/whitespace?
        code_without_comments = candidate_code
        # Remove Python comments
        code_without_comments = "\n".join(
            line for line in code_without_comments.split("\n") 
            if not line.strip().startswith("#")
        )
        
        # Check if there's actual code content (not just whitespace)
        if not code_without_comments.strip():
            return {
                "status": "submitted",
                "challenge_id": challenge_id,
                "evaluation": {
                    "passed": False,
                    "message": "Your submission appears to be empty or contains only comments."
                }
            }
        
        # Get the challenge details to know what we're validating against
        challenge = get_coding_challenge(challenge_id)
        
        # For MVP, we'll just check if certain keywords are present
        # as a very basic proxy for correctness
        essential_keywords = []
        
        # Language-specific basic checks
        if challenge.language.lower() == "python":
            if "def " not in candidate_code:
                return {
                    "status": "submitted",
                    "challenge_id": challenge_id,
                    "evaluation": {
                        "passed": False,
                        "message": "Your solution doesn't appear to define any functions."
                    }
                }
            essential_keywords = ["return", "def"]
            
        elif challenge.language.lower() == "javascript":
            if "function " not in candidate_code and "=>" not in candidate_code:
                return {
                    "status": "submitted",
                    "challenge_id": challenge_id,
                    "evaluation": {
                        "passed": False,
                        "message": "Your solution doesn't appear to define any functions."
                    }
                }
            essential_keywords = ["return", "function"]
        
        # Check if essential keywords are present
        missing_keywords = [kw for kw in essential_keywords if kw not in candidate_code]
        if missing_keywords:
            return {
                "status": "submitted",
                "challenge_id": challenge_id,
                "evaluation": {
                    "passed": False,
                    "message": f"Your solution may be missing important elements: {', '.join(missing_keywords)}"
                }
            }
        
        # For MVP, we'll assume basic correctness if it passes these simple checks
        # and contains a reasonable amount of code
        return {
            "status": "submitted",
            "challenge_id": challenge_id,
            "evaluation": {
                "passed": True,
                "message": "Your solution has been submitted and preliminarily checked. In a real environment, we would run your code against test cases."
            }
        }
        
    except Exception as e:
        logger.error(f"Error processing code submission: {e}")
        return {
            "status": "error",
            "message": "Failed to process your code submission. Please try again."
        }


@tool
def get_coding_hint(challenge_id: str, current_code: Optional[str] = None) -> Dict:
    """
    Get a hint for the current coding challenge.
    
    Args:
        challenge_id: ID of the challenge the candidate is working on
        current_code: Optional current code attempt to contextualize the hint
        
    Returns:
        A dictionary containing a hint for the challenge
    """
    try:
        # Get the challenge
        challenge = get_coding_challenge(challenge_id)
        logger.info(f"Providing hint for challenge: {challenge.id}")
        
        if not challenge.hints:
            return {
                "status": "success",
                "message": "Think about the problem step by step. Try breaking it down into smaller parts."
            }
        
        # For MVP, simply return the first hint
        # In a more advanced implementation, we could analyze the current code
        # and provide a contextual hint
        hint = challenge.hints[0]
        
        return {
            "status": "success",
            "message": hint
        }
    except Exception as e:
        logger.error(f"Error providing coding hint: {e}")
        return {
            "status": "error",
            "message": "Failed to provide a hint. Please try again."
        } 