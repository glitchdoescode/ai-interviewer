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
            },
            "pair_programming_features": {
                "code_suggestions": "Get AI suggestions for code improvements",
                "code_completion": "Get context-aware code completions",
                "code_review": "Get focused code review and feedback"
            }
        }
    except Exception as e:
        logger.error(f"Error starting coding challenge: {e}")
        return {
            "status": "error",
            "message": str(e)
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
            if quality_metrics.get("complexity", {}).get("cyclomatic_complexity", 0) > 10:
                evaluation["feedback"].append(
                    "Consider breaking down complex functions into smaller, more manageable pieces."
                )
            
            if quality_metrics.get("documentation", {}).get("doc_ratio", 0) < 0.5:
                evaluation["feedback"].append(
                    "Adding docstrings to functions and classes would improve code maintainability."
                )
            
            if quality_metrics.get("style", {}).get("pylint_score", 0) < 7:
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
        
        # Get AI pair programming suggestions
        from ai_interviewer.tools.pair_programming import suggest_code_improvements, review_code_section
        suggestions = suggest_code_improvements.invoke({"code": candidate_code})
        if suggestions["status"] == "success":
            evaluation["ai_suggestions"] = suggestions["suggestions"]
        
        # Add code review
        review = review_code_section.invoke({"code": candidate_code})
        if review["status"] == "success":
            evaluation["code_review"] = review["review"]
        
        return {
            "status": "submitted",
            "challenge_id": challenge_id,
            "evaluation": evaluation
        }
        
    except Exception as e:
        logger.error(f"Error processing code submission: {e}")
        return {
            "status": "error",
            "message": str(e)
        }


@tool
def get_coding_hint(challenge_id: str, current_code: str, error_message: Optional[str] = None) -> Dict:
    """
    Get a hint for the current coding challenge.
    
    Args:
        challenge_id: ID of the challenge
        current_code: Current code implementation
        error_message: Optional error message to get specific help
        
    Returns:
        A dictionary containing the hint
    """
    try:
        # Get the challenge details
        challenge = get_coding_challenge(challenge_id)
        
        # Get code suggestions
        from ai_interviewer.tools.pair_programming import suggest_code_improvements, complete_code
        suggestions = suggest_code_improvements.invoke({
            "code": current_code,
            "context": {
                "challenge": challenge.model_dump(),
                "error_message": error_message
            }
        })
        
        # Get code completion suggestions
        completion = complete_code.invoke({
            "code": current_code,
            "context": "Add error handling and edge cases"
        })
        
        # Compile hints
        hints = []
        
        # Add error-specific hint if provided
        if error_message:
            hints.append(f"Regarding the error '{error_message}':")
            hints.append("Consider adding error handling for this case.")
        
        # Add general improvement suggestions
        if suggestions["status"] == "success":
            hints.extend(suggestions["suggestions"])
        
        # Add completion suggestions
        if completion["status"] == "success":
            hints.append("Consider completing the implementation:")
            hints.append(completion["completion"])
        
        return {
            "status": "success",
            "hints": hints,
            "message": "\n".join(hints)
        }
        
    except Exception as e:
        logger.error(f"Error getting coding hint: {e}")
        return {
            "status": "error",
            "message": str(e)
        } 