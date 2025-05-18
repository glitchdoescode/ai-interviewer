from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from enum import Enum
from langchain_core.messages import BaseMessage
from langchain_core.vectorstores import VectorStore
from langchain_core.embeddings import Embeddings
from pydantic import BaseModel, Field, ConfigDict

class InterviewStage(str, Enum):
    """Enhanced enum for tracking interview stages with more granular states"""
    INTRODUCTION = "introduction"
    TECHNICAL_QUESTIONS = "technical_questions"
    CODING_CHALLENGE = "coding_challenge"
    BEHAVIORAL_QUESTIONS = "behavioral_questions"
    CANDIDATE_QUESTIONS = "candidate_questions"
    WRAP_UP = "wrap_up"

class MemoryEntry(BaseModel):
    """Structure for storing individual memory entries"""
    timestamp: datetime = Field(default_factory=datetime.now)
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    relevance_score: float = 0.0

class InterviewMemory(BaseModel):
    """Enhanced memory structure with RAG capabilities"""
    model_config = ConfigDict(arbitrary_types_allowed=True)  # Allow arbitrary types
    
    short_term: List[MemoryEntry] = Field(default_factory=list)
    long_term: List[MemoryEntry] = Field(default_factory=list)
    vector_store: Optional[Any] = None  # Changed from VectorStore to Any
    embeddings: Optional[Any] = None    # Changed from Embeddings to Any

    def add_memory(self, content: str, metadata: Dict[str, Any] = None):
        """Add a new memory entry to both short and long-term memory"""
        entry = MemoryEntry(content=content, metadata=metadata or {})
        self.short_term.append(entry)
        self.long_term.append(entry)
        
        # Update vector store if available
        if self.vector_store and self.embeddings:
            # Use add_texts instead of add_embeddings
            self.vector_store.add_texts(
                texts=[content],
                metadatas=[metadata or {}]
            )

    def retrieve_relevant_memories(self, query: str, k: int = 5) -> List[MemoryEntry]:
        """Retrieve relevant memories using RAG"""
        if not self.vector_store:
            return []
        
        # Use similarity_search_with_score for better relevance tracking
        results = self.vector_store.similarity_search_with_score(query, k=k)
        return [
            MemoryEntry(
                content=doc.page_content,
                metadata=doc.metadata,
                relevance_score=score
            )
            for doc, score in results
        ]

class EnhancedInterviewState(BaseModel):
    """Enhanced interview state with RAG capabilities"""
    model_config = ConfigDict(arbitrary_types_allowed=True)  # Allow arbitrary types
    
    # Basic interview information
    session_id: str
    user_id: str
    candidate_name: str = ""
    
    # Job-related information
    job_role: str
    seniority_level: str
    required_skills: List[str] = Field(default_factory=list)
    job_description: str = ""
    
    # Interview progress
    stage: InterviewStage = InterviewStage.INTRODUCTION
    sub_stage: str = ""  # For more granular state tracking
    progress: float = 0.0  # Interview completion percentage
    
    # Enhanced memory management
    messages: List[BaseMessage] = Field(default_factory=list)
    memory: InterviewMemory = Field(default_factory=InterviewMemory)
    
    # Performance tracking
    performance_metrics: Dict[str, float] = Field(default_factory=dict)
    flags: List[str] = Field(default_factory=list)
    
    # RAG-specific fields
    context_window: List[Dict[str, Any]] = Field(default_factory=list)
    retrieved_context: List[Dict[str, Any]] = Field(default_factory=list)

    def update_with_rag(self, query: str):
        """Update state context using RAG"""
        relevant_memories = self.memory.retrieve_relevant_memories(query)
        self.retrieved_context = [
            {
                "content": memory.content,
                "metadata": memory.metadata,
                "relevance": memory.relevance_score
            }
            for memory in relevant_memories
        ]

    def add_to_memory(self, content: str, metadata: Dict[str, Any] = None):
        """Add new content to memory"""
        self.memory.add_memory(content, metadata)

    def get_current_context(self) -> Dict[str, Any]:
        """Get the current context including RAG-retrieved information"""
        return {
            "stage": self.stage,
            "sub_stage": self.sub_stage,
            "progress": self.progress,
            "recent_messages": self.messages[-5:] if self.messages else [],
            "retrieved_context": self.retrieved_context,
            "performance_metrics": self.performance_metrics,
            "flags": self.flags
        } 