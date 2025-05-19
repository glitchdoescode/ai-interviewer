"""
Profiling script for analyzing LangGraph performance.

This script runs a simulated interview conversation to profile the LangGraph
execution and identify bottlenecks.
"""
import os
import sys
import asyncio
import logging
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

from ai_interviewer.core.ai_interviewer import AIInterviewer
from ai_interviewer.utils.profiling import profile_function

# Configure logging to show timing information
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

@profile_function(output_file="profile_results.prof")
async def run_profile_session():
    """Run a profiling session with a simulated conversation."""
    # Initialize the interviewer
    interviewer = AIInterviewer(
        use_mongodb=False,  # Use in-memory for profiling
        job_role="Python Developer",
        seniority_level="Mid-level",
        required_skills=["Python", "Flask", "SQLAlchemy", "REST APIs"],
        job_description="We are looking for a Python developer with experience in web development, APIs, and database integration."
    )
    
    try:
        # Simulate a conversation
        user_id = "profiler_user"
        
        # Start conversation
        print("\n=== Starting profiling session ===\n")
        response, session_id = await interviewer.run_interview(
            user_id=user_id,
            user_message="Hi, I'm here for the Python Developer interview. My name is Alex."
        )
        print(f"AI: {response}\n")
        
        # Technical question phase
        response, session_id = await interviewer.run_interview(
            user_id=user_id,
            user_message="I have 5 years of experience with Python, mainly working on web applications and APIs.",
            session_id=session_id
        )
        print(f"AI: {response}\n")
        
        # Respond to a technical question
        response, session_id = await interviewer.run_interview(
            user_id=user_id,
            user_message="I prefer using Flask for small to medium projects because of its simplicity and flexibility. For larger applications, I might use Django because of its built-in features and admin interface.",
            session_id=session_id
        )
        print(f"AI: {response}\n")
        
        # Answer another question
        response, session_id = await interviewer.run_interview(
            user_id=user_id,
            user_message="When designing a RESTful API, I focus on using proper HTTP methods, creating clean URL structures, implementing consistent error handling, and ensuring good documentation. I also consider versioning, authentication, and rate limiting.",
            session_id=session_id
        )
        print(f"AI: {response}\n")
        
        print("\n=== Profiling session completed ===\n")
        
    finally:
        # Clean up resources
        interviewer.cleanup()

if __name__ == "__main__":
    # Run the profiling session
    asyncio.run(run_profile_session())
    
    print("\nProfile results saved to profile_results.prof")
    print("To visualize the results, run: python -m snakeviz profile_results.prof") 