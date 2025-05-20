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
from langchain_core.messages import SystemMessage, HumanMessage
from ai_interviewer.utils.config import get_llm_config, SYSTEM_NAME
# Import profiling utilities
from ai_interviewer.utils.profiling import timer, timed_function

# Configure logging
logger = logging.getLogger(__name__)

# Question generation prompt that emphasizes conversational style
QUESTION_GENERATION_PROMPT = """
You are an expert technical interviewer known for your engaging and conversational interview style.
Your task is to generate a natural, thought-provoking question about {topic} that:

1. Sounds natural and conversational while being technically substantive
2. Encourages detailed responses and deeper discussion
3. Relates to real-world scenarios when possible
4. Adapts to the candidate's demonstrated level ({difficulty_level})

CONVERSATION STYLE:
- Use natural language and a friendly tone
- Include context or brief examples when helpful
- Frame questions in a way that invites discussion
- Use appropriate technical terminology without being overly formal

EXAMPLES OF CONVERSATIONAL QUESTIONS:
❌ "Explain the concept of dependency injection."
✅ "I'm curious about your experience with dependency injection. Could you walk me through how you've used it in your projects and what benefits you've seen?"

❌ "What are the differences between REST and GraphQL?"
✅ "You know, I've seen teams switch between REST and GraphQL for different projects. Based on your experience, when would you choose one over the other?"

❌ "Describe the event loop in JavaScript."
✅ "Let's talk about JavaScript's event loop. Could you share a time when understanding it helped you solve a tricky problem in your code?"

Previous questions asked: {previous_questions}
Current discussion topic: {current_topic}
Follow-up context: {follow_up_to}
"""

# Response analysis prompt that maintains conversation flow
RESPONSE_ANALYSIS_PROMPT = """
Analyze the candidate's response while maintaining our conversational interview style.
We want to evaluate their technical knowledge while keeping the discussion natural and engaging.

QUESTION: {question}
CANDIDATE RESPONSE: {response}

Analyze the response considering:
1. Technical accuracy and depth
2. Real-world application understanding
3. Problem-solving approach
4. Communication clarity
5. Areas for follow-up discussion

Provide analysis in a way that helps guide our next conversational direction.
"""

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
        
        # Build the prompt
        prompt = QUESTION_GENERATION_PROMPT.format(
            topic=current_topic or skill_areas_text,
            difficulty_level=difficulty_level,
            previous_questions=previous_questions or [],
            current_topic=current_topic or "general technical assessment",
            follow_up_to=follow_up_to or "initial question"
        )
        
        # Get response from model
        with timer("llm_question_generation", log_level=logging.INFO):
            response = model.invoke([
                SystemMessage(content=prompt),
                HumanMessage(content=f"Generate a {difficulty_level} level technical interview question about {current_topic or skill_areas_text}.")
            ])
        
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
            "question": "I'd love to hear about a challenging project you've worked on recently. Could you walk me through the technical decisions you made and how you approached any obstacles you encountered?",
            "topic": current_topic,
            "difficulty": "intermediate",
            "skill_areas": ["general"],
            "follow_up_questions": [
                "What specific technologies did you use in that project?",
                "How did you overcome the main challenges you faced?",
                "What were the key lessons you learned from that experience?"
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
    Analyze a candidate's response to generate insights and potential follow-up questions.
    
    Args:
        question: The question that was asked
        response: The candidate's response
        job_role: The job role being interviewed for
        skill_areas: List of relevant skill areas
        expected_topics: List of topics expected in the response
        experience_level: Expected experience level
        
    Returns:
        Dictionary containing analysis and follow-up suggestions
    """
    try:
        # Initialize LLM
        llm_config = get_llm_config()
        model = ChatGoogleGenerativeAI(
            model=llm_config["model"],
            temperature=0.1  # Low temperature for objective analysis
        )
        
        # Build the prompt
        prompt = RESPONSE_ANALYSIS_PROMPT.format(
            question=question,
            response=response
        )
        
        # Call the LLM
        response_obj = model.invoke([
            SystemMessage(content=prompt)
        ])
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
        logger.error(f"Error analyzing response: {e}")
        return {
            "error": str(e),
            "status": "error",
            "technical_accuracy": 0,
            "depth_of_knowledge": 0,
            "comprehensive_understanding_score": 0,
            "suggested_follow_up": "Could you elaborate more on your approach to this problem?"
        } 