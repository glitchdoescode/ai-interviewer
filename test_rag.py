#!/usr/bin/env python
"""
Test script for the RAG-enhanced interview system.
"""
import os
import logging
from dotenv import load_dotenv
from ai_interviewer.core.rag_session_manager import RAGSessionManager
from ai_interviewer.core.interview_state import InterviewStage

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

def test_rag_system():
    """Test the RAG-enhanced interview system."""
    # Load environment variables
    load_dotenv()
    
    # Get MongoDB connection details
    mongodb_uri = os.getenv("MONGODB_URI", "mongodb://admin:password@localhost:27017/")
    
    try:
        # Initialize RAG session manager with test directory
        logger.info("Initializing RAG session manager...")
        rag_manager = RAGSessionManager(
            connection_uri=mongodb_uri,
            database_name="ai_interviewer_test",
            collection_name="test_sessions",
            persist_directory="./data/test_chroma_db"
        )
        
        # Create a test session
        logger.info("Creating test interview session...")
        state = rag_manager.create_session(
            user_id="test_user",
            job_role="Full Stack Developer",
            seniority_level="Mid-level",
            required_skills=["Python", "React", "MongoDB", "AWS"],
            job_description="Looking for a Full Stack Developer with experience in Python, "
                          "React, and cloud technologies."
        )
        
        # Test session creation
        logger.info(f"Created session with ID: {state.session_id}")
        logger.info(f"Initial stage: {state.stage}")
        
        # Test adding some interview interactions
        test_interactions = [
            {
                "content": "I have worked with Python for 5 years, building web applications "
                          "with Django and FastAPI. I've implemented several RESTful APIs "
                          "and worked with asyncio for performance optimization.",
                "metadata": {
                    "type": "candidate_response",
                    "skill": "Python",
                    "confidence": 0.9
                }
            },
            {
                "content": "In my current role, I've built several React applications "
                          "with Redux and TypeScript. I'm familiar with React hooks, "
                          "context API, and have experience with Next.js for SSR.",
                "metadata": {
                    "type": "candidate_response",
                    "skill": "React",
                    "confidence": 0.85
                }
            },
            {
                "content": "I've deployed applications on AWS using ECS, Lambda, and "
                          "managed MongoDB Atlas clusters. I've also set up CI/CD pipelines "
                          "using GitHub Actions and AWS CodePipeline.",
                "metadata": {
                    "type": "candidate_response",
                    "skill": "Cloud",
                    "confidence": 0.8
                }
            }
        ]
        
        # Add interactions and test RAG retrieval
        for interaction in test_interactions:
            logger.info(f"\nAdding interaction: {interaction['content'][:100]}...")
            state = rag_manager.update_session(
                state=state,
                message_content=interaction["content"],
                metadata=interaction["metadata"]
            )
        
        # Test context retrieval
        logger.info("\nTesting context retrieval...")
        test_queries = [
            "candidate's Python experience",
            "experience with cloud technologies",
            "frontend development skills"
        ]
        
        for query in test_queries:
            logger.info(f"\nQuerying: {query}")
            context = rag_manager.get_relevant_context(state, query)
            
            logger.info(f"Retrieved {len(context)} relevant contexts:")
            for idx, ctx in enumerate(context, 1):
                logger.info(f"\n{idx}. Content: {ctx['content']}")
                logger.info(f"   Relevance Score: {ctx['relevance']:.3f}")
                logger.info(f"   Metadata: {ctx['metadata']}")
        
        # Print final state
        logger.info("\nFinal interview state:")
        logger.info(f"Stage: {state.stage}")
        logger.info(f"Progress: {state.progress * 100:.1f}%")
        logger.info(f"Performance metrics: {state.performance_metrics}")
        logger.info(f"Flags: {state.flags}")
        
        logger.info("\nRAG system test completed successfully!")
        
    except Exception as e:
        logger.error(f"Error testing RAG system: {e}")
        raise

if __name__ == "__main__":
    test_rag_system() 