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
import os

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

# Constants for fallback challenge generation
FALLBACK_PROBLEM_STATEMENT = "Write a Python function to reverse a given string."

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
    logger.info(f"[generate_coding_challenge_from_jd] Called with difficulty: {difficulty_level}, skills: {skills_required}, job_description: {job_description[:100]}...")

    # Directly use fallback challenge as per user request
    logger.info("[generate_coding_challenge_from_jd] Using fallback challenge directly as per user request.")
    fallback_data = generate_fallback_challenge(skills_required, difficulty_level, "Fallback by user request")
    return {
        "status": "direct_fallback_user_request",
        "challenge": fallback_data,
        "message": fallback_data.get("message", "Using fallback challenge by direct user request.")
    }

    try:
        logger.info(f"Generating coding challenge for skills: {skills_required}")
        logger.info(f"Difficulty level: {difficulty_level}")
        
        llm_config = get_llm_config()
        
        # CRITICAL FIX: Get API key directly from environment since get_llm_config() doesn't include it
        google_api_key = os.environ.get("GOOGLE_API_KEY")
        if not google_api_key:
            logger.error("GOOGLE_API_KEY not found in environment variables")
            fallback_data = generate_fallback_challenge(skills_required, difficulty_level, "GOOGLE_API_KEY not found in environment")
            return {
                "status": "error_no_api_key_fallback",
                "challenge": fallback_data,
                "message": fallback_data.get("message")
            }
        
        model = ChatGoogleGenerativeAI(
            model=llm_config["model"],
            temperature=0.2,
            google_api_key=google_api_key  # CRITICAL FIX: Explicitly pass the API key
        )
        
        prompt_text = format_problem_generation_prompt(
            job_description=job_description,
            skills_required=skills_required,
            difficulty_level=difficulty_level
        )
        logger.debug(f"Formatted prompt for LLM: {prompt_text}")
        
        response_content = ""
        try:
            logger.info("Attempting to call the LLM for problem generation...")
            response = await asyncio.wait_for(
                model.ainvoke(prompt_text), 
                timeout=90.0
            )
            response_content = response.content
            logger.info(f"[generate_coding_challenge_from_jd] Raw LLM Response for challenge generation: {response_content[:500]}...") # LOG RAW LLM RESPONSE
            
            if response_content.strip().startswith("```json"):
                response_content = response_content.strip()[7:-3].strip()
            elif response_content.strip().startswith("```"):
                response_content = response_content.strip()[3:-3].strip()

        except asyncio.TimeoutError:
            logger.error("LLM call timed out after 90 seconds.")
            fallback_data = generate_fallback_challenge(skills_required, difficulty_level, "LLM call timed out.")
            return {
                "status": "error_timeout_fallback",
                "challenge": fallback_data,
                "message": fallback_data.get("message")
            }
        except Exception as e:
            logger.error(f"Error during LLM invocation: {e}", exc_info=True)
            fallback_data = generate_fallback_challenge(skills_required, difficulty_level, f"LLM invocation error: {e}")
            return {
                "status": "error_llm_invocation_fallback",
                "challenge": fallback_data,
                "message": fallback_data.get("message")
            }
        
        try:
            parsed_json_result = json.loads(response_content)
            logger.info(f"[generate_coding_challenge_from_jd] Successfully parsed LLM response. Problem statement: {parsed_json_result.get('problem_statement', 'N/A')[:100]}...") # LOG PARSED DATA
            
            challenge = CodingChallenge(**parsed_json_result)
            
            # Log reference solution before starter code generation
            ref_solution_for_log = challenge.reference_solution if challenge.reference_solution else ""
            logger.info(f"[generate_coding_challenge_from_jd] Reference solution received: \'{ref_solution_for_log[:200]}...\'")

            if challenge.reference_solution:
                challenge.starter_code = _generate_starter_code(challenge.reference_solution).strip()
            else:
                challenge.starter_code = "# TODO: Write your Python solution here\\n".strip()
            logger.info(f"[generate_coding_challenge_from_jd] Generated starter_code: \'{challenge.starter_code[:200]}...\'") # LOG GENERATED STARTER CODE
            
            result_dict = challenge.model_dump() # Use .model_dump() for Pydantic v2+
            
            result_dict["difficulty_level"] = difficulty_level
            result_dict["skills_targeted"] = skills_required
            
            challenge_id = f"gen_{uuid.uuid4().hex[:8]}"
            result_dict["challenge_id"] = challenge_id
            result_dict["id"] = challenge_id
            
            if "language" not in result_dict:
                result_dict["language"] = "python"
                
            if "title" not in result_dict:
                first_line = result_dict["problem_statement"].strip().split("\\n")[0]
                result_dict["title"] = first_line[:50] + ("..." if len(first_line) > 50 else "")
                
            result_dict["status"] = "success"
            result_dict["visible_test_cases"] = _prepare_visible_test_cases(result_dict["test_cases"])
            result_dict["evaluation_criteria"] = {
                "correctness": "Code produces correct output for all test cases",
                "efficiency": "Code uses efficient algorithms and data structures",
                "code_quality": "Code follows best practices and style guidelines",
                "documentation": "Code is well-documented with comments and docstrings"
            }
            
            # Ensure optional fields are present
            result_dict.setdefault("tags", [])
            result_dict.setdefault("hints", [])

            logger.info(f"[generate_coding_challenge_from_jd] Final challenge_data before returning (starter_code snippet): \'{result_dict.get('starter_code', 'N/A')[:200]}...\'")

            return {
                "status": "success",
                "challenge": result_dict # Return the dictionary representation
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing LLM response as JSON: {e}")
            logger.error(f"Raw response content that failed parsing: {response_content}")
            fallback_data = generate_fallback_challenge(skills_required, difficulty_level, f"JSON parsing error: {e}. Response: {response_content[:200]}")
            return {
                "status": "error_json_parsing_fallback",
                "challenge": fallback_data,
                "message": fallback_data.get("message")
            }
        except Exception as e_pydantic: # Catch Pydantic validation errors or other issues
            logger.error(f"Error creating CodingChallenge model or processing data: {e_pydantic}", exc_info=True)
            fallback_data = generate_fallback_challenge(skills_required, difficulty_level, f"Data validation or processing error: {e_pydantic}")
            return {
                "status": "error_validation_fallback",
                "challenge": fallback_data,
                "message": fallback_data.get("message")
            }
            
    except Exception as e:
        logger.error(f"Outer error generating coding challenge: {e}", exc_info=True)
        fallback_data = generate_fallback_challenge(skills_required, difficulty_level, f"Outer error: {e}")
        return {
            "status": "error_outer_fallback",
            "challenge": fallback_data,
            "message": fallback_data.get("message")
        }

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
        logger.error(f"Error processing code submission for generated challenge: {e}")
        import traceback
        logger.error(traceback.format_exc()) # Ensure full traceback is logged
        return {
            "status": "error",
            "challenge_id": challenge_id,
            "message": str(e)
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
        challenge_id = challenge_data.get("challenge_id", challenge_data.get("id", "unknown"))
        logger.info(f"Generating hint for generated challenge: {challenge_id}")

        # Prepare challenge_info for HintGenerator
        challenge_info_for_generator = {
            "id": challenge_id,
            "title": challenge_data.get("title", ""),
            "description": challenge_data.get("problem_statement", ""),
            "difficulty": challenge_data.get("difficulty_level", "intermediate"),
            "language": challenge_data.get("language", "python"),
            "hints": challenge_data.get("hints", []),
            "tags": challenge_data.get("tags", [])
            # Add other fields if HintGenerator uses them, e.g. reference_solution if needed by a specific hint strategy
        }

        # Use the more sophisticated HintGenerator
        # skill_level can be passed if available, defaulting to intermediate for now
        hints_list = HintGenerator.generate_hints(
            code=current_code,
            challenge_info=challenge_info_for_generator,
            error_message=error_message,
            skill_level="intermediate" 
        )
        
        logger.info(f"Successfully generated {len(hints_list)} hints using HintGenerator for challenge {challenge_id}.")
        
        return {
            "status": "success",
            "challenge_id": challenge_id,
            "hints": hints_list if hints_list else ["Sorry, I could not generate a specific hint right now. Try to break down the problem into smaller steps."],
            "related_concepts": challenge_data.get("tags", []) # Include relevant concepts/tags
        }
    except Exception as e:
        logger.error(f"Error generating hint for generated challenge: {e}", exc_info=True)
        return {
            "status": "error", 
            "challenge_id": challenge_id,
            "message": f"Could not generate hint: {e}"
        }

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
            TestCase(input="hello", expected_output="olleh", is_hidden=False, explanation="Simple case"),
            TestCase(input="Python", expected_output="nohtyP", is_hidden=False, explanation="Case with capitals"),
            TestCase(input="", expected_output="", is_hidden=False, explanation="Empty string")
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
    # Convert TestCase objects in test_cases to simple dicts for JSON serializability
    fallback_data["test_cases"] = [tc.model_dump() for tc in fallback_data["test_cases"]]
    
    return fallback_data

def _generate_starter_code(reference_solution: str) -> str:
    """
    Generate starter code from a Python reference solution.
    Attempts to remove comments, docstrings, and function bodies,
    replacing them with 'pass' and a TODO comment.
    Keeps import statements and class definitions if possible.

    Args:
        reference_solution: The reference solution in Python.

    Returns:
        Starter code template.
    """
    logger.info(f"[generate_starter_code] Input reference_solution (first 300 chars): '{reference_solution[:300]}...'")

    # 1. Remove multiline docstrings (greedy match)
    # This handles both """...""" and '''...'''
    code = re.sub(r'"""[\s\S]*?"""', '', reference_solution, flags=re.MULTILINE)
    code = re.sub(r"'''[\s\S]*?'''", '', code, flags=re.MULTILINE)

    # 2. Process line by line
    lines = code.split('\n')
    processed_lines = []
    in_function_body = False
    function_indent = 0

    for line in lines:
        stripped_line = line.strip()

        # Remove single-line comments
        if '#' in stripped_line:
            stripped_line = stripped_line.split('#', 1)[0].rstrip()
            line = line[:len(line) - len(line.lstrip())] + stripped_line # Preserve original indent

        if not stripped_line: # Keep empty lines outside function bodies for readability
            if not in_function_body:
                processed_lines.append("")
            continue

        current_indent = len(line) - len(line.lstrip())

        if in_function_body:
            if current_indent <= function_indent:
                # Exited the function body
                in_function_body = False
                # Fall-through to process this line normally
            else:
                # Still in function body, skip the line
                continue
        
        # Detect function definitions
        func_match = re.match(r'^(\s*)def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\((.*?)\)\s*:', line)
        if func_match:
            indent_str = func_match.group(1)
            func_signature = line # Keep the full signature line
            processed_lines.append(func_signature)
            processed_lines.append(f"{indent_str}    pass")
            processed_lines.append(f"{indent_str}    # TODO: Implement this function")
            in_function_body = True
            function_indent = current_indent
            continue

        # Detect class definitions (keep them and their content for now, can be refined)
        class_match = re.match(r'^(\s*)class\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(?(.*?)\)?\s*:', line)
        if class_match:
            # If we were in a function (e.g. nested class, though less common for starter), stop.
            in_function_body = False 
            processed_lines.append(line)
            # Future: could try to process methods within classes similarly
            continue
        
        # Keep import statements and other top-level code
        if not in_function_body: # Ensure we are not accidentally grabbing lines from a function body
            processed_lines.append(line)

    final_starter_code = "\n".join(processed_lines).strip()
    
    # If the result is empty or just whitespace (e.g. solution was only comments), provide a default
    if not final_starter_code.strip():
        final_starter_code = "# TODO: Write your Python solution here"

    logger.info(f"[generate_starter_code] Final starter code (first 300 chars): '{final_starter_code[:300]}...'")
    return final_starter_code

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