"""
Feedback interaction manager for sequential, AI-driven feedback sessions.
Handles the flow where AI proactively asks candidates about feedback areas.
"""

import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum

from langchain.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from ai_interviewer.utils.config import get_llm_config

logger = logging.getLogger(__name__)

class FeedbackArea(Enum):
    """Available feedback areas for exploration."""
    RUBRIC_SCORES = "rubric_scores"
    CODE_QUALITY = "code_quality"
    EFFICIENCY = "efficiency"
    PROBLEM_SOLVING = "problem_solving"
    COMMUNICATION = "communication"
    OVERALL_PERFORMANCE = "overall_performance"
    IMPROVEMENT_SUGGESTIONS = "improvement_suggestions"
    STRENGTHS = "strengths"
    DETAILED_REPORT = "detailed_report"

class FeedbackInteractionManager:
    """Manages sequential feedback interactions with the candidate."""
    
    def __init__(self):
        llm_config = get_llm_config()
        self.llm = ChatGoogleGenerativeAI(
            model=llm_config["model"],
            temperature=0.7  # Slightly higher for more conversational feedback
        )
        
        self.feedback_areas = {
            FeedbackArea.RUBRIC_SCORES: {
                "title": "Your Detailed Rubric Scores",
                "description": "See how you scored across different dimensions like correctness, efficiency, and code quality",
                "priority": 1
            },
            FeedbackArea.CODE_QUALITY: {
                "title": "Code Quality Analysis",
                "description": "Detailed feedback on your code structure, readability, and best practices",
                "priority": 2
            },
            FeedbackArea.EFFICIENCY: {
                "title": "Algorithm Efficiency Review",
                "description": "Analysis of your solution's time and space complexity",
                "priority": 3
            },
            FeedbackArea.PROBLEM_SOLVING: {
                "title": "Problem-Solving Approach",
                "description": "Feedback on how you approached and broke down the problem",
                "priority": 4
            },
            FeedbackArea.STRENGTHS: {
                "title": "Your Key Strengths",
                "description": "Areas where you performed particularly well",
                "priority": 5
            },
            FeedbackArea.IMPROVEMENT_SUGGESTIONS: {
                "title": "Specific Improvement Suggestions",
                "description": "Concrete steps you can take to improve your coding skills",
                "priority": 6
            },
            FeedbackArea.OVERALL_PERFORMANCE: {
                "title": "Overall Performance Summary",
                "description": "A comprehensive overview of your interview performance",
                "priority": 7
            },
            FeedbackArea.DETAILED_REPORT: {
                "title": "Complete Detailed Report",
                "description": "Full comprehensive report with all metrics and analysis",
                "priority": 8
            }
        }
    
    def generate_feedback_menu(self, rubric_evaluation: Dict[str, Any], 
                             explored_areas: List[str] = None) -> str:
        """Generate a conversational menu of feedback areas for the candidate."""
        
        explored_areas = explored_areas or []
        available_areas = [area for area in FeedbackArea if area.value not in explored_areas]
        
        if not available_areas:
            return self._generate_completion_message()
        
        # Sort by priority
        available_areas.sort(key=lambda x: self.feedback_areas[x]["priority"])
        
        menu_prompt = f"""Based on your coding challenge performance, I have several areas of feedback I can share with you. 

Your overall score was {rubric_evaluation.get('percentage', 'N/A')}% with a trust score of {rubric_evaluation.get('trust_score', 'N/A')}.

Here are the feedback areas I can explore with you:

"""
        
        for i, area in enumerate(available_areas[:4], 1):  # Show top 4 options
            info = self.feedback_areas[area]
            menu_prompt += f"{i}. **{info['title']}** - {info['description']}\n"
        
        menu_prompt += f"""
Which area would you like to explore first? You can either:
- Choose a number (1-{min(4, len(available_areas))})
- Ask about a specific area by name
- Say "surprise me" and I'll pick the most relevant area for you
- Say "show me everything" for a comprehensive overview

What interests you most?"""
        
        return menu_prompt
    
    def provide_area_feedback(self, area: FeedbackArea, rubric_evaluation: Dict[str, Any],
                            code: str = "", problem_statement: str = "") -> str:
        """Provide detailed feedback for a specific area."""
        
        try:
            if area == FeedbackArea.RUBRIC_SCORES:
                return self._provide_rubric_feedback(rubric_evaluation)
            elif area == FeedbackArea.CODE_QUALITY:
                return self._provide_code_quality_feedback(rubric_evaluation, code)
            elif area == FeedbackArea.EFFICIENCY:
                return self._provide_efficiency_feedback(rubric_evaluation, code)
            elif area == FeedbackArea.PROBLEM_SOLVING:
                return self._provide_problem_solving_feedback(rubric_evaluation, code, problem_statement)
            elif area == FeedbackArea.STRENGTHS:
                return self._provide_strengths_feedback(rubric_evaluation)
            elif area == FeedbackArea.IMPROVEMENT_SUGGESTIONS:
                return self._provide_improvement_feedback(rubric_evaluation)
            elif area == FeedbackArea.OVERALL_PERFORMANCE:
                return self._provide_overall_performance_feedback(rubric_evaluation)
            elif area == FeedbackArea.DETAILED_REPORT:
                return self._provide_detailed_report_feedback(rubric_evaluation)
            else:
                return "I don't have specific feedback for that area yet."
                
        except Exception as e:
            logger.error(f"Error providing feedback for {area}: {e}")
            return "I encountered an issue generating that feedback. Let's try a different area."
    
    def suggest_next_area(self, current_area: FeedbackArea, rubric_evaluation: Dict[str, Any],
                         explored_areas: List[str]) -> str:
        """Suggest the next logical feedback area to explore."""
        
        remaining_areas = [area for area in FeedbackArea if area.value not in explored_areas]
        
        if not remaining_areas:
            return self._generate_completion_message()
        
        # Logic for smart suggestions based on current area and performance
        if current_area == FeedbackArea.RUBRIC_SCORES:
            # If they just saw scores, suggest areas where they can improve or their strengths
            low_scores = [dim for dim, data in rubric_evaluation.get("rubric_scores", {}).items() 
                         if data.get("score", 0) <= 2]
            if low_scores and FeedbackArea.IMPROVEMENT_SUGGESTIONS not in [FeedbackArea(a) for a in explored_areas]:
                next_suggestion = FeedbackArea.IMPROVEMENT_SUGGESTIONS
            else:
                next_suggestion = FeedbackArea.STRENGTHS
        
        elif current_area == FeedbackArea.STRENGTHS:
            next_suggestion = FeedbackArea.IMPROVEMENT_SUGGESTIONS
        
        elif current_area == FeedbackArea.IMPROVEMENT_SUGGESTIONS:
            next_suggestion = FeedbackArea.CODE_QUALITY
        
        else:
            # Default progression
            remaining_by_priority = sorted(remaining_areas, key=lambda x: self.feedback_areas[x]["priority"])
            next_suggestion = remaining_by_priority[0]
        
        if next_suggestion not in remaining_areas:
            next_suggestion = remaining_areas[0] if remaining_areas else None
        
        if next_suggestion:
            info = self.feedback_areas[next_suggestion]
            return f"""Great! Would you like to explore **{info['title']}** next? 

{info['description']}

Or would you prefer to look at something else? I still have {len(remaining_areas)} areas we could explore together."""
        
        return self._generate_completion_message()
    
    def _provide_rubric_feedback(self, rubric_evaluation: Dict[str, Any]) -> str:
        """Provide detailed rubric score feedback."""
        
        rubric_scores = rubric_evaluation.get("rubric_scores", {})
        total_score = rubric_evaluation.get("total_score", 0)
        percentage = rubric_evaluation.get("percentage", 0)
        
        feedback = f"""Here's your detailed rubric breakdown:

**Overall Score: {total_score:.2f}/4.0 ({percentage}%)**

Let me break down how you performed in each area:

"""
        
        for dimension, data in rubric_scores.items():
            score = data.get("score", 0)
            score_level = data.get("score_level", "fair")
            rationale = data.get("rationale", "No detailed feedback available")
            
            # Convert score to descriptive performance
            performance_emoji = "🟢" if score >= 3 else "🟡" if score >= 2 else "🔴"
            
            feedback += f"""**{dimension.replace('_', ' ').title()}**: {score}/4 ({score_level}) {performance_emoji}
{rationale}

"""
        
        trust_score = rubric_evaluation.get("trust_score", 0)
        feedback += f"""**Trust Score**: {trust_score}/1.0
This reflects the consistency and reliability of your performance across all dimensions.

The areas where you excelled and those with room for improvement are what we can dive deeper into next!"""
        
        return feedback
    
    def _provide_code_quality_feedback(self, rubric_evaluation: Dict[str, Any], code: str) -> str:
        """Provide detailed code quality feedback."""
        
        quality_metrics = rubric_evaluation.get("quality_metrics", {})
        code_quality_score = rubric_evaluation.get("rubric_scores", {}).get("code_quality", {})
        
        feedback = f"""Let's dive into your code quality:

**Code Quality Score**: {code_quality_score.get('score', 'N/A')}/4 ({code_quality_score.get('score_level', 'N/A')})

"""
        
        if quality_metrics:
            # Extract specific metrics
            lines_of_code = quality_metrics.get("lines_of_code", "N/A")
            complexity = quality_metrics.get("cyclomatic_complexity", {})
            documentation = quality_metrics.get("documentation_score", "N/A")
            
            feedback += f"""**Code Metrics:**
- Lines of code: {lines_of_code}
- Cyclomatic complexity: {complexity.get('average', 'N/A')} (avg)
- Documentation score: {documentation}

"""
        
        feedback += f"""**Detailed Analysis:**
{code_quality_score.get('rationale', 'Your code shows good structure and readability.')}

**Specific Observations:**
"""
        
        for obs in code_quality_score.get('specific_observations', []):
            feedback += f"• {obs}\n"
        
        feedback += "\nThis gives you a clear picture of how readable and maintainable your code is!"
        
        return feedback
    
    def _provide_efficiency_feedback(self, rubric_evaluation: Dict[str, Any], code: str) -> str:
        """Provide algorithm efficiency feedback."""
        
        efficiency_score = rubric_evaluation.get("rubric_scores", {}).get("efficiency", {})
        
        feedback = f"""Let's analyze your algorithm's efficiency:

**Efficiency Score**: {efficiency_score.get('score', 'N/A')}/4 ({efficiency_score.get('score_level', 'N/A')})

**Analysis:**
{efficiency_score.get('rationale', 'Your solution shows good algorithmic thinking.')}

**Key Points:**
"""
        
        for obs in efficiency_score.get('specific_observations', []):
            feedback += f"• {obs}\n"
        
        # Add general efficiency advice
        feedback += """
**Understanding Efficiency:**
- Time complexity: How your algorithm scales with input size
- Space complexity: How much extra memory your solution uses
- Optimization opportunities: Ways to make your code faster

Efficiency becomes crucial when working with large datasets or in production systems!"""
        
        return feedback
    
    def _provide_problem_solving_feedback(self, rubric_evaluation: Dict[str, Any], 
                                        code: str, problem_statement: str) -> str:
        """Provide problem-solving approach feedback."""
        
        problem_solving_score = rubric_evaluation.get("rubric_scores", {}).get("problem_solving", {})
        
        feedback = f"""Let's look at your problem-solving approach:

**Problem-Solving Score**: {problem_solving_score.get('score', 'N/A')}/4 ({problem_solving_score.get('score_level', 'N/A')})

**Your Approach Analysis:**
{problem_solving_score.get('rationale', 'You showed a systematic approach to the problem.')}

**What I Observed:**
"""
        
        for obs in problem_solving_score.get('specific_observations', []):
            feedback += f"• {obs}\n"
        
        feedback += """
**Strong Problem-Solving Includes:**
- Breaking down complex problems into smaller parts
- Identifying patterns and edge cases
- Choosing appropriate data structures and algorithms
- Testing your logic as you build

Your approach to tackling problems is a key indicator of how you'll handle real-world challenges!"""
        
        return feedback
    
    def _provide_strengths_feedback(self, rubric_evaluation: Dict[str, Any]) -> str:
        """Provide feedback on candidate strengths."""
        
        strengths = rubric_evaluation.get("strengths", [])
        
        if not strengths:
            return "While I don't have specific strengths recorded, your participation in this interview shows initiative and willingness to learn!"
        
        feedback = "Here are the areas where you really shone:\n\n"
        
        for strength in strengths:
            area = strength.get("area", "Unknown")
            level = strength.get("level", "good")
            note = strength.get("note", "You performed well in this area")
            
            feedback += f"**{area}** ({level} performance)\n{note}\n\n"
        
        feedback += """These strengths are valuable assets! In real-world development, these are the kinds of skills that make you a strong team member and contributor.

Building on these strengths while addressing improvement areas will make you an even stronger developer."""
        
        return feedback
    
    def _provide_improvement_feedback(self, rubric_evaluation: Dict[str, Any]) -> str:
        """Provide specific improvement suggestions."""
        
        improvements = rubric_evaluation.get("areas_for_improvement", [])
        
        if not improvements:
            return "Great news! You performed well across all areas. Keep practicing to maintain and build on these skills!"
        
        feedback = "Here are specific areas where you can focus your improvement efforts:\n\n"
        
        for improvement in improvements:
            area = improvement.get("area", "Unknown")
            current_level = improvement.get("current_level", "fair")
            suggestion = improvement.get("suggestion", "Continue practicing in this area")
            
            feedback += f"**{area}** (Currently: {current_level})\n{suggestion}\n\n"
        
        feedback += """**Action Steps:**
- Practice coding problems that target these specific areas
- Review best practices and common patterns
- Consider taking online courses or tutorials focused on these topics
- Try explaining your approach out loud as you code

Remember, every developer has areas for growth - what matters is the commitment to continuous improvement!"""
        
        return feedback
    
    def _provide_overall_performance_feedback(self, rubric_evaluation: Dict[str, Any]) -> str:
        """Provide comprehensive overall performance feedback."""
        
        total_score = rubric_evaluation.get("total_score", 0)
        percentage = rubric_evaluation.get("percentage", 0)
        trust_score = rubric_evaluation.get("trust_score", 0)
        overall_assessment = rubric_evaluation.get("overall_assessment", "")
        
        feedback = f"""Here's your complete performance overview:

**Overall Interview Performance**
- Total Score: {total_score:.2f}/4.0 ({percentage}%)
- Trust Score: {trust_score}/1.0
- Assessment: {overall_assessment}

**Performance Summary:**
This interview evaluated you across five key dimensions that matter in real software development roles:

1. **Code Correctness** - Does your code work?
2. **Efficiency** - Is your solution optimal?
3. **Code Quality** - Is your code readable and maintainable?
4. **Problem Solving** - Do you approach problems systematically?
5. **Communication** - Is your code self-documenting?

**What This Means:**
"""
        
        if percentage >= 85:
            feedback += "Excellent performance! You're well-prepared for software development roles."
        elif percentage >= 70:
            feedback += "Strong performance with room for targeted improvement in specific areas."
        elif percentage >= 55:
            feedback += "Good foundation with clear opportunities for growth and development."
        else:
            feedback += "This is a learning opportunity - focus on fundamentals and keep practicing!"
        
        feedback += f"""

**Trust Score Context:**
Your trust score of {trust_score} reflects the consistency of your performance. Higher scores indicate reliable, consistent skills across different areas.

This comprehensive view helps you understand both where you excel and where focused practice will yield the biggest improvements."""
        
        return feedback
    
    def _provide_detailed_report_feedback(self, rubric_evaluation: Dict[str, Any]) -> str:
        """Provide information about accessing the detailed report."""
        
        return f"""Your complete detailed report includes:

**📊 Executive Summary**
- Overall performance metrics and recommendations
- Key strengths and improvement areas identified

**📋 Detailed Rubric Analysis**
- Dimension-by-dimension breakdown with rationale
- Specific observations for each scoring area

**💻 Code Quality Metrics**
- Technical analysis of your code structure
- Best practices compliance assessment

**🎯 Behavioral Assessment**
- Communication and problem-solving approach
- Interview interaction patterns

**📈 Technical Competency**
- Coding ability demonstration
- Problem-solving methodology analysis

**🔍 Interview Flow Analysis**
- Time to solution and interaction patterns
- Help-seeking behavior and learning indicators

**📝 Hiring Recommendations**
- Structured recommendation with confidence level
- Follow-up questions for deeper assessment

This comprehensive report gives you a complete picture of your interview performance and actionable insights for improvement.

The detailed report can be stored in your session memory for future reference and progress tracking."""
        
        return feedback
    
    def _generate_completion_message(self) -> str:
        """Generate a message when all feedback areas have been explored."""
        
        return """We've covered all the feedback areas I had prepared for you! 

You've shown great engagement by exploring different aspects of your performance. This kind of curiosity and desire for improvement is exactly what makes a strong developer.

**Next Steps:**
- Review the specific areas we discussed
- Focus your practice on the improvement areas we identified  
- Build on the strengths we highlighted
- Keep coding and challenging yourself with new problems

**Remember:** Every interview is a learning experience. The insights from today will help you grow as a developer.

Is there anything specific you'd like me to clarify or expand on from our feedback discussion?"""

    def parse_candidate_choice(self, response: str, available_areas: List[FeedbackArea]) -> Optional[FeedbackArea]:
        """Parse the candidate's response to determine which feedback area they want."""
        
        response_lower = response.lower().strip()
        
        # Handle numeric choices
        try:
            choice_num = int(response_lower)
            if 1 <= choice_num <= len(available_areas):
                return available_areas[choice_num - 1]
        except ValueError:
            pass
        
        # Handle "surprise me" or similar
        if any(phrase in response_lower for phrase in ["surprise", "pick for me", "choose", "recommend"]):
            # Return the highest priority available area
            return min(available_areas, key=lambda x: self.feedback_areas[x]["priority"])
        
        # Handle "everything" or "all"
        if any(phrase in response_lower for phrase in ["everything", "all", "comprehensive", "complete"]):
            return FeedbackArea.OVERALL_PERFORMANCE
        
        # Handle specific area mentions
        area_keywords = {
            "rubric": FeedbackArea.RUBRIC_SCORES,
            "score": FeedbackArea.RUBRIC_SCORES,
            "quality": FeedbackArea.CODE_QUALITY,
            "efficiency": FeedbackArea.EFFICIENCY,
            "performance": FeedbackArea.EFFICIENCY,
            "optimization": FeedbackArea.EFFICIENCY,
            "problem": FeedbackArea.PROBLEM_SOLVING,
            "approach": FeedbackArea.PROBLEM_SOLVING,
            "strengths": FeedbackArea.STRENGTHS,
            "strong": FeedbackArea.STRENGTHS,
            "good": FeedbackArea.STRENGTHS,
            "improve": FeedbackArea.IMPROVEMENT_SUGGESTIONS,
            "better": FeedbackArea.IMPROVEMENT_SUGGESTIONS,
            "suggestion": FeedbackArea.IMPROVEMENT_SUGGESTIONS,
            "overall": FeedbackArea.OVERALL_PERFORMANCE,
            "summary": FeedbackArea.OVERALL_PERFORMANCE,
            "report": FeedbackArea.DETAILED_REPORT,
            "detail": FeedbackArea.DETAILED_REPORT
        }
        
        for keyword, area in area_keywords.items():
            if keyword in response_lower and area in available_areas:
                return area
        
        return None


@tool
async def initiate_feedback_interaction(
    rubric_evaluation: dict,
    session_id: str,
    explored_areas: list = None
) -> str:
    """
    Initiate an interactive feedback session with the candidate.
    
    Args:
        rubric_evaluation: Complete rubric evaluation results
        session_id: Session ID for context
        explored_areas: List of already explored feedback areas
        
    Returns:
        Conversational feedback menu for the candidate
    """
    try:
        # Create feedback manager instance
        feedback_manager = FeedbackInteractionManager()
        
        # Generate initial feedback menu
        menu = feedback_manager.generate_feedback_menu(rubric_evaluation, explored_areas)
        
        # Store the interaction
        memory_manager = create_feedback_memory_manager()
        memory_manager.store_feedback_interaction(
            session_id=session_id,
            interaction_data={
                "type": "menu",
                "content": menu,
                "timestamp": datetime.now().isoformat()
            }
        )
        
        return menu
    except Exception as e:
        logger.error(f"Error in initiate_feedback_interaction: {e}")
        return "I apologize, but I encountered an error initiating the feedback session. Let me try a different approach to provide feedback on your code."


@tool
async def provide_feedback_for_area(
    area_name: str,
    rubric_evaluation: dict,
    code: str = "",
    problem_statement: str = "",
    session_id: str = ""
) -> str:
    """
    Provide detailed feedback for a specific area.
    
    Args:
        area_name: Name of the feedback area to explore
        rubric_evaluation: Complete rubric evaluation results
        code: The candidate's code submission
        problem_statement: Original problem statement
        session_id: Session ID for context
        
    Returns:
        Detailed feedback for the specified area
    """
    try:
        # First check if we have stored feedback for this area
        if session_id:
            memory_manager = create_feedback_memory_manager()
            feedback_history = memory_manager.get_feedback_summary(session_id)
            
            # Check if this area was already explored
            if feedback_history and "explored_areas" in feedback_history:
                for interaction in feedback_history.get("feedback_interactions", []):
                    if (interaction.get("type") == "area_explored" and 
                        interaction.get("area") == area_name and 
                        interaction.get("feedback_provided")):
                        
                        # Format the stored feedback for TTS
                        stored_feedback = interaction["feedback_provided"]
                        formatted_feedback = f"""Let me share the feedback about your {area_name.replace('_', ' ')}.

{stored_feedback}

Would you like me to elaborate on any specific aspect of this feedback?"""
                        
                        return formatted_feedback
        
        # If no stored feedback found, generate new feedback
        feedback_manager = FeedbackInteractionManager()
        
        # Get feedback for the specific area
        feedback = feedback_manager.provide_area_feedback(
            area=FeedbackArea[area_name.upper()],
            rubric_evaluation=rubric_evaluation,
            code=code,
            problem_statement=problem_statement
        )
        
        # Format the new feedback for TTS
        formatted_feedback = f"""I've analyzed your {area_name.replace('_', ' ')}. Here's what I found:

{feedback}

Would you like me to explain any part in more detail?"""
        
        # Store the interaction if session_id provided
        if session_id:
            memory_manager = create_feedback_memory_manager()
            memory_manager.store_feedback_interaction(
                session_id=session_id,
                interaction_data={
                    "type": "area_feedback",
                    "area": area_name,
                    "content": formatted_feedback,
                    "timestamp": datetime.now().isoformat()
                }
            )
            memory_manager.record_area_exploration(
                session_id=session_id,
                area=area_name,
                feedback_provided=formatted_feedback
            )
        
        return formatted_feedback
    except Exception as e:
        logger.error(f"Error in provide_feedback_for_area: {e}")
        return f"I apologize, but I encountered an error providing feedback for {area_name}. Let me try a different approach to analyze this aspect of your code."


@tool
async def suggest_next_feedback_area(
    current_area: str,
    rubric_evaluation: dict,
    explored_areas: list,
    session_id: str = ""
) -> str:
    """
    Suggest the next logical feedback area to explore.
    
    Args:
        current_area: Area just explored
        rubric_evaluation: Complete rubric evaluation results
        explored_areas: List of already explored areas
        session_id: Session ID for context
        
    Returns:
        Suggestion for next feedback area
    """
    try:
        # Get stored feedback data if available
        stored_explored_areas = []
        if session_id:
            memory_manager = create_feedback_memory_manager()
            feedback_history = memory_manager.get_feedback_summary(session_id)
            if feedback_history:
                stored_explored_areas = feedback_history.get("explored_areas", [])
        
        # Combine stored and current explored areas
        all_explored_areas = list(set(explored_areas + stored_explored_areas))
        
        # Create feedback manager instance
        feedback_manager = FeedbackInteractionManager()
        
        # Get suggestion for next area
        suggestion = feedback_manager.suggest_next_area(
            current_area=FeedbackArea[current_area.upper()],
            rubric_evaluation=rubric_evaluation,
            explored_areas=all_explored_areas
        )
        
        # Store the interaction if session_id provided
        if session_id:
            memory_manager = create_feedback_memory_manager()
            memory_manager.store_feedback_interaction(
                session_id=session_id,
                interaction_data={
                    "type": "area_suggestion",
                    "current_area": current_area,
                    "suggestion": suggestion,
                    "timestamp": datetime.now().isoformat()
                }
            )
        
        return suggestion
    except Exception as e:
        logger.error(f"Error in suggest_next_feedback_area: {e}")
        return "I apologize, but I encountered an error suggesting the next feedback area. Let's continue with your code review." 