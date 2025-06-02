"""
Rubric-based evaluation tools for coding submissions.
Implements detailed scoring across multiple dimensions as specified in iteration 6.
"""

import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from langchain.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from ai_interviewer.tools.code_quality import CodeQualityMetrics
from ai_interviewer.tools.code_feedback import CodeFeedbackGenerator
from ai_interviewer.utils.config import get_llm_config

logger = logging.getLogger(__name__)

# Define the detailed rubric based on PRD
CODING_RUBRIC = {
    "code_correctness": {
        "weight": 0.25,
        "description": "Does the code produce correct outputs for given inputs?",
        "criteria": {
            "excellent": "All test cases pass, handles edge cases well",
            "good": "Most test cases pass, minor issues with edge cases", 
            "fair": "Some test cases pass, basic functionality works",
            "poor": "Few or no test cases pass, significant logic errors"
        }
    },
    "efficiency": {
        "weight": 0.20,
        "description": "How efficient is the algorithm and implementation?",
        "criteria": {
            "excellent": "Optimal time/space complexity, efficient implementation",
            "good": "Good complexity, mostly efficient implementation",
            "fair": "Acceptable complexity, some inefficiencies",
            "poor": "Poor complexity or very inefficient implementation"
        }
    },
    "code_quality": {
        "weight": 0.20,
        "description": "Code readability, structure, and best practices",
        "criteria": {
            "excellent": "Clean, well-structured, follows best practices",
            "good": "Generally clean and readable, minor style issues",
            "fair": "Somewhat readable, some structural issues",
            "poor": "Hard to read, poor structure, many style violations"
        }
    },
    "problem_solving": {
        "weight": 0.20,
        "description": "Approach to breaking down and solving the problem",
        "criteria": {
            "excellent": "Clear logical approach, well-thought-out solution",
            "good": "Good approach with minor logical gaps",
            "fair": "Basic approach, some logical issues",
            "poor": "Unclear or flawed problem-solving approach"
        }
    },
    "communication": {
        "weight": 0.15,
        "description": "Code comments, variable names, and overall clarity",
        "criteria": {
            "excellent": "Excellent comments, clear naming, self-documenting",
            "good": "Good comments and naming, mostly clear",
            "fair": "Some comments, acceptable naming",
            "poor": "Poor or no comments, unclear naming"
        }
    }
}

SCORE_MAPPING = {
    "excellent": 4,
    "good": 3,
    "fair": 2,
    "poor": 1
}

class RubricEvaluator:
    """Handles rubric-based evaluation of coding submissions."""
    
    def __init__(self):
        llm_config = get_llm_config()
        self.llm = ChatGoogleGenerativeAI(
            model=llm_config["model"],
            temperature=0.1  # Lower temperature for more consistent scoring
        )
    
    def evaluate_coding_submission(self, 
                                 code: str, 
                                 execution_results: Dict[str, Any],
                                 problem_statement: str,
                                 language: str = "python",
                                 candidate_explanation: str = "") -> Dict[str, Any]:
        """
        Evaluate a coding submission against the detailed rubric.
        
        Args:
            code: The submitted code
            execution_results: Results from running the code
            problem_statement: The original problem statement
            language: Programming language used
            candidate_explanation: Any explanation provided by the candidate
            
        Returns:
            Detailed evaluation with scores and rationale
        """
        try:
            # Get code quality metrics
            quality_metrics = CodeQualityMetrics.analyze_python_code(code) if language.lower() == "python" else {}
            
            # Get general feedback
            general_feedback = CodeFeedbackGenerator.generate_feedback(
                code, execution_results, language
            )
            
            # Evaluate each rubric dimension
            rubric_scores = {}
            total_weighted_score = 0
            
            for dimension, config in CODING_RUBRIC.items():
                score_data = self._evaluate_dimension(
                    dimension, config, code, execution_results, 
                    problem_statement, quality_metrics, candidate_explanation
                )
                rubric_scores[dimension] = score_data
                total_weighted_score += score_data["score"] * config["weight"]
            
            # Calculate trust score (initial heuristic)
            trust_score = self._calculate_trust_score(rubric_scores, execution_results)
            
            # Generate overall assessment
            overall_assessment = self._generate_overall_assessment(rubric_scores, total_weighted_score)
            
            return {
                "timestamp": datetime.now().isoformat(),
                "language": language,
                "total_score": round(total_weighted_score, 2),
                "max_score": 4.0,
                "percentage": round((total_weighted_score / 4.0) * 100, 1),
                "trust_score": trust_score,
                "rubric_scores": rubric_scores,
                "overall_assessment": overall_assessment,
                "quality_metrics": quality_metrics,
                "general_feedback": general_feedback,
                "areas_for_improvement": self._identify_improvement_areas(rubric_scores),
                "strengths": self._identify_strengths(rubric_scores)
            }
            
        except Exception as e:
            logger.error(f"Error in rubric evaluation: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def _evaluate_dimension(self, dimension: str, config: Dict[str, Any], 
                          code: str, execution_results: Dict[str, Any],
                          problem_statement: str, quality_metrics: Dict[str, Any],
                          candidate_explanation: str) -> Dict[str, Any]:
        """Evaluate a specific rubric dimension using LLM."""
        
        prompt = f"""You are an expert technical interviewer evaluating a coding submission. 

RUBRIC DIMENSION: {dimension}
DESCRIPTION: {config['description']}

CRITERIA:
{json.dumps(config['criteria'], indent=2)}

PROBLEM STATEMENT:
{problem_statement}

SUBMITTED CODE:
```{code}```

EXECUTION RESULTS:
{json.dumps(execution_results, indent=2)}

QUALITY METRICS:
{json.dumps(quality_metrics, indent=2)}

CANDIDATE EXPLANATION:
{candidate_explanation}

Please evaluate this submission for the "{dimension}" dimension and provide:
1. A score level (excellent/good/fair/poor) based on the criteria
2. A detailed rationale (2-3 sentences) explaining your scoring decision
3. Specific observations that led to this score

Respond in this exact JSON format:
{{
    "score_level": "excellent|good|fair|poor",
    "rationale": "detailed explanation here",
    "specific_observations": ["observation 1", "observation 2", ...]
}}"""

        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            result = json.loads(response.content)
            
            return {
                "dimension": dimension,
                "score_level": result["score_level"],
                "score": SCORE_MAPPING[result["score_level"]],
                "weight": config["weight"],
                "weighted_score": SCORE_MAPPING[result["score_level"]] * config["weight"],
                "rationale": result["rationale"],
                "specific_observations": result["specific_observations"]
            }
            
        except Exception as e:
            logger.error(f"Error evaluating dimension {dimension}: {e}")
            return {
                "dimension": dimension,
                "score_level": "fair",
                "score": 2,
                "weight": config["weight"],
                "weighted_score": 2 * config["weight"],
                "rationale": "Could not evaluate due to error",
                "specific_observations": ["Evaluation error occurred"]
            }
    
    def _calculate_trust_score(self, rubric_scores: Dict[str, Any], 
                             execution_results: Dict[str, Any]) -> float:
        """Calculate a trust score based on various factors."""
        
        # Base trust score from rubric performance
        avg_score = sum(score["score"] for score in rubric_scores.values()) / len(rubric_scores)
        base_trust = avg_score / 4.0
        
        # Adjust based on test case performance
        test_results = execution_results.get("test_results", {})
        if test_results:
            passed = test_results.get("passed", 0)
            total = test_results.get("total", 1)
            test_ratio = passed / total
            base_trust = (base_trust + test_ratio) / 2
        
        # Adjust based on code quality consistency
        quality_penalty = 0
        code_quality_score = rubric_scores.get("code_quality", {}).get("score", 2)
        correctness_score = rubric_scores.get("code_correctness", {}).get("score", 2)
        
        # Penalize if there's a large gap between correctness and quality
        if abs(code_quality_score - correctness_score) > 2:
            quality_penalty = 0.1
        
        trust_score = max(0, min(1, base_trust - quality_penalty))
        return round(trust_score, 3)
    
    def _generate_overall_assessment(self, rubric_scores: Dict[str, Any], 
                                   total_score: float) -> str:
        """Generate an overall assessment summary."""
        
        if total_score >= 3.5:
            level = "Excellent"
        elif total_score >= 2.5:
            level = "Good"
        elif total_score >= 1.5:
            level = "Fair"
        else:
            level = "Needs Improvement"
        
        # Find strongest and weakest areas
        scores_by_dimension = {dim: data["score"] for dim, data in rubric_scores.items()}
        strongest = max(scores_by_dimension, key=scores_by_dimension.get)
        weakest = min(scores_by_dimension, key=scores_by_dimension.get)
        
        return f"{level} performance overall. Strongest area: {strongest.replace('_', ' ')}. " \
               f"Area for improvement: {weakest.replace('_', ' ')}."
    
    def _identify_improvement_areas(self, rubric_scores: Dict[str, Any]) -> List[str]:
        """Identify specific areas for improvement."""
        improvements = []
        
        for dimension, data in rubric_scores.items():
            if data["score"] <= 2:  # Fair or poor
                improvements.append({
                    "area": dimension.replace('_', ' ').title(),
                    "current_level": data["score_level"],
                    "suggestion": data["rationale"]
                })
        
        return improvements
    
    def _identify_strengths(self, rubric_scores: Dict[str, Any]) -> List[str]:
        """Identify candidate strengths."""
        strengths = []
        
        for dimension, data in rubric_scores.items():
            if data["score"] >= 3:  # Good or excellent
                strengths.append({
                    "area": dimension.replace('_', ' ').title(),
                    "level": data["score_level"],
                    "note": data["rationale"]
                })
        
        return strengths


@tool
async def evaluate_coding_submission_with_rubric(
    code: str,
    execution_results: dict,
    problem_statement: str,
    language: str = "python",
    candidate_explanation: str = ""
) -> str:
    """
    Evaluate a coding submission using a detailed rubric across multiple dimensions.
    
    Args:
        code: The submitted source code
        execution_results: Results from executing the code with test cases
        problem_statement: The original problem statement
        language: Programming language used
        candidate_explanation: Any explanation provided by the candidate
        
    Returns:
        JSON string with detailed rubric-based evaluation
    """
    try:
        evaluator = RubricEvaluator()
        evaluation = evaluator.evaluate_coding_submission(
            code, execution_results, problem_statement, language, candidate_explanation
        )
        
        logger.info(f"Completed rubric evaluation with total score: {evaluation.get('total_score', 'N/A')}")
        return json.dumps(evaluation, indent=2)
        
    except Exception as e:
        logger.error(f"Error in evaluate_coding_submission_with_rubric: {e}")
        return json.dumps({
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        })


@tool
async def generate_detailed_report(
    session_id: str,
    rubric_evaluation: dict,
    interview_transcript: str = "",
    coding_logs: list = None
) -> str:
    """
    Generate a detailed interview report with rubric scores and comprehensive analysis.
    
    Args:
        session_id: The interview session ID
        rubric_evaluation: Complete rubric evaluation results
        interview_transcript: Full interview conversation transcript
        coding_logs: List of coding interaction logs
        
    Returns:
        JSON string with comprehensive interview report
    """
    try:
        coding_logs = coding_logs or []
        
        report = {
            "report_metadata": {
                "session_id": session_id,
                "generated_at": datetime.now().isoformat(),
                "report_type": "comprehensive_interview_analysis"
            },
            "executive_summary": {
                "overall_score": rubric_evaluation.get("total_score", 0),
                "percentage": rubric_evaluation.get("percentage", 0),
                "trust_score": rubric_evaluation.get("trust_score", 0),
                "recommendation": _get_recommendation(rubric_evaluation.get("total_score", 0)),
                "key_strengths": [s["area"] for s in rubric_evaluation.get("strengths", [])],
                "key_improvement_areas": [a["area"] for a in rubric_evaluation.get("areas_for_improvement", [])]
            },
            "detailed_rubric_analysis": rubric_evaluation.get("rubric_scores", {}),
            "code_quality_metrics": rubric_evaluation.get("quality_metrics", {}),
            "behavioral_assessment": _extract_behavioral_insights(interview_transcript),
            "technical_competency": {
                "coding_ability": rubric_evaluation.get("overall_assessment", ""),
                "problem_solving_approach": _analyze_problem_solving(coding_logs),
                "communication_during_coding": _analyze_coding_communication(coding_logs)
            },
            "interview_flow_analysis": {
                "total_interactions": len(coding_logs),
                "time_to_solution": _calculate_solution_time(coding_logs),
                "help_requests": _count_help_requests(coding_logs)
            },
            "recommendations": {
                "hiring_recommendation": _get_hiring_recommendation(rubric_evaluation),
                "development_areas": rubric_evaluation.get("areas_for_improvement", []),
                "follow_up_questions": _suggest_follow_up_questions(rubric_evaluation)
            },
            "raw_data": {
                "transcript": interview_transcript,
                "coding_logs": coding_logs,
                "full_evaluation": rubric_evaluation
            }
        }
        
        logger.info(f"Generated detailed report for session {session_id}")
        return json.dumps(report, indent=2)
        
    except Exception as e:
        logger.error(f"Error generating detailed report: {e}")
        return json.dumps({
            "error": str(e),
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        })


def _get_recommendation(total_score: float) -> str:
    """Get hiring recommendation based on total score."""
    if total_score >= 3.5:
        return "Strong Hire - Excellent performance across all dimensions"
    elif total_score >= 2.8:
        return "Hire - Good performance with minor areas for improvement"
    elif total_score >= 2.0:
        return "Borderline - Requires additional evaluation"
    else:
        return "No Hire - Significant improvement needed"


def _extract_behavioral_insights(transcript: str) -> Dict[str, Any]:
    """Extract behavioral insights from interview transcript."""
    return {
        "communication_clarity": "Assessment would require transcript analysis",
        "problem_approach": "Extracted from transcript",
        "confidence_level": "Derived from interaction patterns"
    }


def _analyze_problem_solving(coding_logs: List[Dict]) -> str:
    """Analyze problem-solving approach from coding logs."""
    if not coding_logs:
        return "No coding interaction data available"
    
    return "Problem-solving analysis based on coding interaction patterns"


def _analyze_coding_communication(coding_logs: List[Dict]) -> str:
    """Analyze communication during coding from logs."""
    if not coding_logs:
        return "No coding communication data available"
    
    return "Communication analysis during coding phase"


def _calculate_solution_time(coding_logs: List[Dict]) -> str:
    """Calculate time to solution from logs."""
    if not coding_logs:
        return "0 minutes"
    
    return "Time calculation from logs"


def _count_help_requests(coding_logs: List[Dict]) -> int:
    """Count help requests from coding logs."""
    return len([log for log in coding_logs if log.get("event_type") == "hint_request"])


def _get_hiring_recommendation(evaluation: Dict[str, Any]) -> Dict[str, Any]:
    """Generate detailed hiring recommendation."""
    total_score = evaluation.get("total_score", 0)
    trust_score = evaluation.get("trust_score", 0)
    
    return {
        "decision": _get_recommendation(total_score),
        "confidence": trust_score,
        "rationale": f"Based on overall score of {total_score}/4.0 and trust score of {trust_score}"
    }


def _suggest_follow_up_questions(evaluation: Dict[str, Any]) -> List[str]:
    """Suggest follow-up questions based on evaluation."""
    questions = []
    
    weak_areas = evaluation.get("areas_for_improvement", [])
    for area in weak_areas:
        if area["area"].lower() == "code quality":
            questions.append("Can you explain your approach to writing maintainable code?")
        elif area["area"].lower() == "efficiency":
            questions.append("How would you optimize this solution for better performance?")
        elif area["area"].lower() == "problem solving":
            questions.append("Walk me through your thought process for this problem.")
    
    return questions 