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
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from contextlib import redirect_stdout, redirect_stderr

from langchain_core.tools import tool

# Import docker sandbox
from ai_interviewer.tools.docker_sandbox import DockerSandbox

# Configure logging
logger = logging.getLogger(__name__)

# Initialize Docker sandbox (will be lazily loaded)
_docker_sandbox = None

def get_docker_sandbox() -> Optional[DockerSandbox]:
    """
    Get or initialize the Docker sandbox instance.
    
    Returns:
        DockerSandbox instance or None if Docker is not available
    """
    global _docker_sandbox
    
    if _docker_sandbox is None:
        try:
            _docker_sandbox = DockerSandbox()
            # Verify Docker is available
            docker_check = _docker_sandbox.check_docker_requirements()
            if docker_check.get("docker_available", False):
                logger.info("Docker sandbox initialized successfully")
            else:
                logger.warning(f"Docker not available: {docker_check.get('message', 'Unknown error')}")
                _docker_sandbox = None
        except Exception as e:
            logger.error(f"Failed to initialize Docker sandbox: {e}")
            _docker_sandbox = None
    
    return _docker_sandbox

@tool
async def execute_candidate_code(language: str, code: str, test_cases: List[Dict]) -> Dict:
    """
    Execute candidate code in a secure sandbox with resource limits.
    
    Args:
        language: Programming language (python, javascript, etc.)
        code: Source code to execute
        test_cases: List of test cases to run against the code
        
    Returns:
        Dictionary with execution results including pass_count, total_tests, outputs, and errors
    """
    try:
        logger.info(f"Executing {language} code in secure sandbox")
        
        # Get Docker sandbox instance
        sandbox = get_docker_sandbox()
        
        # Check if Docker is available
        if sandbox is not None:
            # Execute code in Docker sandbox
            logger.info("Using Docker sandbox for secure execution")
            results = await sandbox.execute_code(
                language=language,
                code=code,
                test_cases=test_cases
            )
            
            # Format results for consumption by the interviewer agent
            return {
                "status": results.get("status", "error"),
                "pass_count": results.get("passed", 0),
                "total_tests": results.get("passed", 0) + results.get("failed", 0),
                "outputs": [t.get("output") for t in results.get("test_results", [])],
                "errors": results.get("error_message", ""),
                "detailed_results": results
            }
        else:
            # Fall back to legacy execution method for compatibility
            logger.warning("Docker not available, falling back to legacy CodeExecutor")
            
            if language.lower() == "python":
                results = await CodeExecutor.execute_python_code(code, test_cases)
                return {
                    "status": results.get("status", "error"),
                    "pass_count": results.get("passed", 0),
                    "total_tests": results.get("passed", 0) + results.get("failed", 0),
                    "outputs": [t.get("output") for t in results.get("test_results", [])],
                    "errors": results.get("error_message", ""),
                    "detailed_results": results
                }
            else:
                return {
                    "status": "error",
                    "error_message": f"Legacy execution not supported for language: {language}",
                    "pass_count": 0,
                    "total_tests": len(test_cases),
                    "outputs": [],
                    "errors": f"Legacy execution not supported for language: {language}"
                }
    except Exception as e:
        logger.error(f"Error executing code: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "status": "error",
            "error_message": str(e),
            "pass_count": 0,
            "total_tests": len(test_cases),
            "outputs": [],
            "errors": str(e)
        }

class CodeExecutor:
    """
    Safely executes code and evaluates it against test cases.
    
    This class handles different languages and provides detailed
    execution metrics and test results.
    """

    @staticmethod
    async def execute_python_code(code: str, test_cases: List[Dict[str, Any]], 
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
        # First, try using the Docker sandbox if available
        sandbox = get_docker_sandbox()
        if sandbox:
            logger.info("Using Docker sandbox for Python code execution")
            return await sandbox.execute_code(
                language="python",
                code=code,
                test_cases=test_cases,
                function_name=function_name,
                timeout=timeout
            )
        
        # Fall back to legacy in-process execution if Docker is not available
        logger.warning("Docker sandbox not available, using legacy in-process execution (less secure)")
        
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
                function_name = await asyncio.to_thread(CodeExecutor._extract_python_function_name, code)
            except Exception as e:
                logger.error(f"Error extracting function name: {e}")
                results["status"] = "error"
                results["error_message"] = "Could not identify a function to test"
                return results
        
        # Safely execute the code to define the function
        try:
            # Create namespace
            namespace = {}
            
            # Execute code in the namespace using asyncio.to_thread for CPU-bound operation
            await asyncio.to_thread(exec, code, namespace)
            
            # Check if function exists
            if function_name not in namespace:
                results["status"] = "error"
                results["error_message"] = f"Function '{function_name}' not found in code"
                return results
            
            # Get the function
            func = namespace[function_name]
            
            # Run test cases
            start_time = time.time()
            
            for test_case in test_cases:
                test_result = {
                    "test_case": test_case,
                    "passed": False,
                    "output": None,
                    "error": None,
                    "execution_time": 0
                }
                
                try:
                    # Capture stdout and stderr
                    stdout = io.StringIO()
                    stderr = io.StringIO()
                    
                    # Execute test case with timeout using asyncio.wait_for
                    test_start = time.time()
                    with redirect_stdout(stdout), redirect_stderr(stderr):
                        # Run the function call in a separate thread to allow timeout
                        args = test_case.get("input", [])
                        if not isinstance(args, (list, tuple)):
                            args = [args]
                        
                        try:
                            output = await asyncio.wait_for(
                                asyncio.to_thread(func, *args),
                                timeout=timeout
                            )
                            
                            test_result["output"] = output
                            test_result["stdout"] = stdout.getvalue()
                            test_result["stderr"] = stderr.getvalue()
                            
                            # Check output
                            expected = test_case.get("expected")
                            test_result["passed"] = await asyncio.to_thread(
                                CodeExecutor._check_output_equality,
                                output,
                                expected
                            )
                            
                            if test_result["passed"]:
                                results["passed"] += 1
                            else:
                                results["failed"] += 1
                                test_result["error"] = f"Expected {expected}, but got {output}"
                            
                        except asyncio.TimeoutError:
                            test_result["error"] = f"Execution timed out after {timeout} seconds"
                            results["failed"] += 1
                            
                    test_result["execution_time"] = time.time() - test_start
                    
                except Exception as e:
                    test_result["error"] = str(e)
                    test_result["traceback"] = traceback.format_exc()
                    results["failed"] += 1
                
                results["test_results"].append(test_result)
            
            results["execution_time"] = time.time() - start_time
            
            # Calculate pass rate
            total_tests = len(test_cases)
            results["pass_rate"] = (results["passed"] / total_tests) if total_tests > 0 else 0
            
            return results
            
        except Exception as e:
            logger.error(f"Error executing Python code: {e}")
            results["status"] = "error"
            results["error_message"] = str(e)
            results["traceback"] = traceback.format_exc()
            return results

    @staticmethod
    async def execute_javascript_code(code: str, test_cases: List[Dict[str, Any]],
                               function_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute JavaScript code against provided test cases.
        
        Args:
            code: JavaScript code to execute
            test_cases: List of test cases to run
            function_name: Name of the function to test
            
        Returns:
            Dictionary with execution results
        """
        # Try using the Docker sandbox
        sandbox = get_docker_sandbox()
        if sandbox:
            logger.info("Using Docker sandbox for JavaScript code execution")
            return await sandbox.execute_code(
                language="javascript",
                code=code,
                test_cases=test_cases,
                function_name=function_name
            )
        else:
            return {
                "status": "error",
                "error_message": "JavaScript execution requires Docker sandbox",
                "passed": 0,
                "failed": len(test_cases),
                "test_results": []
            }

    @staticmethod
    def _extract_python_function_name(code: str) -> str:
        """Extract the first function name from Python code."""
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    return node.name
            raise ValueError("No function definition found in code")
        except Exception as e:
            raise ValueError(f"Error parsing Python code: {str(e)}")

    @staticmethod
    def _check_output_equality(actual: Any, expected: Any) -> bool:
        """
        Check if actual output matches expected output.
        
        Handles various Python data types and structures.
        """
        # Handle None
        if actual is None and expected is None:
            return True
        
        # Handle different types
        if type(actual) != type(expected):
            return False
        
        # Handle lists and tuples
        if isinstance(actual, (list, tuple)):
            if len(actual) != len(expected):
                return False
            return all(CodeExecutor._check_output_equality(a, e) for a, e in zip(actual, expected))
        
        # Handle dictionaries
        if isinstance(actual, dict):
            if len(actual) != len(expected):
                return False
            if set(actual.keys()) != set(expected.keys()):
                return False
            return all(CodeExecutor._check_output_equality(actual[k], expected[k]) for k in actual)
        
        # Handle sets
        if isinstance(actual, set):
            return actual == expected
        
        # Handle numeric types with tolerance for floating point
        if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
            if isinstance(actual, float) or isinstance(expected, float):
                return abs(actual - expected) < 1e-6
            return actual == expected
        
        # Default comparison
        return actual == expected

class SafetyChecker:
    """
    Checks code for potential security issues.
    
    This class provides static methods for analyzing code
    to identify potential security risks before execution.
    """
    
    @staticmethod
    async def check_python_code_safety(code: str) -> Tuple[bool, str]:
        """
        Check Python code for potential security issues.
        
        Args:
            code: Python code to analyze
            
        Returns:
            Tuple of (is_safe, message)
        """
        try:
            # Parse code to AST - this is CPU-bound so use to_thread
            tree = await asyncio.to_thread(ast.parse, code)
            
            # Look for dangerous operations
            dangerous_calls = []
            
            for node in ast.walk(tree):
                # Check for system calls
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        func_name = node.func.id
                        if func_name in ['eval', 'exec', 'compile']:
                            dangerous_calls.append(f"Use of {func_name}()")
                    elif isinstance(node.func, ast.Attribute):
                        if isinstance(node.func.value, ast.Name):
                            # Check for os.system, os.popen, etc.
                            if node.func.value.id == 'os':
                                attr = node.func.attr
                                if attr in ['system', 'popen', 'spawn', 'exec']:
                                    dangerous_calls.append(f"Use of os.{attr}()")
                            # Check for subprocess calls
                            elif node.func.value.id == 'subprocess':
                                attr = node.func.attr
                                if attr in ['call', 'run', 'Popen']:
                                    dangerous_calls.append(f"Use of subprocess.{attr}()")
                
                # Check for imports
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    for name in node.names:
                        module = name.name.split('.')[0]
                        if module in ['os', 'subprocess', 'sys']:
                            dangerous_calls.append(f"Import of {module} module")
            
            if dangerous_calls:
                return False, f"Potentially unsafe code detected: {', '.join(dangerous_calls)}"
            
            return True, "Code appears safe"
            
        except SyntaxError as e:
            return False, f"Syntax error in code: {str(e)}"
        except Exception as e:
            return False, f"Error analyzing code safety: {str(e)}"