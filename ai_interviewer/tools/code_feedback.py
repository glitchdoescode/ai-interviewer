"""
Code feedback generation for AI Interviewer platform.

This module provides utilities for generating detailed feedback on code submissions,
including specific improvement suggestions and performance analysis.
"""
import logging
from typing import Dict, List, Optional, Any
import re

from ai_interviewer.tools.code_quality import CodeQualityMetrics

# Configure logging
logger = logging.getLogger(__name__)


class CodeFeedbackGenerator:
    """
    Generates detailed and structured feedback for coding challenge submissions.
    
    Features:
    - Performance analysis (time and space complexity)
    - Code quality assessment (style, maintainability)
    - Specific improvement suggestions
    - Pattern recognition for common anti-patterns
    - Language-specific best practices
    """
    
    @staticmethod
    def generate_feedback(
        code: str, 
        execution_results: Dict[str, Any],
        language: str = "python",
        skill_level: str = "intermediate"
    ) -> Dict[str, Any]:
        """
        Generate comprehensive feedback for a code submission.
        
        Args:
            code: The submitted code
            execution_results: Results from code execution
            language: Programming language of submission
            skill_level: Skill level of the candidate (beginner, intermediate, advanced)
            
        Returns:
            Dictionary containing structured feedback
        """
        feedback = {
            "summary": "",
            "correctness": {},
            "efficiency": {},
            "code_quality": {},
            "suggestions": [],
            "strengths": [],
            "areas_for_improvement": [],
            "tailored_by_level": {}
        }
        
        # Process execution results
        if execution_results:
            feedback["correctness"] = CodeFeedbackGenerator._analyze_correctness(execution_results)
        
        # Get language-specific quality metrics and feedback
        if language.lower() == "python":
            quality_metrics = CodeQualityMetrics.analyze_python_code(code)
            feedback["code_quality"] = CodeFeedbackGenerator._analyze_code_quality(quality_metrics)
            feedback["efficiency"] = CodeFeedbackGenerator._analyze_python_efficiency(code, execution_results)
        elif language.lower() == "javascript":
            feedback["code_quality"] = {"message": "JavaScript code quality analysis not fully implemented"}
            feedback["efficiency"] = {"message": "JavaScript efficiency analysis not fully implemented"}
        
        # Generate detailed suggestions
        feedback["suggestions"] = CodeFeedbackGenerator._generate_improvement_suggestions(
            code, language, execution_results
        )
        
        # Identify code strengths
        feedback["strengths"] = CodeFeedbackGenerator._identify_strengths(
            code, language, execution_results, feedback["code_quality"]
        )
        
        # Identify areas for improvement
        feedback["areas_for_improvement"] = CodeFeedbackGenerator._identify_improvement_areas(
            code, language, execution_results, feedback["code_quality"]
        )
        
        # Tailor feedback based on skill level
        feedback["tailored_by_level"] = CodeFeedbackGenerator._tailor_by_skill_level(
            skill_level, feedback
        )
        
        # Generate summary
        feedback["summary"] = CodeFeedbackGenerator._generate_summary(feedback)
        
        return feedback
    
    @staticmethod
    def _analyze_correctness(execution_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze the correctness of the submission based on test case results.
        
        Args:
            execution_results: Results from code execution
            
        Returns:
            Dictionary with correctness analysis
        """
        correctness = {
            "passed_all_tests": execution_results.get("passed", 0) == len(execution_results.get("test_results", [])),
            "pass_rate": 0,
            "analysis": [],
            "test_case_feedback": []
        }
        
        # Calculate pass rate
        total_tests = len(execution_results.get("test_results", []))
        passed_tests = execution_results.get("passed", 0)
        
        if total_tests > 0:
            correctness["pass_rate"] = passed_tests / total_tests
        
        # Generate overall analysis
        if correctness["passed_all_tests"]:
            correctness["analysis"].append("All test cases passed successfully.")
        elif correctness["pass_rate"] > 0.5:
            correctness["analysis"].append(
                f"The solution passed {passed_tests} out of {total_tests} test cases. "
                "There are some issues to address."
            )
        else:
            correctness["analysis"].append(
                f"The solution passed only {passed_tests} out of {total_tests} test cases. "
                "There are significant issues to address."
            )
        
        # Generate specific feedback for each test case
        for test_result in execution_results.get("test_results", []):
            # Only provide detailed feedback for failed tests
            if not test_result.get("passed", True) and not test_result.get("is_hidden", False):
                input_val = test_result.get("input")
                expected = test_result.get("expected_output")
                actual = test_result.get("output")
                explanation = test_result.get("explanation", "")
                
                # Format the feedback
                feedback = f"Test with input {input_val} failed. "
                feedback += f"Expected {expected}, but got {actual}. "
                
                # Add explanation if available
                if explanation:
                    feedback += f"This test checks: {explanation}"
                
                # Add error information if available
                if test_result.get("error"):
                    feedback += f" Error: {test_result.get('error')}"
                
                correctness["test_case_feedback"].append(feedback)
        
        return correctness
    
    @staticmethod
    def _analyze_code_quality(quality_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze code quality based on metrics.
        
        Args:
            quality_metrics: Code quality metrics
            
        Returns:
            Dictionary with code quality analysis
        """
        quality = {
            "overall_score": 0,
            "complexity": {},
            "maintainability": {},
            "style": {},
            "documentation": {},
            "analysis": []
        }
        
        # Calculate overall score (0-10)
        scores = []
        if "complexity" in quality_metrics:
            cc = quality_metrics["complexity"].get("cyclomatic_complexity", 0)
            cc_score = 10 - min(10, max(0, cc - 1))  # Lower complexity is better
            quality["complexity"] = {
                "score": cc_score,
                "value": cc,
                "interpretation": quality_metrics["complexity"].get("interpretation", "")
            }
            scores.append(cc_score)
        
        if "maintainability" in quality_metrics:
            mi = quality_metrics["maintainability"].get("maintainability_index", 0)
            mi_score = min(10, max(0, mi / 10))  # Higher MI is better
            quality["maintainability"] = {
                "score": mi_score,
                "value": mi,
                "interpretation": quality_metrics["maintainability"].get("interpretation", "")
            }
            scores.append(mi_score)
        
        if "style" in quality_metrics:
            style_score = quality_metrics["style"].get("pylint_score", 0)
            quality["style"] = {
                "score": style_score,
                "value": style_score,
                "interpretation": quality_metrics["style"].get("interpretation", "")
            }
            scores.append(style_score)
        
        if "documentation" in quality_metrics:
            doc_ratio = quality_metrics["documentation"].get("doc_ratio", 0)
            doc_score = min(10, max(0, doc_ratio * 10))  # Higher ratio is better
            quality["documentation"] = {
                "score": doc_score,
                "value": doc_ratio,
                "interpretation": quality_metrics["documentation"].get("interpretation", "")
            }
            scores.append(doc_score)
        
        # Calculate overall score
        if scores:
            quality["overall_score"] = sum(scores) / len(scores)
        
        # Generate overall analysis
        quality["analysis"] = quality_metrics.get("interpretations", [])
        
        return quality
    
    @staticmethod
    def _analyze_python_efficiency(code: str, execution_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze the efficiency of Python code.
        
        Args:
            code: Python code to analyze
            execution_results: Results from code execution
            
        Returns:
            Dictionary with efficiency analysis
        """
        efficiency = {
            "time_complexity": "Unknown",
            "space_complexity": "Unknown",
            "execution_metrics": {},
            "analysis": []
        }
        
        # Extract execution metrics if available
        if "detailed_metrics" in execution_results:
            metrics = execution_results["detailed_metrics"]
            efficiency["execution_metrics"] = {
                "avg_execution_time": metrics.get("avg_execution_time", 0),
                "max_execution_time": metrics.get("max_execution_time", 0)
            }
        
        # Heuristic time complexity estimation based on code patterns
        # This is a simplified analysis - in a production system, this would be more sophisticated
        # and would analyze the AST for loops, nested loops, recursion, etc.
        if "for" in code and "for" in code.split("for")[1]:
            # Nested loops detected
            efficiency["time_complexity"] = "O(n²) - Quadratic"
            efficiency["analysis"].append(
                "The code contains nested loops, suggesting quadratic time complexity."
            )
        elif "for" in code:
            # Single loop
            efficiency["time_complexity"] = "O(n) - Linear"
            efficiency["analysis"].append(
                "The code contains a loop, suggesting linear time complexity."
            )
        elif "while" in code:
            # While loop
            efficiency["time_complexity"] = "O(n) - Linear"
            efficiency["analysis"].append(
                "The code contains a while loop, suggesting linear or potentially higher time complexity."
            )
        elif "recursion" in execution_results.get("patterns", []):
            # Recursive function
            efficiency["time_complexity"] = "O(?) - Recursive"
            efficiency["analysis"].append(
                "The code uses recursion, making complexity dependent on recursion depth."
            )
        else:
            # Default to constant time
            efficiency["time_complexity"] = "O(1) - Constant"
            efficiency["analysis"].append(
                "The code appears to have constant time complexity."
            )
        
        # Execution time analysis
        avg_time = efficiency["execution_metrics"].get("avg_execution_time", 0)
        if avg_time > 0.1:
            efficiency["analysis"].append(
                f"Average execution time of {avg_time:.6f} seconds suggests room for optimization."
            )
        
        return efficiency
    
    @staticmethod
    def _generate_improvement_suggestions(
        code: str, language: str, execution_results: Dict[str, Any]
    ) -> List[str]:
        """
        Generate specific improvement suggestions based on code analysis.
        
        Args:
            code: The code to analyze
            language: Programming language of the code
            execution_results: Results from code execution
            
        Returns:
            List of improvement suggestions
        """
        suggestions = []
        
        # Add general suggestions based on execution results
        if not execution_results.get("all_passed", False):
            suggestions.append(
                "Focus on fixing failed test cases. Check your logic for edge cases."
            )
        
        # Language-specific suggestions
        if language.lower() == "python":
            # Check for list comprehension opportunities
            if "for" in code and "append" in code and "[" not in code.split("for")[0]:
                suggestions.append(
                    "Consider using list comprehensions for concise collection generation."
                )
            
            # Check for error handling
            if "try" not in code and "except" not in code:
                suggestions.append(
                    "Add error handling with try-except blocks to make your code more robust."
                )
            
            # Check for docstrings
            if '"""' not in code and "'''" not in code:
                suggestions.append(
                    "Add docstrings to document your functions and clarify their purpose."
                )
            
            # Check for magic numbers
            if re.search(r"[^0-9]\d+[^0-9]", code):
                suggestions.append(
                    "Replace magic numbers with named constants for better readability."
                )
                
            # Check for function decomposition opportunities
            if len(code.split("\n")) > 20 and code.count("def ") < 2:
                suggestions.append(
                    "Consider breaking down your solution into smaller, focused functions."
                )
        
        # JavaScript-specific suggestions
        elif language.lower() == "javascript":
            # Check for error handling
            if "try" not in code and "catch" not in code:
                suggestions.append(
                    "Add error handling with try-catch blocks to make your code more robust."
                )
            
            # Check for arrow functions opportunities
            if "function(" in code and "=>" not in code:
                suggestions.append(
                    "Consider using arrow functions for more concise function definitions."
                )
        
        # Generic suggestions
        if execution_results.get("execution_time", 0) > 0.1:
            suggestions.append(
                "Look for opportunities to optimize performance, such as avoiding redundant calculations."
            )
        
        # Add algorithm-specific suggestions based on problem patterns
        # (This would be expanded in a real implementation)
        
        return suggestions
    
    @staticmethod
    def _identify_strengths(
        code: str, language: str, execution_results: Dict[str, Any], quality: Dict[str, Any]
    ) -> List[str]:
        """
        Identify strengths in the code submission.
        
        Args:
            code: The code to analyze
            language: Programming language of the code
            execution_results: Results from code execution
            quality: Code quality metrics
            
        Returns:
            List of identified strengths
        """
        strengths = []
        
        # Correctness strengths
        if execution_results.get("all_passed", False):
            strengths.append("Correctly solves all test cases.")
        elif execution_results.get("passed", 0) / max(1, len(execution_results.get("test_results", []))) > 0.7:
            strengths.append("Successfully handles most test cases.")
        
        # Quality-related strengths
        if quality.get("overall_score", 0) > 7:
            strengths.append("Overall high code quality.")
        
        # Complexity strengths
        if quality.get("complexity", {}).get("score", 0) > 7:
            strengths.append("Appropriately manages code complexity.")
        
        # Style strengths
        if quality.get("style", {}).get("score", 0) > 7:
            strengths.append("Good adherence to coding style guidelines.")
        
        # Documentation strengths
        if quality.get("documentation", {}).get("score", 0) > 7:
            strengths.append("Well-documented code with clear comments and docstrings.")
        
        # Language-specific strengths
        if language.lower() == "python":
            # Check for pythonic features
            if "list comprehension" in execution_results.get("patterns", []):
                strengths.append("Good use of Pythonic features like list comprehensions.")
            
            if "lambda" in code:
                strengths.append("Effective use of lambda functions for functional programming patterns.")
            
            if "with" in code:
                strengths.append("Good use of context managers for resource management.")
            
        elif language.lower() == "javascript":
            # Check for modern JS features
            if "=>" in code:
                strengths.append("Good use of modern JavaScript features like arrow functions.")
            
            if "const" in code or "let" in code:
                strengths.append("Proper use of block-scoped variables.")
        
        return strengths
    
    @staticmethod
    def _identify_improvement_areas(
        code: str, language: str, execution_results: Dict[str, Any], quality: Dict[str, Any]
    ) -> List[str]:
        """
        Identify areas for improvement in the code submission.
        
        Args:
            code: The code to analyze
            language: Programming language of the code
            execution_results: Results from code execution
            quality: Code quality metrics
            
        Returns:
            List of areas for improvement
        """
        areas = []
        
        # Correctness issues
        if not execution_results.get("all_passed", False):
            areas.append("Fix failing test cases to ensure correct functionality.")
        
        # Quality issues
        if quality.get("overall_score", 10) < 5:
            areas.append("Improve overall code quality through better practices.")
        
        # Complexity issues
        if quality.get("complexity", {}).get("score", 10) < 5:
            areas.append("Reduce code complexity for better maintainability.")
        
        # Style issues
        if quality.get("style", {}).get("score", 10) < 5:
            areas.append("Address style issues to improve code readability.")
        
        # Documentation issues
        if quality.get("documentation", {}).get("score", 10) < 5:
            areas.append("Improve code documentation with better comments and docstrings.")
        
        # Efficiency issues
        if execution_results.get("execution_time", 0) > 0.5:
            areas.append("Optimize for better performance to reduce execution time.")
        
        # Language-specific areas for improvement
        if language.lower() == "python":
            # Check for non-pythonic patterns
            if "for" in code and "append" in code and "[" not in code.split("for")[0]:
                areas.append("Make code more Pythonic by using list comprehensions where appropriate.")
            
            if "range(len(" in code:
                areas.append("Use enumerate() instead of range(len()) for more Pythonic iteration.")
        
        return areas
    
    @staticmethod
    def _tailor_by_skill_level(skill_level: str, feedback: Dict[str, Any]) -> Dict[str, Any]:
        """
        Tailor feedback based on candidate's skill level.
        
        Args:
            skill_level: Skill level of the candidate
            feedback: Existing feedback data
            
        Returns:
            Tailored feedback data
        """
        tailored = {
            "focus_areas": [],
            "learning_resources": []
        }
        
        # Tailor based on skill level
        if skill_level.lower() == "beginner":
            # For beginners, focus on correctness and readability
            tailored["focus_areas"] = [
                "Focus on getting your solutions to work correctly first.",
                "Practice writing clean, readable code with good variable names.",
                "Add comments to explain your thinking process."
            ]
            
            # Add beginner-friendly resources
            tailored["learning_resources"] = [
                "Codecademy or freeCodeCamp for interactive tutorials",
                "Python for Everybody or JavaScript.info",
                "Practice on LeetCode's easy problems"
            ]
            
        elif skill_level.lower() == "intermediate":
            # For intermediates, focus on efficiency and patterns
            tailored["focus_areas"] = [
                "Focus on optimizing your solutions for efficiency.",
                "Learn and apply design patterns appropriate to the problem.",
                "Practice more complex data structures and algorithms."
            ]
            
            # Add intermediate-level resources
            tailored["learning_resources"] = [
                "Clean Code by Robert C. Martin",
                "Algorithm Design Manual by Steven Skiena",
                "Medium difficulty problems on LeetCode or HackerRank"
            ]
            
        elif skill_level.lower() == "advanced":
            # For advanced, focus on optimization and edge cases
            tailored["focus_areas"] = [
                "Focus on handling all edge cases elegantly.",
                "Optimize for both time and space complexity.",
                "Apply advanced language features and design patterns appropriately."
            ]
            
            # Add advanced resources
            tailored["learning_resources"] = [
                "Introduction to Algorithms (CLRS)",
                "System Design interviews and resources",
                "Challenging problems on LeetCode, Codeforces, or competitive programming sites"
            ]
        
        return tailored
    
    @staticmethod
    def _generate_summary(feedback: Dict[str, Any]) -> str:
        """
        Generate a concise summary of the feedback.
        
        Args:
            feedback: Complete feedback data
            
        Returns:
            Summary string
        """
        # Generate a concise summary based on key metrics and findings
        
        # Start with correctness assessment
        correctness = feedback["correctness"]
        if correctness.get("passed_all_tests", False):
            summary = "Your solution correctly passes all test cases. "
        else:
            pass_rate = correctness.get("pass_rate", 0)
            summary = f"Your solution passes {int(pass_rate * 100)}% of test cases. "
        
        # Add quality assessment
        quality_score = feedback["code_quality"].get("overall_score", 0)
        if quality_score > 8:
            summary += "Code quality is excellent. "
        elif quality_score > 6:
            summary += "Code quality is good. "
        elif quality_score > 4:
            summary += "Code quality could use improvement. "
        else:
            summary += "Code quality needs significant improvement. "
        
        # Add key strength if available
        if feedback["strengths"]:
            summary += f"Key strength: {feedback['strengths'][0]} "
        
        # Add key improvement area if available
        if feedback["areas_for_improvement"]:
            summary += f"Focus on: {feedback['areas_for_improvement'][0]}"
        
        return summary 