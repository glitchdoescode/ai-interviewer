"""
AI components for the {SYSTEM_NAME} platform.

This package contains AI-related components including prompts, models, and utilities.
"""

from ai_interviewer.ai.prompts.interview_prompts import (
    INTERVIEW_SYSTEM_PROMPT,
    FOLLOW_UP_PROMPT,
    TRANSITION_PROMPT,
    TECHNICAL_DISCUSSION_PROMPT,
    FEEDBACK_PROMPT
)

__all__ = [
    'INTERVIEW_SYSTEM_PROMPT',
    'FOLLOW_UP_PROMPT',
    'TRANSITION_PROMPT',
    'TECHNICAL_DISCUSSION_PROMPT',
    'FEEDBACK_PROMPT'
] 