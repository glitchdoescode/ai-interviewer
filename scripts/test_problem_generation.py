import sys
import os

# Add the project root to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import asyncio
import json
from ai_interviewer.tools.problem_generation_tool import generate_coding_challenge_from_jd
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def main():
    """
    Main function to test the problem generation tool.
    """
    load_dotenv()  # Load environment variables from .env file

    # Example inputs
    job_description = """
    We are looking for a Senior Python Developer to join our team. 
    The ideal candidate will have extensive experience in building scalable web applications,
    working with databases, and developing RESTful APIs. Experience with Django or Flask
    is a plus. The role involves designing and implementing new features, maintaining existing code,
    and collaborating with cross-functional teams. Strong problem-solving skills are essential.
    """
    skills_required = ["Python", "Data Structures", "Algorithms", "API Design"]
    difficulty_level = "intermediate" # or "beginner" or "advanced"

    logger.info(f"Requesting challenge for skills: {skills_required}, difficulty: {difficulty_level}")

    try:
        # Call the tool
        # Note: generate_coding_challenge_from_jd is a Langchain @tool decorated async function.
        # To call it directly, you access its .func attribute if it's wrapped,
        # or call it if the @tool decorator handles direct async calls correctly.
        # Assuming the @tool decorator makes it directly callable as an async function:
        if hasattr(generate_coding_challenge_from_jd, 'ainvoke'): # Check if it's a Runnable
             challenge = await generate_coding_challenge_from_jd.ainvoke({
                 "job_description": job_description,
                 "skills_required": skills_required,
                 "difficulty_level": difficulty_level
             })
        elif asyncio.iscoroutinefunction(generate_coding_challenge_from_jd.func): # Check if the underlying func is async
            challenge = await generate_coding_challenge_from_jd.func(
                job_description=job_description,
                skills_required=skills_required,
                difficulty_level=difficulty_level
            )
        else: # Fallback for direct call if tool is not a Runnable and func is not async (should not happen with async def)
             challenge = await generate_coding_challenge_from_jd(
                 job_description=job_description,
                 skills_required=skills_required,
                 difficulty_level=difficulty_level
             )


        logger.info("Successfully generated coding challenge:")
        print(json.dumps(challenge, indent=2))

        # Basic verification checks
        if challenge.get("status") == "success":
            logger.info("Challenge generation reported success.")
            assert "problem_statement" in challenge, "Missing problem_statement"
            assert "test_cases" in challenge and len(challenge["test_cases"]) >= 3, "Missing or insufficient test_cases"
            assert "reference_solution" in challenge, "Missing reference_solution"
            assert "starter_code" in challenge, "Missing starter_code"
            assert "title" in challenge, "Missing title"
            logger.info("Basic structural validation passed.")
        else:
            logger.error(f"Challenge generation failed or returned an error status: {challenge.get('status')}")
            if "message" in challenge:
                logger.error(f"Error message: {challenge.get('message')}")


    except Exception as e:
        logger.error(f"An error occurred during problem generation test: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main()) 