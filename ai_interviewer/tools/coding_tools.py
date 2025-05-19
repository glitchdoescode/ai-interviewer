"""
Coding challenge tools for the {SYSTEM_NAME} platform.

This module implements tools for starting, interacting with, and evaluating coding challenges.
"""
import logging
from typing import Dict, List, Optional, Any, Callable
import uuid

from langchain_core.tools import tool
from ai_interviewer.models.coding_challenge import get_coding_challenge, CodingChallenge
from ai_interviewer.tools.code_quality import CodeQualityMetrics
from ai_interviewer.tools.code_execution import CodeExecutor, SafetyChecker, execute_candidate_code
from ai_interviewer.tools.code_feedback import CodeFeedbackGenerator
from ai_interviewer.tools.pair_programming import HintGenerator
from ai_interviewer.utils.config import SYSTEM_NAME

# Configure logging
logger = logging.getLogger(__name__)


@tool
async def start_coding_challenge(challenge_id: Optional[str] = None, difficulty: Optional[str] = None, 
                           topic: Optional[str] = None, stream_callback: Optional[Callable] = None) -> Dict[str, Any]:
    """
    Start a coding challenge with streaming progress updates.
    
    Args:
        challenge_id: Optional specific challenge ID
        difficulty: Optional difficulty level
        topic: Optional topic area
        stream_callback: Optional callback for streaming updates
        
    Returns:
        Challenge details and initial setup
    """
    try:
        # Emit starting event
        if stream_callback:
            await stream_callback({
                "type": "challenge_starting",
                "challenge_id": challenge_id
            })
            
        # Load challenge database
        if stream_callback:
            await stream_callback({
                "type": "loading_challenges",
                "message": "Loading challenge database..."
            })
            
        challenges = load_coding_challenges()
        
        # Select appropriate challenge
        if stream_callback:
            await stream_callback({
                "type": "selecting_challenge",
                "message": "Selecting appropriate challenge..."
            })
            
        challenge = select_challenge(challenges, challenge_id, difficulty, topic)
        
        # Prepare test environment
        if stream_callback:
            await stream_callback({
                "type": "preparing_environment",
                "message": "Setting up test environment..."
            })
            
        test_env = prepare_test_environment(challenge)
        
        # Emit completion event
        if stream_callback:
            await stream_callback({
                "type": "challenge_ready",
                "challenge_id": challenge["id"],
                "title": challenge["title"]
            })
            
        return {
            "challenge_id": challenge["id"],
            "title": challenge["title"],
            "description": challenge["description"],
            "initial_code": challenge.get("initial_code", ""),
            "test_cases": challenge.get("test_cases", []),
            "hints": challenge.get("hints", []),
            "difficulty": challenge.get("difficulty", "medium"),
            "time_limit": challenge.get("time_limit", 30),  # minutes
            "test_env": test_env
        }
    except Exception as e:
        logger.error(f"Error starting coding challenge: {e}")
        if stream_callback:
            await stream_callback({
                "type": "challenge_error",
                "error": str(e)
            })
        raise


@tool
async def submit_code_for_challenge(code: str, challenge_id: str, stream_callback: Optional[Callable] = None) -> Dict[str, Any]:
    """
    Submit and evaluate code for a challenge with streaming progress.
    
    Args:
        code: The submitted code
        challenge_id: Challenge identifier
        stream_callback: Optional callback for streaming updates
        
    Returns:
        Evaluation results
    """
    try:
        # Emit starting event
        if stream_callback:
            await stream_callback({
                "type": "evaluation_starting",
                "challenge_id": challenge_id
            })
            
        # Load challenge
        if stream_callback:
            await stream_callback({
                "type": "loading_challenge",
                "message": "Loading challenge details..."
            })
            
        challenge = get_challenge_by_id(challenge_id)
        
        # Syntax check
        if stream_callback:
            await stream_callback({
                "type": "syntax_check",
                "message": "Checking code syntax..."
            })
            
        syntax_result = check_syntax(code)
        if not syntax_result["valid"]:
            if stream_callback:
                await stream_callback({
                    "type": "syntax_error",
                    "errors": syntax_result["errors"]
                })
            return {
                "status": "syntax_error",
                "errors": syntax_result["errors"]
            }
            
        # Run tests
        if stream_callback:
            await stream_callback({
                "type": "running_tests",
                "message": "Running test cases..."
            })
            
        test_results = run_tests(code, challenge["test_cases"])
        
        # Code quality analysis
        if stream_callback:
            await stream_callback({
                "type": "analyzing_quality",
                "message": "Analyzing code quality..."
            })
            
        quality_metrics = analyze_code_quality(code)
        
        # Prepare feedback
        if stream_callback:
            await stream_callback({
                "type": "generating_feedback",
                "message": "Generating detailed feedback..."
            })
            
        feedback = generate_feedback(test_results, quality_metrics)
        
        # Emit completion event
        if stream_callback:
            await stream_callback({
                "type": "evaluation_complete",
                "challenge_id": challenge_id,
                "passed": test_results["passed"],
                "total": test_results["total"]
            })
            
        return {
            "status": "complete",
            "challenge_id": challenge_id,
            "test_results": test_results,
            "quality_metrics": quality_metrics,
            "feedback": feedback
        }
    except Exception as e:
        logger.error(f"Error evaluating code submission: {e}")
        if stream_callback:
            await stream_callback({
                "type": "evaluation_error",
                "error": str(e)
            })
        raise


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