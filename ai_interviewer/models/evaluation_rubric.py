from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from enum import Enum

class RatingLevel(str, Enum):
    POOR = "poor"
    AVERAGE = "average"
    GOOD = "good"
    EXCELLENT = "excellent"

class ClarityRating(BaseModel):
    """Evaluates the clarity and communication of candidate responses"""
    rating: RatingLevel = Field(..., description="Overall clarity rating")
    explanation: str = Field(..., description="Explanation for the rating")
    key_points: List[str] = Field(default_factory=list, description="Key points noted in the response")

class TechnicalEvaluation(BaseModel):
    """Technical evaluation for coding challenges and technical questions"""
    correctness: RatingLevel = Field(..., description="Correctness of the solution/answer")
    efficiency: RatingLevel = Field(..., description="Code/solution efficiency")
    code_quality: RatingLevel = Field(..., description="Code organization and best practices")
    problem_solving: RatingLevel = Field(..., description="Problem-solving approach and methodology")
    explanation: str = Field(..., description="Detailed explanation of the technical evaluation")

class SoftSkillsEvaluation(BaseModel):
    """Evaluation of candidate's soft skills during the interview"""
    communication: RatingLevel = Field(..., description="Communication effectiveness")
    adaptability: RatingLevel = Field(..., description="Ability to adapt to questions/challenges")
    collaboration: RatingLevel = Field(..., description="Collaboration potential based on responses")
    explanation: str = Field(..., description="Detailed explanation of soft skills evaluation")

class InterviewEvaluation(BaseModel):
    """Complete interview evaluation combining all aspects"""
    candidate_id: str = Field(..., description="Unique identifier for the candidate")
    interview_id: str = Field(..., description="Unique identifier for the interview session")
    qa_evaluation: Dict[str, ClarityRating] = Field(
        default_factory=dict, 
        description="Evaluation of each Q&A response"
    )
    coding_evaluation: Optional[TechnicalEvaluation] = Field(
        None, 
        description="Evaluation of coding challenge if applicable"
    )
    soft_skills: SoftSkillsEvaluation = Field(..., description="Evaluation of soft skills")
    overall_notes: str = Field(..., description="Overall interview notes and summary")
    trust_score: float = Field(
        ..., 
        ge=0, 
        le=10, 
        description="Overall trust score (0-10) based on consistency and depth"
    )
    
    class Config:
        schema_extra = {
            "example": {
                "candidate_id": "cand_123",
                "interview_id": "int_456",
                "qa_evaluation": {
                    "q1": {
                        "rating": "good",
                        "explanation": "Clear explanation of Python decorators with practical examples",
                        "key_points": ["Understood core concept", "Provided real-world usage"]
                    }
                },
                "coding_evaluation": {
                    "correctness": "good",
                    "efficiency": "average",
                    "code_quality": "good",
                    "problem_solving": "good",
                    "explanation": "Solution works correctly with good organization, but could be optimized"
                },
                "soft_skills": {
                    "communication": "excellent",
                    "adaptability": "good",
                    "collaboration": "good",
                    "explanation": "Demonstrated strong communication and adaptability throughout"
                },
                "overall_notes": "Strong candidate with good technical foundation and excellent communication",
                "trust_score": 8.5
            }
        } 