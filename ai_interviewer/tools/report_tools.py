"""
Report generation tools for the AI Interviewer platform.

This module implements tools for generating interview reports in various formats.
"""
import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path

from langchain_core.tools import tool
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

from ai_interviewer.models.rubric import InterviewEvaluation

# Configure logging
logger = logging.getLogger(__name__)

def _calculate_summary_statistics(evaluation: InterviewEvaluation) -> Dict[str, Any]:
    """Calculate summary statistics from the evaluation."""
    qa_scores = []
    for qa_eval in evaluation.qa_evaluations:
        for question, criteria in qa_eval.items():
            qa_scores.extend([
                criteria.clarity.score,
                criteria.technical_accuracy.score,
                criteria.depth_of_understanding.score,
                criteria.communication.score
            ])
    
    coding_scores = []
    if evaluation.coding_evaluation:
        coding_scores = [
            evaluation.coding_evaluation.correctness.score,
            evaluation.coding_evaluation.code_quality.score,
            evaluation.coding_evaluation.efficiency.score,
            evaluation.coding_evaluation.problem_solving.score
        ]
    
    return {
        "qa_average": sum(qa_scores) / len(qa_scores) if qa_scores else 0,
        "coding_average": sum(coding_scores) / len(coding_scores) if coding_scores else 0,
        "overall_average": sum(qa_scores + coding_scores) / len(qa_scores + coding_scores) if (qa_scores + coding_scores) else 0,
        "trust_score": evaluation.trust_score,
        "total_questions": len(evaluation.qa_evaluations),
        "coding_completed": bool(evaluation.coding_evaluation)
    }

def _generate_pdf_report(
    interview_id: str,
    candidate_id: Optional[str],
    evaluation: InterviewEvaluation,
    output_dir: str = "reports"
) -> str:
    """Generate a PDF report from the evaluation data."""
    # Create output directory if it doesn't exist
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Create the PDF file
    filename = f"{output_dir}/interview_report_{interview_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    doc = SimpleDocTemplate(filename, pagesize=letter)
    styles = getSampleStyleSheet()
    
    # Create custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        spaceAfter=12
    )
    
    # Calculate summary statistics
    stats = _calculate_summary_statistics(evaluation)
    
    # Build the document content
    content = []
    
    # Title
    content.append(Paragraph("AI Interviewer - Interview Report", title_style))
    content.append(Spacer(1, 12))
    
    # Interview Details
    content.append(Paragraph("Interview Details", heading_style))
    details_data = [
        ["Interview ID:", interview_id],
        ["Candidate ID:", candidate_id or "Not provided"],
        ["Date:", datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
        ["Trust Score:", f"{stats['trust_score']:.2f}"]
    ]
    details_table = Table(details_data, colWidths=[2*inch, 4*inch])
    details_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('PADDING', (0, 0), (-1, -1), 6)
    ]))
    content.append(details_table)
    content.append(Spacer(1, 20))
    
    # Summary Statistics
    content.append(Paragraph("Performance Summary", heading_style))
    summary_data = [
        ["Metric", "Score"],
        ["Q&A Average:", f"{stats['qa_average']:.2f}/5.0"],
        ["Coding Average:", f"{stats['coding_average']:.2f}/5.0"],
        ["Overall Average:", f"{stats['overall_average']:.2f}/5.0"]
    ]
    summary_table = Table(summary_data, colWidths=[3*inch, 3*inch])
    summary_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('PADDING', (0, 0), (-1, -1), 6)
    ]))
    content.append(summary_table)
    content.append(Spacer(1, 20))
    
    # Q&A Evaluation Details
    content.append(Paragraph("Q&A Evaluation Details", heading_style))
    for i, qa_eval in enumerate(evaluation.qa_evaluations, 1):
        for question, criteria in qa_eval.items():
            content.append(Paragraph(f"Question {i}: {question}", styles["Heading3"]))
            qa_data = [
                ["Criterion", "Score", "Justification"],
                ["Clarity", str(criteria.clarity.score), criteria.clarity.justification],
                ["Technical Accuracy", str(criteria.technical_accuracy.score), criteria.technical_accuracy.justification],
                ["Understanding", str(criteria.depth_of_understanding.score), criteria.depth_of_understanding.justification],
                ["Communication", str(criteria.communication.score), criteria.communication.justification]
            ]
            qa_table = Table(qa_data, colWidths=[2*inch, 1*inch, 3*inch])
            qa_table.setStyle(TableStyle([
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('PADDING', (0, 0), (-1, -1), 6)
            ]))
            content.append(qa_table)
            content.append(Spacer(1, 12))
    
    # Coding Evaluation Details
    if evaluation.coding_evaluation:
        content.append(Paragraph("Coding Challenge Evaluation", heading_style))
        coding_data = [
            ["Criterion", "Score", "Justification"],
            ["Correctness", str(evaluation.coding_evaluation.correctness.score), 
             evaluation.coding_evaluation.correctness.justification],
            ["Code Quality", str(evaluation.coding_evaluation.code_quality.score),
             evaluation.coding_evaluation.code_quality.justification],
            ["Efficiency", str(evaluation.coding_evaluation.efficiency.score),
             evaluation.coding_evaluation.efficiency.justification],
            ["Problem Solving", str(evaluation.coding_evaluation.problem_solving.score),
             evaluation.coding_evaluation.problem_solving.justification]
        ]
        coding_table = Table(coding_data, colWidths=[2*inch, 1*inch, 3*inch])
        coding_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('PADDING', (0, 0), (-1, -1), 6)
        ]))
        content.append(coding_table)
    
    # Overall Notes
    if evaluation.overall_notes:
        content.append(Spacer(1, 20))
        content.append(Paragraph("Overall Notes", heading_style))
        content.append(Paragraph(evaluation.overall_notes, styles["Normal"]))
    
    # Build the PDF
    doc.build(content)
    return filename

@tool
def generate_interview_report(
    interview_id: str,
    candidate_id: Optional[str],
    evaluation: Dict[str, Any],
    output_format: str = "both"
) -> Dict[str, Any]:
    """
    Generate a comprehensive interview report in JSON and/or PDF format.
    
    Args:
        interview_id: Unique identifier for the interview
        candidate_id: Optional identifier for the candidate
        evaluation: The complete interview evaluation data
        output_format: Format of the report ("json", "pdf", or "both")
        
    Returns:
        Dictionary containing the report data and/or file paths
    """
    logger.info(f"Generating {output_format} report for interview {interview_id}")
    
    try:
        # Convert the evaluation dict to our Pydantic model
        evaluation_model = InterviewEvaluation(**evaluation)
        
        # Calculate summary statistics
        stats = _calculate_summary_statistics(evaluation_model)
        
        # Prepare the report data
        report_data = {
            "interview_id": interview_id,
            "candidate_id": candidate_id,
            "timestamp": datetime.now().isoformat(),
            "summary_statistics": stats,
            "evaluation": evaluation_model.model_dump()
        }
        
        result = {"success": True}
        
        # Generate JSON report
        if output_format in ["json", "both"]:
            json_path = f"reports/interview_report_{interview_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            Path("reports").mkdir(parents=True, exist_ok=True)
            with open(json_path, 'w') as f:
                json.dump(report_data, f, indent=2)
            result["json_path"] = json_path
        
        # Generate PDF report
        if output_format in ["pdf", "both"]:
            pdf_path = _generate_pdf_report(interview_id, candidate_id, evaluation_model)
            result["pdf_path"] = pdf_path
        
        return result
    
    except Exception as e:
        logger.error(f"Error generating report: {e}")
        return {
            "success": False,
            "error": str(e)
        }