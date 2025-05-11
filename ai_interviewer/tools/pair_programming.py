"""
AI Pair Programming tools for the AI Interviewer platform.

This module provides advanced pair programming support, including:
- Context-aware code suggestions
- Intelligent code completion
- Real-time code review
- Pattern-based hints
"""
import logging
from typing import Dict, List, Optional, Any
import ast
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
import re

from ai_interviewer.tools.code_quality import CodeQualityMetrics

# Configure logging
logger = logging.getLogger(__name__)

class CodeAnalyzer:
    """
    Analyzes code structure and patterns to provide intelligent suggestions.
    """
    
    @staticmethod
    def extract_code_context(code: str) -> Dict[str, Any]:
        """
        Extract contextual information from the code.
        
        Args:
            code: The code to analyze
            
        Returns:
            Dict containing code context information
        """
        try:
            tree = ast.parse(code)
            context = {
                "imports": [],
                "functions": [],
                "classes": [],
                "variables": [],
                "current_scope": None,
                "patterns": []
            }
            
            # Extract imports
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    context["imports"].extend(n.name for n in node.names)
                elif isinstance(node, ast.ImportFrom):
                    context["imports"].append(f"{node.module}.{node.names[0].name}")
                    
                # Extract functions
                elif isinstance(node, ast.FunctionDef):
                    func_info = {
                        "name": node.name,
                        "args": [arg.arg for arg in node.args.args],
                        "returns": node.returns.id if node.returns else None,
                        "docstring": ast.get_docstring(node)
                    }
                    context["functions"].append(func_info)
                    
                # Extract classes
                elif isinstance(node, ast.ClassDef):
                    class_info = {
                        "name": node.name,
                        "bases": [base.id for base in node.bases if isinstance(base, ast.Name)],
                        "methods": [m.name for m in node.body if isinstance(m, ast.FunctionDef)]
                    }
                    context["classes"].append(class_info)
                    
                # Extract variables
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            context["variables"].append(target.id)
            
            # Detect common patterns
            context["patterns"] = CodeAnalyzer._detect_patterns(tree)
            
            return context
            
        except Exception as e:
            logger.error(f"Error extracting code context: {e}")
            return {}
    
    @staticmethod
    def _detect_patterns(tree: ast.AST) -> List[str]:
        """
        Detect common programming patterns in the code.
        
        Args:
            tree: AST of the code
            
        Returns:
            List of detected patterns
        """
        patterns = []
        
        for node in ast.walk(tree):
            # Detect list comprehension
            if isinstance(node, ast.ListComp):
                patterns.append("list_comprehension")
                
            # Detect error handling
            elif isinstance(node, ast.Try):
                patterns.append("error_handling")
                
            # Detect recursion
            elif isinstance(node, ast.FunctionDef):
                for inner_node in ast.walk(node):
                    if isinstance(inner_node, ast.Call):
                        if hasattr(inner_node.func, 'id') and inner_node.func.id == node.name:
                            patterns.append("recursion")
                            break
                            
            # Detect iteration patterns
            elif isinstance(node, ast.For):
                patterns.append("iteration")
                
            # Detect map/filter/reduce patterns
            elif isinstance(node, ast.Call):
                if hasattr(node.func, 'id'):
                    if node.func.id in ['map', 'filter', 'reduce']:
                        patterns.append(f"{node.func.id}_function")
        
        return list(set(patterns))  # Remove duplicates

@tool
def suggest_code_improvements(code: str, context: Optional[Dict] = None) -> Dict:
    """
    Suggest improvements for the candidate's code.
    
    Args:
        code: The code to analyze
        context: Optional contextual information
        
    Returns:
        Dictionary with improvement suggestions
    """
    try:
        # Validate parameters
        if not code or not isinstance(code, str):
            return {
                "status": "error",
                "message": "Invalid code provided. Please submit a valid code snippet."
            }
        
        # Log request details
        logger.info(f"Suggesting improvements for code snippet ({len(code)} chars)")
        
        # For MVP, we'll return generic improvement suggestions based on code patterns
        suggestions = []
        
        # Check for basic code patterns and suggest improvements
        # 1. Missing docstrings
        if not _has_docstrings(code):
            suggestions.append("Consider adding docstrings to functions and classes for better documentation.")
        
        # 2. Long functions
        if _has_long_functions(code):
            suggestions.append("Break down long functions into smaller, more focused functions for better readability and maintainability.")
        
        # 3. Variable naming
        if _has_poor_variable_names(code):
            suggestions.append("Use more descriptive variable names to improve code readability.")
        
        # 4. Error handling
        if not _has_error_handling(code):
            suggestions.append("Add error handling (try-except blocks) to make your code more robust.")
        
        # 5. Comments
        if not _has_comments(code):
            suggestions.append("Add comments to explain complex logic and the reasoning behind your implementation.")
        
        # 6. Code organization
        suggestions.append("Consider organizing your code into logical sections with clear separation of concerns.")
        
        # 7. Testing suggestions
        suggestions.append("Consider adding test cases to verify your solution works as expected.")
        
        # If context includes a challenge, add challenge-specific suggestions
        if context and "challenge" in context:
            challenge = context["challenge"]
            
            # Extraction of challenge title/description
            challenge_title = challenge.get("title", "")
            challenge_desc = challenge.get("description", "")
            
            # Add challenge-specific suggestions based on its difficulty
            difficulty = challenge.get("difficulty", "medium").lower()
            if difficulty == "easy":
                suggestions.append("For easy challenges, focus on code clarity and simplicity over optimization.")
            elif difficulty == "medium":
                suggestions.append("For medium difficulty challenges, balance between performance and readability.")
            elif difficulty == "hard":
                suggestions.append("For hard challenges, pay special attention to efficiency and algorithm choice.")
                
            # If error message provided, add specific suggestions
            if "error_message" in context and context["error_message"]:
                error_msg = context["error_message"]
                
                if "index" in error_msg.lower() and "out of" in error_msg.lower():
                    suggestions.append("Add bounds checking to prevent index out of range errors.")
                elif "type" in error_msg.lower():
                    suggestions.append("Add type checking or conversion to handle different data types.")
                elif "memory" in error_msg.lower():
                    suggestions.append("Consider optimizing your algorithm to reduce memory usage.")
                elif "time" in error_msg.lower() and "limit" in error_msg.lower():
                    suggestions.append("Consider a more efficient algorithm to meet time constraints.")
        
        # Return suggestions
        return {
            "status": "success",
            "suggestions": suggestions
        }
    except Exception as e:
        logger.error(f"Error suggesting code improvements: {e}")
        return {
            "status": "error",
            "message": str(e)
        }

@tool
def complete_code(code: str, context: Optional[str] = None) -> Dict:
    """
    Provide completion for partially written code.
    
    Args:
        code: The partial code to complete
        context: Optional description of what the completion should achieve
        
    Returns:
        Dictionary with code completion
    """
    try:
        # Validate parameters
        if not code or not isinstance(code, str):
            return {
                "status": "error",
                "message": "Invalid code provided. Please submit a valid code snippet."
            }
        
        # Log request details
        logger.info(f"Completing code snippet ({len(code)} chars)")
        
        # For MVP, we'll provide simple code completions based on patterns
        # Identify the programming language
        language = _determine_language(code)
        
        # Generate appropriate completion based on language and context
        completion = ""
        if language == "python":
            if "def " in code and not code.strip().endswith(":"):
                # Function definition needs completion
                completion = _complete_python_function(code, context)
            elif "class " in code and not code.strip().endswith(":"):
                # Class definition needs completion
                completion = _complete_python_class(code, context)
            elif "if " in code and not code.strip().endswith(":"):
                # If statement needs completion
                completion = _complete_python_if_statement(code, context)
            elif "for " in code and not code.strip().endswith(":"):
                # For loop needs completion
                completion = _complete_python_loop(code, context, "for")
            elif "while " in code and not code.strip().endswith(":"):
                # While loop needs completion
                completion = _complete_python_loop(code, context, "while")
            else:
                # General code completion
                completion = _complete_general_python(code, context)
        elif language == "javascript":
            # JavaScript completions
            completion = _complete_javascript(code, context)
        else:
            # Generic code completion
            completion = "# Suggested completion:\n# Add your implementation logic here\n# Don't forget to handle edge cases"
        
        # Return completion
        return {
            "status": "success",
            "completion": completion
        }
    except Exception as e:
        logger.error(f"Error completing code: {e}")
        return {
            "status": "error",
            "message": str(e)
        }

@tool
def review_code_section(code: str, section: Optional[str] = None) -> Dict:
    """
    Review a specific section of code.
    
    Args:
        code: The code to review
        section: Optional section identifier
        
    Returns:
        Dictionary with code review feedback
    """
    try:
        # Validate parameters
        if not code or not isinstance(code, str):
            return {
                "status": "error",
                "message": "Invalid code provided. Please submit a valid code snippet."
            }
        
        # Log request details
        logger.info(f"Reviewing code section ({len(code)} chars)")
        
        # For MVP, we'll provide simple code review
        review = []
        
        # Identify the programming language
        language = _determine_language(code)
        
        # General review items
        review.append("Overall, your code is well-structured and demonstrates good understanding of programming concepts.")
        
        # Language-specific reviews
        if language == "python":
            review.extend(_review_python_code(code, section))
        elif language == "javascript":
            review.extend(_review_javascript_code(code, section))
        else:
            review.extend(_review_generic_code(code, section))
        
        # Add positive reinforcement
        review.append("Your solution shows good problem-solving skills and logical thinking.")
        
        # Return review
        return {
            "status": "success",
            "review": review
        }
    except Exception as e:
        logger.error(f"Error reviewing code section: {e}")
        return {
            "status": "error",
            "message": str(e)
        }

# Helper functions

def _has_docstrings(code: str) -> bool:
    """Check if code has docstrings."""
    if '"""' in code or "'''" in code:
        return True
    return False

def _has_long_functions(code: str) -> bool:
    """Check if code has functions with many lines."""
    lines = code.split('\n')
    function_lines = 0
    in_function = False
    
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('def ') and stripped.endswith(':'):
            in_function = True
            function_lines = 1
        elif in_function:
            if stripped and not stripped.startswith('#'):
                function_lines += 1
            if function_lines > 15:  # Arbitrary threshold
                return True
            if not stripped or stripped == '':
                in_function = False
    
    return False

def _has_poor_variable_names(code: str) -> bool:
    """Check for single-letter variable names (except common ones like i, j, k)."""
    # This is a simplistic check
    words = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', code)
    single_letter_vars = [w for w in words if len(w) == 1 and w not in ('i', 'j', 'k', 'x', 'y', 'n', 'm')]
    return len(single_letter_vars) > 0

def _has_error_handling(code: str) -> bool:
    """Check if code has error handling."""
    return 'try:' in code and 'except' in code

def _has_comments(code: str) -> bool:
    """Check if code has comments."""
    lines = code.split('\n')
    for line in lines:
        if '#' in line and not line.strip().startswith('"""') and not line.strip().startswith("'''"):
            return True
    return False

def _determine_language(code: str) -> str:
    """Determine the programming language of the code."""
    # Check for Python-specific constructs
    if 'def ' in code or 'import ' in code or '# ' in code:
        return "python"
    # Check for JavaScript-specific constructs
    elif 'function ' in code or 'var ' in code or 'const ' in code or 'let ' in code or '//' in code:
        return "javascript"
    # Default to Python if unsure
    return "python"

def _complete_python_function(code: str, context: Optional[str]) -> str:
    """Complete a Python function."""
    # This is a simplistic completion
    return ":\n    # Add your function implementation here\n    pass"

def _complete_python_class(code: str, context: Optional[str]) -> str:
    """Complete a Python class."""
    return ":\n    def __init__(self):\n        # Initialize class attributes\n        pass\n        \n    def process(self):\n        # Add core functionality\n        pass"

def _complete_python_if_statement(code: str, context: Optional[str]) -> str:
    """Complete a Python if statement."""
    return ":\n    # Add your condition handling here\n    pass\nelse:\n    # Handle the else case\n    pass"

def _complete_python_loop(code: str, context: Optional[str], loop_type: str) -> str:
    """Complete a Python loop."""
    if loop_type == "for":
        return ":\n    # Process each item in the loop\n    pass"
    else:  # while
        return ":\n    # Process the loop iteration\n    # Don't forget the exit condition to avoid infinite loops\n    pass"

def _complete_general_python(code: str, context: Optional[str]) -> str:
    """General Python code completion."""
    if context and "error handling" in context.lower():
        return "\n\ntry:\n    # Your implementation here\n    pass\nexcept Exception as e:\n    # Handle errors\n    print(f\"Error: {e}\")"
    elif context and "edge case" in context.lower():
        return "\n\n# Handle edge cases\nif not input_data:  # Empty input\n    return []\n\nif len(input_data) == 1:  # Single item\n    return input_data\n\n# Main implementation\nresult = process_data(input_data)\nreturn result"
    else:
        return "\n\n# Main implementation\ndef process_data(data):\n    # Process the data\n    result = data\n    return result\n\n# Test the function\nprint(process_data(input_data))"

def _complete_javascript(code: str, context: Optional[str]) -> str:
    """JavaScript code completion."""
    return "\n\n// Main implementation\nfunction processData(data) {\n    // Process the data\n    let result = data;\n    return result;\n}\n\n// Test the function\nconsole.log(processData(inputData));"

def _review_python_code(code: str, section: Optional[str]) -> List[str]:
    """Review Python code."""
    review = []
    
    # Check indentation
    if '    ' in code and '\t' in code:
        review.append("Inconsistent indentation - mixing tabs and spaces. Stick to one style (preferably spaces).")
    
    # Check variable naming
    if _has_poor_variable_names(code):
        review.append("Use more descriptive variable names to improve code readability.")
    
    # Check docstrings
    if not _has_docstrings(code):
        review.append("Consider adding docstrings to document your functions and classes.")
    
    # Check error handling
    if not _has_error_handling(code):
        review.append("Consider adding error handling for more robust code.")
    
    return review

def _review_javascript_code(code: str, section: Optional[str]) -> List[str]:
    """Review JavaScript code."""
    review = []
    
    # Check semicolons
    if ';' not in code:
        review.append("Consider adding semicolons at the end of statements for better code consistency.")
    
    # Check braces style
    if '{' in code and '}' in code and '{\n' not in code:
        review.append("Consider using consistent brace style for better readability.")
    
    return review

def _review_generic_code(code: str, section: Optional[str]) -> List[str]:
    """Generic code review."""
    review = []
    
    # Check comments
    if not _has_comments(code):
        review.append("Add comments to explain your logic and approach.")
    
    # Check code organization
    review.append("Ensure your code is well-organized with clear separation of concerns.")
    
    return review