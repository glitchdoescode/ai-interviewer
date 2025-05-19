"""
Dynamic question generation tools for the {SYSTEM_NAME} platform.

This module implements tools for generating contextually-relevant, adaptive interview questions
based on job role, candidate skill level, and previous responses. It implements the requirements
from Task P2.3.1 in the project checklist.
"""
import logging
from typing import Dict, List, Optional, Any, Union
import re

from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from ai_interviewer.utils.config import get_llm_config, SYSTEM_NAME
# Import profiling utilities
from ai_interviewer.utils.profiling import timer, timed_function

# Configure logging
logger = logging.getLogger(__name__)


@tool
@timed_function(log_level=logging.INFO)
def generate_interview_question(
    job_role: str,
    skill_areas: Optional[List[str]] = None,
    difficulty_level: str = "intermediate",
    previous_questions: Optional[List[str]] = None,
    previous_responses: Optional[List[str]] = None,
    current_topic: Optional[str] = None,
    follow_up_to: Optional[str] = None
) -> Dict[str, Any]:
    """
    Generate a contextually-relevant interview question based on job role, skill areas, 
    and previous candidate responses.
    
    Args:
        job_role: The job role for which the interview is being conducted
        skill_areas: List of specific skills to focus on (e.g., "Python", "Data Structures")
        difficulty_level: Level of difficulty ("beginner", "intermediate", "advanced")
        previous_questions: List of questions already asked in this interview
        previous_responses: List of candidate's previous responses
        current_topic: The current discussion topic, if any
        follow_up_to: Specific question or response to follow up on
        
    Returns:
        Dictionary containing the generated question and metadata
    """
    logger.info(f"Generating question for {job_role} at {difficulty_level} level")
    logger.info(f"Skill areas: {skill_areas}")
    
    try:
        # Initialize LLM with appropriate temperature for creative but controlled question generation
        with timer("initialize_llm_model", log_level=logging.INFO):
            model = ChatGoogleGenerativeAI(
                model=get_llm_config()["model"],
                temperature=0.7,
                convert_system_message_to_human=True
            )
        
        # Format previous Q&A for context
        conversation_context = ""
        if previous_questions and previous_responses:
            # Pair questions with responses for context
            qa_pairs = zip(previous_questions, previous_responses)
            conversation_context = "\n".join([f"Q: {q}\nA: {r}" for q, r in qa_pairs])
        
        # Default skill areas if none provided
        skill_areas_text = ", ".join(skill_areas) if skill_areas else "general technical skills for the role"
        
        # Adjust difficulty parameters based on level
        difficulty_params = {
            "beginner": {
                "depth": "focus on fundamentals and basic concepts",
                "complexity": "straightforward questions with clear answers"
            },
            "intermediate": {
                "depth": "explore practical application and real-world scenarios",
                "complexity": "questions requiring analysis and critical thinking"
            },
            "advanced": {
                "depth": "deep technical knowledge and expert-level understanding",
                "complexity": "complex scenarios requiring in-depth knowledge and experience"
            }
        }.get(difficulty_level.lower(), {
            "depth": "balanced mix of theoretical and practical knowledge",
            "complexity": "moderate complexity appropriate for experienced professionals"
        })
        
        # Build the prompt
        prompt = [
            SystemMessage(content=QUESTION_GENERATION_PROMPT),
            HumanMessage(content=f"Generate a {difficulty_level} level technical interview question about {current_topic}.")
        ]
        
        # Get response from model
        with timer("llm_question_generation", log_level=logging.INFO):
            response = model.invoke(prompt)
        
        # Extract question from response
        question = response.content.strip()
        
        logger.info(f"Generated question about {current_topic} at {difficulty_level} level")
        
        return {
            "status": "success",
            "question": question,
            "topic": current_topic,
            "difficulty": difficulty_level,
            "skill_areas": skill_areas,
            "job_role": job_role,
            "requested_difficulty": difficulty_level,
            "requested_skill_areas": skill_areas,
            "generated_from_model": True
        }
    except Exception as e:
        logger.error(f"Error generating interview question: {e}")
        # Fallback return in case of errors
        return {
            "status": "error",
            "question": "Tell me about your most challenging project and the technical skills you used to complete it.",
            "topic": current_topic,
            "difficulty": "intermediate",
            "skill_areas": ["general"],
            "follow_up_questions": [
                "What specific technologies did you use?",
                "What obstacles did you overcome?",
                "What did you learn from the experience?"
            ],
            "error": str(e),
            "job_role": job_role,
            "requested_difficulty": difficulty_level,
            "requested_skill_areas": skill_areas,
            "generated_from_error": True
        }


@tool
@timed_function(log_level=logging.INFO)
def analyze_candidate_response(
    question: str,
    response: str,
    job_role: str,
    skill_areas: Optional[List[str]] = None,
    expected_topics: Optional[List[str]] = None,
    experience_level: str = "intermediate"
) -> Dict[str, Any]:
    """
    Analyze a candidate's response to identify strengths, weaknesses, and potential follow-up areas.
    Performs deep analysis of concept understanding and knowledge depth.
    
    Args:
        question: The question that was asked
        response: The candidate's response to analyze
        job_role: The job role for context
        skill_areas: Skills that were being evaluated
        expected_topics: Expected topics in a good answer
        experience_level: Experience level of the candidate (beginner, intermediate, advanced)
        
    Returns:
        Dictionary containing detailed analysis results
    """
    logger.info(f"Analyzing candidate response for job role: {job_role}")
    
    try:
        # Initialize LLM
        llm_config = get_llm_config()
        model = ChatGoogleGenerativeAI(
            model=llm_config["model"],
            temperature=0.1  # Low temperature for objective analysis
        )
        
        # Build the prompt
        prompt = f"""
You are an expert technical interviewer evaluating candidates for {job_role} positions.

Analyze the following candidate response to the interview question. Focus on extracting key concepts and performing a deep analysis of the candidate's understanding.

QUESTION: {question}

CANDIDATE RESPONSE: {response}

JOB ROLE: {job_role}
EXPERIENCE LEVEL: {experience_level}
{"SKILL AREAS: " + ", ".join(skill_areas) if skill_areas else ""}
{"EXPECTED TOPICS: " + ", ".join(expected_topics) if expected_topics else ""}

ANALYSIS TASKS:
1. Identify the main points made by the candidate
2. Extract key concepts and technical terms used by the candidate
3. Evaluate how well the response addresses the question
4. Assess technical accuracy and depth of knowledge
5. Evaluate the candidate's conceptual understanding (not just surface-level knowledge)
6. Identify evidence of practical experience vs. theoretical knowledge
7. Note any missing key concepts or topics that should have been addressed
8. Assess problem-solving approach and critical thinking
9. Identify areas where follow-up questions would be valuable
10. Determine strengths and weaknesses in the response

DEPTH OF UNDERSTANDING ASSESSMENT:
- Consider whether the candidate explains underlying principles or just surface details
- Look for connections made between different concepts
- Assess whether the candidate can explain "why" not just "what" or "how"
- Evaluate their ability to consider edge cases or limitations
- Check for evidence of real-world application of knowledge

RESPONSE FORMAT:
Return your analysis as a valid JSON object with the following fields:
- "main_points": List of main points made by the candidate
- "key_concepts": List of key concepts or technical terms correctly used by the candidate
- "relevance_score": 1-10 rating of how relevant the response was to the question
- "technical_accuracy": 1-10 rating of technical accuracy
- "depth_of_knowledge": 1-10 rating of knowledge depth
- "conceptual_understanding": 1-10 rating of understanding of underlying concepts and principles
- "practical_experience": 1-10 rating of evidence of practical experience
- "problem_solving": 1-10 rating of demonstrated problem-solving ability
- "misconceptions": List of any misconceptions or technical inaccuracies
- "missing_topics": Key topics that were not addressed
- "follow_up_areas": Areas that would benefit from follow-up questions
- "concept_connections": How well the candidate connected different concepts (1-10)
- "edge_case_awareness": How well they considered edge cases or limitations (1-10)
- "strengths": List of strengths in the response
- "weaknesses": List of weaknesses in the response
- "recommended_follow_up_question": One specific follow-up question designed to assess deeper understanding
- "alternative_follow_up_questions": 2-3 additional follow-up questions focusing on different aspects
- "depth_analysis": A paragraph explaining the candidate's depth of understanding
"""
        
        # Call the LLM
        response_obj = model.invoke(prompt)
        response_content = response_obj.content
        
        # Extract the JSON part
        json_match = re.search(r'```json\s*(.*?)\s*```', response_content, re.DOTALL)
        if json_match:
            response_content = json_match.group(1)
        else:
            # Try to find JSON object without markdown
            json_match = re.search(r'(\{.*\})', response_content, re.DOTALL)
            if json_match:
                response_content = json_match.group(1)
        
        # Parse the response
        import json
        result = json.loads(response_content)
        
        # Calculate a comprehensive understanding score
        understanding_scores = [
            result.get("technical_accuracy", 0),
            result.get("depth_of_knowledge", 0),
            result.get("conceptual_understanding", 0),
            result.get("problem_solving", 0),
            result.get("concept_connections", 0),
            result.get("edge_case_awareness", 0)
        ]
        
        # Filter out zero values and calculate average
        valid_scores = [score for score in understanding_scores if score > 0]
        if valid_scores:
            result["comprehensive_understanding_score"] = sum(valid_scores) / len(valid_scores)
        else:
            result["comprehensive_understanding_score"] = 0
        
        # Add metadata
        result["question"] = question
        result["job_role"] = job_role
        result["experience_level"] = experience_level
        
        return result
    except Exception as e:
        logger.error(f"Error analyzing candidate response: {e}")
        # Fallback return in case of errors
        return {
            "main_points": ["Unable to extract main points due to error"],
            "key_concepts": [],
            "relevance_score": 5,
            "technical_accuracy": 5,
            "depth_of_knowledge": 5,
            "conceptual_understanding": 5,
            "practical_experience": 5,
            "problem_solving": 5,
            "misconceptions": ["Unable to determine misconceptions"],
            "missing_topics": ["Unable to determine missing topics"],
            "follow_up_areas": ["General clarification"],
            "concept_connections": 5,
            "edge_case_awareness": 5,
            "strengths": ["Unable to determine strengths"],
            "weaknesses": ["Unable to determine weaknesses"],
            "recommended_follow_up_question": "Could you elaborate more on your answer?",
            "alternative_follow_up_questions": [
                "Can you explain how this works in practice?",
                "What are some challenges you might encounter with this approach?",
                "How would you modify your approach for a different scenario?"
            ],
            "depth_analysis": "Unable to analyze depth of understanding due to an error in processing.",
            "comprehensive_understanding_score": 5,
            "question": question,
            "job_role": job_role,
            "experience_level": experience_level,
            "error": str(e),
            "generated_from_error": True
        } 