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
def generate_coding_challenge_from_jd(
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
        prompt = format_problem_generation_prompt(
            job_description=job_description,
            skills_required=skills_required,
            difficulty_level=difficulty_level
        )
        
        # Call the LLM
        response = model.invoke(prompt)
        response_content = response.content
        
        # Extract JSON from the response
        json_match = re.search(r'```json\s*(.*?)\s*```', response_content, re.DOTALL)
        if json_match:
            response_content = json_match.group(1)
        else:
            # Try to find JSON object without markdown
            json_match = re.search(r'(\{.*\})', response_content, re.DOTALL)
            if json_match:
                response_content = json_match.group(1)
        
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
            
            # Create suitable starter code from the reference solution
            if "starter_code" not in result:
                result["starter_code"] = _generate_starter_code(result["reference_solution"])
            
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
        return generate_fallback_challenge(skills_required, difficulty_level)

@tool
def submit_code_for_generated_challenge(challenge_data: Dict[str, Any], candidate_code: str, skill_level: str = "intermediate") -> Dict:
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
        execution_results = execute_candidate_code(
            language=language,
            code=candidate_code,
            test_cases=test_cases
        )
        
        logger.info(f"Execution results: {execution_results.get('status')}, passed {execution_results.get('pass_count', 0)}/{execution_results.get('total_tests', 0)} tests")
        
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
def get_hint_for_generated_challenge(challenge_data: Dict[str, Any], current_code: str, error_message: Optional[str] = None) -> Dict:
    """
    Get a context-aware hint for a dynamically generated coding challenge.
    
    Args:
        challenge_data: The generated challenge data
        current_code: Current code implementation
        error_message: Optional error message to get specific help
        
    Returns:
        A dictionary containing targeted hints
    """
    try:
        challenge_id = challenge_data.get("challenge_id", challenge_data.get("id", "unknown"))
        logger.info(f"Generating hint for challenge: {challenge_id}")
        logger.info(f"Challenge data keys available: {list(challenge_data.keys())}")
        
        # Extract problem statement and reference solution
        problem_statement = challenge_data.get("problem_statement", "")
        reference_solution = challenge_data.get("reference_solution", "")
        
        logger.info(f"Problem statement length: {len(problem_statement)}")
        logger.info(f"Reference solution available: {bool(reference_solution)}")
        
        # Create challenge info dictionary
        challenge_info = {
            "id": challenge_id,
            "title": challenge_data.get("title", "Coding Challenge"),
            "description": problem_statement,
            "difficulty": challenge_data.get("difficulty_level", "intermediate"),
            "language": challenge_data.get("language", "python"),
            "reference_solution": reference_solution,
            "hints": challenge_data.get("hints", []),
            "tags": challenge_data.get("skills_targeted", [])
        }
        
        # Use the HintGenerator to get context-aware hints
        logger.info(f"Generating hints using HintGenerator")
        hints = HintGenerator.generate_hints(
            code=current_code,
            challenge_info=challenge_info,
            reference_solution=reference_solution,
            error_message=error_message,
            skill_level="intermediate"  # This could be passed as a parameter in the future
        )
        
        # If we couldn't generate any hints, generate some based on the problem
        if not hints:
            logger.info(f"No hints generated by HintGenerator, falling back to problem-based hints")
            hints = _generate_hints_from_problem(problem_statement, reference_solution, current_code)
            
        # If we still have no hints, provide generic ones
        if not hints:
            logger.warning(f"Failed to generate specific hints, using generic hints")
            hints = [
                "Try breaking the problem down into smaller steps.",
                "Review the test cases carefully to understand all requirements.",
                "Consider edge cases in your solution."
            ]
        
        logger.info(f"Successfully generated {len(hints)} hints")
        
        # Return the hints
        return {
            "status": "success",
            "challenge_id": challenge_id,
            "hints": hints,
            "related_concepts": challenge_data.get("skills_targeted", [])
        }
        
    except Exception as e:
        logger.error(f"Error generating coding hint: {e}")
        import traceback
        traceback_str = traceback.format_exc()
        logger.error(f"Detailed traceback: {traceback_str}")
        return {
            "status": "error",
            "message": f"Could not generate hint: {str(e)}",
            "traceback": traceback_str,
            "fallback_hints": [
                "Review your algorithm logic step by step.",
                "Check for edge cases in your solution.",
                "Make sure your code handles all the test case scenarios."
            ]
        }

def generate_fallback_challenge(skills_required: List[str], difficulty_level: str) -> Dict[str, Any]:
    """Generate a fallback coding challenge when the LLM fails."""
    challenge_id = f"fallback_{uuid.uuid4().hex[:8]}"
    return {
        "status": "success",
        "challenge_id": challenge_id,
        "id": challenge_id,
        "title": "Find Most Frequent Element",
        "problem_statement": "Write a function that finds the most frequent element in a list.",
        "test_cases": [
            {"input": [1, 2, 2, 3, 3, 3], "expected_output": 3, "is_hidden": False, "explanation": "Basic test case"},
            {"input": ["a", "b", "a"], "expected_output": "a", "is_hidden": False, "explanation": "String test case"},
            {"input": [], "expected_output": None, "is_hidden": False, "explanation": "Empty list test case"}
        ],
        "visible_test_cases": [
            {"input": [1, 2, 2, 3, 3, 3], "expected_output": 3, "explanation": "Basic test case"},
            {"input": ["a", "b", "a"], "expected_output": "a", "explanation": "String test case"},
            {"input": [], "expected_output": None, "explanation": "Empty list test case"}
        ],
        "reference_solution": """def find_most_frequent(lst):
    if not lst:
        return None
    return max(set(lst), key=lst.count)""",
        "starter_code": """def find_most_frequent(lst):
    # Write your code here
    pass

# Example usage:
# print(find_most_frequent([1, 2, 2, 3, 3, 3]))  # Should print: 3
# print(find_most_frequent(["a", "b", "a"]))     # Should print: "a"
# print(find_most_frequent([]))                  # Should print: None
""",
        "language": "python",
        "difficulty_level": difficulty_level,
        "skills_targeted": skills_required,
        "generated_from_fallback": True,
        "evaluation_criteria": {
            "correctness": "Code produces correct output for all test cases",
            "efficiency": "Code uses efficient algorithms and data structures",
            "code_quality": "Code follows best practices and style guidelines",
            "documentation": "Code is well-documented with comments and docstrings"
        }
    }

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

def _generate_hints_from_problem(problem_statement: str, reference_solution: str, current_code: str) -> List[str]:
    """
    Generate hints based on the problem statement and reference solution when other hint generation fails.
    
    Args:
        problem_statement: Problem description
        reference_solution: Reference solution code
        current_code: Current user code
        
    Returns:
        List of generated hints
    """
    try:
        # Initialize LLM with appropriate temperature
        llm_config = get_llm_config()
        model = ChatGoogleGenerativeAI(
            model=llm_config["model"],
            temperature=0.3
        )
        
        # Create prompt for hint generation
        prompt = f"""As an interview coach, I need to provide helpful hints for a coding challenge.

PROBLEM:
{problem_statement}

CANDIDATE'S CURRENT CODE:
```python
{current_code}
```

REFERENCE SOLUTION (Do not reveal this directly):
```python
{reference_solution}
```

Generate 3 progressive hints that guide the candidate toward the solution without giving it away. 
Start with a conceptual hint, then a more specific hint, and finally a targeted hint that addresses 
a key part of the algorithm.

Return only the hints, numbered 1-3."""
        
        # Generate hints
        response = model.invoke(prompt)
        hint_text = response.content
        
        # Parse hints
        hints = []
        for line in hint_text.strip().split('\n'):
            line = line.strip()
            if line and (line.startswith('- ') or line.startswith('* ') or 
                         line.startswith('1. ') or line.startswith('2. ') or 
                         line.startswith('3. ') or line.startswith('Hint ') or
                         line[0].isdigit() and line[1] == '.'):
                # Remove hint number/prefix
                hint = re.sub(r'^[*\-\d\.]+\s*|^Hint\s+\d+:\s*', '', line).strip()
                if hint:
                    hints.append(hint)
        
        # If no structured hints found, just use the whole response
        if not hints and hint_text.strip():
            # Split by newline and filter empty lines
            hints = [line.strip() for line in hint_text.strip().split('\n') if line.strip()]
            # Take up to 3 hints
            hints = hints[:3]
        
        return hints
    except Exception as e:
        logger.error(f"Error generating hints from problem: {e}")
        return [] 