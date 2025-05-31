"""
Problem generation tool for the AI Interviewer platform.

This module implements a tool for generating coding challenges based on job descriptions
and required skills. It implements the requirements from Task P2.5.1 in the project checklist.
"""
import json
import logging
import uuid
from typing import Dict, List, Any, Optional
import re
import asyncio

from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field
from ai_interviewer.utils.config import get_llm_config
from ai_interviewer.prompts.problem_generation_prompts import format_problem_generation_prompt

# Import needed for code evaluation and feedback
from ai_interviewer.tools.code_execution import execute_candidate_code
from ai_interviewer.tools.code_quality import CodeQualityMetrics
from ai_interviewer.tools.code_feedback import CodeFeedbackGenerator
from ai_interviewer.tools.pair_programming import HintGenerator

# Configure logging
logger = logging.getLogger(__name__)

class TestCase(BaseModel):
    """Model for a single test case."""
    input: Any = Field(..., description="Input for the test case")
    expected_output: Any = Field(..., description="Expected output for the test case")
    is_hidden: bool = False  # Added field for compatibility with coding_tools
    explanation: Optional[str] = None  # Added field for compatibility with coding_tools

class CodingChallenge(BaseModel):
    """Model for a complete coding challenge."""
    problem_statement: str = Field(..., description="Clear description of the coding problem")
    test_cases: List[TestCase] = Field(..., min_items=3, description="List of test cases with inputs and expected outputs")
    reference_solution: str = Field(..., description="Reference solution in Python")
    
    # Added fields for compatibility with coding_tools.py
    language: str = "python"  # Default to Python
    starter_code: str = ""  # Will be populated based on reference solution
    tags: List[str] = []
    hints: List[str] = []

@tool
async def generate_coding_challenge_from_jd(
    job_description: str,
    skills_required: List[str],
    difficulty_level: str = "intermediate"
) -> Dict[str, Any]:
    """
    Generate a coding challenge based on a job description and required skills.
    
    Args:
        job_description: Description of the job position
        skills_required: List of required technical skills
        difficulty_level: Desired difficulty level ("beginner", "intermediate", "advanced")
        
    Returns:
        Dictionary containing the generated coding challenge with problem statement,
        test cases, and reference solution.
    """
    try:
        logger.info(f"Generating coding challenge for skills: {skills_required}")
        logger.info(f"Difficulty level: {difficulty_level}")
        
        # Initialize LLM with appropriate temperature for consistent problem generation
        llm_config = get_llm_config()
        model = ChatGoogleGenerativeAI(
            model=llm_config["model"],
            temperature=0.2  # Lower temperature for more consistent output
        )
        
        # Get formatted prompt from template
        prompt_text = format_problem_generation_prompt(
            job_description=job_description,
            skills_required=skills_required,
            difficulty_level=difficulty_level
        )
        logger.debug(f"Formatted prompt for LLM: {prompt_text}")
        
        # Call the LLM
        try:
            logger.info("Attempting to call the LLM for problem generation...")
            response = await asyncio.wait_for(
                model.ainvoke(prompt_text), 
                timeout=90.0  # Add a 90-second timeout
            )
            response_content = response.content
            logger.info("Successfully received response from LLM.")
            # logger.debug(f"Raw LLM response content: {response_content}")

            # Strip markdown fences if present
            if response_content.strip().startswith("```json"):
                # Handles ```json ... ```
                response_content = response_content.strip()[7:-3].strip()
            elif response_content.strip().startswith("```"):
                # Handles ``` ... ```
                response_content = response_content.strip()[3:-3].strip()
            
            # Pre-process the response_content to fix common LLM JSON errors
            # (Existing pre-processing code, if any, would be here)
            # Based on current file, there isn't any complex re.sub here anymore.

        except asyncio.TimeoutError:
            logger.error("LLM call timed out after 90 seconds.")
            return generate_fallback_challenge(skills_required, difficulty_level, "LLM call timed out.")
        except Exception as e:
            logger.error(f"Error during LLM invocation: {e}", exc_info=True)
            return generate_fallback_challenge(skills_required, difficulty_level, f"LLM invocation error: {e}")
        
        # Parse and validate the response
        try:
            result = json.loads(response_content)
            
            # Validate with Pydantic model
            challenge = CodingChallenge(**result)
            
            # Add metadata
            result["difficulty_level"] = difficulty_level
            result["skills_targeted"] = skills_required
            
            # Generate a unique challenge ID
            challenge_id = f"gen_{uuid.uuid4().hex[:8]}"
            result["challenge_id"] = challenge_id
            result["id"] = challenge_id  # For compatibility
            
            # Generate starter code from the reference solution
            if challenge.reference_solution:
                challenge.starter_code = _generate_starter_code(challenge.reference_solution).strip()
            else:
                challenge.starter_code = "# TODO: Write your Python solution here\n".strip()
            
            # Add language, defaults to Python
            if "language" not in result:
                result["language"] = "python"
                
            # Add title if not present
            if "title" not in result:
                # Extract a title from the problem statement
                first_line = result["problem_statement"].strip().split("\n")[0]
                result["title"] = first_line[:50] + ("..." if len(first_line) > 50 else "")
                
            # Add success status for compatibility with frontend expectations
            result["status"] = "success"
            
            # Make test cases compatible with the coding_tools format
            result["visible_test_cases"] = _prepare_visible_test_cases(result["test_cases"])
            
            # Add evaluation criteria for frontend
            result["evaluation_criteria"] = {
                "correctness": "Code produces correct output for all test cases",
                "efficiency": "Code uses efficient algorithms and data structures",
                "code_quality": "Code follows best practices and style guidelines",
                "documentation": "Code is well-documented with comments and docstrings"
            }
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing LLM response as JSON: {e}")
            logger.error(f"Raw response: {response_content}")
            raise
            
    except Exception as e:
        logger.error(f"Outer error generating coding challenge: {e}", exc_info=True)
        return generate_fallback_challenge(skills_required, difficulty_level, f"Outer error: {e}")

@tool
async def submit_code_for_generated_challenge(challenge_data: Dict[str, Any], candidate_code: str, skill_level: str = "intermediate") -> Dict:
    """
    Submit a candidate's code solution for a generated coding challenge.
    
    Args:
        challenge_data: The generated challenge data from generate_coding_challenge_from_jd
        candidate_code: The code solution provided by the candidate
        skill_level: Skill level of the candidate (beginner, intermediate, advanced)
        
    Returns:
        A dictionary containing the detailed evaluation results
    """
    try:
        challenge_id = challenge_data.get("challenge_id", challenge_data.get("id", "unknown"))
        logger.info(f"Received code submission for generated challenge: {challenge_id}")
        logger.info(f"Challenge data structure: {list(challenge_data.keys())}")
        
        # Basic validation - check for empty submission
        code_without_comments = "\n".join(
            line for line in candidate_code.split("\n") 
            if not line.strip().startswith("#")
        )
        
        if not code_without_comments.strip():
            logger.warning(f"Empty code submission received for challenge {challenge_id}")
            return {
                "status": "submitted",
                "challenge_id": challenge_id,
                "evaluation": {
                    "passed": False,
                    "message": "Your submission appears to be empty or contains only comments."
                }
            }
        
        # Convert test cases to the format expected by execute_candidate_code
        test_cases = []
        logger.info(f"Number of test cases found: {len(challenge_data.get('test_cases', []))}")
        
        for tc in challenge_data.get("test_cases", []):
            # Handle both our model format and the format from the LLM
            input_val = tc.get("input") if isinstance(tc, dict) else tc.input
            expected_val = tc.get("expected_output") if isinstance(tc, dict) else tc.expected_output
            explanation = tc.get("explanation", "") if isinstance(tc, dict) else getattr(tc, "explanation", "")
            is_hidden = tc.get("is_hidden", False) if isinstance(tc, dict) else getattr(tc, "is_hidden", False)
            
            test_cases.append({
                "input": input_val,
                "expected_output": expected_val,
                "explanation": explanation,
                "is_hidden": is_hidden
            })
            
        logger.info(f"Processed {len(test_cases)} test cases for execution")
        
        # Execute the code using our secure executor
        language = challenge_data.get("language", "python").lower()
        logger.info(f"Executing candidate code in language: {language}")
        
        # Prepare arguments for the tool
        tool_input_args = {
            "language": language,
            "code": candidate_code,
            "test_cases": test_cases
        }
        # Call the tool with a single dictionary argument
        execution_results = await execute_candidate_code.ainvoke(tool_input_args)
        
        # MODIFIED: Log full execution_results if status is error
        if execution_results.get('status') == 'error':
            logger.error(f"Full execution_results on error: {execution_results}")
        else:
            logger.info(f"Execution results: {execution_results.get('status')}, passed {execution_results.get('pass_count', 0)}/{execution_results.get('total_tests', 0)} tests")
        
        # MODIFIED: Log candidate_code before feedback generation
        logger.info(f"Candidate code before feedback generation:\n{candidate_code}")
        
        # Generate detailed feedback
        feedback = CodeFeedbackGenerator.generate_feedback(
            code=candidate_code,
            execution_results=execution_results.get("detailed_results", execution_results),
            language=language,
            skill_level=skill_level
        )
        
        # Return detailed evaluation
        return {
            "status": "submitted",
            "challenge_id": challenge_id,
            "execution_results": execution_results,
            "feedback": feedback,
            "evaluation": {
                "passed": execution_results.get("status") == "success" and 
                         execution_results.get("pass_count", 0) == execution_results.get("total_tests", 0),
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
        traceback_str = traceback.format_exc()
        logger.error(f"Detailed traceback: {traceback_str}")
        return {
            "status": "error",
            "message": str(e),
            "traceback": traceback_str
        }

@tool
async def get_hint_for_generated_challenge(challenge_data: Dict[str, Any], current_code: str, error_message: Optional[str] = None) -> Dict:
    """
    Provide a hint for a given coding challenge, candidate's code, and error message.
    Args:
        challenge_data: The challenge data from problem generation.
        current_code: The candidate's current attempt at solving the problem.
        error_message: Optional error message from a previous execution attempt.
    Returns:
        A dictionary containing the generated hint.
    """
    try:
        problem_statement = challenge_data.get("problem_statement", "")
        reference_solution = challenge_data.get("reference_solution", "")
        
        if not problem_statement or not reference_solution:
            logger.warning("Missing problem statement or reference solution for hint generation.")
            return {"status": "error", "message": "Challenge data is incomplete for hint generation."}

        llm_config = get_llm_config()
        model = ChatGoogleGenerativeAI(model=llm_config["model"], temperature=0.3) # Slightly higher temp for creative hints

        prompt = format_hint_generation_prompt(
            problem_statement=problem_statement,
            current_code=current_code,
            reference_solution=reference_solution,
            error_message=error_message
        )
        logger.info("Attempting to call LLM for hint generation...")
        
        response = await asyncio.wait_for(
            model.ainvoke(prompt),
            timeout=30.0 # 30 second timeout for hint generation
        )
        
        hints_text = response.content
        logger.info("Successfully received hint response from LLM.")
        
        # Parse numbered hints
        hints_list = [h.strip() for h in re.findall(r'\\d+\\.\\s*(.*)', hints_text)]
        
        if not hints_list and hints_text: # Fallback if regex doesn't match but we have content
            hints_list = [hints_text.strip()]

        return {
            "status": "success",
            "hints": hints_list if hints_list else ["Sorry, I could not generate a specific hint right now. Try to break down the problem into smaller steps."],
        }
    except asyncio.TimeoutError:
        logger.error("Hint generation LLM call timed out.")
        return {"status": "error", "message": "Hint generation timed out."}
    except Exception as e:
        logger.error(f"Error generating hint: {e}", exc_info=True)
        return {"status": "error", "message": f"Could not generate hint: {e}"}

def generate_fallback_challenge(skills_required: List[str], difficulty_level: str, error_info: Optional[str] = None) -> Dict[str, Any]:
    """
    Generates a static fallback coding challenge if the LLM fails.
    """
    logger.warning(f"Generating fallback challenge. Reason: {error_info if error_info else 'Unknown LLM failure.'}")
    # Simplified fallback based on first skill or generic
    primary_skill = skills_required[0] if skills_required else "general"
    challenge_id = f"fallback_{uuid.uuid4().hex[:8]}"

    fallback_data = {
        "problem_statement": f"This is a fallback coding challenge for {primary_skill} at {difficulty_level} level. Implement a function that reverses a string.",
        "test_cases": [
            {"input": "hello", "expected_output": "olleh", "is_hidden": False, "explanation": "Simple case"},
            {"input": "Python", "expected_output": "nohtyP", "is_hidden": False, "explanation": "Case with capitals"},
            {"input": "", "expected_output": "", "is_hidden": False, "explanation": "Empty string"}
        ],
        "reference_solution": "def reverse_string(s):\\n    return s[::-1]",
        "language": "python",
        "starter_code": "def reverse_string(s):\\n    # Your code here\\n    pass",
        "title": f"Fallback: Reverse String ({difficulty_level})",
        "challenge_id": challenge_id,
        "id": challenge_id, # For compatibility
        "difficulty_level": difficulty_level,
        "skills_targeted": skills_required,
        "status": "fallback_success", # Indicate this is a fallback
        "message": f"A fallback challenge was generated due to an issue. {error_info if error_info else ''}".strip(),
        "visible_test_cases": [
            {"input": "hello", "expected_output": "olleh", "explanation": "Simple case"},
            {"input": "Python", "expected_output": "nohtyP", "explanation": "Case with capitals"},
            {"input": "", "expected_output": "", "explanation": "Empty string"}
        ],
        "evaluation_criteria": {
            "correctness": "Code produces correct output for all test cases",
        }
    }
    # Make test cases compatible with Pydantic model if needed for other parts of system
    validated_test_cases = []
    for tc_data in fallback_data["test_cases"]:
        # Ensure all required fields for TestCase model are present, even if with defaults
        tc_data.setdefault("is_hidden", False) 
        tc_data.setdefault("explanation", "")
        validated_test_cases.append(TestCase(**tc_data)) # Validate against TestCase model
    fallback_data["test_cases"] = validated_test_cases
    
    return fallback_data

def _generate_starter_code(reference_solution: str) -> str:
    """
    Generate starter code from a reference solution.
    
    Args:
        reference_solution: The reference solution
        
    Returns:
        Starter code template
    """
    # Extract function signature
    lines = reference_solution.strip().split('\n')
    if not lines:
        return "# Please implement your solution here"
    
    # Get function definition line
    func_def = lines[0]
    
    # Create starter code with function signature and placeholders
    starter_code = [func_def]
    starter_code.append("    # Write your code here")
    starter_code.append("    pass")
    starter_code.append("")
    
    # Add example usage comments
    if "def " in func_def:
        # Extract function name
        func_name = func_def.split("def ")[1].split("(")[0].strip()
        starter_code.append("# Example usage:")
        
        # Get test cases from function parameters
        params = func_def.split("(")[1].split(")")[0].strip()
        if params:
            starter_code.append(f"# print({func_name}(...))  # Add test cases here")
        else:
            starter_code.append(f"# print({func_name}())  # Add test cases here")
    
    return "\n".join(starter_code)

def _prepare_visible_test_cases(test_cases: List[Dict]) -> List[Dict]:
    """
    Prepare visible test cases for the frontend.
    
    Args:
        test_cases: Original test cases
        
    Returns:
        Test cases formatted for frontend display
    """
    visible_test_cases = []
    for tc in test_cases:
        # Handle both dictionary and object formats
        if isinstance(tc, dict):
            if not tc.get("is_hidden", False):
                visible_test_cases.append({
                    "input": tc.get("input"),
                    "expected_output": tc.get("expected_output"),
                    "explanation": tc.get("explanation", "")
                })
        else:
            if not getattr(tc, "is_hidden", False):
                visible_test_cases.append({
                    "input": tc.input,
                    "expected_output": tc.expected_output,
                    "explanation": getattr(tc, "explanation", "")
                })
    
    return visible_test_cases 