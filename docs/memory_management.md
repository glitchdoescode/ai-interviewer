# Enhanced Memory Management System

The AI Interviewer platform features a sophisticated memory management system that addresses several key requirements for reliable and effective interview sessions. This document explains the architecture and usage of the memory system.

## Memory Architecture

The memory management system consists of two main components:

1. **Thread-level Memory Persistence**: 
   - Handles state management for each individual interview session
   - Implemented using LangGraph's checkpointing system with MongoDB
   - Ensures conversation context is maintained within a single interview session

2. **Cross-thread Memory Persistence**:
   - Maintains candidate information across multiple interview sessions
   - Implemented using LangGraph's persistent store infrastructure
   - Allows the system to remember candidates from previous interactions

## Memory Manager API

The `InterviewMemoryManager` class provides a unified interface for both thread-level and cross-thread memory operations:

### Key Methods

#### Thread-level Memory

- `get_checkpointer()` - Returns the MongoDBSaver for checkpoint operations
- `setup()` - Sets up collections and indexes for memory storage

#### Cross-thread Memory

- `save_user_memory(user_id, key, value)` - Saves user-specific memory items
- `save_candidate_profile(user_id, profile_data)` - Saves or updates candidate profiles
- `get_candidate_profile(user_id)` - Retrieves a candidate's profile
- `save_interview_memory(session_id, memory_type, memory_data)` - Stores interview-specific memory
- `get_interview_memories(session_id, memory_type)` - Retrieves interview memories
- `search_memories(query, user_id, max_results)` - Searches across all memory spaces

## Memory Types

The system stores several types of memory in different namespaces:

1. **Candidate Profiles** (`candidate_profiles` namespace):
   - Structured information about candidates that persists across sessions
   - Includes skills, experiences, strengths, areas for improvement, etc.
   - Intelligently merged when new information is discovered

2. **Interview Memories** (`interview_memories` namespace):
   - Session-specific but retrievable for historical context
   - Types include insights, evaluations, feedback, and coding data

## Using Memory in LangGraph Workflows

The memory system is integrated into the LangGraph workflow:

1. **Initial Interview Setup**:
   - System retrieves any existing candidate profile during initialization
   - Previous interview insights are incorporated into the system prompt

2. **During Interview**:
   - Thread-level memory maintains context within the current session
   - Long context is managed through summarization when message count exceeds threshold

3. **After Interview**:
   - Candidate insights are extracted and saved to cross-thread memory
   - Profile information is intelligently merged to avoid duplication

## API Access to Memory

The API exposes endpoints for accessing the memory system:

1. `POST /api/memory/search` - Search across memory spaces
2. `GET /api/memory/profile/{user_id}` - Retrieve a candidate's profile

## Configuration

Memory management configuration can be customized in the `.env` file:

```
# MongoDB Configuration
MONGODB_URI=mongodb+srv://...
MONGODB_DATABASE=ai_interviewer
MONGODB_SESSIONS_COLLECTION=interview_sessions
MONGODB_METADATA_COLLECTION=interview_metadata

# Session Configuration
MAX_SESSION_HISTORY=50
```

## Implementation Details

### Thread-level Checkpoint Structure

```json
{
  "thread_id": "session-uuid",
  "config": {
    "configurable": {
      "session_id": "session-uuid",
      "user_id": "user-id"
    }
  },
  "state": {
    "messages": [...],
    "candidate_name": "John Doe",
    "job_role": "Software Engineer",
    "interview_stage": "technical_questions",
    "conversation_summary": "Summary text...",
    "message_count": 15,
    "max_messages_before_summary": 20
  }
}
```

### Cross-thread Memory Structure

Candidate Profile:
```json
{
  "user_id": "user-123",
  "key_skills": ["Python", "JavaScript", "AWS"],
  "notable_experiences": ["Built a distributed system at Company X"],
  "strengths": ["Problem solving", "System design"],
  "areas_for_improvement": ["Frontend design"],
  "coding_ability": {
    "languages": ["Python", "JavaScript"],
    "assessment": "Strong problem-solving skills demonstrated"
  },
  "created_at": "2023-07-15T14:30:00.000Z",
  "updated_at": "2023-07-16T10:15:00.000Z"
}
```

## How This Addresses System Shortcomings

This enhanced memory management system addresses several key shortcomings:

1. **Comprehensive Data Capture**: All interview data is properly structured and stored
2. **Context Management**: Proper summarization and message reduction for long interviews
3. **Cross-Session Memory**: Candidate information persists across multiple interview sessions
4. **Efficient Retrieval**: Fast access to relevant information during interviews
5. **Memory Search**: Ability to search across all memory spaces
6. **Performance Optimization**: Proper connection pooling and resource cleanup

## Future Enhancements

Planned future improvements to the memory system:

1. **Vector Embedding Search**: Add semantic search capabilities
2. **Memory Visualization**: Tools to visualize candidate memory over time
3. **Automatic Profile Enhancement**: LLM-driven memory consolidation and enhancement
4. **Memory Streaming**: Real-time memory updates during interview sessions 