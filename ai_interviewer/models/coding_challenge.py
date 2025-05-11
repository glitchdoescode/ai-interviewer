"""
Coding Challenge definitions for the AI Interviewer platform.

This module defines the structure and sample data for coding challenges
that can be presented to candidates during the interview process.
"""
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field


class TestCase(BaseModel):
    """
    Represents a test case for a coding challenge.
    
    Attributes:
        input: The input values for the test case (could be any data type)
        expected_output: The expected output for the test case
        is_hidden: Whether this test case should be visible to the candidate
        explanation: Optional explanation of what this test case is checking
    """
    input: Any
    expected_output: Any
    is_hidden: bool = False
    explanation: Optional[str] = None


class CodingChallenge(BaseModel):
    """
    Represents a coding challenge to be presented to a candidate.
    
    Attributes:
        id: Unique identifier for the challenge
        title: Title of the challenge
        description: Detailed description of the problem
        difficulty: Relative difficulty level (easy, medium, hard)
        language: Primary programming language for the challenge
        starter_code: Initial code provided to the candidate
        test_cases: List of test cases to evaluate the solution
        time_limit_mins: Suggested time limit in minutes
        tags: Categories or topics related to this challenge
        hints: Optional hints that can be provided if the candidate gets stuck
    """
    id: str
    title: str
    description: str
    difficulty: str = "medium"
    language: str
    starter_code: str
    test_cases: List[TestCase]
    time_limit_mins: int = 20
    tags: List[str] = []
    hints: List[str] = []


# Sample coding challenges for different languages and difficulty levels
SAMPLE_CODING_CHALLENGES = {
    "py_001": CodingChallenge(
        id="py_001",
        title="String Reversal",
        description="""
Write a function `reverse_string(s)` that takes a string as input and returns the reverse of that string.

For example:
- Input: "hello"
- Output: "olleh"

Your solution should work for any string input.
""",
        difficulty="easy",
        language="python",
        starter_code="""def reverse_string(s: str) -> str:
    # Write your code here
    pass

# Example usage:
# print(reverse_string("hello"))  # Should print: olleh
""",
        test_cases=[
            TestCase(
                input="hello",
                expected_output="olleh",
                is_hidden=False,
                explanation="Basic string reversal"
            ),
            TestCase(
                input="",
                expected_output="",
                is_hidden=False,
                explanation="Empty string test case"
            ),
            TestCase(
                input="a",
                expected_output="a",
                is_hidden=False,
                explanation="Single character test case"
            ),
            TestCase(
                input="racecar",
                expected_output="racecar",
                is_hidden=True,
                explanation="Palindrome test case"
            ),
            TestCase(
                input="Python Programming",
                expected_output="gnimmargorP nohtyP",
                is_hidden=True,
                explanation="String with spaces"
            )
        ],
        time_limit_mins=5,
        tags=["strings", "basics"],
        hints=[
            "In Python, strings can be treated like arrays - you can access individual characters by index.",
            "Python has built-in capabilities for string manipulation, including slicing.",
            "Try using the slice notation with a negative step: s[::-1]"
        ]
    ),
    
    "py_002": CodingChallenge(
        id="py_002",
        title="FizzBuzz Implementation",
        description="""
Write a function `fizzbuzz(n)` that returns a list of strings for the numbers from 1 to n according to the following rules:
- For multiples of 3, add "Fizz" to the list
- For multiples of 5, add "Buzz" to the list
- For multiples of both 3 and 5, add "FizzBuzz" to the list
- For other numbers, add the string representation of the number to the list

For example, fizzbuzz(15) should return:
["1", "2", "Fizz", "4", "Buzz", "Fizz", "7", "8", "Fizz", "Buzz", "11", "Fizz", "13", "14", "FizzBuzz"]
""",
        difficulty="easy",
        language="python",
        starter_code="""def fizzbuzz(n: int) -> List[str]:
    # Write your code here
    pass

# Example usage:
# print(fizzbuzz(5))  # Should print: ["1", "2", "Fizz", "4", "Buzz"]
""",
        test_cases=[
            TestCase(
                input=5,
                expected_output=["1", "2", "Fizz", "4", "Buzz"],
                is_hidden=False,
                explanation="Basic test up to 5"
            ),
            TestCase(
                input=15,
                expected_output=["1", "2", "Fizz", "4", "Buzz", "Fizz", "7", "8", "Fizz", "Buzz", "11", "Fizz", "13", "14", "FizzBuzz"],
                is_hidden=False,
                explanation="Test up to 15, including a FizzBuzz"
            ),
            TestCase(
                input=1,
                expected_output=["1"],
                is_hidden=True,
                explanation="Edge case with just one number"
            )
        ],
        time_limit_mins=10,
        tags=["conditionals", "loops", "basics"],
        hints=[
            "Use the modulo operator (%) to check for divisibility.",
            "Remember to check for divisibility by both 3 and 5 first, before checking for each individually.",
            "You can use a for loop to iterate through the numbers from 1 to n."
        ]
    ),
    
    "js_001": CodingChallenge(
        id="js_001",
        title="Array Filter Implementation",
        description="""
Write a function `filterEvens(numbers)` that takes an array of numbers and returns a new array containing only the even numbers from the original array.

For example:
- Input: [1, 2, 3, 4, 5, 6]
- Output: [2, 4, 6]

Your solution should work for any valid array of numbers.
""",
        difficulty="easy",
        language="javascript",
        starter_code="""function filterEvens(numbers) {
    // Write your code here
}

// Example usage:
// console.log(filterEvens([1, 2, 3, 4, 5, 6]));  // Should print: [2, 4, 6]
""",
        test_cases=[
            TestCase(
                input=[1, 2, 3, 4, 5, 6],
                expected_output=[2, 4, 6],
                is_hidden=False,
                explanation="Basic even number filtering"
            ),
            TestCase(
                input=[1, 3, 5],
                expected_output=[],
                is_hidden=False,
                explanation="No even numbers in the array"
            ),
            TestCase(
                input=[2, 4, 6],
                expected_output=[2, 4, 6],
                is_hidden=False,
                explanation="All even numbers"
            ),
            TestCase(
                input=[],
                expected_output=[],
                is_hidden=True,
                explanation="Empty array edge case"
            )
        ],
        time_limit_mins=10,
        tags=["arrays", "filtering", "basics"],
        hints=[
            "You can use the modulo operator (%) to check if a number is even: num % 2 === 0",
            "Consider using Array methods like filter() for a concise solution.",
            "You can also implement this with a for loop and a new array."
        ]
    ),
    
    "py_003": CodingChallenge(
        id="py_003",
        title="Binary Search Implementation",
        description="""
Implement a binary search algorithm in a function `binary_search(arr, target)` that:
- Takes a sorted array `arr` and a target value `target`
- Returns the index of the target value if found, or -1 if not found

For example:
- Input: arr = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], target = 7
- Output: 6 (because 7 is at index 6 in the array)

Your implementation should have a time complexity of O(log n).
""",
        difficulty="medium",
        language="python",
        starter_code="""def binary_search(arr: List[int], target: int) -> int:
    # Write your code here
    pass

# Example usage:
# print(binary_search([1, 2, 3, 4, 5], 3))  # Should print: 2
""",
        test_cases=[
            TestCase(
                input={"arr": [1, 2, 3, 4, 5], "target": 3},
                expected_output=2,
                is_hidden=False,
                explanation="Target in the middle of the array"
            ),
            TestCase(
                input={"arr": [1, 2, 3, 4, 5], "target": 1},
                expected_output=0,
                is_hidden=False,
                explanation="Target at the beginning of the array"
            ),
            TestCase(
                input={"arr": [1, 2, 3, 4, 5], "target": 5},
                expected_output=4,
                is_hidden=False,
                explanation="Target at the end of the array"
            ),
            TestCase(
                input={"arr": [1, 2, 3, 4, 5], "target": 6},
                expected_output=-1,
                is_hidden=False,
                explanation="Target not in the array"
            ),
            TestCase(
                input={"arr": [], "target": 1},
                expected_output=-1,
                is_hidden=True,
                explanation="Empty array edge case"
            ),
            TestCase(
                input={"arr": [1, 3, 5, 7, 9, 11, 13, 15, 17, 19], "target": 7},
                expected_output=3,
                is_hidden=True,
                explanation="Larger array test"
            )
        ],
        time_limit_mins=15,
        tags=["algorithms", "binary search", "data structures"],
        hints=[
            "Start by defining low and high pointers at the beginning and end of the array.",
            "In each step, compare the middle element with the target value.",
            "If the middle element equals the target, you've found it. Otherwise, adjust your low or high pointer to search in the appropriate half.",
            "Continue until you find the target or the low pointer exceeds the high pointer."
        ]
    )
}


def get_coding_challenge(challenge_id: Optional[str] = None) -> CodingChallenge:
    """
    Retrieves a coding challenge by ID or a random challenge if no ID is provided.
    
    Args:
        challenge_id: Optional ID of the specific challenge to retrieve
        
    Returns:
        The requested coding challenge or a random challenge
    """
    import random
    
    if challenge_id and challenge_id in SAMPLE_CODING_CHALLENGES:
        return SAMPLE_CODING_CHALLENGES[challenge_id]
    
    # If no valid ID provided, return a random challenge
    random_id = random.choice(list(SAMPLE_CODING_CHALLENGES.keys()))
    return SAMPLE_CODING_CHALLENGES[random_id] 