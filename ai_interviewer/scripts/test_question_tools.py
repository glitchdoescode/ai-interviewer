#!/usr/bin/env python
"""
Test script for question generation tools.

This script demonstrates the functionality of the question generation tools
by generating sample questions for different job roles and difficulty levels.
"""
import json
import logging
import sys
import os

# Add the parent directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from ai_interviewer.tools.question_tools import generate_interview_question, analyze_candidate_response

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


def test_question_generation():
    """Test the question generation tool with various parameters"""
    print("\n=== Testing Question Generation Tool ===\n")
    
    # Test 1: Basic question for a frontend developer
    print("Test 1: Generate a basic question for a frontend developer")
    question_result = generate_interview_question(
        job_role="Frontend Developer",
        skill_areas=["JavaScript", "React", "CSS"],
        difficulty_level="intermediate"
    )
    pretty_print_json(question_result)
    
    # Test 2: Question with previous context
    print("Test 2: Generate a follow-up question based on previous response")
    previous_questions = [
        "Can you explain the difference between controlled and uncontrolled components in React?"
    ]
    previous_responses = [
        "In React, controlled components are those where form data is handled by the React component state. The component maintains and updates state based on user input. Uncontrolled components, on the other hand, store form data in the DOM itself, not in component state. You would use refs to access the values from the DOM directly."
    ]
    
    question_result = generate_interview_question(
        job_role="Frontend Developer",
        skill_areas=["React", "State Management"],
        difficulty_level="advanced",
        previous_questions=previous_questions,
        previous_responses=previous_responses,
        follow_up_to=previous_responses[0]
    )
    pretty_print_json(question_result)
    
    # Test 3: Question for a different role
    print("Test 3: Generate a question for a backend developer")
    question_result = generate_interview_question(
        job_role="Backend Developer",
        skill_areas=["Python", "Databases", "API Design"],
        difficulty_level="intermediate"
    )
    pretty_print_json(question_result)
    

def test_response_analysis():
    """Test the response analysis tool"""
    print("\n=== Testing Response Analysis Tool ===\n")
    
    # Test analyzing a relatively strong response
    print("Test 1: Analyze a strong response")
    question = "How would you optimize a React application that's experiencing performance issues?"
    response = """
    To optimize a React application with performance issues, I'd first identify the root causes using 
    tools like React DevTools Profiler and Chrome Performance tab. Common issues include unnecessary 
    re-renders, which I'd fix using React.memo, useMemo, and useCallback to memoize components and values.
    
    For large lists, I'd implement virtualization with react-window or react-virtualized to render only 
    visible items. I'd also optimize bundle size by code-splitting with React.lazy and Suspense, enabling 
    lazy loading of components. Using efficient state management is crucial - sometimes context API 
    causes too many re-renders, so I might use Redux with selectors or libraries like Recoil for fine-grained 
    updates.
    
    Server-side rendering or static site generation can improve perceived performance. Finally, I'd use 
    performance monitoring in production to catch issues early.
    """
    
    analysis_result = analyze_candidate_response(
        question=question,
        response=response,
        job_role="Frontend Developer",
        skill_areas=["React", "Performance Optimization", "JavaScript"],
        expected_topics=["React rendering", "Code splitting", "State management", "Measuring performance"]
    )
    pretty_print_json(analysis_result)
    
    # Test analyzing a weaker response
    print("Test 2: Analyze a weaker response")
    question = "Explain the differences between REST and GraphQL APIs and when you might choose one over the other."
    response = "REST APIs are more common and use different HTTP methods. GraphQL is newer and gives exactly what you need. I prefer GraphQL because it's more modern, but REST is fine too."
    
    analysis_result = analyze_candidate_response(
        question=question,
        response=response,
        job_role="Backend Developer",
        skill_areas=["API Design", "GraphQL", "REST"],
        expected_topics=["REST principles", "GraphQL queries", "Over-fetching/under-fetching", "Use cases"]
    )
    pretty_print_json(analysis_result)


if __name__ == "__main__":
    test_question_generation()
    test_response_analysis() 