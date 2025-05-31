"""
Docker-based secure code execution sandbox for AI Interviewer platform.

This module implements a secure sandbox for executing candidate code using Docker containers
with appropriate resource limits and security constraints.
"""
import os
import logging
import tempfile
import json
import uuid
import subprocess
import shutil
from typing import Dict, List, Optional, Any, Tuple
import docker
from docker.errors import DockerException, ImageNotFound, ContainerError
import asyncio

# Configure logging
logger = logging.getLogger(__name__)

# Default resource limits for containers
DEFAULT_MEMORY_LIMIT = "128m"  # 128 MB memory limit
DEFAULT_CPU_LIMIT = 0.5  # 0.5 CPU cores
DEFAULT_TIMEOUT = 10  # 10 seconds timeout
DEFAULT_NETWORK_DISABLED = True  # No network access

class DockerSandbox:
    """
    Docker-based secure sandbox for code execution.
    
    This class implements a secure environment for executing untrusted code
    using Docker containers with appropriate resource limits and security constraints.
    """
    
    def __init__(self):
        """Initialize the Docker sandbox."""
        try:
            self.client = docker.from_env()
            # Verify Docker is running
            self.client.ping()
            logger.info("Docker sandbox initialized successfully")
        except DockerException as e:
            logger.error(f"Failed to initialize Docker client: {e}")
            raise RuntimeError(f"Docker not available: {e}")
    
    async def execute_code(
        self,
        language: str,
        code: str,
        test_cases: List[Dict[str, Any]],
        function_name: Optional[str] = None,
        memory_limit: str = DEFAULT_MEMORY_LIMIT,
        cpu_limit: float = DEFAULT_CPU_LIMIT,
        timeout: int = DEFAULT_TIMEOUT,
        network_disabled: bool = DEFAULT_NETWORK_DISABLED
    ) -> Dict[str, Any]:
        """
        Execute code in a secure Docker container with resource limits.
        
        Args:
            language: Programming language (python, javascript, etc.)
            code: Source code to execute
            test_cases: List of test cases to run against the code
            function_name: Name of the function to test (optional, will be extracted if not provided)
            memory_limit: Container memory limit (e.g., "128m")
            cpu_limit: Container CPU limit (e.g., 0.5 for half a core)
            timeout: Execution timeout in seconds
            network_disabled: Whether to disable network access
            
        Returns:
            Dictionary with execution results
        """
        # Normalize language
        language = language.lower()
        
        # Choose execution handler based on language
        if language == "python":
            return await self._execute_python(code, test_cases, function_name, memory_limit, cpu_limit, timeout, network_disabled)
        elif language in ["javascript", "js"]:
            return await self._execute_javascript(code, test_cases, function_name, memory_limit, cpu_limit, timeout, network_disabled)
        else:
            return {
                "status": "error",
                "message": f"Unsupported language: {language}",
                "error": True
            }
    
    async def _execute_python(
        self,
        code: str,
        test_cases: List[Dict[str, Any]],
        function_name: Optional[str] = None,
        memory_limit: str = DEFAULT_MEMORY_LIMIT,
        cpu_limit: float = DEFAULT_CPU_LIMIT,
        timeout: int = DEFAULT_TIMEOUT,
        network_disabled: bool = DEFAULT_NETWORK_DISABLED
    ) -> Dict[str, Any]:
        """
        Execute Python code in a Docker container.
        
        Args:
            code: Python source code
            test_cases: List of test cases
            function_name: Name of the function to test
            memory_limit: Container memory limit
            cpu_limit: Container CPU limit
            timeout: Execution timeout in seconds
            network_disabled: Whether to disable network access
            
        Returns:
            Dictionary with execution results
        """
        # Create a temporary directory for the execution files
        temp_dir = await asyncio.to_thread(tempfile.mkdtemp, prefix="ai_interviewer_")
        
        try:
            # Create the runner script
            code_py_path = os.path.join(temp_dir, "code.py")
            await asyncio.to_thread(self._write_file, code_py_path, code)
                
            # Create the test runner script
            runner_code = self._generate_python_test_runner(test_cases, function_name)
            runner_py_path = os.path.join(temp_dir, "runner.py")
            await asyncio.to_thread(self._write_file, runner_py_path, runner_code)
                
            # Create test cases file
            test_cases_json_path = os.path.join(temp_dir, "test_cases.json")
            await asyncio.to_thread(self._write_json_file, test_cases_json_path, test_cases)
                
            # Run the container
            container_name = f"ai-interviewer-python-{uuid.uuid4().hex[:8]}"
            container = None
            
            try:
                # Prepare container settings
                container_settings = {
                    "image": "python:3.10-slim",
                    "volumes": {temp_dir: {"bind": "/app", "mode": "ro"}},
                    "working_dir": "/app",
                    "command": ["python", "runner.py"],
                    "mem_limit": memory_limit,
                    "cpu_quota": int(cpu_limit * 100000),  # Docker CPU quota in microseconds
                    "network_disabled": network_disabled,
                    "name": container_name,
                    "detach": True,
                    "read_only": True,
                }
                
                # Run the container
                container = await asyncio.to_thread(
                    self.client.containers.run,
                    **container_settings
                )
                
                # Wait for container to complete with timeout
                try:
                    await asyncio.to_thread(container.wait, timeout=timeout)
                except Exception as e:
                    if container:
                        try:
                            await asyncio.to_thread(container.stop, timeout=1)
                        except Exception as stop_exc:
                            logger.warning(f"Failed to stop container {container_name} during timeout handling: {stop_exc}")
                    return {
                        "status": "error",
                        "message": f"Execution timed out or error during wait: {str(e)}",
                        "execution_time": timeout,
                        "error": True
                    }
                
                # Get container logs
                try:
                    logs_bytes = await asyncio.to_thread(container.logs)
                    logs = logs_bytes.decode("utf-8")
                    
                    # Parse the JSON output from the runner
                    try:
                        # Find JSON output in logs
                        json_start = logs.find("__RESULTS_JSON_START__")
                        json_end = logs.find("__RESULTS_JSON_END__")
                        
                        if json_start >= 0 and json_end > json_start:
                            json_data = logs[json_start + len("__RESULTS_JSON_START__"):json_end].strip()
                            results = json.loads(json_data)
                            results["logs"] = logs
                            return results
                        else:
                            # No JSON results found, return error
                            return {
                                "status": "error",
                                "message": "Failed to parse execution results from logs",
                                "logs": logs,
                                "error": True
                            }
                    except json.JSONDecodeError:
                        return {
                            "status": "error",
                            "message": "Failed to parse execution results JSON from logs",
                            "logs": logs,
                            "error": True
                        }
                except Exception as log_exc:
                    logger.error(f"Error retrieving logs for container {container_name}: {log_exc}")
                    return {
                        "status": "error",
                        "message": f"Failed to retrieve execution logs: {str(log_exc)}",
                        "error": True
                    }
                
            except ContainerError as e:
                # Container run failed
                return {
                    "status": "error",
                    "message": f"Container execution failed: {str(e)}",
                    "stderr": e.stderr.decode("utf-8") if hasattr(e, "stderr") and e.stderr else "",
                    "error": True
                }
            except ImageNotFound:
                # Python image not found
                return {
                    "status": "error",
                    "message": "Python Docker image not found",
                    "error": True
                }
            except Exception as e:
                # Other exceptions
                logger.error(f"Docker execution error: {str(e)}")
                return {
                    "status": "error",
                    "message": f"Execution error: {str(e)}",
                    "error": True
                }
            finally:
                if container:
                    try:
                        # Explicitly remove the container now that we are done with it.
                        await asyncio.to_thread(container.remove, force=True)
                        logger.debug(f"Successfully removed container {container_name}")
                    except DockerException as e:
                        logger.warning(f"Error during explicit container cleanup for {container_name}: {e}")
                        
        finally:
            # Clean up temporary directory
            if os.path.exists(temp_dir):
                 await asyncio.to_thread(shutil.rmtree, temp_dir, ignore_errors=True)
    
    async def _execute_javascript(
        self,
        code: str,
        test_cases: List[Dict[str, Any]],
        function_name: Optional[str] = None,
        memory_limit: str = DEFAULT_MEMORY_LIMIT,
        cpu_limit: float = DEFAULT_CPU_LIMIT,
        timeout: int = DEFAULT_TIMEOUT,
        network_disabled: bool = DEFAULT_NETWORK_DISABLED
    ) -> Dict[str, Any]:
        """
        Execute JavaScript code in a Docker container.
        
        Args:
            code: JavaScript source code
            test_cases: List of test cases
            function_name: Name of the function to test
            memory_limit: Container memory limit
            cpu_limit: Container CPU limit
            timeout: Execution timeout in seconds
            network_disabled: Whether to disable network access
            
        Returns:
            Dictionary with execution results
        """
        # Create a temporary directory for the execution files
        temp_dir = await asyncio.to_thread(tempfile.mkdtemp, prefix="ai_interviewer_js_")
        container = None

        try:
            # Create the runner script
            code_js_path = os.path.join(temp_dir, "code.js")
            await asyncio.to_thread(self._write_file, code_js_path, code)

            # Create the test runner script
            runner_code = self._generate_javascript_test_runner(test_cases, function_name)
            runner_js_path = os.path.join(temp_dir, "runner.js")
            await asyncio.to_thread(self._write_file, runner_js_path, runner_code)

            # Create test cases file
            test_cases_json_path = os.path.join(temp_dir, "test_cases.json")
            await asyncio.to_thread(self._write_json_file, test_cases_json_path, test_cases)

            # Run the container
            container_name = f"ai-interviewer-js-{uuid.uuid4().hex[:8]}"
            
            try:
                # Prepare container settings
                container_settings = {
                    "image": "node:18-slim",
                    "volumes": {temp_dir: {"bind": "/app", "mode": "ro"}},
                    "working_dir": "/app",
                    "command": ["node", "runner.js"],
                    "mem_limit": memory_limit,
                    "cpu_quota": int(cpu_limit * 100000),
                    "network_disabled": network_disabled,
                    "name": container_name,
                    "detach": True,
                    "read_only": True,
                }

                # Run the container
                container = await asyncio.to_thread(
                    self.client.containers.run,
                    **container_settings
                )

                # Wait for container to complete with timeout
                try:
                    await asyncio.to_thread(container.wait, timeout=timeout)
                except Exception as e:
                    if container:
                        try:
                            await asyncio.to_thread(container.stop, timeout=1)
                        except Exception as stop_exc:
                            logger.warning(f"Failed to stop container {container_name} during timeout handling: {stop_exc}")
                    return {
                        "status": "error",
                        "message": f"Execution timed out or error during wait: {str(e)}",
                        "execution_time": timeout,
                        "error": True
                    }

                # Get container logs
                try:
                    logs_bytes = await asyncio.to_thread(container.logs)
                    logs = logs_bytes.decode("utf-8")

                    # Parse the JSON output from the runner
                    try:
                        json_start = logs.find("__RESULTS_JSON_START__")
                        json_end = logs.find("__RESULTS_JSON_END__")

                        if json_start >= 0 and json_end > json_start:
                            json_data = logs[json_start + len("__RESULTS_JSON_START__"):json_end].strip()
                            results = json.loads(json_data)
                            results["logs"] = logs
                            return results
                        else:
                            return {
                                "status": "error",
                                "message": "Failed to parse execution results from logs",
                                "logs": logs,
                                "error": True
                            }
                    except json.JSONDecodeError:
                        return {
                            "status": "error",
                            "message": "Failed to parse execution results JSON from logs",
                            "logs": logs,
                            "error": True
                        }
                except Exception as log_exc:
                    logger.error(f"Error retrieving logs for container {container_name}: {log_exc}")
                    return {
                        "status": "error",
                        "message": f"Failed to retrieve execution logs: {str(log_exc)}",
                        "error": True
                    }

            except ContainerError as e:
                return {
                    "status": "error",
                    "message": f"Container execution failed: {str(e)}",
                    "stderr": e.stderr.decode("utf-8") if hasattr(e, "stderr") and e.stderr else "",
                    "error": True
                }
            except ImageNotFound:
                return {
                    "status": "error",
                    "message": "Node.js Docker image not found",
                    "error": True
                }
            except Exception as e:
                logger.error(f"Docker execution error: {str(e)}")
                return {
                    "status": "error",
                    "message": f"Execution error: {str(e)}",
                    "error": True
                }
            finally:
                if container:
                    try:
                        # Explicitly remove the container
                        await asyncio.to_thread(container.remove, force=True)
                        logger.debug(f"Successfully removed JS container {container_name}")
                    except DockerException as e:
                        logger.warning(f"Error during explicit container cleanup for {container_name}: {e}")

        finally:
            # Clean up temporary directory
            if os.path.exists(temp_dir):
                 await asyncio.to_thread(shutil.rmtree, temp_dir, ignore_errors=True)

    # Helper methods for file operations to be used with asyncio.to_thread
    def _write_file(self, file_path: str, content: str):
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

    def _write_json_file(self, file_path: str, data: Any):
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f)

    @staticmethod
    def _generate_python_test_runner(test_cases: List[Dict[str, Any]], function_name: Optional[str] = None) -> str:
        """
        Generate a Python test runner script for the Docker container.
        
        Args:
            test_cases: List of test cases to run
            function_name: Name of the function to test (extracted from code if None)
            
        Returns:
            Python script code for the test runner
        """
        return """
import sys
import io
import time
import json
import ast
from contextlib import redirect_stdout, redirect_stderr

# Load the candidate's code
with open("code.py", "r") as f:
    code = f.read()

# Load the test cases
with open("test_cases.json", "r") as f:
    test_cases = json.load(f)

# Function to extract the function name from the code
def extract_function_name(code):
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                return node.name
        raise ValueError("No function definition found in code")
    except Exception as e:
        raise ValueError(f"Error parsing code: {{str(e)}}")

# Determine the function name
function_name = "{}"
if not function_name:
    try:
        function_name = extract_function_name(code)
    except Exception as e:
        print(f"Error extracting function name: {{str(e)}}")
        results = {{
            "status": "error",
            "error_message": f"Could not identify a function to test: {{str(e)}}"
        }}
        print("__RESULTS_JSON_START__")
        print(json.dumps(results))
        print("__RESULTS_JSON_END__")
        sys.exit(1)

# Prepare results
results = {{
    "status": "success",
    "passed": 0,
    "failed": 0,
    "error": False,
    "execution_time": 0,
    "test_results": []
}}

# Execute the code to define the function
try:
    namespace = {{}};
    exec(code, namespace)

    # Check if function exists
    if function_name not in namespace:
        results["status"] = "error"
        results["error_message"] = f"Function '{{function_name}}' not found in code"
        print("__RESULTS_JSON_START__")
        print(json.dumps(results))
        print("__RESULTS_JSON_END__")
        sys.exit(1)

    # Get the function
    function = namespace[function_name]

    # Execute test cases
    total_time = 0

    for i, test_case in enumerate(test_cases):
        test_input = test_case["input"]
        expected_output = test_case["expected_output"]

        # Prepare test result
        test_result = {{
            "test_case_id": i + 1,
            "input": test_input,
            "expected_output": expected_output,
            "is_hidden": test_case.get("is_hidden", False),
            "explanation": test_case.get("explanation", ""),
            "passed": False,
            "execution_time": 0,
            "output": None,
            "error": None
        }}

        # Capture stdout and stderr
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

            # Get stdout and stderr content
            stdout_content = stdout_buffer.getvalue()
            stderr_content = stderr_buffer.getvalue()

            # Check if output matches expected output
            output_matches = False
            if actual_output == expected_output:
                output_matches = True
            elif (isinstance(actual_output, (list, tuple)) and 
                  isinstance(expected_output, (list, tuple)) and
                  len(actual_output) == len(expected_output) and
                  all(a == e for a, e in zip(actual_output, expected_output))):
                output_matches = True
            elif (isinstance(actual_output, dict) and 
                  isinstance(expected_output, dict) and
                  len(actual_output) == len(expected_output) and
                  all(actual_output.get(k) == v for k, v in expected_output.items())):
                output_matches = True

            if output_matches:
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
            import traceback
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
    results["detailed_metrics"] = {{
        "avg_execution_time": total_time / len(test_cases) if test_cases else 0,
        "max_execution_time": max((t["execution_time"] for t in results["test_results"]), default=0),
        "success_rate": results["passed"] / len(test_cases) if test_cases else 0
    }}

except Exception as e:
    import traceback
    results["status"] = "error"
    results["error_message"] = str(e)
    results["traceback"] = traceback.format_exc()

# Output the results as JSON
print("__RESULTS_JSON_START__")
print(json.dumps(results))
print("__RESULTS_JSON_END__")
""".format(function_name or "")
    
    @staticmethod
    def _generate_javascript_test_runner(test_cases: List[Dict[str, Any]], function_name: Optional[str] = None) -> str:
        """
        Generate a JavaScript test runner script for the Docker container.
        
        Args:
            test_cases: List of test cases to run
            function_name: Name of the function to test
            
        Returns:
            JavaScript script code for the test runner
        """
        return """
const fs = require('fs');

// Load the candidate's code
const code = fs.readFileSync('code.js', 'utf8');

// Load the test cases
const testCases = JSON.parse(fs.readFileSync('test_cases.json', 'utf8'));

// Function to extract the function name from the code (basic implementation)
function extractFunctionName(code) {
    const functionRegex = /function\\s+([a-zA-Z0-9_]+)\\s*\\(/;
    const arrowFunctionRegex = /const\\s+([a-zA-Z0-9_]+)\\s*=\\s*\\(?.*\\)?\\s*=>/;
    
    const functionMatch = code.match(functionRegex);
    if (functionMatch) return functionMatch[1];
    
    const arrowMatch = code.match(arrowFunctionRegex);
    if (arrowMatch) return arrowMatch[1];
    
    throw new Error("No function definition found in code");
}

// Determine the function name
let functionName = "{functionName}";
if (!functionName) {
    try {
        functionName = extractFunctionName(code);
    } catch (e) {
        console.error(`Error extracting function name: ${e.message}`);
        const results = {
            status: "error",
            error_message: `Could not identify a function to test: ${e.message}`
        };
        console.log("__RESULTS_JSON_START__");
        console.log(JSON.stringify(results));
        console.log("__RESULTS_JSON_END__");
        process.exit(1);
    }
}

// Prepare results
const results = {
    status: "success",
    passed: 0,
    failed: 0,
    error: false,
    execution_time: 0,
    test_results: []
};

// Execute the code to define the function
try {
    // Create a new context and evaluate the code
    eval(code);
    
    // Check if function exists
    if (typeof global[functionName] !== 'function') {
        results.status = "error";
        results.error_message = `Function '${functionName}' not found in code`;
        console.log("__RESULTS_JSON_START__");
        console.log(JSON.stringify(results));
        console.log("__RESULTS_JSON_END__");
        process.exit(1);
    }
    
    // Get the function
    const fn = global[functionName];
    
    // Execute test cases
    let totalTime = 0;
    
    testCases.forEach((testCase, i) => {
        const testInput = testCase.input;
        const expectedOutput = testCase.expected_output;
        
        // Prepare test result
        const testResult = {
            test_case_id: i + 1,
            input: testInput,
            expected_output: expectedOutput,
            is_hidden: testCase.is_hidden || false,
            explanation: testCase.explanation || "",
            passed: false,
            execution_time: 0,
            output: null,
            error: null
        };
        
        try {
            // Measure execution time
            const startTime = Date.now();
            
            // Execute function
            let actualOutput;
            if (Array.isArray(testInput)) {
                actualOutput = fn(...testInput);
            } else if (typeof testInput === 'object' && testInput !== null && !Array.isArray(testInput)) {
                actualOutput = fn(testInput);
            } else {
                actualOutput = fn(testInput);
            }
            
            // Calculate execution time
            const executionTime = (Date.now() - startTime) / 1000;
            totalTime += executionTime;
            
            // Check if output matches expected output
            let outputMatches = false;
            
            // Handle various output types
            if (JSON.stringify(actualOutput) === JSON.stringify(expectedOutput)) {
                outputMatches = true;
            }
            
            if (outputMatches) {
                testResult.passed = true;
                results.passed++;
            } else {
                testResult.passed = false;
                results.failed++;
            }
            
            // Add actual output and execution information
            testResult.output = actualOutput;
            testResult.execution_time = executionTime;
            
        } catch (e) {
            // Handle exceptions
            testResult.passed = false;
            testResult.error = e.message;
            testResult.stack = e.stack;
            results.failed++;
        }
        
        // Add test result
        results.test_results.push(testResult);
    });
    
    // Calculate overall metrics
    results.execution_time = totalTime;
    results.all_passed = results.failed === 0;
    results.detailed_metrics = {
        avg_execution_time: testCases.length ? totalTime / testCases.length : 0,
        max_execution_time: Math.max(...results.test_results.map(t => t.execution_time)),
        success_rate: testCases.length ? results.passed / testCases.length : 0
    };
    
} catch (e) {
    // Handle exceptions during code execution setup
    results.status = "error";
    results.error_message = e.message;
    results.stack = e.stack;
}

// Output the results as JSON
console.log("__RESULTS_JSON_START__");
console.log(JSON.stringify(results));
console.log("__RESULTS_JSON_END__");
""".replace("{functionName}", function_name or "")

    def check_docker_requirements(self) -> Dict[str, Any]:
        """
        Check if Docker is installed and available.
        
        Returns:
            Dictionary with check results
        """
        try:
            # Check if Docker is installed
            try:
                version = self.client.version()
                return {
                    "status": "success",
                    "docker_available": True,
                    "version": version
                }
            except DockerException:
                # Try using docker CLI
                try:
                    result = subprocess.run(["docker", "--version"], capture_output=True, text=True)
                    if result.returncode == 0:
                        return {
                            "status": "success",
                            "docker_available": True,
                            "version": result.stdout.strip(),
                            "note": "Docker API not available, using CLI"
                        }
                    else:
                        return {
                            "status": "error",
                            "docker_available": False,
                            "message": "Docker CLI unavailable"
                        }
                except:
                    return {
                        "status": "error",
                        "docker_available": False,
                        "message": "Docker not installed or not in PATH"
                    }
        except Exception as e:
            return {
                "status": "error",
                "docker_available": False,
                "message": str(e)
            }

    async def execute_code_with_stdin(
        self,
        language: str,
        code: str,
        input_str: str = "",
        memory_limit: str = DEFAULT_MEMORY_LIMIT,
        cpu_limit: float = DEFAULT_CPU_LIMIT,
        timeout: int = DEFAULT_TIMEOUT,
        network_disabled: bool = DEFAULT_NETWORK_DISABLED
    ) -> Dict[str, Any]:
        """
        Execute code with provided standard input in a Docker container.

        Args:
            language: Programming language (python, javascript, etc.)
            code: Source code to execute
            input_str: String to pass as standard input to the code
            memory_limit: Container memory limit
            cpu_limit: Container CPU limit
            timeout: Execution timeout in seconds
            network_disabled: Whether to disable network access

        Returns:
            Dictionary with execution results (stdout, stderr, status, error_message)
        """
        language = language.lower()
        if language == "python":
            return await self._execute_python_with_stdin(code, input_str, memory_limit, cpu_limit, timeout, network_disabled)
        elif language in ["javascript", "js"]:
            return await self._execute_javascript_with_stdin(code, input_str, memory_limit, cpu_limit, timeout, network_disabled)
        else:
            return {
                "status": "error",
                "error_message": f"Unsupported language for stdin execution: {language}",
                "stdout": "",
                "stderr": f"Unsupported language: {language}"
            }

    async def _execute_python_with_stdin(
        self,
        code: str,
        input_str: str,
        memory_limit: str,
        cpu_limit: float,
        timeout: int,
        network_disabled: bool
    ) -> Dict[str, Any]:
        temp_dir = await asyncio.to_thread(tempfile.mkdtemp, prefix="ai_interviewer_py_stdin_")
        container = None
        try:
            code_py_path = os.path.join(temp_dir, "code.py")
            await asyncio.to_thread(self._write_file, code_py_path, code)

            input_txt_path = os.path.join(temp_dir, "input.txt")
            await asyncio.to_thread(self._write_file, input_txt_path, input_str)

            runner_code = self._generate_python_stdin_runner()
            runner_py_path = os.path.join(temp_dir, "runner.py")
            await asyncio.to_thread(self._write_file, runner_py_path, runner_code)

            container_name = f"ai-interviewer-py-stdin-{uuid.uuid4().hex[:8]}"
            container_settings = {
                "image": "python:3.10-slim",
                "volumes": {temp_dir: {"bind": "/app", "mode": "ro"}},
                "working_dir": "/app",
                "command": ["python", "runner.py"],
                "mem_limit": memory_limit,
                "cpu_quota": int(cpu_limit * 100000),
                "network_disabled": network_disabled,
                "name": container_name,
                "detach": True,
                "read_only": True, # Keep rootfs read-only
            }
            container = await asyncio.to_thread(self.client.containers.run, **container_settings)
            
            try:
                await asyncio.to_thread(container.wait, timeout=timeout)
            except Exception as e: # Covers timeout from container.wait
                if container:
                    try: await asyncio.to_thread(container.stop, timeout=1)
                    except Exception as stop_exc: logger.warning(f"Failed to stop container {container_name} during timeout: {stop_exc}")
                return {
                    "status": "error", 
                    "error_message": "Execution timed out", 
                    "stdout": "", 
                    "stderr": f"Execution timed out after {timeout} seconds.",
                    "execution_time": timeout
                }

            logs_bytes = await asyncio.to_thread(container.logs, stdout=True, stderr=True)
            logs_str = logs_bytes.decode("utf-8", errors="replace")
            
            # Split logs into stdout and potential stderr if runner script uses markers
            # For stdin runner, output is simpler: stdout then RESULTS_SEPARATOR then stderr
            parts = logs_str.split("__STDERR_RESULTS_SEPARATOR__", 1)
            stdout_content = parts[0]
            stderr_content = parts[1] if len(parts) > 1 else ""

            if stderr_content.strip(): # If there's anything in stderr, consider it an execution error
                 return {"status": "error", "error_message": "Runtime error", "stdout": stdout_content.strip(), "stderr": stderr_content.strip()}
            
            return {"status": "success", "stdout": stdout_content.strip(), "stderr": stderr_content.strip()}

        except ImageNotFound:
            return {"status": "error", "error_message": "Python Docker image not found", "stdout": "", "stderr": "Python Docker image not found"}
        except ContainerError as e:
            return {"status": "error", "error_message": "Container execution failed", "stdout": "", "stderr": e.stderr.decode("utf-8") if hasattr(e, "stderr") and e.stderr else str(e)}
        except Exception as e:
            logger.error(f"Python stdin execution error: {str(e)}", exc_info=True)
            return {"status": "error", "error_message": f"Execution error: {str(e)}", "stdout": "", "stderr": str(e)}
        finally:
            if container:
                try:
                    await asyncio.to_thread(container.remove, force=True)
                    logger.debug(f"Successfully removed Python STDIN container {container_name}")
                except DockerException as e: logger.warning(f"Error cleaning up container {container_name}: {e}")
            if os.path.exists(temp_dir):
                await asyncio.to_thread(shutil.rmtree, temp_dir, ignore_errors=True)

    async def _execute_javascript_with_stdin(
        self,
        code: str,
        input_str: str,
        memory_limit: str,
        cpu_limit: float,
        timeout: int,
        network_disabled: bool
    ) -> Dict[str, Any]:
        temp_dir = await asyncio.to_thread(tempfile.mkdtemp, prefix="ai_interviewer_js_stdin_")
        container = None
        try:
            code_js_path = os.path.join(temp_dir, "code.js")
            await asyncio.to_thread(self._write_file, code_js_path, code)

            input_txt_path = os.path.join(temp_dir, "input.txt") # For JS runner to read
            await asyncio.to_thread(self._write_file, input_txt_path, input_str)

            runner_code = self._generate_javascript_stdin_runner()
            runner_js_path = os.path.join(temp_dir, "runner.js")
            await asyncio.to_thread(self._write_file, runner_js_path, runner_code)

            container_name = f"ai-interviewer-js-stdin-{uuid.uuid4().hex[:8]}"
            container_settings = {
                "image": "node:18-slim",
                "volumes": {temp_dir: {"bind": "/app", "mode": "ro"}},
                "working_dir": "/app",
                "command": ["node", "runner.js"],
                "mem_limit": memory_limit,
                "cpu_quota": int(cpu_limit * 100000),
                "network_disabled": network_disabled,
                "name": container_name,
                "detach": True,
                "read_only": True,
            }
            container = await asyncio.to_thread(self.client.containers.run, **container_settings)

            try:
                await asyncio.to_thread(container.wait, timeout=timeout)
            except Exception as e: # Covers timeout
                if container:
                    try: await asyncio.to_thread(container.stop, timeout=1)
                    except Exception as stop_exc: logger.warning(f"Failed to stop JS container {container_name} during timeout: {stop_exc}")
                return {
                    "status": "error", 
                    "error_message": "Execution timed out", 
                    "stdout": "", 
                    "stderr": f"Execution timed out after {timeout} seconds.",
                    "execution_time": timeout
                }

            logs_bytes = await asyncio.to_thread(container.logs, stdout=True, stderr=True)
            logs_str = logs_bytes.decode("utf-8", errors="replace")

            parts = logs_str.split("__STDERR_RESULTS_SEPARATOR__", 1)
            stdout_content = parts[0]
            stderr_content = parts[1] if len(parts) > 1 else ""

            if stderr_content.strip():
                 return {"status": "error", "error_message": "Runtime error", "stdout": stdout_content.strip(), "stderr": stderr_content.strip()}

            return {"status": "success", "stdout": stdout_content.strip(), "stderr": stderr_content.strip()}

        except ImageNotFound:
            return {"status": "error", "error_message": "Node.js Docker image not found", "stdout": "", "stderr": "Node.js Docker image not found"}
        except ContainerError as e:
            return {"status": "error", "error_message": "Container execution failed", "stdout": "", "stderr": e.stderr.decode("utf-8") if hasattr(e, "stderr") and e.stderr else str(e)}
        except Exception as e:
            logger.error(f"JavaScript stdin execution error: {str(e)}", exc_info=True)
            return {"status": "error", "error_message": f"Execution error: {str(e)}", "stdout": "", "stderr": str(e)}
        finally:
            if container:
                try:
                    await asyncio.to_thread(container.remove, force=True)
                    logger.debug(f"Successfully removed JS STDIN container {container_name}")
                except DockerException as e: logger.warning(f"Error cleaning up JS container {container_name}: {e}")
            if os.path.exists(temp_dir):
                await asyncio.to_thread(shutil.rmtree, temp_dir, ignore_errors=True)

    @staticmethod
    def _generate_python_stdin_runner() -> str:
        """Generate a Python runner script for stdin execution."""
        return '''
import sys
import os

try:
    # Read user's code
    with open("code.py", "r", encoding="utf-8") as f:
        user_code = f.read()

    # Read input string
    input_str = ""
    if os.path.exists("input.txt"):
        with open("input.txt", "r", encoding="utf-8") as f:
            input_str = f.read()

    # Prepare to capture stdout and stderr
    from io import StringIO
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    redirected_stdout = StringIO()
    redirected_stderr = StringIO()

    sys.stdout = redirected_stdout
    sys.stderr = redirected_stderr

    # Provide input_str to stdin
    old_stdin = sys.stdin
    sys.stdin = StringIO(input_str)

    # Execute the user's code
    exec(user_code, {}) # Execute in a new, empty global scope

    sys.stdout = old_stdout
    sys.stderr = old_stderr
    sys.stdin = old_stdin

    stdout_val = redirected_stdout.getvalue()
    stderr_val = redirected_stderr.getvalue()

    # Print stdout, then separator, then stderr
    print(stdout_val, end="")
    print("__STDERR_RESULTS_SEPARATOR__", end="")
    print(stderr_val, end="")

except Exception as e:
    sys.stdout = old_stdout # Ensure original stdout is restored
    sys.stderr = old_stderr # Ensure original stderr is restored
    sys.stdin = old_stdin
    # Print nothing to stdout, separator, then error to stderr
    print("__STDERR_RESULTS_SEPARATOR__", end="")
    import traceback
    print("Runner script error:", str(e), file=sys.__stderr__)
    print(traceback.format_exc(), file=sys.__stderr__)
'''

    @staticmethod
    def _generate_javascript_stdin_runner() -> str:
        """Generate a JavaScript runner script for stdin execution."""
        return '''
const fs = require('fs');

async function main() {
    try {
        const userCode = fs.readFileSync('code.js', 'utf8');
        let inputStr = '';
        if (fs.existsSync('input.txt')) {
            inputStr = fs.readFileSync('input.txt', 'utf8');
        }

        // Temporarily override console.log and console.error
        let capturedStdout = '';
        let capturedStderr = '';
        const origConsoleLog = console.log;
        const origConsoleError = console.error;

        console.log = (...args) => {
            capturedStdout += args.map(arg => String(arg)).join(' ') + '\n';
        };
        console.error = (...args) => {
            capturedStderr += args.map(arg => String(arg)).join(' ') + '\n';
        };

        // Mock process.stdin
        const Readable = require('stream').Readable;
        const mockStdin = new Readable();
        mockStdin.push(inputStr);
        mockStdin.push(null); // Signifies EOF
        const origProcessStdin = process.stdin;
        process.stdin = mockStdin;

        // Evaluate the user's code
        // Using a new Function to scope the code and allow async execution if user code is async
        const AsyncFunction = Object.getPrototypeOf(async function(){}).constructor;
        const userFunction = new AsyncFunction(userCode);
        await userFunction();

        // Restore original console and stdin
        console.log = origConsoleLog;
        console.error = origConsoleError;
        process.stdin = origProcessStdin;

        // Output captured stdout, separator, then captured stderr
        origConsoleLog(capturedStdout + "__STDERR_RESULTS_SEPARATOR__" + capturedStderr);

    } catch (e) {
        // Restore original console and stdin on error
        if (typeof origConsoleLog !== 'undefined') console.log = origConsoleLog;
        if (typeof origConsoleError !== 'undefined') console.error = origConsoleError;
        if (typeof origProcessStdin !== 'undefined') process.stdin = origProcessStdin;
        
        // Output separator and error to actual stderr
        // (console.error was restored, so this goes to actual stderr)
        console.error("__STDERR_RESULTS_SEPARATOR__" + `Runner script error: ${e.stack || e}`);
    }
}

main();
''' 