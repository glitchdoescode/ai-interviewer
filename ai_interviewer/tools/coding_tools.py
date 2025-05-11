"""
Coding challenge tools for the AI Interviewer platform.

This module implements tools for starting, interacting with, and evaluating coding challenges.
"""
import logging
from typing import Dict, List, Optional, Any
import uuid

from langchain_core.tools import tool
from ai_interviewer.models.coding_challenge import get_coding_challenge, CodingChallenge
from ai_interviewer.tools.code_quality import CodeQualityMetrics

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
            "time_limit_mins": challenge.time_limit_mins,
            "evaluation_criteria": {
                "correctness": "Code produces correct output for all test cases",
                "efficiency": "Code uses efficient algorithms and data structures",
                "code_quality": "Code follows best practices and style guidelines",
                "documentation": "Code is well-documented with comments and docstrings"
            }
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
        logger.info(f"Received code submission for challenge: {challenge_id}")
        
        # Get the challenge details
        challenge = get_coding_challenge(challenge_id)
        
        # Basic validation - check for empty submission
        code_without_comments = "\n".join(
            line for line in candidate_code.split("\n") 
            if not line.strip().startswith("#")
        )
        
        if not code_without_comments.strip():
            return {
                "status": "submitted",
                "challenge_id": challenge_id,
                "evaluation": {
                    "passed": False,
                    "message": "Your submission appears to be empty or contains only comments."
                }
            }
        
        # Analyze code quality
        quality_metrics = {}
        if challenge.language.lower() == "python":
            quality_metrics = CodeQualityMetrics.analyze_python_code(candidate_code)
        
        # Language-specific basic checks
        if challenge.language.lower() == "python":
            if "def " not in candidate_code:
                return {
                    "status": "submitted",
                    "challenge_id": challenge_id,
                    "evaluation": {
                        "passed": False,
                        "message": "Your solution doesn't appear to define any functions.",
                        "quality_metrics": quality_metrics
                    }
                }
            
        elif challenge.language.lower() == "javascript":
            if "function " not in candidate_code and "=>" not in candidate_code:
                return {
                    "status": "submitted",
                    "challenge_id": challenge_id,
                    "evaluation": {
                        "passed": False,
                        "message": "Your solution doesn't appear to define any functions.",
                        "quality_metrics": quality_metrics
                    }
                }
        
        # For MVP, we'll provide a detailed evaluation without actual execution
        evaluation = {
            "passed": True,
            "test_results": [],
            "quality_metrics": quality_metrics,
            "feedback": []
        }
        
        # Add quality-based feedback
        if quality_metrics:
            evaluation["feedback"].extend(quality_metrics.get("interpretations", []))
            
            # Add specific recommendations
            if quality_metrics["complexity"]["cyclomatic_complexity"] > 10:
                evaluation["feedback"].append(
                    "Consider breaking down complex functions into smaller, more manageable pieces."
                )
            
            if quality_metrics["documentation"]["doc_ratio"] < 0.5:
                evaluation["feedback"].append(
                    "Adding docstrings to functions and classes would improve code maintainability."
                )
            
            if quality_metrics["style"]["pylint_score"] < 7:
                evaluation["feedback"].append(
                    "Review PEP 8 style guidelines to improve code readability."
                )
        
        # Add test case results (placeholder for MVP)
        for test_case in challenge.test_cases:
            test_result = {
                "input": test_case.input,
                "expected_output": test_case.expected_output,
                "passed": True,  # Placeholder - would be actual test execution result
                "explanation": test_case.explanation
            }
            evaluation["test_results"].append(test_result)
        
        return {
            "status": "submitted",
            "challenge_id": challenge_id,
            "evaluation": evaluation
        }
        
    except Exception as e:
        logger.error(f"Error processing code submission: {e}")
        return {
            "status": "error",
            "message": "Failed to process your code submission. Please try again."
        }


@tool
def get_coding_hint(challenge_id: str, current_code: str, error_message: Optional[str] = None) -> Dict:
    """
    Get a hint for the current coding challenge.
    
    Args:
        challenge_id: ID of the challenge
        current_code: Current code state
        error_message: Optional error message if the code is failing
        
    Returns:
        Dictionary containing the hint and any additional guidance
    """
    try:
        challenge = get_coding_challenge(challenge_id)
        
        # Get available hints
        available_hints = challenge.hints
        
        # Analyze current code state
        code_state = {
            "has_function_definition": "def " in current_code or "function" in current_code,
            "has_return_statement": "return" in current_code,
            "line_count": len(current_code.splitlines())
        }
        
        # Select appropriate hint based on code state
        if not code_state["has_function_definition"]:
            hint = "Start by defining a function with the correct name and parameters."
        elif not code_state["has_return_statement"]:
            hint = "Don't forget to return your result using a return statement."
        elif error_message:
            hint = f"Your code is raising an error: {error_message}. Check your logic and data types."
        elif available_hints:
            # Use the next available hint
            hint = available_hints[0]  # In production, would track which hints were already given
        else:
            hint = "Try breaking down the problem into smaller steps and solve each part separately."
        
        return {
            "status": "success",
            "hint": hint,
            "additional_resources": [
                "Review the problem description carefully",
                "Look at the test cases for examples",
                "Consider edge cases in your solution"
            ]
        }
        
    except Exception as e:
        logger.error(f"Error getting coding hint: {e}")
        return {
            "status": "error",
            "message": "Failed to generate hint. Please try again."
        } 