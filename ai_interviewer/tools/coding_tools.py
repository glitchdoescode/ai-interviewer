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
from ai_interviewer.tools.code_execution import CodeExecutor, SafetyChecker, execute_candidate_code
from ai_interviewer.tools.code_feedback import CodeFeedbackGenerator
from ai_interviewer.tools.pair_programming import HintGenerator

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
            },
            "pair_programming_features": {
                "code_suggestions": "Get AI suggestions for code improvements",
                "code_completion": "Get context-aware code completions",
                "code_review": "Get focused code review and feedback",
                "hints": "Get targeted hints when you're stuck"
            }
        }
    except Exception as e:
        logger.error(f"Error starting coding challenge: {e}")
        return {
            "status": "error",
            "message": str(e)
        }


@tool
def submit_code_for_challenge(challenge_id: str, candidate_code: str, skill_level: str = "intermediate") -> Dict:
    """
    Submit a candidate's code solution for evaluation.
    
    Args:
        challenge_id: ID of the challenge being solved
        candidate_code: The code solution provided by the candidate
        skill_level: Skill level of the candidate (beginner, intermediate, advanced)
        
    Returns:
        A dictionary containing the detailed evaluation results
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
            
        # Extract all test cases (including hidden)
        test_cases = [
            {
                "input": tc.input,
                "expected_output": tc.expected_output,
                "explanation": tc.explanation,
                "is_hidden": tc.is_hidden
            }
            for tc in challenge.test_cases
        ]
        
        # Execute the code using our secure Docker executor
        execution_results = execute_candidate_code(
            language=challenge.language.lower(),
            code=candidate_code,
            test_cases=test_cases
        )
        
        # Generate detailed feedback
        feedback = CodeFeedbackGenerator.generate_feedback(
            code=candidate_code,
            execution_results=execution_results.get("detailed_results", execution_results),
            language=challenge.language,
            skill_level=skill_level
        )
        
        # Return detailed evaluation
        return {
            "status": "submitted",
            "challenge_id": challenge_id,
            "candidate_code": candidate_code,
            "execution_results": execution_results,
            "feedback": feedback,
            "evaluation": {
                "passed": execution_results.get("status") == "success" and execution_results.get("pass_count", 0) == execution_results.get("total_tests", 0),
                "pass_rate": feedback["correctness"].get("pass_rate", 0),
                "code_quality_score": feedback["code_quality"].get("overall_score", 0),
                "summary": feedback["summary"],
                "suggestions": feedback["suggestions"],
                "strengths": feedback["strengths"],
                "areas_for_improvement": feedback["areas_for_improvement"]
            }
        }
        
    except Exception as e:
        logger.error(f"Error processing code submission: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "status": "error",
            "message": str(e)
        }


@tool
def get_coding_hint(challenge_id: str, current_code: str, error_message: Optional[str] = None) -> Dict:
    """
    Get a context-aware hint for the current coding challenge based on the candidate's code.
    
    Args:
        challenge_id: ID of the challenge
        current_code: Current code implementation
        error_message: Optional error message to get specific help
        
    Returns:
        A dictionary containing targeted hints
    """
    try:
        # Get the challenge details
        challenge = get_coding_challenge(challenge_id)
        logger.info(f"Generating hint for challenge: {challenge.id} - {challenge.title}")
        
        # Create context dictionary for the hint generator
        challenge_info = {
            "id": challenge.id,
            "title": challenge.title,
            "description": challenge.description,
            "difficulty": challenge.difficulty,
            "language": challenge.language,
            "hints": challenge.hints,
            "tags": challenge.tags
        }
        
        # Use the new HintGenerator to get context-aware hints
        hints = HintGenerator.generate_hints(
            code=current_code,
            challenge_info=challenge_info,
            error_message=error_message,
            skill_level="intermediate"  # This could be passed as a parameter in the future
        )
        
        # If we couldn't generate any hints, fall back to predefined hints
        if not hints and challenge.hints:
            hints = [challenge.hints[0]]  # Just provide the first hint
            
        # If we still have no hints, provide a generic one
        if not hints:
            hints = [
                "Try breaking the problem down into smaller steps.",
                "Review the test cases carefully to understand all requirements.",
                "Consider edge cases in your solution."
            ]
        
        # Return the hints
        return {
            "status": "success",
            "challenge_id": challenge.id,
            "hints": hints,
            "related_concepts": challenge.tags  # Include relevant concepts/tags
        }
        
    except Exception as e:
        logger.error(f"Error generating coding hint: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "status": "error",
            "message": f"Could not generate hint: {str(e)}",
            "fallback_hints": [
                "Review your algorithm logic step by step.",
                "Check for edge cases in your solution.",
                "Make sure your code handles all the test case scenarios."
            ]
        } 