"""
Code quality analysis tools for the AI Interviewer platform.

This module provides tools for analyzing code quality, including metrics
for complexity, style, and best practices.
"""
import ast
import logging
import io
import sys
from typing import Dict, List, Optional, Any
from radon.complexity import cc_visit
from radon.metrics import h_visit, mi_visit
from radon.raw import analyze
import pylint.lint
from pylint.reporters import JSONReporter

# Configure logging
logger = logging.getLogger(__name__)

class CodeQualityMetrics:
    """
    Analyzes code quality using various metrics and tools.
    
    This class uses multiple Python static analysis tools to evaluate:
    - Cyclomatic complexity
    - Maintainability index
    - Code style (PEP 8)
    - Common anti-patterns
    - Documentation quality
    """
    
    @staticmethod
    def analyze_python_code(code: str) -> Dict[str, Any]:
        """
        Analyze Python code quality using multiple metrics.
        
        Args:
            code: The Python code to analyze
            
        Returns:
            Dict containing various code quality metrics
        """
        try:
            # Run pylint with custom reporter
            pylint_score = 10.0  # Default score
            try:
                # Create a temporary file for pylint
                file_path = io.StringIO()
                file_path.write(code)
                file_path.seek(0)
                
                # Set up a custom JSON reporter to capture output
                json_reporter = JSONReporter()
                
                # Run pylint with the JSON reporter
                # Newer versions of pylint use Run constructor differently
                args = ['--output-format=json', '--disable=import-error', '--disable=no-name-in-module']
                pylint.lint.Run([*args, ''], reporter=json_reporter, exit=False)
                
                # Process messages
                messages = json_reporter.messages
                
                # Calculate score based on message types
                if messages:
                    error_count = sum(1 for msg in messages if msg.category in ('error', 'fatal'))
                    warning_count = sum(1 for msg in messages if msg.category == 'warning')
                    convention_count = sum(1 for msg in messages if msg.category == 'convention')
                    
                    # Deduct points based on message severity
                    pylint_score -= error_count * 2.0
                    pylint_score -= warning_count * 1.0
                    pylint_score -= convention_count * 0.5
                    
                    # Ensure score is between 0 and 10
                    pylint_score = max(0.0, min(10.0, pylint_score))
            except Exception as e:
                logger.error(f"Error running pylint: {e}")
                pylint_score = 5.0  # Default score on error
            
            # Calculate cyclomatic complexity
            try:
                complexity_results = cc_visit(code)
                avg_complexity = sum(item.complexity for item in complexity_results) / len(complexity_results) if complexity_results else 0
            except Exception as e:
                logger.error(f"Error calculating cyclomatic complexity: {e}")
                avg_complexity = 5.0  # Default value on error
            
            # Calculate maintainability index
            try:
                mi_result = mi_visit(code, multi=True)
                maintainability_index = sum(mi_result.values()) / len(mi_result) if mi_result else 100
            except Exception as e:
                logger.error(f"Error calculating maintainability index: {e}")
                maintainability_index = 70.0  # Default value on error
            
            # Calculate Halstead metrics
            try:
                h_result = h_visit(code)
            except Exception as e:
                logger.error(f"Error calculating Halstead metrics: {e}")
                h_result = None
            
            # Calculate raw metrics
            try:
                raw_metrics = analyze(code)
            except Exception as e:
                logger.error(f"Error calculating raw metrics: {e}")
                raw_metrics = None
            
            # Analyze documentation
            try:
                doc_ratio = CodeQualityMetrics._analyze_documentation(code)
            except Exception as e:
                logger.error(f"Error analyzing documentation: {e}")
                doc_ratio = 0.5  # Default value on error
            
            # Compile metrics
            metrics = {
                "complexity": {
                    "cyclomatic_complexity": avg_complexity,
                    "interpretation": "Low" if avg_complexity < 5 else "Medium" if avg_complexity < 10 else "High"
                },
                "maintainability": {
                    "maintainability_index": maintainability_index,
                    "interpretation": "Good" if maintainability_index > 80 else "Medium" if maintainability_index > 60 else "Poor"
                },
                "style": {
                    "pylint_score": pylint_score,
                    "interpretation": "Good" if pylint_score >= 8 else "Medium" if pylint_score >= 6 else "Poor"
                },
                "documentation": {
                    "doc_ratio": doc_ratio,
                    "interpretation": "Good" if doc_ratio >= 0.8 else "Medium" if doc_ratio >= 0.5 else "Poor"
                }
            }
            
            # Add Halstead metrics if available
            if h_result:
                metrics["halstead"] = {
                    "volume": h_result.volume,
                    "difficulty": h_result.difficulty,
                    "effort": h_result.effort,
                    "time": h_result.time,
                    "bugs": h_result.bugs
                }
            
            # Add raw metrics if available
            if raw_metrics:
                metrics["size"] = {
                    "loc": raw_metrics.loc,
                    "lloc": raw_metrics.lloc,
                    "sloc": raw_metrics.sloc,
                    "comments": raw_metrics.comments,
                    "multi": raw_metrics.multi,
                    "blank": raw_metrics.blank
                }
            
            # Add interpretations
            metrics["interpretations"] = [
                f"Code complexity is {metrics['complexity']['interpretation'].lower()}",
                f"Maintainability is {metrics['maintainability']['interpretation'].lower()}",
                f"Code style compliance is {metrics['style']['interpretation'].lower()}",
                f"Documentation coverage is {metrics['documentation']['interpretation'].lower()}"
            ]
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error analyzing code quality: {e}")
            return {
                "error": str(e),
                "status": "failed"
            }
    
    @staticmethod
    def _analyze_documentation(code: str) -> float:
        """
        Analyze documentation coverage and quality.
        
        Args:
            code: The Python code to analyze
            
        Returns:
            float: Documentation ratio (0.0 to 1.0)
        """
        try:
            tree = ast.parse(code)
            total_nodes = 0
            documented_nodes = 0
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Module)):
                    total_nodes += 1
                    if ast.get_docstring(node):
                        documented_nodes += 1
            
            return documented_nodes / total_nodes if total_nodes > 0 else 0.0
        except Exception as e:
            logger.error(f"Error analyzing documentation: {e}")
            return 0.0
    
    @staticmethod
    def _has_module_docstring(code: str) -> bool:
        """
        Check if the module has a docstring.
        
        Args:
            code: The Python code to analyze
            
        Returns:
            bool: True if module has a docstring
        """
        try:
            tree = ast.parse(code)
            return bool(ast.get_docstring(tree))
        except Exception as e:
            logger.error(f"Error checking module docstring: {e}")
            return False
    
    @staticmethod
    def _check_pep8_compliance(code: str) -> Dict[str, Any]:
        """
        Check code for PEP 8 compliance.
        
        Args:
            code: The Python code to analyze
            
        Returns:
            Dict containing PEP 8 compliance metrics
        """
        try:
            # Use pycodestyle for PEP 8 checking
            import pycodestyle
            style_guide = pycodestyle.StyleGuide(quiet=True)
            
            # Create a temporary file-like object
            file_like = io.StringIO(code)
            
            # Check the code
            checker = pycodestyle.Checker(lines=code.splitlines(), options=style_guide.options)
            
            # Get all violations
            violations = list(checker.check_all())
            
            return {
                "total_violations": len(violations),
                "is_compliant": len(violations) == 0,
                "details": [str(v) for v in violations[:5]]  # First 5 violations
            }
        except Exception as e:
            return {
                "error": str(e),
                "is_compliant": False
            }
    
    @staticmethod
    def _interpret_metrics(metrics: Dict[str, Any]) -> List[str]:
        """
        Generate human-readable interpretations of the metrics.
        
        Args:
            metrics: Dictionary of collected metrics
            
        Returns:
            List of interpretation strings
        """
        interpretations = []
        
        # Complexity interpretations
        cc = metrics["complexity"]["cyclomatic_complexity"]
        if cc < 5:
            interpretations.append("Code has low complexity, which is good for maintainability.")
        elif cc < 10:
            interpretations.append("Code has moderate complexity. Consider breaking down complex functions.")
        else:
            interpretations.append("High code complexity detected. Refactoring recommended.")
        
        # Documentation interpretations
        doc_ratio = metrics["documentation"]["doc_ratio"]
        if doc_ratio > 0.8:
            interpretations.append("Excellent documentation coverage.")
        elif doc_ratio > 0.4:
            interpretations.append("Moderate documentation coverage. Consider adding more docstrings.")
        else:
            interpretations.append("Low documentation coverage. Documentation improvements needed.")
        
        # Style interpretations
        pylint_score = metrics["style"]["pylint_score"]
        if pylint_score > 8:
            interpretations.append("Code follows good Python style practices.")
        elif pylint_score > 5:
            interpretations.append("Some style issues detected. Review PEP 8 guidelines.")
        else:
            interpretations.append("Significant style issues found. Code needs cleanup.")
        
        # Size interpretations
        if metrics["size"]["comments"] / max(metrics["size"]["loc"], 1) < 0.1:
            interpretations.append("Low comment ratio. Consider adding more explanatory comments.")
        
        return interpretations 