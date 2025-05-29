# AI Interviewer Coding Challenge Tools

This directory contains the tools used by the AI Interviewer platform to generate, manage, and evaluate coding challenges during technical interviews.

## Overview

We have two main approaches for coding challenges:

1. **Predefined Challenges** (`coding_tools.py`): A library of predefined coding challenges with fixed test cases.
2. **Dynamic Generation** (`problem_generation_tool.py`): LLM-powered generation of customized coding challenges based on job descriptions and required skills.

The dynamic generation approach is preferred as it creates more relevant and tailored challenges for each candidate.

## Primary Tools

### Problem Generation Tools

From `problem_generation_tool.py`:

- `generate_coding_challenge_from_jd`: Generates a custom coding challenge based on job description and required skills.
- `submit_code_for_generated_challenge`: Evaluates candidate solutions for dynamically generated challenges.
- `get_hint_for_generated_challenge`: Provides context-aware hints for dynamically generated challenges.

### Legacy Challenge Tools

From `coding_tools.py`:

- `start_coding_challenge`: Retrieves a predefined coding challenge.
- `submit_code_for_challenge`: Evaluates candidate solutions for predefined challenges.
- `get_coding_hint`: Provides hints for predefined challenges.

### Supporting Modules

- `code_execution.py`: Handles secure execution of candidate code.
- `code_quality.py`: Analyzes code quality metrics.
- `code_feedback.py`: Generates feedback on code submissions.
- `pair_programming.py`: Provides pair programming assistance during coding challenges.

## Prompt Templates

Prompt templates for LLM-based challenge generation and evaluation are in `ai_interviewer/prompts/problem_generation_prompts.py`.

## Usage in Interview Flow

The AI Interviewer uses these tools during the coding challenge stage of interviews:

1. When the interview enters the "coding_challenge" stage, `generate_coding_challenge_from_jd` is called.
2. The candidate is presented with the challenge in the UI.
3. The candidate submits their solution through `submit_code_for_generated_challenge`.
4. The candidate can request hints via `get_hint_for_generated_challenge`.

## Data Models

The challenge data models are defined in:
- `ai_interviewer/models/coding_challenge.py` for predefined challenges
- `problem_generation_tool.py` for dynamically generated challenges

## Integration

The challenge tools are integrated into the AI Interviewer workflow in `ai_interviewer/core/ai_interviewer.py`.

## Frontend Compatibility

Both predefined and dynamically generated challenges produce compatible output formats for the frontend, ensuring consistent UI presentation regardless of the challenge source. 