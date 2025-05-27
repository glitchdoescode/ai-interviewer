import asyncio
import sys
import os
from pathlib import Path

# Add the project root to the Python path to make imports work
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from ai_interviewer.tools.code_execution import execute_candidate_code, SafetyChecker

async def main():
    print("Starting code execution tests...")
    
    # Test 1: Simple Python function
    code = """
def add(a, b):
    return a + b
"""
    test_cases = [
        {"input": [1, 2], "expected_output": 3},
        {"input": [-1, 1], "expected_output": 0}
    ]
    
    print("\nTest 1: Testing simple Python function")
    result = await execute_candidate_code.ainvoke({
        "language": "python",
        "code": code,
        "test_cases": test_cases
    })
    print(f"Test 1 Result: {result}")
    
    # Test 2: Timeout
    code_timeout = """
def slow(n):
    import time
    time.sleep(2)  # Set to 2 seconds to make test faster
    return n
"""
    test_cases_timeout = [{"input": [1], "expected_output": 1}]
    
    print("\nTest 2: Testing timeout handling")
    result_timeout = await execute_candidate_code.ainvoke({
        "language": "python",
        "code": code_timeout,
        "test_cases": test_cases_timeout
    })
    print(f"Test 2 Result: {result_timeout}")
    
    # Test 3: Safety Checker
    dangerous_code = """
import os
def dangerous():
    os.system('echo "This is potentially dangerous"')
    return True
"""
    print("\nTest 3: Testing code safety checker")
    is_safe, message = await SafetyChecker.check_python_code_safety(dangerous_code)
    print(f"Test 3 Result: Safe={is_safe}, Message={message}")
    
    # Test 4: Syntax Error
    invalid_code = """
def broken_function(x):
    return x +  # Syntax error: missing operand
"""
    test_cases_invalid = [{"input": [1], "expected_output": 1}]
    
    print("\nTest 4: Testing syntax error handling")
    result_invalid = await execute_candidate_code.ainvoke({
        "language": "python",
        "code": invalid_code,
        "test_cases": test_cases_invalid
    })
    print(f"Test 4 Result: {result_invalid}")
    
    print("\nAll tests completed.")

if __name__ == "__main__":
    asyncio.run(main())