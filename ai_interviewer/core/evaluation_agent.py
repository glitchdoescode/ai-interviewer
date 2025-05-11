from typing import Dict, List, Optional, TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from ai_interviewer.models.evaluation_rubric import (
    InterviewEvaluation, 
    ClarityRating,
    TechnicalEvaluation,
    SoftSkillsEvaluation,
    RatingLevel
)

class EvaluationState(TypedDict):
    """State maintained during evaluation process"""
    messages: List[dict]  # Chat history
    current_evaluation: Optional[InterviewEvaluation]  # Current evaluation being built
    candidate_id: str
    interview_id: str

def create_evaluation_agent(model_name: str = "gemini-1.5-pro-latest"):
    """Creates an evaluation agent using LangGraph"""
    
    # Initialize the LLM
    llm = ChatGoogleGenerativeAI(
        model=model_name,
        temperature=0.1  # Low temperature for more consistent evaluations
    )
    
    # System prompt for evaluation
    EVAL_SYSTEM_PROMPT = """You are an expert technical interviewer tasked with evaluating candidate responses.
    Follow these guidelines strictly:
    
    1. Evaluate responses based on:
       - Technical accuracy and depth
       - Communication clarity
       - Problem-solving approach
       - Soft skills demonstrated
    
    2. Provide specific examples and quotes to justify ratings
    
    3. Be objective and consistent in applying the rubric
    
    4. Consider both what was said and how it was communicated
    
    5. For coding challenges, evaluate:
       - Correctness of solution
       - Code efficiency and complexity
       - Code organization and style
       - Problem-solving methodology
    
    Rate each aspect using these levels: POOR, AVERAGE, GOOD, EXCELLENT
    
    Maintain high standards while being fair and constructive.
    """
    
    # Create the evaluation chain
    eval_prompt = ChatPromptTemplate.from_messages([
        ("system", EVAL_SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="messages"),
        ("human", "Based on the interview transcript above, generate a structured evaluation following the rubric format. Focus on {aspect} evaluation.")
    ])
    
    eval_chain = eval_prompt | llm
    
    def evaluate_response(state: EvaluationState) -> EvaluationState:
        """Evaluates a single response or aspect of the interview"""
        # Extract relevant messages
        messages = state["messages"]
        
        # Initialize evaluation if not exists
        if not state.get("current_evaluation"):
            state["current_evaluation"] = InterviewEvaluation(
                candidate_id=state["candidate_id"],
                interview_id=state["interview_id"],
                soft_skills=SoftSkillsEvaluation(
                    communication=RatingLevel.AVERAGE,
                    adaptability=RatingLevel.AVERAGE,
                    collaboration=RatingLevel.AVERAGE,
                    explanation="Initial evaluation"
                ),
                overall_notes="",
                trust_score=5.0
            )
        
        # Evaluate Q&A responses
        qa_result = eval_chain.invoke({
            "messages": messages,
            "aspect": "Q&A"
        })
        
        # Update Q&A evaluation
        # Note: In practice, you'd parse the LLM response to extract structured ratings
        # This is a simplified example
        state["current_evaluation"].qa_evaluation["latest"] = ClarityRating(
            rating=RatingLevel.GOOD,
            explanation=qa_result.content,
            key_points=["Point extracted from response"]
        )
        
        # Evaluate soft skills
        soft_skills_result = eval_chain.invoke({
            "messages": messages,
            "aspect": "soft skills"
        })
        
        # Update soft skills evaluation
        # In practice, parse the LLM response for structured ratings
        state["current_evaluation"].soft_skills = SoftSkillsEvaluation(
            communication=RatingLevel.GOOD,
            adaptability=RatingLevel.GOOD,
            collaboration=RatingLevel.GOOD,
            explanation=soft_skills_result.content
        )
        
        return state
    
    def should_continue(state: EvaluationState) -> bool:
        """Determines if evaluation should continue or end"""
        # Add your logic for when to end evaluation
        # For example, after processing all responses or reaching a conclusion
        return END
    
    # Create the evaluation workflow
    workflow = StateGraph(EvaluationState)
    
    # Add nodes
    workflow.add_node("evaluate", evaluate_response)
    
    # Add edges
    workflow.add_edge("evaluate", should_continue)
    
    return workflow.compile()

# Example usage:
# evaluation_agent = create_evaluation_agent()
# state = {
#     "messages": [...],  # Interview transcript
#     "candidate_id": "cand_123",
#     "interview_id": "int_456"
# }
# result = evaluation_agent.invoke(state) 