"""
Code quality analysis tools for the AI Interviewer platform.

This module provides tools for analyzing code quality, including metrics
for complexity, style, and best practices.
"""
import ast
import logging
from typing import Dict, List, Optional, Any
from radon.complexity import cc_visit
from radon.metrics import h_visit, mi_visit
from radon.raw import analyze
from pylint.lint import Run
from pylint.reporters import JSONReporter
import io
import tokenize

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
            # Basic code metrics
            raw_metrics = analyze(code)
            
            # Cyclomatic complexity
            cc_results = cc_visit(code)
            avg_complexity = sum(cc.complexity for cc in cc_results) / len(cc_results) if cc_results else 0
            
            # Maintainability index
            mi_result = mi_visit(code, multi=True)
            maintainability = mi_result.mi if mi_result else 0
            
            # Halstead metrics
            h_result = h_visit(code)
            
            # Run pylint for detailed analysis
            pylint_output = io.StringIO()
            reporter = JSONReporter(pylint_output)
            Run(['--output-format=json', '--from-stdin'], reporter=reporter, do_exit=False)
            pylint_score = float(reporter.messages[0].get('score', 0)) if reporter.messages else 0
            
            # Documentation analysis
            doc_ratio = CodeQualityMetrics._analyze_documentation(code)
            
            # Collect all metrics
            metrics = {
                "complexity": {
                    "cyclomatic_complexity": avg_complexity,
                    "maintainability_index": maintainability,
                    "halstead_difficulty": h_result.difficulty if h_result else 0,
                    "halstead_effort": h_result.effort if h_result else 0
                },
                "size": {
                    "loc": raw_metrics.loc,
                    "lloc": raw_metrics.lloc,
                    "sloc": raw_metrics.sloc,
                    "comments": raw_metrics.comments,
                    "multi": raw_metrics.multi,
                    "blank": raw_metrics.blank
                },
                "documentation": {
                    "doc_ratio": doc_ratio,
                    "has_docstring": CodeQualityMetrics._has_module_docstring(code)
                },
                "style": {
                    "pylint_score": pylint_score,
                    "pep8_compliance": CodeQualityMetrics._check_pep8_compliance(code)
                }
            }
            
            # Add interpretations
            metrics["interpretations"] = CodeQualityMetrics._interpret_metrics(metrics)
            
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
        except:
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
        except:
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