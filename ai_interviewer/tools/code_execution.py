"""
Code execution utilities for AI Interviewer platform.

This module provides functionality for safely executing code submissions
against test cases in a controlled environment.
"""
import sys
import io
import logging
import traceback
import ast
import time
from typing import Dict, List, Optional, Any, Tuple
from contextlib import redirect_stdout, redirect_stderr

# Configure logging
logger = logging.getLogger(__name__)


class CodeExecutor:
    """
    Safely executes code and evaluates it against test cases.
    
    This class handles different languages and provides detailed
    execution metrics and test results.
    """

    @staticmethod
    def execute_python_code(code: str, test_cases: List[Dict[str, Any]], 
                            function_name: Optional[str] = None,
                            timeout: int = 5) -> Dict[str, Any]:
        """
        Execute Python code against provided test cases.
        
        Args:
            code: Python code to execute
            test_cases: List of test cases to run
            function_name: Name of the function to test (extracts from code if None)
            timeout: Maximum execution time in seconds per test case
            
        Returns:
            Dictionary with execution results
        """
        results = {
            "status": "success",
            "passed": 0,
            "failed": 0,
            "error": False,
            "execution_time": 0,
            "memory_usage": 0,
            "test_results": [],
            "detailed_metrics": {}
        }
        
        # Extract the function name if not provided
        if not function_name:
            try:
                function_name = CodeExecutor._extract_python_function_name(code)
            except Exception as e:
                logger.error(f"Error extracting function name: {e}")
                results["status"] = "error"
                results["error_message"] = "Could not identify a function to test"
                return results
        
        # Safely execute the code to define the function
        try:
            # Create namespace
            namespace = {}
            
            # Execute code in the namespace
            exec(code, namespace)
            
            # Check if function exists
            if function_name not in namespace:
                results["status"] = "error"
                results["error_message"] = f"Function '{function_name}' not found in code"
                return results
            
            # Get the function
            function = namespace[function_name]
            
            # Execute test cases
            total_time = 0
            
            for i, test_case in enumerate(test_cases):
                test_input = test_case["input"]
                expected_output = test_case["expected_output"]
                
                # Prepare test result
                test_result = {
                    "test_case_id": i + 1,
                    "input": test_input,
                    "expected_output": expected_output,
                    "is_hidden": test_case.get("is_hidden", False),
                    "explanation": test_case.get("explanation", ""),
                    "passed": False,
                    "execution_time": 0,
                    "memory_usage": 0,
                    "output": None,
                    "error": None
                }
                
                # Capture stdout
                stdout_buffer = io.StringIO()
                stderr_buffer = io.StringIO()
                
                try:
                    # Measure execution time
                    start_time = time.time()
                    
                    # Execute with stdout/stderr redirection
                    with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
                        if isinstance(test_input, (list, tuple)) and not isinstance(test_input, str):
                            actual_output = function(*test_input)
                        elif isinstance(test_input, dict):
                            actual_output = function(**test_input)
                        else:
                            actual_output = function(test_input)
                    
                    # Calculate execution time
                    execution_time = time.time() - start_time
                    total_time += execution_time
                    
                    # Get stdout content
                    stdout_content = stdout_buffer.getvalue()
                    stderr_content = stderr_buffer.getvalue()
                    
                    # Check if output matches expected output
                    if CodeExecutor._check_output_equality(actual_output, expected_output):
                        test_result["passed"] = True
                        results["passed"] += 1
                    else:
                        test_result["passed"] = False
                        results["failed"] += 1
                    
                    # Add actual output and execution information
                    test_result["output"] = actual_output
                    test_result["execution_time"] = execution_time
                    
                    # Add stdout/stderr if any
                    if stdout_content:
                        test_result["stdout"] = stdout_content
                    if stderr_content:
                        test_result["stderr"] = stderr_content
                    
                except Exception as e:
                    # Handle exceptions
                    test_result["passed"] = False
                    test_result["error"] = str(e)
                    test_result["traceback"] = traceback.format_exc()
                    test_result["stderr"] = stderr_buffer.getvalue()
                    results["failed"] += 1
                
                # Add test result
                results["test_results"].append(test_result)
            
            # Calculate overall metrics
            results["execution_time"] = total_time
            results["all_passed"] = results["failed"] == 0
            
            # Add detailed metrics
            results["detailed_metrics"] = {
                "avg_execution_time": total_time / len(test_cases) if test_cases else 0,
                "max_execution_time": max((t["execution_time"] for t in results["test_results"]), default=0),
                "success_rate": results["passed"] / len(test_cases) if test_cases else 0
            }
            
            return results
            
        except Exception as e:
            # Handle exceptions during code execution setup
            logger.error(f"Error executing code: {e}")
            results["status"] = "error"
            results["error_message"] = str(e)
            results["traceback"] = traceback.format_exc()
            return results
    
    @staticmethod
    def execute_javascript_code(code: str, test_cases: List[Dict[str, Any]],
                               function_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute JavaScript code using Node.js in a controlled environment.
        
        This is a placeholder for future implementation using either:
        1. subprocess to call Node.js
        2. PyExecJS or similar for JavaScript execution
        3. Docker-based sandboxing
        
        Args:
            code: JavaScript code to execute
            test_cases: List of test cases to run
            function_name: Name of the function to test
            
        Returns:
            Dictionary with execution results (currently mocked)
        """
        # Placeholder implementation - would use subprocess to call Node.js in real implementation
        return {
            "status": "not_implemented",
            "message": "JavaScript execution not yet implemented. This would use Node.js in a production environment."
        }
    
    @staticmethod
    def _extract_python_function_name(code: str) -> str:
        """
        Extract the name of the first function defined in the code.
        
        Args:
            code: Python code to analyze
            
        Returns:
            The name of the first function found
            
        Raises:
            ValueError: If no function definition is found
        """
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    return node.name
            
            raise ValueError("No function definition found in code")
        except Exception as e:
            raise ValueError(f"Error parsing code: {e}")
    
    @staticmethod
    def _check_output_equality(actual: Any, expected: Any) -> bool:
        """
        Check if actual output equals expected output with appropriate type handling.
        
        Args:
            actual: Actual output from code execution
            expected: Expected output for comparison
            
        Returns:
            True if outputs match, otherwise False
        """
        # Handle None specifically
        if actual is None and expected is None:
            return True
        
        # Handle different types of collections
        if isinstance(expected, list) and isinstance(actual, list):
            # Check lengths
            if len(expected) != len(actual):
                return False
            
            # Check each element
            return all(CodeExecutor._check_output_equality(a, e) for a, e in zip(actual, expected))
        
        # Handle dictionaries
        if isinstance(expected, dict) and isinstance(actual, dict):
            # Check keys
            if set(expected.keys()) != set(actual.keys()):
                return False
            
            # Check each value
            return all(CodeExecutor._check_output_equality(actual[k], expected[k]) for k in expected)
        
        # Handle sets
        if isinstance(expected, set) and isinstance(actual, set):
            return expected == actual
        
        # Handle tuples
        if isinstance(expected, tuple) and isinstance(actual, tuple):
            if len(expected) != len(actual):
                return False
            return all(CodeExecutor._check_output_equality(a, e) for a, e in zip(actual, expected))
        
        # For primitive types and other cases, use direct equality
        try:
            return actual == expected
        except Exception:
            # If comparison fails, they're not equal
            return False


class SafetyChecker:
    """
    Checks code for potentially unsafe operations before execution.
    
    This is important for preventing malicious code execution in the sandbox.
    """
    
    @staticmethod
    def check_python_code_safety(code: str) -> Tuple[bool, str]:
        """
        Check Python code for potentially unsafe operations.
        
        Args:
            code: Python code to check
            
        Returns:
            Tuple of (is_safe, reason) where reason is empty if code is safe
        """
        # Check for imports of dangerous modules
        dangerous_modules = {
            'os', 'sys', 'subprocess', 'shutil', 'socket', 'requests', 
            'urllib', 'http', 'ftplib', 'telnetlib', 'importlib'
        }
        
        # Use AST parsing for better detection
        try:
            tree = ast.parse(code)
            
            for node in ast.walk(tree):
                # Check for dangerous imports
                if isinstance(node, ast.Import):
                    for name in node.names:
                        if name.name.split('.')[0] in dangerous_modules:
                            return False, f"Unsafe module import: {name.name}"
                
                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.module.split('.')[0] in dangerous_modules:
                        return False, f"Unsafe module import: {node.module}"
                
                # Check for exec or eval calls
                elif isinstance(node, ast.Call) and hasattr(node.func, 'id'):
                    if node.func.id in ('exec', 'eval', 'compile'):
                        return False, f"Unsafe function call: {node.func.id}"
                
                # Check for dangerous attribute access (like os.system)
                elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                    if node.value.id in dangerous_modules and node.attr in ('system', 'popen', 'spawn', 'exec'):
                        return False, f"Unsafe attribute access: {node.value.id}.{node.attr}"
            
            return True, ""
        
        except Exception as e:
            logger.error(f"Error checking code safety: {e}")
            return False, f"Error analyzing code: {str(e)}" 