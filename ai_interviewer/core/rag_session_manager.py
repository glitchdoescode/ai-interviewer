from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
import os
from langchain_core.vectorstores import VectorStore
from langchain_core.embeddings import Embeddings
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from ai_interviewer.core.interview_state import (
    EnhancedInterviewState,
    InterviewMemory,
    InterviewStage
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RAGSessionManager:
    """Enhanced session manager with RAG capabilities"""
    
    def __init__(
        self,
        connection_uri: str,
        database_name: str = "ai_interviewer",
        collection_name: str = "interview_sessions",
        embedding_model: str = "models/embedding-001",
        persist_directory: str = "./data/chroma_db"
    ):
        """Initialize the RAG session manager"""
        self.connection_uri = connection_uri
        self.database_name = database_name
        self.collection_name = collection_name
        self.persist_directory = persist_directory
        
        # Create persist directory if it doesn't exist
        os.makedirs(self.persist_directory, exist_ok=True)
        
        # Initialize vector store and embeddings
        self.embeddings = GoogleGenerativeAIEmbeddings(model=embedding_model)
        self.vector_store = Chroma(
            collection_name=f"{collection_name}_vectors",
            embedding_function=self.embeddings,
            persist_directory=self.persist_directory
        )
        
        logger.info(f"Initialized RAG session manager with vector store at {self.persist_directory}")
    
    def create_session(
        self,
        user_id: str,
        job_role: str,
        seniority_level: str,
        required_skills: Optional[List[str]] = None,
        job_description: str = ""
    ) -> EnhancedInterviewState:
        """Create a new interview session with RAG capabilities"""
        session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{user_id}"
        
        # Initialize memory with vector store
        memory = InterviewMemory(
            vector_store=self.vector_store,
            embeddings=self.embeddings
        )
        
        # Create enhanced state
        state = EnhancedInterviewState(
            session_id=session_id,
            user_id=user_id,
            job_role=job_role,
            seniority_level=seniority_level,
            required_skills=required_skills or [],
            job_description=job_description,
            memory=memory
        )
        
        # Store initial context in memory
        initial_context = (
            f"Interview session started for {job_role} position at {seniority_level} level. "
            f"Required skills: {', '.join(required_skills or [])}. "
            f"Job description: {job_description}"
        )
        state.add_to_memory(initial_context, {
            "type": "session_start",
            "timestamp": datetime.now().isoformat()
        })
        
        logger.info(f"Created new RAG-enhanced session {session_id}")
        return state
    
    def update_session(
        self,
        state: EnhancedInterviewState,
        message_content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> EnhancedInterviewState:
        """Update session state with new information"""
        # Add message to memory
        state.add_to_memory(message_content, metadata)
        
        # Update context using RAG
        state.update_with_rag(message_content)
        
        # Update progress based on stage
        self._update_progress(state)
        
        logger.info(f"Updated session {state.session_id} with new content")
        return state
    
    def _update_progress(self, state: EnhancedInterviewState):
        """Update interview progress based on stage and metrics"""
        stage_weights = {
            InterviewStage.INTRODUCTION: 0.1,
            InterviewStage.TECHNICAL_QUESTIONS: 0.3,
            InterviewStage.CODING_CHALLENGE: 0.3,
            InterviewStage.BEHAVIORAL_QUESTIONS: 0.2,
            InterviewStage.CANDIDATE_QUESTIONS: 0.05,
            InterviewStage.WRAP_UP: 0.05
        }
        
        # Calculate base progress from stage
        current_stage_index = list(InterviewStage).index(state.stage)
        base_progress = sum(
            stage_weights[stage] 
            for stage in list(InterviewStage)[:current_stage_index]
        )
        
        # Adjust progress based on performance metrics
        if state.performance_metrics:
            avg_performance = sum(state.performance_metrics.values()) / len(state.performance_metrics)
            state.progress = min(1.0, base_progress + (avg_performance * stage_weights[state.stage]))
        else:
            state.progress = base_progress
    
    def get_relevant_context(
        self,
        state: EnhancedInterviewState,
        query: str,
        k: int = 5
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant context for the current interaction"""
        state.update_with_rag(query)
        return state.retrieved_context 