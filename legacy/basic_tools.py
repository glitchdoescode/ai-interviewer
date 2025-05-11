"""
Basic tools for the AI Interviewer platform.

This module contains simple tool implementations for the interview process.
"""
import logging
import uuid
from typing import List, Dict, Optional

from langchain_core.tools import tool

# Configure logging
logger = logging.getLogger(__name__)

# Sample questions for different topics (for MVP)
SAMPLE_QUESTIONS = {
    "python": [
        {
            "id": "py_001",
            "text": "Can you explain what list comprehensions are in Python and provide a simple example?",
            "expected_keywords": ["iteration", "concise", "syntax", "list", "expression", "for loop"]
        },
        {
            "id": "py_002",
            "text": "How would you handle exceptions in Python and why is it important?",
            "expected_keywords": ["try", "except", "finally", "raise", "error handling", "robustness"]
        }
    ],
    "javascript": [
        {
            "id": "js_001",
            "text": "Explain the difference between '==' and '===' in JavaScript with examples.",
            "expected_keywords": ["equality", "type", "coercion", "strict", "comparison", "value"]
        },
        {
            "id": "js_002",
            "text": "Describe closure in JavaScript and how it can be useful.",
            "expected_keywords": ["scope", "function", "variable", "lexical", "private", "data"]
        }
    ],
    "data_structures": [
        {
            "id": "ds_001",
            "text": "Compare and contrast arrays and linked lists. When would you use one over the other?",
            "expected_keywords": ["memory", "access", "insertion", "deletion", "contiguous", "pointer"]
        },
        {
            "id": "ds_002",
            "text": "Explain what a hash table is and describe its time complexity for common operations.",
            "expected_keywords": ["key", "value", "collision", "O(1)", "lookup", "hash function"]
        }
    ],
    "general": [
        {
            "id": "gen_001",
            "text": "Tell me about a challenging technical problem you solved recently.",
            "expected_keywords": ["problem", "solution", "approach", "outcome", "learned"]
        },
        {
            "id": "gen_002",
            "text": "How do you stay updated with new technologies and programming languages?",
            "expected_keywords": ["learning", "resources", "projects", "community", "practice"]
        }
    ]
}


@tool
def get_next_question(topic: str = "general") -> Dict:
    """
    Retrieve a technical interview question based on the specified topic.
    
    Args:
        topic: The interview topic (python, javascript, data_structures, general)
        
    Returns:
        A dictionary containing the question ID, text, and expected keywords
    """
    logger.info(f"Getting next question for topic: {topic}")
    
    # Get questions for the topic, defaulting to general if not found
    questions = SAMPLE_QUESTIONS.get(topic.lower(), SAMPLE_QUESTIONS["general"])
    
    # For MVP, just return the first question
    # In a real implementation, we would track asked questions and select a new one
    question = questions[0]
    
    logger.info(f"Selected question: {question['id']}")
    return {
        "question_id": question["id"],
        "question_text": question["text"],
        "expected_answer_keywords": question["expected_keywords"]
    }


@tool
def submit_answer(question_id: str, answer: str) -> Dict:
    """
    Submit an answer to the current question.
    
    Args:
        question_id: The ID of the question being answered
        answer: The candidate's answer to the current question
        
    Returns:
        A dictionary with evaluation results
    """
    logger.info(f"Answer submitted for question {question_id}: {answer[:50]}...")
    
    # Find the question from the sample questions
    question_data = None
    for topic, questions in SAMPLE_QUESTIONS.items():
        for question in questions:
            if question["id"] == question_id:
                question_data = question
                break
        if question_data:
            break
    
    # Simple evaluation based on keyword presence
    evaluation = {
        "score": 0,
        "feedback": "Answer recorded."
    }
    
    if question_data:
        # Count how many expected keywords are in the answer
        keywords_found = []
        for keyword in question_data["expected_keywords"]:
            if keyword.lower() in answer.lower():
                keywords_found.append(keyword)
        
        # Calculate score based on keyword matches
        keyword_ratio = len(keywords_found) / len(question_data["expected_keywords"])
        score = min(5, int(keyword_ratio * 5) + 1)  # 1-5 score
        
        evaluation = {
            "score": score,
            "keywords_found": keywords_found,
            "keywords_missing": [kw for kw in question_data["expected_keywords"] if kw not in keywords_found],
            "feedback": f"Answer evaluated with score {score}/5."
        }
    
    return {
        "status": "success",
        "question_id": question_id,
        "evaluation": evaluation
    } 