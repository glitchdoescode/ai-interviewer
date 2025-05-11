"""
Rubric definitions for the AI Interviewer platform.

This module defines the evaluation rubrics used to assess candidates during interviews.
"""
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

class EvaluationCriteria(BaseModel):
    """Base model for evaluation criteria."""
    score: int = Field(..., ge=1, le=5, description="Score from 1-5")
    justification: str = Field(..., description="Brief explanation for the score")

class QACriteria(BaseModel):
    """Criteria for evaluating Q&A responses."""
    clarity: EvaluationCriteria = Field(..., description="How clear and well-structured the answer is")
    technical_accuracy: EvaluationCriteria = Field(..., description="Technical correctness of the answer")
    depth_of_understanding: EvaluationCriteria = Field(..., description="Demonstrated depth of knowledge")
    communication: EvaluationCriteria = Field(..., description="Communication effectiveness")

class CodingCriteria(BaseModel):
    """Criteria for evaluating coding challenge responses."""
    correctness: EvaluationCriteria = Field(..., description="Code produces correct output")
    code_quality: EvaluationCriteria = Field(..., description="Code organization and style")
    efficiency: EvaluationCriteria = Field(..., description="Algorithm efficiency and performance")
    problem_solving: EvaluationCriteria = Field(..., description="Problem-solving approach")

class InterviewEvaluation(BaseModel):
    """Complete interview evaluation."""
    qa_evaluations: List[Dict[str, QACriteria]] = Field(default_factory=list, description="List of Q&A evaluations")
    coding_evaluation: Optional[CodingCriteria] = Field(None, description="Coding challenge evaluation if applicable")
    overall_notes: str = Field("", description="General notes about the candidate's performance")
    trust_score: float = Field(..., ge=0.0, le=1.0, description="AI-generated confidence score in the evaluation") 