"""
AI Pair Programming tools for the {SYSTEM_NAME} platform.

This module provides advanced pair programming support, including:
- Context-aware code suggestions
- Intelligent code completion
- Real-time code review
- Pattern-based hints
"""
import logging
from typing import Dict, List, Optional, Any
import ast
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
import re

from ai_interviewer.tools.code_quality import CodeQualityMetrics
from ai_interviewer.utils.config import SYSTEM_NAME
# Import profiling utilities
from ai_interviewer.utils.profiling import timer, timed_function

# Configure logging
logger = logging.getLogger(__name__)

class HintGenerator:
    """
    Advanced hint generation system that provides context-aware hints
    based on code analysis and challenge context.
    """
    
    @staticmethod
    def generate_hints(code: str, challenge_info: Dict, 
                       error_message: Optional[str] = None, 
                       skill_level: str = "intermediate") -> List[str]:
        """
        Generate context-aware hints based on the code and challenge.
        
        Args:
            code: Current code implementation
            challenge_info: Information about the challenge
            error_message: Optional error message to address
            skill_level: Candidate's skill level (beginner, intermediate, advanced)
            
        Returns:
            List of hints appropriate for the context
        """
        hints = []
        
        try:
            # 1. Use predefined hints if available
            if challenge_info and "hints" in challenge_info and challenge_info["hints"]:
                # For demo purposes, provide the first hint
                # In production, we would track how many hints were provided
                hints.append(challenge_info["hints"][0])
                
            # 2. Add error-specific hints
            if error_message:
                error_hints = HintGenerator._generate_error_specific_hints(error_message, code)
                hints.extend(error_hints)
            
            # 3. Analyze code patterns and add pattern-specific hints
            pattern_hints = HintGenerator._generate_pattern_hints(code, challenge_info)
            hints.extend(pattern_hints)
            
            # 4. Generate difficulty-appropriate hints
            if challenge_info and "difficulty" in challenge_info:
                difficulty = challenge_info["difficulty"].lower()
                diff_hints = HintGenerator._generate_difficulty_based_hints(difficulty, skill_level)
                hints.extend(diff_hints)
            
            # 5. Generate algorithm hints based on challenge tags
            if challenge_info and "tags" in challenge_info:
                algo_hints = HintGenerator._generate_algorithm_hints(challenge_info["tags"])
                hints.extend(algo_hints)
                
            # 6. If we don't have enough hints, generate LLM-based hints
            if len(hints) < 2:
                llm_hints = HintGenerator._generate_llm_based_hints(code, challenge_info, error_message)
                hints.extend(llm_hints)
                
            return hints
        except Exception as e:
            logger.error(f"Error generating hints: {e}")
            return ["Try breaking the problem down into smaller steps.",
                    "Consider reviewing the problem requirements again."]
    
    @staticmethod
    def _generate_error_specific_hints(error_message: str, code: str) -> List[str]:
        """Generate hints based on specific error messages."""
        hints = []
        
        # Common Python errors and appropriate hints
        if "IndexError" in error_message or "index out of range" in error_message:
            hints.append("Check your array/list indices - you might be accessing beyond the bounds of your data structure.")
            hints.append("Add bounds checking before accessing elements by index.")
            
        elif "TypeError" in error_message:
            if "NoneType" in error_message:
                hints.append("You're trying to use a value that is None. Check for None before operations.")
            else:
                hints.append("The error suggests you're using incompatible types. Check your data types.")
                
        elif "NameError" in error_message:
            if "is not defined" in error_message:
                # Extract the variable name
                match = re.search(r"name '(\w+)' is not defined", error_message)
                if match:
                    var_name = match.group(1)
                    hints.append(f"The variable '{var_name}' is used but hasn't been defined yet.")
                else:
                    hints.append("You're using a variable before defining it.")
                    
        elif "SyntaxError" in error_message:
            hints.append("There's a syntax error in your code. Check for mismatched parentheses, missing colons, etc.")
            
        elif "ZeroDivisionError" in error_message:
            hints.append("You're attempting to divide by zero. Add a check to prevent this.")
            
        elif "RecursionError" in error_message or "maximum recursion depth exceeded" in error_message:
            hints.append("Your recursive function doesn't have a proper base case or isn't progressing toward it.")
            
        elif "KeyError" in error_message:
            hints.append("You're trying to access a dictionary key that doesn't exist. Use .get() or check for key existence first.")
            
        elif "timeout" in error_message.lower() or "time limit" in error_message.lower():
            hints.append("Your solution is taking too long. Consider a more efficient algorithm.")
            hints.append("Check if there's a nested loop or recursion that can be optimized.")
            
        return hints
    
    @staticmethod
    def _generate_pattern_hints(code: str, challenge_info: Dict) -> List[str]:
        """Generate hints based on code patterns found or expected."""
        hints = []
        
        # Analyze code for missing patterns that might be helpful
        try:
            # Parse the AST
            tree = ast.parse(code)
            
            # Check for common patterns
            has_loop = False
            has_recursion = False
            has_dict = False
            has_hashmap = False
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.For, ast.While)):
                    has_loop = True
                elif isinstance(node, ast.Dict):
                    has_dict = True
                
                # Check for recursion (function calling itself)
                if isinstance(node, ast.FunctionDef):
                    function_name = node.name
                    for subnode in ast.walk(node):
                        if isinstance(subnode, ast.Call) and hasattr(subnode.func, 'id') and subnode.func.id == function_name:
                            has_recursion = True
            
            # Generate hints based on challenge tags
            if challenge_info and "tags" in challenge_info:
                tags = [tag.lower() for tag in challenge_info["tags"]]
                
                # If problem requires recursion but none is used
                if "recursion" in tags and not has_recursion:
                    hints.append("This problem might be easier to solve using recursion.")
                
                # If problem could use dynamic programming
                if "dynamic programming" in tags and not has_dict:
                    hints.append("Consider using memoization to store already computed results.")
                
                # If problem could use a hashmap
                if "hashtable" in tags and not has_dict:
                    hints.append("A dictionary/hashtable can help store and look up values efficiently.")
                
                # If problem requires sorting
                if "sorting" in tags and "sorted" not in code and "sort(" not in code:
                    hints.append("Sorting the data might simplify your solution.")
            
        except Exception as e:
            logger.error(f"Error analyzing code patterns: {e}")
        
        return hints
    
    @staticmethod
    def _generate_difficulty_based_hints(difficulty: str, skill_level: str) -> List[str]:
        """Generate hints based on challenge difficulty and candidate skill level."""
        hints = []
        
        if difficulty == "easy":
            if skill_level == "beginner":
                hints.append("Focus on a straightforward approach - there's usually a simple solution for this problem.")
            else:
                hints.append("For easy problems, prioritize code clarity over optimization.")
                
        elif difficulty == "medium":
            if skill_level == "beginner":
                hints.append("Break down the problem into smaller, manageable steps.")
                hints.append("Consider drawing the problem on paper first to understand the pattern.")
            else:
                hints.append("Medium difficulty problems often require considering edge cases carefully.")
                
        elif difficulty == "hard":
            if skill_level == "beginner":
                hints.append("This is a challenging problem. Start with a brute force approach, then optimize.")
            elif skill_level == "intermediate":
                hints.append("Hard problems often require specific algorithms or data structures for optimal solutions.")
            else:
                hints.append("Consider the time and space complexity of your approach. Can you optimize further?")
                
        return hints
    
    @staticmethod
    def _generate_algorithm_hints(tags: List[str]) -> List[str]:
        """Generate algorithm-specific hints based on challenge tags."""
        hints = []
        tags = [tag.lower() for tag in tags]
        
        # Algorithm-specific hints
        if "arrays" in tags or "lists" in tags:
            hints.append("Consider using two pointers or a sliding window approach.")
            
        if "strings" in tags:
            hints.append("String problems often benefit from using dictionaries to count character occurrences.")
            
        if "binary search" in tags:
            hints.append("Binary search works on sorted arrays and has O(log n) complexity.")
            
        if "dynamic programming" in tags:
            hints.append("Try breaking down the problem into overlapping subproblems.")
            
        if "graph" in tags:
            hints.append("Consider using BFS (breadth-first search) or DFS (depth-first search) algorithms.")
            
        if "tree" in tags:
            hints.append("Tree traversals (pre-order, in-order, post-order) are powerful techniques for tree problems.")
            
        if "recursion" in tags:
            hints.append("Make sure your recursive solution has a clear base case to avoid infinite recursion.")
            
        return hints
    
    @staticmethod
    def _generate_llm_based_hints(code: str, challenge_info: Dict, error_message: Optional[str] = None) -> List[str]:
        """Generate hints using an LLM when other hints aren't sufficient."""
        try:
            # Create a prompt for the LLM
            prompt_template = """
            You are an expert programming mentor. Based on the code and challenge below, provide 2-3 helpful hints
            that will guide the candidate without revealing the complete solution.
            
            CHALLENGE DESCRIPTION:
            {description}
            
            CANDIDATE'S CURRENT CODE:
            ```
            {code}
            ```
            
            {error_info}
            
            Provide only the hints (no explanations, no code examples). Be concise and specific.
            """
            
            error_info = f"ERROR MESSAGE: {error_message}" if error_message else ""
            description = challenge_info.get("description", "No description available")
            
            # Create messages for the prompt
            messages = [
                SystemMessage(content="You are an expert programming mentor providing hints."),
                HumanMessage(content=prompt_template.format(
                    description=description,
                    code=code,
                    error_info=error_info
                ))
            ]
            
            # Get model from config (in production, this should use the configured model)
            llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0.2)
            
            # Generate response
            response = llm.invoke(messages)
            
            # Parse response into hints
            hint_text = response.content
            # Split response into individual hints
            raw_hints = hint_text.split("\n")
            # Clean up hints
            hints = [h.strip().strip("*-").strip() for h in raw_hints if h.strip()]
            # Filter out any hint that looks too long (likely explanation)
            hints = [h for h in hints if len(h) < 200]
            # Take up to 3 hints
            hints = hints[:3]
            
            return hints
            
        except Exception as e:
            logger.error(f"Error generating LLM-based hints: {e}")
            return ["Try a different approach if you're stuck."]

class CodeAnalyzer:
    """
    Analyzes code structure and patterns to provide intelligent suggestions.
    """
    
    @staticmethod
    def extract_code_context(code: str) -> Dict[str, Any]:
        """
        Extract contextual information from the code.
        
        Args:
            code: The code to analyze
            
        Returns:
            Dict containing code context information
        """
        try:
            tree = ast.parse(code)
            context = {
                "imports": [],
                "functions": [],
                "classes": [],
                "variables": [],
                "current_scope": None,
                "patterns": []
            }
            
            # Extract imports
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    context["imports"].extend(n.name for n in node.names)
                elif isinstance(node, ast.ImportFrom):
                    context["imports"].append(f"{node.module}.{node.names[0].name}")
                    
                # Extract functions
                elif isinstance(node, ast.FunctionDef):
                    func_info = {
                        "name": node.name,
                        "args": [arg.arg for arg in node.args.args],
                        "returns": node.returns.id if node.returns else None,
                        "docstring": ast.get_docstring(node)
                    }
                    context["functions"].append(func_info)
                    
                # Extract classes
                elif isinstance(node, ast.ClassDef):
                    class_info = {
                        "name": node.name,
                        "bases": [base.id for base in node.bases if isinstance(base, ast.Name)],
                        "methods": [m.name for m in node.body if isinstance(m, ast.FunctionDef)]
                    }
                    context["classes"].append(class_info)
                    
                # Extract variables
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            context["variables"].append(target.id)
            
            # Detect common patterns
            context["patterns"] = CodeAnalyzer._detect_patterns(tree)
            
            return context
            
        except Exception as e:
            logger.error(f"Error extracting code context: {e}")
            return {}
    
    @staticmethod
    def _detect_patterns(tree: ast.AST) -> List[str]:
        """
        Detect common programming patterns in the code.
        
        Args:
            tree: AST of the code
            
        Returns:
            List of detected patterns
        """
        patterns = []
        
        for node in ast.walk(tree):
            # Detect list comprehension
            if isinstance(node, ast.ListComp):
                patterns.append("list_comprehension")
                
            # Detect error handling
            elif isinstance(node, ast.Try):
                patterns.append("error_handling")
                
            # Detect recursion
            elif isinstance(node, ast.FunctionDef):
                for inner_node in ast.walk(node):
                    if isinstance(inner_node, ast.Call):
                        if hasattr(inner_node.func, 'id') and inner_node.func.id == node.name:
                            patterns.append("recursion")
                            break
                            
            # Detect iteration patterns
            elif isinstance(node, ast.For):
                patterns.append("iteration")
                
            # Detect map/filter/reduce patterns
            elif isinstance(node, ast.Call):
                if hasattr(node.func, 'id'):
                    if node.func.id in ['map', 'filter', 'reduce']:
                        patterns.append(f"{node.func.id}_function")
        
        return list(set(patterns))  # Remove duplicates

@tool
@timed_function(log_level=logging.INFO)
def suggest_code_improvements(code: str, context: Optional[Dict] = None) -> Dict:
    """
    Suggest improvements for the candidate's code.
    
    Args:
        code: The code to analyze
        context: Optional context about the code, challenge, etc.
        
    Returns:
        Dictionary containing suggestions and quality metrics
    """
    logger.info("Generating code improvement suggestions")
    
    try:
        # Extract language
        language = _determine_language(code)
        logger.info(f"Detected language: {language}")
        
        # Get quality metrics
        with timer("code_quality_metrics", log_level=logging.INFO):
            quality_metrics = CodeQualityMetrics.analyze_code(code, language)
        
        # Generate general suggestions
        suggestions = []
        
        # Add language-specific suggestions
        if language.lower() == "python":
            # Check if code has docstrings
            if not _has_docstrings(code):
                suggestions.append("Add docstrings to functions to clarify their purpose and parameters")
                
            # Check if code has long functions
            if _has_long_functions(code):
                suggestions.append("Consider breaking down long functions into smaller, focused ones")
                
            # Check if code has proper error handling
            if not _has_error_handling(code):
                suggestions.append("Add error handling for robust code (try/except blocks)")
                
            # Check for poor variable names
            if _has_poor_variable_names(code):
                suggestions.append("Use more descriptive variable names to improve readability")
            
            # Check for comments
            if not _has_comments(code):
                suggestions.append("Add comments to explain complex logic or algorithms")
        
        # Add context-aware suggestions
        if context:
            with timer("context_aware_suggestions", log_level=logging.INFO):
                context_suggestions = _generate_context_aware_suggestions(code, context)
                suggestions.extend(context_suggestions)
        
        # If no specific suggestions, get LLM-based suggestions
        if len(suggestions) < 3:
            with timer("llm_improvement_suggestions", log_level=logging.INFO):
                llm_config = {}  # Add LLM config if needed
                model = ChatGoogleGenerativeAI(
                    model="gemini-pro",
                    temperature=0.2
                )
                
                prompt = ChatPromptTemplate.from_messages([
                    SystemMessage(content="You are an expert code reviewer helping to improve code quality."),
                    HumanMessage(content=f"""
                    Analyze this {language} code and suggest 3-5 concrete, actionable improvements:
                    
                    ```{language}
                    {code}
                    ```
                    
                    Focus on:
                    1. Code organization
                    2. Algorithm efficiency
                    3. Best practices
                    4. Readability
                    
                    Provide specific, actionable suggestions, not general advice.
                    List each suggestion as a separate item.
                    """)
                ])
                
                response = model.invoke(prompt)
                
                # Extract suggestions (one per line)
                llm_suggestions = response.content.split('\n')
                # Clean up and filter suggestions
                llm_suggestions = [s.strip() for s in llm_suggestions if s.strip() and not s.startswith("```")]
                # Remove numbered prefixes like "1. " or "- "
                llm_suggestions = [re.sub(r'^(\d+\.\s*|\-\s*)', '', s) for s in llm_suggestions]
                # Limit to 5 suggestions
                llm_suggestions = [s for s in llm_suggestions if len(s) > 10][:5]
                
                suggestions.extend(llm_suggestions)
        
        # Return a limited number of unique suggestions
        unique_suggestions = list(set(suggestions))
        
        return {
            "suggestions": unique_suggestions[:5],  # Limit to 5 suggestions
            "quality_metrics": quality_metrics,
            "language": language
        }
        
    except Exception as e:
        logger.error(f"Error generating code improvements: {e}")
        return {
            "suggestions": ["Break your code into smaller, more manageable functions",
                            "Add comments to explain your approach",
                            "Check edge cases in your solution"],
            "quality_metrics": {"error": str(e)},
            "language": "unknown"
        }

@tool
@timed_function(log_level=logging.INFO)
def complete_code(code: str, context: Optional[str] = None) -> Dict:
    """
    Complete partially written code based on context and patterns.
    
    Args:
        code: Partial code to complete
        context: Optional context about what the code should do
        
    Returns:
        Dictionary containing completed code and confidence level
    """
    logger.info("Generating code completion")
    
    try:
        # Determine the language
        language = _determine_language(code)
        logger.info(f"Detected language: {language}")
        
        # Generate completion
        with timer("llm_code_completion", log_level=logging.INFO):
            completed_code = _generate_llm_completion(code, context, language)
        
        # If LLM completion is empty, fall back to rule-based completion
        if not completed_code:
            logger.warning("LLM completion failed, falling back to rule-based")
            if language.lower() == "python":
                # Analyze what kind of Python code needs completion
                if "def " in code and "return" not in code:
                    completed_code = _complete_python_function(code, context)
                elif "class " in code:
                    completed_code = _complete_python_class(code, context)
                elif "if " in code and ":" in code:
                    completed_code = _complete_python_if_statement(code, context)
                elif "for " in code or "while " in code:
                    loop_type = "for" if "for " in code else "while"
                    completed_code = _complete_python_loop(code, context, loop_type)
                else:
                    completed_code = _complete_general_python(code, context)
            else:
                # For other languages, use a more generic approach
                completed_code = _complete_javascript(code, context)
        
        return {
            "completed_code": completed_code,
            "language": language,
            "confidence": "high" if len(completed_code) > len(code) * 1.5 else "medium"
        }
        
    except Exception as e:
        logger.error(f"Error completing code: {e}")
        return {
            "completed_code": code + "\n# Unable to generate completion\n",
            "language": "unknown",
            "confidence": "low",
            "error": str(e)
        }

@tool
@timed_function(log_level=logging.INFO)
def review_code_section(code: str, section: Optional[str] = None) -> Dict:
    """
    Review a specific section of code and provide targeted feedback.
    
    Args:
        code: Code to review
        section: Optional section specifier (e.g., "error handling", "algorithm", "performance")
        
    Returns:
        Dictionary containing review comments organized by category
    """
    logger.info(f"Reviewing code{' section: ' + section if section else ''}")
    
    try:
        # Determine the language
        language = _determine_language(code)
        logger.info(f"Detected language: {language}")
        
        # Get initial review comments
        review_comments = []
        
        # Generate language-specific reviews
        with timer("generate_code_review", log_level=logging.INFO):
            if language.lower() == "python":
                review_comments = _review_python_code(code, section)
            elif language.lower() in ["javascript", "js"]:
                review_comments = _review_javascript_code(code, section)
            else:
                review_comments = _review_generic_code(code, section)
            
            # If we have very few comments, get LLM-based review
            if len(review_comments) < 3:
                llm_review = _generate_llm_code_review(code, section, language)
                review_comments.extend(llm_review)
        
        # Categorize comments
        categorized = {
            "style": [],
            "logic": [],
            "performance": [],
            "security": [],
            "general": []
        }
        
        # Basic categorization
        for comment in review_comments:
            if any(kw in comment.lower() for kw in ["format", "naming", "indent", "whitespace", "style"]):
                categorized["style"].append(comment)
            elif any(kw in comment.lower() for kw in ["algorithm", "logic", "condition", "bug", "error"]):
                categorized["logic"].append(comment)
            elif any(kw in comment.lower() for kw in ["performance", "efficient", "complex", "slow", "optimization"]):
                categorized["performance"].append(comment)
            elif any(kw in comment.lower() for kw in ["security", "injection", "validation", "sanitize"]):
                categorized["security"].append(comment)
            else:
                categorized["general"].append(comment)
        
        # Get quality metrics
        quality_metrics = CodeQualityMetrics.analyze_code(code, language)
        
        return {
            "comments": review_comments,
            "categorized": {k: v for k, v in categorized.items() if v},  # Only include non-empty categories
            "language": language,
            "quality_metrics": quality_metrics
        }
        
    except Exception as e:
        logger.error(f"Error reviewing code: {e}")
        return {
            "comments": ["Check for proper syntax and structure", 
                         "Ensure your logic handles all cases"],
            "categorized": {"general": ["Check for proper syntax and structure",
                                       "Ensure your logic handles all cases"]},
            "language": "unknown",
            "error": str(e)
        }

# Helper functions

def _has_docstrings(code: str) -> bool:
    """Check if code has docstrings."""
    return '"""' in code or "'''" in code

def _has_long_functions(code: str) -> bool:
    """Check if code has long functions."""
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if len(node.body) > 15:  # Arbitrary threshold
                    return True
        return False
    except:
        # If parsing fails, we can't determine
        return False

def _has_poor_variable_names(code: str) -> bool:
    """Check if code has poor variable names."""
    # Simple heuristic: look for single-letter variables that aren't common iterators
    single_letter_vars = re.findall(r'\b([a-zA-Z])\b', code)
    return any(v for v in single_letter_vars if v.lower() not in ['i', 'j', 'k', 'n', 'm', 'x', 'y'])

def _has_error_handling(code: str) -> bool:
    """Check if code has error handling."""
    return "try:" in code and "except" in code

def _has_comments(code: str) -> bool:
    """Check if code has comments."""
    # Look for # comments, excluding docstrings
    non_docstring_lines = code.replace('"""', '').replace("'''", '')
    return '#' in non_docstring_lines

def _determine_language(code: str) -> str:
    """Determine the language of the code."""
    if "def " in code or "import " in code or "class " in code or ":" in code:
        return "python"
    elif "function " in code or "var " in code or "let " in code or "const " in code or "{" in code:
        return "javascript"
    else:
        # Default to Python
        return "python"

def _generate_context_aware_suggestions(code: str, context: Dict) -> List[str]:
    """Use LLM to generate context-aware code suggestions."""
    try:
        # Create a prompt
        prompt_template = """
        You are an expert code reviewer. Analyze the following code and provide up to 3 specific,
        actionable suggestions for improvement that are relevant to the context.
        
        CODE:
        ```
        {code}
        ```
        
        CONTEXT:
        {context}
        
        Provide only the suggestions, one per line. Be specific but concise.
        """
        
        # Format context
        context_str = ""
        if "challenge" in context:
            challenge = context["challenge"]
            context_str += f"Problem: {challenge.get('title', '')}\n"
            context_str += f"Description: {challenge.get('description', '')}\n"
            context_str += f"Difficulty: {challenge.get('difficulty', 'medium')}\n"
            
        if "error_message" in context and context["error_message"]:
            context_str += f"Error: {context['error_message']}\n"
        
        if not context_str:
            context_str = "No specific context provided."
            
        # Create messages
        messages = [
            SystemMessage(content="You are an expert code reviewer providing actionable suggestions."),
            HumanMessage(content=prompt_template.format(code=code, context=context_str))
        ]
        
        # Get model response
        llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0.2)
        response = llm.invoke(messages)
        
        # Parse response into suggestions
        suggestion_text = response.content
        # Split by lines and clean up
        suggestions = [line.strip().strip("*-•").strip() for line in suggestion_text.split("\n") if line.strip()]
        # Filter out non-suggestions
        suggestions = [s for s in suggestions if len(s) > 10 and len(s) < 200]
        # Take up to 3 suggestions
        return suggestions[:3]
    except Exception as e:
        logger.error(f"Error generating LLM suggestions: {e}")
        return []

def _generate_llm_completion(code: str, context: Optional[str], language: str) -> str:
    """Generate code completion using an LLM."""
    try:
        # Create a prompt
        prompt_template = """
        You are an expert programmer. Complete the following code according to the context.
        
        LANGUAGE: {language}
        
        CODE TO COMPLETE:
        ```
        {code}
        ```
        
        CONTEXT: {context}
        
        Provide only the completed code without explanations or comments around it. 
        Include the original code followed by your completion in a way that makes the result 
        a working solution. Don't rewrite the entire code, just add what's missing.
        """
        
        context_text = context if context else "Complete the code in a logical way based on what's already written."
        
        # Create messages
        messages = [
            SystemMessage(content="You are an expert programmer providing code completions."),
            HumanMessage(content=prompt_template.format(
                language=language,
                code=code,
                context=context_text
            ))
        ]
        
        # Get model response
        llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0.2)
        response = llm.invoke(messages)
        
        # Extract code from response
        completion_text = response.content
        
        # Try to extract code block if present
        code_match = re.search(r'```(?:\w*\n)?([\s\S]*?)```', completion_text)
        if code_match:
            completion = code_match.group(1)
        else:
            completion = completion_text
            
        # Clean up the completion to make sure it properly continues the original code
        # This is a simplified approach; a production system would need more robust handling
        completion = completion.strip()
        
        return completion
    except Exception as e:
        logger.error(f"Error generating LLM completion: {e}")
        return "# Error generating completion\n"

def _generate_llm_code_review(code: str, section: Optional[str], language: str) -> List[str]:
    """Generate code review using an LLM."""
    try:
        # Create a prompt
        prompt_template = """
        You are an expert code reviewer. Review the following code and provide specific, 
        actionable feedback.
        
        LANGUAGE: {language}
        
        CODE TO REVIEW:
        ```
        {code}
        ```
        
        {section_info}
        
        Provide only the review comments, one per line. Be specific and actionable.
        Focus on issues and opportunities for improvement. Don't include explanations or introductions.
        """
        
        section_info = f"FOCUS ON SECTION: {section}" if section else "Review the entire code snippet."
        
        # Create messages
        messages = [
            SystemMessage(content="You are an expert code reviewer providing actionable feedback."),
            HumanMessage(content=prompt_template.format(
                language=language,
                code=code,
                section_info=section_info
            ))
        ]
        
        # Get model response
        llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0.2)
        response = llm.invoke(messages)
        
        # Parse response into review comments
        review_text = response.content
        # Split by lines and clean up
        comments = [line.strip().strip("*-•").strip() for line in review_text.split("\n") if line.strip()]
        # Filter out non-comments
        comments = [c for c in comments if len(c) > 10 and len(c) < 200]
        # Take up to 5 comments
        return comments[:5]
    except Exception as e:
        logger.error(f"Error generating LLM review: {e}")
        return []

# Simple placeholder implementations for code completion

def _complete_python_function(code: str, context: Optional[str]) -> str:
    """Complete a Python function."""
    return _generate_llm_completion(code, context, "python")

def _complete_python_class(code: str, context: Optional[str]) -> str:
    """Complete a Python class."""
    return _generate_llm_completion(code, context, "python")

def _complete_python_if_statement(code: str, context: Optional[str]) -> str:
    """Complete a Python if statement."""
    return _generate_llm_completion(code, context, "python")

def _complete_python_loop(code: str, context: Optional[str], loop_type: str) -> str:
    """Complete a Python loop."""
    context_with_loop = f"{context or ''} Complete a {loop_type} loop."
    return _generate_llm_completion(code, context_with_loop, "python")

def _complete_general_python(code: str, context: Optional[str]) -> str:
    """Complete general Python code."""
    return _generate_llm_completion(code, context, "python")

def _complete_javascript(code: str, context: Optional[str]) -> str:
    """Complete JavaScript code."""
    return _generate_llm_completion(code, context, "javascript")

# Simple placeholder implementations for code review

def _review_python_code(code: str, section: Optional[str]) -> List[str]:
    """Review Python code."""
    comments = []
    
    try:
        # Parse the AST to analyze code structure
        tree = ast.parse(code)
        
        # Check for various issues
        for node in ast.walk(tree):
            # Check for unused imports
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                comments.append("Check for unused imports and remove them.")
                break
                
        # Check for complex functions
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and len(node.body) > 15:
                comments.append(f"The function '{node.name}' is quite long. Consider breaking it into smaller functions.")
                
    except Exception as e:
        logger.error(f"Error parsing Python code for review: {e}")
        
    return comments

def _review_javascript_code(code: str, section: Optional[str]) -> List[str]:
    """Review JavaScript code."""
    comments = []
    
    # Simple pattern-based review for JavaScript
    if "var " in code:
        comments.append("Consider using 'let' or 'const' instead of 'var' for more predictable scoping.")
    
    if "==" in code:
        comments.append("Use strict equality '===' instead of '==' to avoid type coercion issues.")
        
    if "function " in code and "=>" not in code:
        comments.append("Consider using arrow functions for cleaner syntax where appropriate.")
        
    return comments

def _review_generic_code(code: str, section: Optional[str]) -> List[str]:
    """Review code generically."""
    comments = []
    
    if len(code.split("\n")) > 30:
        comments.append("The code is quite long. Consider modularizing it into smaller, reusable components.")
        
    if not _has_comments(code):
        comments.append("Add comments to explain complex logic and implementation decisions.")
        
    if not _has_docstrings(code):
        comments.append("Add docstrings to document the purpose and usage of functions and classes.")
        
    return comments