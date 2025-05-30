"""
Prompt templates for generating coding challenges.

This module contains the prompt templates used by the problem generation tool
to create coding challenges based on job descriptions and required skills.
"""
from typing import List, Dict, Any, Optional

from langchain_core.prompts import PromptTemplate

# Template for generating coding challenges
PROBLEM_GENERATION_TEMPLATE = PromptTemplate(
    input_variables=["job_description", "skills_required", "difficulty_level"],
    template="""You are an expert at creating coding challenges for technical interviews.

Your task is to generate ONE coding challenge that effectively evaluates a candidate's technical skills for the following position:

JOB DESCRIPTION:
{job_description}

REQUIRED SKILLS:
{skills_required}

DIFFICULTY LEVEL: {difficulty_level}

The coding challenge should:
1. Be relevant to the job description and required skills
2. Be solvable within 20-30 minutes
3. Test algorithmic thinking and code quality
4. Have clear requirements and constraints
5. Include diverse test cases (normal cases, edge cases, error cases)
6. Have a clean and efficient reference solution

Return your response as a valid JSON object with the following structure:
{{
    "problem_statement": "Clear description of the problem, including input/output format and constraints",
    "test_cases": [
        {{"input": input_value, "expected_output": expected_value}},
        // At least 3 test cases
    ],
    "reference_solution": "Complete Python solution with comments"
}}

Ensure all JSON values are properly escaped and the entire response is a valid JSON object.
Pay special attention to backslashes (\) within strings, such as in Python code for regular expressions or file paths; these MUST be escaped as \\ for the JSON to be valid.
"""
)

# Template for generating language-specific coding challenges
LANGUAGE_SPECIFIC_TEMPLATE = PromptTemplate(
    input_variables=["job_description", "skills_required", "difficulty_level", "language"],
    template="""You are an expert at creating coding challenges for technical interviews.

Your task is to generate ONE coding challenge that effectively evaluates a candidate's technical skills for the following position:

JOB DESCRIPTION:
{job_description}

REQUIRED SKILLS:
{skills_required}

DIFFICULTY LEVEL: {difficulty_level}

PROGRAMMING LANGUAGE: {language}

The coding challenge should:
1. Be relevant to the job description and required skills
2. Be solvable within 20-30 minutes
3. Test algorithmic thinking and code quality
4. Have clear requirements and constraints
5. Include diverse test cases (normal cases, edge cases, error cases)
6. Have a clean and efficient reference solution in {language}
7. Use language-specific idioms and best practices for {language}

Return your response as a valid JSON object with the following structure:
{{
    "title": "Short descriptive title for the challenge",
    "problem_statement": "Clear description of the problem, including input/output format and constraints",
    "test_cases": [
        {{"input": input_value, "expected_output": expected_value, "explanation": "What this test case is checking"}},
        // At least 3 test cases with explanations
    ],
    "reference_solution": "Complete {language} solution with comments",
    "starter_code": "Skeleton code to provide to the candidate",
    "hints": [
        "Hint 1 - conceptual guidance without giving away the solution",
        "Hint 2 - more specific guidance",
        "Hint 3 - targeted hint about a key algorithm or data structure"
    ]
}}

Ensure all JSON values are properly escaped and the entire response is a valid JSON object.
"""
)

# Template for generating hints for a coding challenge
HINT_GENERATION_TEMPLATE = PromptTemplate(
    input_variables=["problem_statement", "current_code", "reference_solution", "error_message"],
    template="""As an interview coach, I need to provide helpful hints for a coding challenge.

PROBLEM:
{problem_statement}

CANDIDATE'S CURRENT CODE:
```
{current_code}
```

REFERENCE SOLUTION (Do not reveal this directly):
```
{reference_solution}
```

ERROR MESSAGE (if any):
{error_message}

Generate 3 progressive hints that guide the candidate toward the solution without giving it away. 
Start with a conceptual hint, then a more specific hint, and finally a targeted hint that addresses 
a key part of the algorithm.

The hints should:
1. Be constructive and encouraging
2. Not reveal the complete solution
3. Address specific issues in the candidate's current code
4. Be clear and concise

Return only the hints, numbered 1-3, without any additional text.
"""
)

# Template for evaluating code submissions
CODE_EVALUATION_TEMPLATE = PromptTemplate(
    input_variables=["problem_statement", "candidate_code", "reference_solution", "test_results", "language"],
    template="""You are an experienced technical interviewer evaluating a candidate's coding solution.

PROBLEM STATEMENT:
{problem_statement}

CANDIDATE'S SOLUTION:
```{language}
{candidate_code}
```

TEST RESULTS:
{test_results}

REFERENCE SOLUTION (For your reference only):
```{language}
{reference_solution}
```

Provide a comprehensive evaluation of the candidate's solution covering:

1. Correctness: Does the solution produce the correct output for all test cases?
2. Efficiency: What is the time and space complexity? Could it be optimized?
3. Code Quality: Is the code well-structured, readable, and maintainable?
4. Problem-Solving Approach: Did the candidate demonstrate good problem-solving skills?

Structure your evaluation as a JSON object with the following fields:
{{
    "correctness_score": 0-10,
    "efficiency_score": 0-10,
    "code_quality_score": 0-10,
    "problem_solving_score": 0-10,
    "overall_score": 0-10,
    "strengths": ["strength1", "strength2", ...],
    "areas_for_improvement": ["area1", "area2", ...],
    "detailed_feedback": "Detailed paragraph of feedback"
}}

Be fair, balanced, and constructive in your evaluation. Include specific examples from the code to support your assessment.
"""
)

def format_problem_generation_prompt(
    job_description: str,
    skills_required: List[str],
    difficulty_level: str = "intermediate"
) -> str:
    """
    Format the problem generation prompt with the given parameters.
    
    Args:
        job_description: Description of the job position
        skills_required: List of required technical skills
        difficulty_level: Desired difficulty level ("beginner", "intermediate", "advanced")
        
    Returns:
        Formatted prompt string ready to be sent to the LLM
    """
    return PROBLEM_GENERATION_TEMPLATE.format(
        job_description=job_description,
        skills_required=", ".join(skills_required) if isinstance(skills_required, list) else skills_required,
        difficulty_level=difficulty_level
    )

def format_language_specific_prompt(
    job_description: str,
    skills_required: List[str],
    language: str,
    difficulty_level: str = "intermediate"
) -> str:
    """
    Format the language-specific problem generation prompt with the given parameters.
    
    Args:
        job_description: Description of the job position
        skills_required: List of required technical skills
        language: Programming language for the challenge
        difficulty_level: Desired difficulty level ("beginner", "intermediate", "advanced")
        
    Returns:
        Formatted prompt string ready to be sent to the LLM
    """
    return LANGUAGE_SPECIFIC_TEMPLATE.format(
        job_description=job_description,
        skills_required=", ".join(skills_required) if isinstance(skills_required, list) else skills_required,
        language=language,
        difficulty_level=difficulty_level
    )

def format_hint_generation_prompt(
    problem_statement: str,
    current_code: str,
    reference_solution: str,
    error_message: Optional[str] = None
) -> str:
    """
    Format the hint generation prompt with the given parameters.
    
    Args:
        problem_statement: Description of the coding problem
        current_code: The candidate's current code
        reference_solution: The reference solution
        error_message: Optional error message from code execution
        
    Returns:
        Formatted prompt string ready to be sent to the LLM
    """
    return HINT_GENERATION_TEMPLATE.format(
        problem_statement=problem_statement,
        current_code=current_code,
        reference_solution=reference_solution,
        error_message=error_message or "No error message provided."
    )

def format_code_evaluation_prompt(
    problem_statement: str,
    candidate_code: str,
    reference_solution: str,
    test_results: Dict[str, Any],
    language: str = "python"
) -> str:
    """
    Format the code evaluation prompt with the given parameters.
    
    Args:
        problem_statement: Description of the coding problem
        candidate_code: The candidate's code submission
        reference_solution: The reference solution
        test_results: Results of executing the candidate's code
        language: Programming language of the code
        
    Returns:
        Formatted prompt string ready to be sent to the LLM
    """
    # Format test results as a string
    test_results_str = ""
    if isinstance(test_results, dict):
        test_results_str = "\n".join(f"{k}: {v}" for k, v in test_results.items())
    else:
        test_results_str = str(test_results)
        
    return CODE_EVALUATION_TEMPLATE.format(
        problem_statement=problem_statement,
        candidate_code=candidate_code,
        reference_solution=reference_solution,
        test_results=test_results_str,
        language=language
    ) 