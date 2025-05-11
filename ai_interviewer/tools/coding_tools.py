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
from ai_interviewer.tools.code_execution import CodeExecutor, SafetyChecker
from ai_interviewer.tools.code_feedback import CodeFeedbackGenerator

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
        
        # Check code safety before execution
        is_safe = True
        safety_message = ""
        
        if challenge.language.lower() == "python":
            is_safe, safety_message = SafetyChecker.check_python_code_safety(candidate_code)
        
        if not is_safe:
            return {
                "status": "security_error",
                "challenge_id": challenge_id,
                "evaluation": {
                    "passed": False,
                    "message": f"Security check failed: {safety_message}. Please remove unsafe operations."
                }
            }
        
        # Execute the code against test cases
        execution_results = {}
        
        if challenge.language.lower() == "python":
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
            
            # Execute the code
            execution_results = CodeExecutor.execute_python_code(
                code=candidate_code,
                test_cases=test_cases,
                timeout=challenge.time_limit_mins * 60  # Convert minutes to seconds
            )
        elif challenge.language.lower() == "javascript":
            # JavaScript execution is a placeholder for now
            execution_results = CodeExecutor.execute_javascript_code(
                code=candidate_code,
                test_cases=[tc.dict() for tc in challenge.test_cases]
            )
        
        # Generate detailed feedback
        feedback = CodeFeedbackGenerator.generate_feedback(
            code=candidate_code,
            execution_results=execution_results,
            language=challenge.language,
            skill_level=skill_level
        )
        
        # Return detailed evaluation
        return {
            "status": "submitted",
            "challenge_id": challenge_id,
            "execution_results": execution_results,
            "feedback": feedback,
            "evaluation": {
                "passed": execution_results.get("all_passed", False),
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
        
        # Check if there are predefined hints available
        if challenge.hints:
            # Return a predefined hint
            hint_index = 0  # In a full implementation, this would track how many hints were already given
            return {
                "status": "success",
                "challenge_id": challenge_id,
                "hint": challenge.hints[hint_index % len(challenge.hints)]
            }
        
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
        
        # If still no hints, provide a generic hint
        if not hints:
            hints = [
                "Break down the problem step by step.",
                f"For this {challenge.difficulty} challenge, consider the edge cases carefully.",
                "Try working through a simple example manually to understand the solution process."
            ]
        
        return {
            "status": "success",
            "challenge_id": challenge_id,
            "hints": hints
        }
        
    except Exception as e:
        logger.error(f"Error generating hint: {e}")
        return {
            "status": "error",
            "message": str(e)
        } 