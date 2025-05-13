#!/usr/bin/env python
"""
Test script for enhanced response analysis.

This script demonstrates the functionality of the enhanced response analysis tool
that extracts key concepts and assesses depth of understanding.
"""
import json
import logging
import sys
import os

# Add the parent directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from ai_interviewer.tools.question_tools import analyze_candidate_response

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def pretty_print_json(data):
    """Pretty print a JSON object"""
    print(json.dumps(data, indent=2))
    print("-" * 80)


def test_depth_analysis():
    """Test the enhanced depth of understanding analysis"""
    print("\n=== Testing Enhanced Response Analysis Tool ===\n")
    
    # Test 1: Deep understanding response
    print("Test 1: Analyze a response demonstrating deep understanding")
    question = "Explain the concept of closures in JavaScript and why they're useful."
    response = """
    Closures in JavaScript occur when a function retains access to variables from its outer (enclosing) lexical scope, even after the outer function has finished executing. This happens because functions in JavaScript form closures at creation time, capturing their environment.

    For example, when you define a function inside another function, the inner function has access to the variables of the outer function, even after the outer function has returned. This creates a private state that persists across function calls.

    Closures are particularly useful for:
    1. Data encapsulation and private variables - They allow you to create private variables that can't be accessed directly from outside.
    2. Factory functions - Creating functions with pre-set parameters or behavior.
    3. Callback functions - Preserving the state when a function will be executed later.
    4. Module pattern - Creating modules with private and public methods.

    The key to understanding closures is recognizing that functions in JavaScript don't just capture the values of variables, but the actual variable bindings themselves, meaning they reflect changes to those variables even after the outer function has returned.

    A common issue with closures is in loops - if you're not careful, they might capture the final value of a loop variable rather than its current value, which can be addressed with block-scoped variables (let) or creating new function scopes.
    """
    
    analysis_result = analyze_candidate_response(
        question=question,
        response=response,
        job_role="Frontend Developer",
        skill_areas=["JavaScript", "Programming Concepts"],
        expected_topics=["Closure definition", "Lexical scope", "Practical applications"],
        experience_level="advanced"
    )
    pretty_print_json(analysis_result)
    
    # Test 2: Shallow understanding response
    print("Test 2: Analyze a response demonstrating shallow understanding")
    question = "Explain the concept of closures in JavaScript and why they're useful."
    response = """
    Closures in JavaScript are when a function can access variables from its parent function. They're useful because you can use them to create private variables and for callbacks. I've used them in my code before when working with event handlers and for creating modules.
    """
    
    analysis_result = analyze_candidate_response(
        question=question,
        response=response,
        job_role="Frontend Developer",
        skill_areas=["JavaScript", "Programming Concepts"],
        expected_topics=["Closure definition", "Lexical scope", "Practical applications"],
        experience_level="intermediate"
    )
    pretty_print_json(analysis_result)
    
    # Test 3: Response with misconceptions
    print("Test 3: Analyze a response with technical misconceptions")
    question = "Explain how React's virtual DOM works and its benefits."
    response = """
    React's virtual DOM is a copy of the real DOM. When the state of a component changes, React rebuilds the entire virtual DOM from scratch and then compares it with the old virtual DOM. It then updates only the parts of the real DOM that have changed.

    The main benefit is speed - because the virtual DOM is stored in memory, it's much faster than accessing the real DOM directly. Also, React batches all DOM updates and performs them at once, which is more efficient than updating the DOM for every small change.

    The virtual DOM is faster because it avoids reflow and repaint in the browser, which are expensive operations. Every time you change something in the DOM, the browser has to recalculate the CSS, do a layout, and then repaint the screen.
    """
    
    analysis_result = analyze_candidate_response(
        question=question,
        response=response,
        job_role="Frontend Developer",
        skill_areas=["React", "JavaScript", "Web Performance"],
        expected_topics=["Virtual DOM concept", "Reconciliation", "Performance benefits", "Diffing algorithm"],
        experience_level="intermediate"
    )
    pretty_print_json(analysis_result)
    
    # Test 4: Test with different experience level expectation
    print("Test 4: Analyze a response from a beginner candidate")
    question = "What is a RESTful API and how does it work?"
    response = """
    A RESTful API is a way for different systems to communicate over the internet. It uses HTTP methods like GET, POST, PUT, and DELETE to perform operations on resources. Each resource has a unique URL, and you can get or modify data by making requests to these URLs.
    
    For example, to get a list of users, you might make a GET request to "/api/users". To create a new user, you'd make a POST request to the same URL with the user data. REST APIs usually return data in JSON format, which is easy for applications to work with.
    
    I've worked with REST APIs in a few small projects, mostly by using the fetch API in JavaScript to get data from a server.
    """
    
    analysis_result = analyze_candidate_response(
        question=question,
        response=response,
        job_role="Backend Developer",
        skill_areas=["API Design", "Web Development"],
        expected_topics=["REST principles", "HTTP methods", "Resource-based design"],
        experience_level="beginner"
    )
    pretty_print_json(analysis_result)


if __name__ == "__main__":
    test_depth_analysis() 