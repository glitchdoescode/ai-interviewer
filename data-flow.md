# AI Interviewer: End-to-End Data Flow

This document outlines the complete data flow for the AI Interviewer application, detailing how data moves through different components from initialization to interview completion.

## 1. System Architecture Overview

The AI Interviewer application consists of:

- **Frontend**: React-based web application with Chakra UI
- **Backend**: FastAPI server with LangGraph-based AI interviewer
- **Data Persistence**: MongoDB for session storage and transcript history
- **External Services**: Deepgram API for speech-to-text and text-to-speech

```
┌────────────┐     ┌───────────────────┐     ┌────────────┐     ┌────────────┐
│            │     │                   │     │            │     │            │
│  Frontend  │◄────┤  FastAPI Server   │◄────┤ LangGraph  │◄────┤  MongoDB   │
│  (React)   │─────►                   │─────► AI Workflow │─────►            │
│            │     │                   │     │            │     │            │
└────────────┘     └───────────────────┘     └────────────┘     └────────────┘
                           │   ▲
                           ▼   │
                     ┌─────────────────┐
                     │                 │
                     │  Deepgram API   │
                     │  (STT & TTS)    │
                     │                 │
                     └─────────────────┘
```

## 2. Application Initialization Flow

### 2.1 Backend Initialization

1. **Configuration Loading**:
   - Environment variables loaded via `dotenv` in `config.py`
   - Logging configuration established

2. **Server Initialization**:
   - FastAPI app created with route definitions in `server.py`
   - CORS middleware configured for cross-origin requests
   - Rate limiting configured with `slowapi`

3. **AI Interviewer Initialization**:
   - `AIInterviewer` class initialized in `ai_interviewer.py`
   - Tools registered (coding challenges, pair programming, etc.)
   - LLM model initialized (Google Gemini)
   - MongoDB connection established for persistence

4. **Speech Processing Initialization**:
   - Deepgram API connections configured for STT/TTS
   - Voice handler initialized if API keys are available

### 2.2 Frontend Initialization

1. **React Application Loading**:
   - React app initializes with routes and components
   - Context providers established for state management

2. **API Connection Setup**:
   - API service connections initialized to backend endpoints
   - WebSockets for real-time communication (if applicable)

3. **UI Rendering**:
   - Initial interview interface displayed
   - Audio recording capabilities initialized

## 3. User Session Flow

### 3.1 Session Initialization

```
┌──────────┐     ┌──────────┐     ┌──────────────────┐     ┌──────────┐
│          │     │          │     │                  │     │          │
│  Client  │──1──►  Server  │──2──►  AIInterviewer   │──3──►  MongoDB │
│          │     │          │     │                  │     │          │
└──────────┘     └──────────┘     └──────────────────┘     └──────────┘
      ▲               │                     │                   │
      │               │                     │                   │
      └───────6───────┴─────────5───────────┴─────────4─────────┘

1. User initiates session (via frontend)
2. Server creates session request
3. AIInterviewer initiates LangGraph workflow & session
4. Session ID stored in MongoDB
5. Session context returned to server
6. Session ID returned to client
```

1. **User Initiates Interview**:
   - Client sends initial message to `/api/interview` endpoint
   - Server generates unique user ID if not provided
   - Session manager creates new session in MongoDB

2. **Session Storage**:
   - Session details stored with metadata:
     - User ID
     - Session ID
     - Created timestamp
     - Status ("active")
     - Interview stage ("introduction")

3. **Initial Context Setup**:
   - AIInterviewer initializes LangGraph workflow with:
     - System prompt with interviewer instructions
     - Initial messages state
     - Thread ID for persistence

### 3.2 Text-Based Interview Flow

```
┌──────────┐     ┌──────────┐     ┌──────────────────┐     ┌──────────┐
│          │     │          │     │                  │     │          │
│  Client  │──1──►  Server  │──2──►  AIInterviewer   │──3──►LangGraph │
│          │◄─7──┤          │◄─6──┤                  │◄─4──┤          │
└──────────┘     └──────────┘     └──────────────────┘     └──────────┘
                                          │                     │
                                          │                     │
                                          └─────────5───────────┘

1. User sends message via interface
2. Message routed to run_interview method
3. Message added to LangGraph state
4. LLM responds, potentially with tool calls
5. Tool execution results integrated
6. Response processed and updates session metadata
7. Response sent to client
```

1. **User Message Processing**:
   - User sends message via `/api/interview/{session_id}` endpoint
   - Message wrapped in `HumanMessage` for LangGraph
   - Session context loaded from MongoDB

2. **LangGraph Processing**:
   - Message added to existing conversation thread
   - System prompt updated with:
     - Extracted candidate name (if available)
     - Current interview stage
     - Interview context

3. **LLM Response Generation**:
   - LLM generates response with potential tool calls
   - Response wrapped in `AIMessage` with content

4. **Tool Execution** (if applicable):
   - Tools like `start_coding_challenge` executed
   - Results integrated into conversation

5. **Interview Stage Tracking**:
   - Current interview stage determined:
     - INTRODUCTION → TECHNICAL_QUESTIONS → CODING_CHALLENGE → FEEDBACK → CONCLUSION
   - Stage stored in session metadata

6. **Response Processing**:
   - AI response extracted from LangGraph output
   - Session metadata updated with transcript and stage
   - Session activity timestamp updated

### 3.3 Voice-Based Interview Flow

```
┌──────────┐     ┌──────────┐     ┌───────────┐     ┌──────────────────┐
│          │     │          │     │           │     │                  │
│  Client  │──1──►  Server  │──2──►  Deepgram │──3──►  AIInterviewer   │
│          │◄─8──┤          │◄─7──┤  STT/TTS  │◄─6──┤                  │
└──────────┘     └──────────┘     └───────────┘     └──────────────────┘
                                                            │ 
                                                            │
                                                            ▼
                                                     ┌──────────────┐
                                                     │              │
                                                     │   LangGraph  │
                                                     │              │
                                                     └──────────────┘
                                                           4-5

1. User sends audio recording
2. Server receives audio via /api/audio/transcribe
3. Deepgram STT transcribes audio to text
4-5. Same LangGraph workflow as text-based interview
6. Response text sent to Deepgram TTS
7. Audio file generated and URL returned
8. Response with audio URL sent to client
```

1. **Audio Recording**:
   - Frontend records audio using `useAudioRecorder` React hook
   - Audio converted to Base64 format
   - Posted to `/api/audio/transcribe` endpoint

2. **Speech-to-Text Conversion**:
   - `VoiceHandler` processes audio via Deepgram API
   - Audio bytes converted to temporary WAV file
   - Transcription result returned as text

3. **Text Processing**:
   - Transcribed text processed through same LangGraph workflow as text-based interview
   - AI response generated with same workflow

4. **Text-to-Speech Conversion**:
   - AI response text sent to Deepgram TTS API
   - WAV audio file generated with selected voice model
   - Audio file saved to server's audio_responses directory

5. **Audio Response Delivery**:
   - Audio file URL constructed (/api/audio/response/{filename})
   - Response includes both text and audio URL
   - Client plays audio automatically on reception

## 4. Coding Challenge Flow

```
┌──────────┐     ┌──────────┐     ┌──────────────────┐     ┌──────────────┐
│          │     │          │     │                  │     │              │
│  Client  │──1──►  Server  │──2──►  AIInterviewer   │──3──►   LangGraph  │
│          │◄─8──┤          │◄─7──┤                  │◄─4──┤              │
└──────────┘     └──────────┘     └──────────────────┘     └──────────────┘
                                          │                       │
                                          │                       │
                                          │                       ▼
                                          │               ┌────────────────┐
                                          │               │                │
                                          └───────6───────┤  Coding Tools  │
                                                          │                │
                                                          └────────────────┘
                                                                  │
                                                                  ▼
                                                          ┌────────────────┐
                                                          │                │
                                                          │ Code Execution │
                                                          │ & Evaluation   │
                                                          │                │
                                                          └────────────────┘
```

1. **Challenge Initiation**:
   - LLM calls `start_coding_challenge` tool
   - Tool selects challenge (random or specific ID)
   - Challenge details returned to LLM

2. **Challenge Presentation**:
   - Challenge details presented to user:
     - Description, starter code, examples
     - Visible test cases (hidden ones kept for evaluation)
     - Difficulty level and time limit

3. **Code Submission**:
   - User submits solution via frontend
   - Code sent to server through API endpoint
   - LLM calls `submit_code_for_challenge` tool

4. **Code Evaluation**:
   - Safety check performed on code
   - Code executed against test cases
   - Detailed feedback generated

5. **Pair Programming Assistance**:
   - User can request hints (`get_coding_hint`)
   - User can get code improvements (`suggest_code_improvements`)
   - User can get specific code review (`review_code_section`)

6. **Feedback Integration**:
   - Evaluation results integrated into LangGraph workflow
   - AI generates personalized feedback on solution
   - Interview stage may progress to FEEDBACK

## 5. Session Management and Persistence

### 5.1 MongoDB Data Model

**Sessions Collection**: Primary session data with state
- `session_id`: Unique session identifier
- `user_id`: User identifier
- `created_at`: Creation timestamp
- `last_active`: Last activity timestamp
- `status`: Session status (active/completed)
- Thread state managed by LangGraph

**Metadata Collection**: Additional session information
- `session_id`: Unique session identifier (linked to Sessions)
- `user_id`: User identifier
- `metadata`: Additional data including:
  - `candidate_name`: Extracted from conversation
  - `interview_stage`: Current stage of interview
  - `transcript`: Full conversation history
  - `coding_challenge_state`: Status of any coding challenges

### 5.2 State Management Lifecycle

1. **State Initialization**:
   - Initial state created with system prompt
   - Thread ID assigned for persistence

2. **State Updates**:
   - Each message exchange updates state
   - State persisted to MongoDB via MongoDBSaver

3. **State Retrieval**:
   - Conversation state loaded from MongoDB on session resume
   - LangGraph continues with loaded state

4. **Session Cleanup**:
   - Inactive sessions tracked via `last_active` timestamp
   - Resources cleaned up on server shutdown

## 6. Frontend/Backend Communication

### 6.1 REST API Endpoints

**Interview Management**:
- `POST /api/interview`: Start new interview
- `POST /api/interview/{session_id}`: Continue existing interview
- `GET /api/sessions/{user_id}`: Get all sessions for a user

**Voice Processing**:
- `POST /api/audio/transcribe`: Transcribe audio to text and get response
- `POST /api/audio/upload`: Upload audio file for transcription
- `GET /api/audio/response/{filename}`: Stream audio response file

**System Management**:
- `GET /api/health`: Check system health status

### 6.2 Data Exchange Formats

**Request Models**:
- `MessageRequest`: Text-based messages
- `AudioTranscriptionRequest`: Voice-based messages with audio data

**Response Models**:
- `MessageResponse`: Text responses with session info
- `AudioTranscriptionResponse`: Voice responses with audio URL

## 7. Error Handling and Recovery

### 7.1 Error Flow

```
┌──────────┐     ┌──────────┐     ┌──────────────────┐
│          │     │          │     │                  │
│  Client  │──1──►  Server  │──2──►     Process      │
│          │◄─4──┤          │◄─3──┤                  │
└──────────┘     └──────────┘     └──────────────────┘

1. Client request initiated
2. Server passes request to process
3. Error occurs, logged, and formatted response generated
4. HTTP error with status code returned to client
```

1. **Error Detection**:
   - Exceptions caught at various levels
   - Detailed error logging with timestamps

2. **Error Classification**:
   - HTTP status codes for different error types:
     - 400: Bad Request (validation errors)
     - 404: Not Found (invalid session)
     - 422: Unprocessable Entity (audio transcription errors)
     - 429: Too Many Requests (rate limiting)
     - 500: Internal Server Error (system errors)
     - 501: Not Implemented (voice processing unavailable)

3. **Error Recovery**:
   - Fallbacks for MongoDB connection failures
   - In-memory persistence as backup
   - Graceful degradation of voice features

## 8. Voice Processing Pipeline

### 8.1 Speech-to-Text Flow

```
┌──────────┐     ┌──────────┐     ┌───────────┐     ┌──────────┐
│  Browser │     │  Server  │     │ VoiceHandler │  │ Deepgram │
│ Recorder │──1──►          │──2──►           │──3──►   API    │
│          │     │          │     │           │◄─4──┤          │
└──────────┘     └──────────┘     └───────────┘     └──────────┘
                                       │  ▲
                                     5 │  │ 6
                                       ▼  │
                                   ┌──────────┐
                                   │  Temp    │
                                   │  Files   │
                                   └──────────┘
```

1. **Audio Recording**: 
   - Frontend records audio via MediaRecorder API
   - Audio blob converted to base64
   - Base64 sent to backend

2. **Audio Processing**:
   - Server decodes base64 to binary audio
   - `VoiceHandler` converts to WAV format
   - Creates temporary files for processing

3. **Transcription**:
   - Audio sent to Deepgram Nova API
   - API returns transcript and confidence scores
   - Transcript extracted from response

### 8.2 Text-to-Speech Flow

```
┌──────────┐     ┌──────────┐     ┌───────────┐     ┌──────────┐
│          │     │          │     │           │     │          │
│  Client  │◄─6──┤  Server  │◄─5──┤VoiceHandler│◄─4──┤ Deepgram │
│          │     │          │──1──►           │──2──►   API    │
└──────────┘     └──────────┘     └───────────┘     └──────────┘
                                       │  ▲
                                     3 │  │
                                       ▼  │
                                   ┌──────────┐
                                   │  Audio   │
                                   │  Files   │
                                   └──────────┘
```

1. **Text Processing**:
   - AI response text sent to `VoiceHandler`
   - Text formatted for TTS with proper pauses/emphasis

2. **Speech Synthesis**:
   - Text sent to Deepgram Aura TTS API
   - Voice model selection (default: nova)
   - WAV audio data returned

3. **Audio Storage**:
   - Audio saved to filesystem (audio_responses directory)
   - Unique filename generated with session ID and timestamp

4. **Audio Delivery**:
   - Audio URL constructed from filename
   - Client receives URL in response
   - Browser plays audio using native Audio API

## 9. Complete Request/Response Cycle

A typical end-to-end request cycle with text-based interaction:

1. **Request Initiation**:
   - User inputs message in frontend interface
   - Frontend sends message to `/api/interview/{session_id}` endpoint

2. **Request Processing**:
   - FastAPI server receives request
   - Request validated against `MessageRequest` model
   - User ID and session ID verified

3. **Interview Logic**:
   - Request passed to `interviewer.run_interview()`
   - Session loaded from MongoDB
   - Message added to LangGraph workflow

4. **AI Response Generation**:
   - LLM generates response based on context
   - Tools executed if called by LLM
   - Response wrapped in `AIMessage`

5. **Response Processing**:
   - Response extracted from LangGraph output
   - Session metadata updated
   - MongoDB state persisted

6. **Response Delivery**:
   - Response formatted as `MessageResponse`
   - JSON returned to frontend
   - Frontend displays message to user

## 10. Security Considerations

- **Rate Limiting**: Prevents abuse of API endpoints
- **Input Validation**: Pydantic models validate all inputs
- **Code Execution Safety**: Sandbox for executing submitted code
- **Environment Variables**: Sensitive credentials stored in environment variables
- **Error Handling**: Prevents information disclosure in error messages

## 11. API Integration Points

### 11.1 Google Generative AI

- **Integration Point**: Core LLM for the interview system
- **Data Flow**: Messages sent to Google Gemini API with system prompt and chat history
- **Response**: Structured response with potential tool calls

### 11.2 Deepgram API

- **Integration Point**: Speech-to-text and text-to-speech capabilities
- **Data Flow**: Audio sent for transcription, text sent for speech synthesis
- **Configuration**: API keys stored in environment variables

### 11.3 MongoDB

- **Integration Point**: Session persistence and state management
- **Data Flow**: Session state and metadata stored in collections
- **Configuration**: Connection string and database details in environment

## 12. Deployment Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│                 │     │                 │     │                 │
│   Web Browser   │◄────┤   Web Server    │◄────┤  FastAPI App    │
│   (Frontend)    │─────► (Static Files)  │─────►  (Backend API)  │
│                 │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                        │
                              ┌─────────────────────────┼─────────────────────────┐
                              │                         │                         │
                              ▼                         ▼                         ▼
                     ┌─────────────────┐      ┌─────────────────┐      ┌─────────────────┐
                     │                 │      │                 │      │                 │
                     │  MongoDB Atlas  │      │  Google Gemini  │      │  Deepgram API   │
                     │  (Persistence)  │      │  (LLM Services) │      │  (Voice Services)│
                     │                 │      │                 │      │                 │
                     └─────────────────┘      └─────────────────┘      └─────────────────┘
```

1. **Frontend Deployment**:
   - React app built to static files
   - Static files served by web server or CDN

2. **Backend Deployment**:
   - FastAPI server running on ASGI server (e.g., Uvicorn)
   - API endpoints exposed for frontend communication

3. **Database Deployment**:
   - MongoDB Atlas for cloud-based persistence
   - Connection managed via URI in environment

4. **External Services**:
   - Google Gemini API for LLM capabilities
   - Deepgram API for voice processing

This data flow diagram provides a comprehensive view of how data moves through the AI Interviewer system, from initialization to user interaction to persistence. 