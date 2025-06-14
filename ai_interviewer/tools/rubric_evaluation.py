"""
Rubric-based evaluation tools for coding submissions.
Implements detailed scoring across multiple dimensions as specified in iteration 6.
"""

import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import re

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
        
        # Define default max scores for each dimension
        self.dimension_max_scores = {
            "efficiency": 5.0,
            "code_quality": 5.0,
            "problem_solving": 5.0,
            "communication": 5.0
        }
        
        # Define score levels
        self.score_levels = {
            (0, 2.0): "Needs Improvement",
            (2.0, 3.5): "Satisfactory",
            (3.5, 4.5): "Good",
            (4.5, 5.0): "Excellent"
        }
    
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
            # Initialize evaluation structure
            evaluation = {
                "dimensions": {},
                "total_score": 0.0,
                "max_possible_score": sum(self.dimension_max_scores.values()),
                "feedback": {},
                "trust_score": 0.0
            }
            
            # Get code quality metrics
            quality_metrics = CodeQualityMetrics.analyze_python_code(code) if language.lower() == "python" else {}
            
            # Get general feedback
            general_feedback = CodeFeedbackGenerator.generate_feedback(
                code, execution_results, language
            )
            
            # Evaluate each dimension
            for dimension, max_score in self.dimension_max_scores.items():
                dimension_result = self._evaluate_dimension(
                    dimension, 
                    {"max_score": max_score}, 
                    code, 
                    execution_results,
                    problem_statement,
                    quality_metrics,
                    candidate_explanation
                )
                evaluation["dimensions"][dimension] = dimension_result
                evaluation["total_score"] += dimension_result["score"]
            
            # Calculate normalized score (0-5 scale)
            normalized_score = (evaluation["total_score"] / evaluation["max_possible_score"]) * 5.0

            # Calculate score level
            for (min_score, max_score), level in self.score_levels.items():
                if min_score <= normalized_score <= max_score:
                    evaluation["score_level"] = level
                    break
            else:
                evaluation["score_level"] = "Needs Improvement"
            
            # Calculate trust score
            evaluation["trust_score"] = self._calculate_trust_score(
                evaluation["dimensions"], 
                execution_results
            )
            
            # Generate overall assessment
            evaluation["overall_assessment"] = self._generate_overall_assessment(
                evaluation["dimensions"], 
                evaluation["total_score"]
            )
            
            # Identify areas for improvement and strengths
            evaluation["improvement_areas"] = self._identify_improvement_areas(evaluation["dimensions"])
            evaluation["strengths"] = self._identify_strengths(evaluation["dimensions"])
            
            return {
                "timestamp": datetime.now().isoformat(),
                "language": language,
                "total_score": round(evaluation["total_score"], 2),
                "max_score": evaluation["max_possible_score"],
                "percentage": round((evaluation["total_score"] / evaluation["max_possible_score"]) * 100, 1),
                "trust_score": evaluation["trust_score"],
                "score_level": evaluation["score_level"],
                "overall_assessment": evaluation["overall_assessment"],
                "quality_metrics": quality_metrics,
                "general_feedback": general_feedback,
                "improvement_areas": evaluation["improvement_areas"],
                "strengths": evaluation["strengths"]
            }
            
        except Exception as e:
            logger.error(f"Error in rubric evaluation: {e}")
            return {
                "dimensions": {},
                "total_score": 0.0,
                "max_possible_score": sum(self.dimension_max_scores.values()),
                "feedback": {"error": str(e)},
                "trust_score": 0.0,
                "score_level": "Error in evaluation",
                "overall_assessment": "Could not complete evaluation",
                "improvement_areas": [],
                "strengths": []
            }
    
    def _evaluate_dimension(self, dimension: str, config: Dict[str, Any], 
                          code: str, execution_results: Dict[str, Any],
                          problem_statement: str, quality_metrics: Dict[str, Any],
                          candidate_explanation: str) -> Dict[str, Any]:
        """Evaluate a specific dimension of the rubric."""
        try:
            max_score = config.get("max_score", 5.0)  # Default to 5.0 if not specified
            
            # Initialize base evaluation structure
            evaluation = {
                "score": 0.0,
                "max_score": max_score,
                "feedback": "",
                "details": {}
            }
            
            # Evaluate based on dimension
            if dimension == "code_correctness":
                test_results = execution_results.get("test_results", [])
                passed_tests = sum(1 for test in test_results if test.get("passed", False))
                total_tests = len(test_results)
                evaluation["score"] = (passed_tests / total_tests) * max_score if total_tests > 0 else 0
                evaluation["feedback"] = f"Passed {passed_tests} out of {total_tests} test cases."
                evaluation["details"] = {"passed_tests": passed_tests, "total_tests": total_tests}
                
            elif dimension == "efficiency":
                complexity = quality_metrics.get("complexity", {})
                evaluation["score"] = self._calculate_efficiency_score(complexity, max_score)
                evaluation["feedback"] = self._generate_efficiency_feedback(complexity)
                evaluation["details"] = complexity
                
            elif dimension == "code_quality":
                style_issues = quality_metrics.get("style_issues", [])
                evaluation["score"] = self._calculate_quality_score(style_issues, max_score)
                evaluation["feedback"] = self._generate_quality_feedback(style_issues)
                evaluation["details"] = {"style_issues": style_issues}
                
            elif dimension == "problem_solving":
                # Get solution patterns
                patterns = self._identify_solution_patterns(code, problem_statement)
                
                # Calculate score based on patterns
                pattern_scores = {
                    "uses_appropriate_data_structures": 1.0,
                    "handles_edge_cases": 1.5,
                    "efficient_algorithm": 1.5,
                    "clear_logic": 1.0
                }
                
                total_score = sum(pattern_scores[pattern] for pattern, present in patterns.items() if present)
                evaluation["score"] = min(total_score, max_score)
                
                # Generate feedback based on patterns
                strengths = [pattern.replace("_", " ").title() for pattern, present in patterns.items() if present]
                areas_for_improvement = [pattern.replace("_", " ").title() for pattern, present in patterns.items() if not present]
                
                feedback_parts = []
                if strengths:
                    feedback_parts.append(f"Strengths: {', '.join(strengths)}.")
                if areas_for_improvement:
                    feedback_parts.append(f"Areas for improvement: {', '.join(areas_for_improvement)}.")
                
                evaluation["feedback"] = " ".join(feedback_parts)
                evaluation["details"] = {"patterns": patterns}
                
            elif dimension == "communication":
                evaluation["score"] = self._evaluate_communication(code, candidate_explanation, max_score)
                evaluation["feedback"] = self._generate_communication_feedback(code, candidate_explanation)
                evaluation["details"] = {
                    "code_clarity_score": self._assess_code_clarity(code),
                    "explanation_score": self._assess_explanation(candidate_explanation)
                }
            
            return evaluation
            
        except Exception as e:
            logging.error(f"Error evaluating dimension {dimension}: {str(e)}")
            # Return a default evaluation if something goes wrong
            return {
                "score": max_score * 0.6,  # Default to 60% score
                "max_score": max_score,
                "feedback": "Unable to fully evaluate this dimension. Using default assessment.",
                "details": {"error": str(e)}
            }
    
    def _calculate_efficiency_score(self, complexity: Dict[str, Any], max_score: float) -> float:
        """Calculate efficiency score based on complexity metrics."""
        # Default score if no complexity data
        if not complexity:
            return max_score * 0.6  # Default to 60% if no data
            
        # Get complexity metrics
        cyclomatic = complexity.get("cyclomatic", 0)
        cognitive = complexity.get("cognitive", 0)
        
        # Score based on complexity (lower is better)
        if cyclomatic <= 5 and cognitive <= 5:
            return max_score
        elif cyclomatic <= 10 and cognitive <= 10:
            return max_score * 0.8
        elif cyclomatic <= 15 and cognitive <= 15:
            return max_score * 0.6
        else:
            return max_score * 0.4
    
    def _generate_efficiency_feedback(self, complexity: Dict[str, Any]) -> str:
        """Generate feedback about code efficiency."""
        cyclomatic = complexity.get("cyclomatic", 1)
        if cyclomatic <= 5:
            return "Code has good complexity characteristics."
        elif cyclomatic <= 10:
            return "Code complexity is moderate. Consider simplifying some logic."
        else:
            return "Code is quite complex. Consider breaking down into smaller functions."
    
    def _calculate_quality_score(self, style_issues: List[Dict], max_score: float) -> float:
        """Calculate code quality score based on style issues."""
        if not style_issues:
            return max_score  # Perfect score if no issues
            
        # Count issues by severity
        severity_counts = {
            "error": 0,
            "warning": 0,
            "convention": 0,
            "refactor": 0
        }
        
        for issue in style_issues:
            severity = issue.get("type", "convention").lower()
            if severity in severity_counts:
                severity_counts[severity] += 1
                
        # Calculate penalty
        penalty = (
            severity_counts["error"] * 0.2 +
            severity_counts["warning"] * 0.1 +
            severity_counts["convention"] * 0.05 +
            severity_counts["refactor"] * 0.05
        )
        
        # Apply penalty but ensure score doesn't go below 20% of max
        return max(max_score * 0.2, max_score * (1 - penalty))
    
    def _generate_quality_feedback(self, style_issues: List[Dict]) -> str:
        """Generate feedback about code quality."""
        if not style_issues:
            return "Code follows good style practices."
        return f"Found {len(style_issues)} style issues. Consider addressing them for better code quality."
    
    def _evaluate_problem_solving(self, code: str, problem_statement: str, max_score: float) -> float:
        """Evaluate problem-solving approach."""
        patterns = self._identify_solution_patterns(code, problem_statement)
        
        # Calculate score based on identified patterns
        score = max_score * 0.6  # Start with 60% base score
        
        if patterns.get("uses_appropriate_data_structures", False):
            score += max_score * 0.1
        if patterns.get("handles_edge_cases", False):
            score += max_score * 0.1
        if patterns.get("efficient_algorithm", False):
            score += max_score * 0.1
        if patterns.get("clear_logic", False):
            score += max_score * 0.1
            
        return min(score, max_score)  # Ensure we don't exceed max_score
    
    def _generate_problem_solving_feedback(self, code: str, problem_statement: str) -> str:
        """Generate feedback about problem-solving approach."""
        solution_patterns = self._identify_solution_patterns(code, problem_statement)
        if solution_patterns["optimal"]:
            return "Excellent problem-solving approach with optimal solution."
        elif solution_patterns["valid"]:
            return "Good problem-solving approach. Consider optimizing further."
        else:
            return "Basic solution implemented. Consider exploring more efficient approaches."
    
    def _evaluate_communication(self, code: str, explanation: str, max_score: float) -> float:
        """Evaluate communication through code clarity and explanation."""
        code_clarity_score = self._assess_code_clarity(code) * 0.6  # 60% weight
        explanation_score = self._assess_explanation(explanation) * 0.4  # 40% weight
        
        return (code_clarity_score + explanation_score) * max_score
    
    def _generate_communication_feedback(self, code: str, explanation: str) -> str:
        """Generate feedback about communication."""
        code_clarity = self._assess_code_clarity(code)
        explanation_quality = self._assess_explanation(explanation)
        if code_clarity > 0.8 and explanation_quality > 0.8:
            return "Excellent communication through both code and explanation."
        elif code_clarity > 0.5 and explanation_quality > 0.5:
            return "Good communication. Consider adding more comments or explanation."
        else:
            return "Communication could be improved. Add comments and explain your approach."
    
    def _identify_solution_patterns(self, code: str, problem_statement: str) -> Dict[str, bool]:
        """Identify patterns in the solution implementation."""
        patterns = {
            "uses_appropriate_data_structures": False,
            "handles_edge_cases": False,
            "efficient_algorithm": False,
            "clear_logic": False
        }
        
        try:
            # Check for appropriate data structures
            data_structure_keywords = ["list", "dict", "set", "tuple", "array", "queue", "stack", "heap"]
            patterns["uses_appropriate_data_structures"] = any(keyword in code.lower() for keyword in data_structure_keywords)
            
            # Check for edge case handling
            edge_case_keywords = ["if", "else", "try", "except", "raise", "assert", "None", "empty", "len("]
            patterns["handles_edge_cases"] = any(keyword in code for keyword in edge_case_keywords)
            
            # Check for algorithm efficiency
            inefficient_patterns = ["nested for", "while True", "sleep(", "time.sleep"]
            efficient_patterns = ["[::-1]", "reversed(", "join(", "map(", "filter(", "comprehension"]
            patterns["efficient_algorithm"] = (
                not any(pattern in code for pattern in inefficient_patterns) or
                any(pattern in code for pattern in efficient_patterns)
            )
            
            # Check for clear logic
            clear_code_indicators = [
                len(code.split('\n')) < 20,  # Not too long
                code.count('    ') < 10,     # Not too deeply nested
                '#' in code,                 # Has comments
                code.count('\n\n') > 0,      # Uses spacing for readability
                not any(var in code for var in ['x', 'y', 'z', 'i', 'j', 'k'])  # Descriptive variable names
            ]
            patterns["clear_logic"] = sum(clear_code_indicators) >= 2  # At least 2 indicators present
            
        except Exception as e:
            logging.error(f"Error in _identify_solution_patterns: {str(e)}")
            # Return default patterns if analysis fails
            return patterns
            
        return patterns
    
    def _assess_code_clarity(self, code: str) -> float:
        """Assess the clarity of code implementation."""
        try:
            # Count positive indicators
            indicators = [
                len(code.split('\n')) < 20,  # Not too long
                code.count('    ') < 10,     # Not too deeply nested
                '#' in code,                 # Has comments
                code.count('\n\n') > 0,      # Uses spacing for readability
                not any(var in code for var in ['x', 'y', 'z', 'i', 'j', 'k'])  # Descriptive variable names
            ]
            
            # Calculate score (0.0 to 1.0)
            return sum(indicators) / len(indicators)
            
        except Exception as e:
            logging.error(f"Error in _assess_code_clarity: {str(e)}")
            return 0.6  # Default to moderate score if analysis fails
    
    def _assess_explanation(self, explanation: str) -> float:
        """Assess the quality of code explanation."""
        try:
            if not explanation:
                return 0.5  # Default score for no explanation
                
            # Count positive indicators
            indicators = [
                len(explanation.split()) >= 10,  # Reasonably detailed
                any(word in explanation.lower() for word in ['because', 'since', 'as']),  # Shows reasoning
                any(word in explanation.lower() for word in ['time', 'space', 'complexity']),  # Discusses complexity
                any(word in explanation.lower() for word in ['test', 'edge', 'case']),  # Mentions testing/edge cases
                explanation.count('.') >= 2  # Multiple complete thoughts
            ]
            
            # Calculate score (0.0 to 1.0)
            return sum(indicators) / len(indicators)
            
        except Exception as e:
            logging.error(f"Error in _assess_explanation: {str(e)}")
            return 0.5  # Default to moderate score if analysis fails
    
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
    
    def _generate_overall_assessment(self, dimensions: Dict[str, Any], total_score: float) -> str:
        """Generate an overall assessment based on dimension scores."""
        max_possible = sum(self.dimension_max_scores.values())
        percentage = (total_score / max_possible) * 100
        
        strengths = []
        areas_for_improvement = []
        
        for dimension, data in dimensions.items():
            score_percentage = (data["score"] / data["max_score"]) * 100
            if score_percentage >= 80:
                strengths.append(dimension)
            elif score_percentage <= 60:
                areas_for_improvement.append(dimension)
        
        assessment = []
        if percentage >= 80:
            assessment.append("Excellent performance overall.")
        elif percentage >= 60:
            assessment.append("Good performance with some areas for improvement.")
        else:
            assessment.append("Shows potential but needs significant improvement.")
            
        if strengths:
            assessment.append(f"Strong in: {', '.join(strengths)}.")
        if areas_for_improvement:
            assessment.append(f"Could improve in: {', '.join(areas_for_improvement)}.")
            
        return " ".join(assessment)
    
    def _identify_improvement_areas(self, dimensions: Dict[str, Any]) -> List[Dict[str, str]]:
        """Identify areas needing improvement based on scores."""
        improvements = []
        for dimension, data in dimensions.items():
            score_percentage = (data["score"] / data["max_score"]) * 100
            if score_percentage <= 70:
                improvements.append({
                    "area": dimension,
                    "feedback": data["feedback"],
                    "score": data["score"],
                    "max_score": data["max_score"]
                })
        return improvements
    
    def _identify_strengths(self, dimensions: Dict[str, Any]) -> List[Dict[str, str]]:
        """Identify areas of strength based on scores."""
        strengths = []
        for dimension, data in dimensions.items():
            score_percentage = (data["score"] / data["max_score"]) * 100
            if score_percentage >= 80:
                strengths.append({
                    "area": dimension,
                    "feedback": data["feedback"],
                    "score": data["score"],
                    "max_score": data["max_score"]
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
    """Evaluate a coding submission using a detailed rubric across multiple dimensions."""
    try:
        # Create evaluator instance
        evaluator = RubricEvaluator()
        
        # Get evaluation results
        evaluation = evaluator.evaluate_coding_submission(
            code=code,
            execution_results=execution_results,
            problem_statement=problem_statement,
            language=language,
            candidate_explanation=candidate_explanation
        )
        
        # Ensure we have all required fields
        if not evaluation:
            evaluation = {
                "dimensions": {},
                "total_score": 0.0,
                "max_possible_score": 20.0,  # 4 dimensions * 5 points each
                "feedback": {"error": "Evaluation failed"},
                "trust_score": 0.0,
                "score_level": "Error in evaluation",
                "overall_assessment": "Could not complete evaluation",
                "improvement_areas": [],
                "strengths": []
            }
        
        # Convert to JSON string
        return json.dumps(evaluation)
        
    except Exception as e:
        logging.error(f"Error in rubric evaluation: {str(e)}")
        error_response = {
            "dimensions": {},
            "total_score": 0.0,
            "max_possible_score": 20.0,
            "feedback": {"error": str(e)},
            "trust_score": 0.0,
            "score_level": "Error in evaluation",
            "overall_assessment": "Could not complete evaluation",
            "improvement_areas": [],
            "strengths": []
        }
        return json.dumps(error_response)


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
                "key_improvement_areas": [a["area"] for a in rubric_evaluation.get("improvement_areas", [])]
            },
            "detailed_rubric_analysis": rubric_evaluation.get("dimensions", {}),
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
                "development_areas": rubric_evaluation.get("improvement_areas", []),
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
    
    weak_areas = evaluation.get("improvement_areas", [])
    for area in weak_areas:
        if area["area"].lower() == "code quality":
            questions.append("Can you explain your approach to writing maintainable code?")
        elif area["area"].lower() == "efficiency":
            questions.append("How would you optimize this solution for better performance?")
        elif area["area"].lower() == "problem solving":
            questions.append("Walk me through your thought process for this problem.")
    
    return questions 