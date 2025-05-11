"""
Dynamic tools for the AI Interviewer platform.

This module implements more advanced tools that use LLMs for dynamic content generation.
"""
import logging
import uuid
from typing import List, Dict, Optional

from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

# Configure logging
logger = logging.getLogger(__name__)

@tool
def generate_interview_question(
    current_topic: str, 
    previous_questions: Optional[List[str]] = None, 
    candidate_skill_level: str = "general",
    previous_responses: Optional[List[str]] = None
) -> Dict:
    """
    Generate a dynamic interview question based on topic, previous questions, and candidate skill level.
    Uses an LLM to create contextually appropriate questions that avoid repetition.
    
    Args:
        current_topic: The topic area for the question (e.g., "python", "javascript", "data_structures")
        previous_questions: List of previously asked questions to avoid repetition
        candidate_skill_level: Indicated skill level of the candidate (general, junior, mid, senior)
        previous_responses: List of candidate's previous responses to inform follow-up questions
        
    Returns:
        A dictionary containing the generated question ID, text, and expected keywords
    """
    logger.info(f"Generating question for topic: {current_topic}, skill level: {candidate_skill_level}")
    
    # Default values for empty lists
    if previous_questions is None:
        previous_questions = []
    if previous_responses is None:
        previous_responses = []
    
    # Create a system prompt for question generation
    system_prompt = """You are an expert technical interviewer who creates insightful interview questions.
    
Your task is to generate ONE challenging but fair technical interview question on the specified topic.

The question should:
1. Be clear and specific
2. Not be too lengthy
3. Be appropriate for the candidate's skill level
4. Not repeat any previously asked questions
5. If previous responses are provided, create a natural follow-up that builds on the conversation

Format your response as a JSON object with these fields:
- question_id: A unique identifier (string)
- question_text: The actual question (string)
- expected_answer_keywords: A list of 5-8 keywords that would indicate a good answer (array of strings)

Do not include any explanations or additional text outside the JSON object.
"""

    # Create human prompt with context
    human_prompt = f"""
Topic: {current_topic}
Candidate skill level: {candidate_skill_level}

Previous questions (avoid repeating these):
{previous_questions}

Previous responses (for context):
{previous_responses}

Generate a single appropriate interview question for this context:
"""

    # Initialize an LLM for question generation with high quality & consistency
    llm = ChatGoogleGenerativeAI(
        model="gemini-1.5-pro-latest", 
        temperature=0.3,
        convert_system_message_to_human=True
    )
    
    try:
        # Create messages for the LLM
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt)
        ]
        
        # Generate the question
        response = llm.invoke(messages)
        
        # Extract the JSON response
        # Note: In a production system, we would add more robust JSON parsing with error handling
        import json
        result = json.loads(response.content)
        
        # Ensure all required fields are present
        if not all(k in result for k in ["question_id", "question_text", "expected_answer_keywords"]):
            # If missing fields, create a default ID and ensure all fields exist
            if "question_id" not in result:
                result["question_id"] = f"q_{str(uuid.uuid4())[:8]}"
            if "expected_answer_keywords" not in result:
                result["expected_answer_keywords"] = []
        
        logger.info(f"Generated question: {result['question_id']}")
        return result
    
    except Exception as e:
        logger.error(f"Error generating question: {e}")
        # Fallback to a generic question if generation fails
        return {
            "question_id": f"fallback_{str(uuid.uuid4())[:8]}",
            "question_text": f"Could you share your experience with {current_topic}?",
            "expected_answer_keywords": ["experience", "skills", "projects", "challenges", "solutions"]
        }

@tool
def evaluate_candidate_response(
    question: str, 
    candidate_answer: str, 
    criteria: Optional[List[str]] = None
) -> Dict:
    """
    Evaluate a candidate's response to a technical interview question.
    
    Args:
        question: The question that was asked
        candidate_answer: The candidate's response to evaluate
        criteria: Optional specific criteria to evaluate against
        
    Returns:
        A dictionary containing evaluation scores and feedback
    """
    logger.info(f"Evaluating response for question: {question[:50]}...")
    
    # Default criteria if none provided
    if criteria is None:
        criteria = ["clarity", "technical_accuracy", "depth_of_understanding", "communication"]
    
    # Create a system prompt for evaluation
    system_prompt = """You are an expert technical evaluator for interview responses.
    
Assess the candidate's answer objectively based on the question asked and provided evaluation criteria.

For each criterion, provide:
1. A score from 1-5 (where 1 is poor and 5 is excellent)
2. A brief justification for the score (1-2 sentences)

Also provide overall feedback and suggested follow-up areas if applicable.

Format your response as a JSON object.
"""

    # Create human prompt with context
    human_prompt = f"""
Question: {question}

Candidate's answer: {candidate_answer}

Evaluation criteria: {criteria}

Provide your evaluation:
"""

    # Initialize an LLM for evaluation with low temperature for consistency
    llm = ChatGoogleGenerativeAI(
        model="gemini-1.5-pro-latest", 
        temperature=0.2,
        convert_system_message_to_human=True
    )
    
    try:
        # Create messages for the LLM
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=human_prompt)
        ]
        
        # Generate the evaluation
        response = llm.invoke(messages)
        
        # Extract the JSON response
        import json
        result = json.loads(response.content)
        
        logger.info(f"Completed evaluation")
        return result
    
    except Exception as e:
        logger.error(f"Error evaluating response: {e}")
        # Fallback to a simple evaluation if generation fails
        return {
            "overall_score": 3,
            "overall_feedback": "The response was recorded but automatic evaluation failed.",
            "scores": {criterion: 3 for criterion in criteria},
            "justifications": {criterion: "Automatic evaluation unavailable" for criterion in criteria}
        } 