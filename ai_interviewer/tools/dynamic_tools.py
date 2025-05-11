"""
Dynamic tools for the AI Interviewer platform.

This module implements more advanced tools that use LLMs for dynamic content generation.
"""
import logging
import uuid
import json
from typing import List, Dict, Optional

from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

from ai_interviewer.models.rubric import QACriteria, EvaluationCriteria

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
    Evaluate a candidate's response to a technical interview question using a rubric-based approach.
    
    Args:
        question: The question that was asked
        candidate_answer: The candidate's response to evaluate
        criteria: Optional specific criteria to evaluate against
        
    Returns:
        A dictionary containing evaluation scores and feedback based on the rubric
    """
    logger.info(f"Evaluating response for question: {question[:50]}...")
    
    # Default criteria if none provided
    if criteria is None:
        criteria = ["clarity", "technical_accuracy", "depth_of_understanding", "communication"]
    
    # Create a system prompt for evaluation
    system_prompt = """You are an expert technical evaluator for interview responses.
    
Assess the candidate's answer objectively based on the question asked and the following criteria:

1. Clarity (1-5):
   - How well-structured and clear is the response?
   - Is the explanation easy to follow?
   - Are key points well-articulated?

2. Technical Accuracy (1-5):
   - Is the information technically correct?
   - Are technical terms used appropriately?
   - Are there any misconceptions or errors?

3. Depth of Understanding (1-5):
   - Does the answer show deep knowledge?
   - Are concepts explained thoroughly?
   - Are relationships between concepts understood?

4. Communication (1-5):
   - Is the response well-articulated?
   - Is technical information explained at an appropriate level?
   - Is the communication style professional?

For each criterion:
- Provide a score from 1-5 (where 1 is poor and 5 is excellent)
- Include a brief justification (1-2 sentences)

Also calculate a trust score (0.0-1.0) indicating your confidence in this evaluation.

Format your response as a JSON object matching this structure:
{
    "clarity": {"score": 4, "justification": "Clear structure with good examples"},
    "technical_accuracy": {"score": 5, "justification": "All technical details correct"},
    "depth_of_understanding": {"score": 3, "justification": "Basic concepts covered"},
    "communication": {"score": 4, "justification": "Well-articulated response"},
    "trust_score": 0.85,
    "overall_notes": "Brief overall assessment"
}
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
        result = json.loads(response.content)
        
        # Validate against our QACriteria model
        evaluation = QACriteria(
            clarity=EvaluationCriteria(**result["clarity"]),
            technical_accuracy=EvaluationCriteria(**result["technical_accuracy"]),
            depth_of_understanding=EvaluationCriteria(**result["depth_of_understanding"]),
            communication=EvaluationCriteria(**result["communication"])
        )
        
        # Return the validated result
        return {
            "evaluation": evaluation.model_dump(),
            "trust_score": result.get("trust_score", 0.5),
            "overall_notes": result.get("overall_notes", "")
        }
    
    except Exception as e:
        logger.error(f"Error evaluating response: {e}")
        # Fallback to a simple evaluation if generation fails
        return {
            "evaluation": {
                "clarity": {"score": 3, "justification": "Automatic evaluation unavailable"},
                "technical_accuracy": {"score": 3, "justification": "Automatic evaluation unavailable"},
                "depth_of_understanding": {"score": 3, "justification": "Automatic evaluation unavailable"},
                "communication": {"score": 3, "justification": "Automatic evaluation unavailable"}
            },
            "trust_score": 0.0,
            "overall_notes": "Automatic evaluation failed. Manual review recommended."
        } 