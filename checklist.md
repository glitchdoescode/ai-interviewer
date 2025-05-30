# AI Interviewer Platform Development Checklist

This document outlines the tasks to build the AI Interviewer Platform, following an agile methodology with iterative development. The primary goal is to first deliver a Minimum Viable Product (MVP) focusing on the core interview logic using a LangGraph architecture similar to `gizomobot.py`, tested via a simple chat interface. Subsequent phases will add more features.

## Phase 1: MVP - Core Logic & Test Chat Interface

### Sprint 1: Foundation & Core LangGraph Setup
*   **Task 1.1: Project Setup**
    *   [x] Create project directory structure.
    *   [x] Initialize Git repository.
    *   [x] Set up Python virtual environment.
    *   [x] Install basic dependencies: `langchain`, `langgraph`, `langchain-google-genai` (or chosen LLM SDK), `python-dotenv`.
    *   [x] Create initial README.md and requirements.txt.

*   **Task 1.2: Core State Management**
    *   [x] Define `InterviewState` class with essential fields.
    *   [x] Implement state persistence with LangGraph checkpointing.
    *   [x] Add proper state transitions between interview stages.

*   **Task 1.3: Basic Agent & Tools**
    *   [x] Create initial interviewer agent with system prompt.
    *   [x] Implement basic tools for question handling.
    *   [x] Set up tool node for processing tool calls.

*   **Task 1.4: Workflow Graph**
    *   [x] Create StateGraph with proper nodes.
    *   [x] Implement edge conditions for stage transitions.
    *   [x] Add message handling and state updates.

### Sprint 2: Dynamic Q&A Implementation
*   **Task 2.1: Question Generation**
    *   [x] Implement `generate_interview_question` tool.
    *   [x] Add context awareness for follow-up questions.
    *   [x] Handle previous questions to avoid repetition.

*   **Task 2.2: Response Handling**
    *   [x] Create `submit_answer` tool.
    *   [x] Store responses in state.
    *   [x] Track conversation context.

*   **Task 2.3: Stage Management**
    *   [x] Implement proper stage transitions.
    *   [x] Add stage-specific behavior.
    *   [x] Handle edge cases in transitions.

### Sprint 3: Interactive Coding Challenges
*   **Task 3.1: Challenge Infrastructure**
    *   [x] Define coding challenge data structures.
    *   [x] Create sample challenges.
    *   [x] Implement challenge selection logic.

*   **Task 3.2: Challenge Flow Integration**
    *   [x] Add coding stage to interview flow.
    *   [x] Implement `start_coding_challenge` tool.
    *   [x] Handle challenge state in workflow.

*   **Task 3.3: Implement `SubmitCodeTool` (Placeholder Execution)**
    *   [x] Create tool for submitting code answers.
    *   [x] Implement basic code validation.
    *   [x] Add proper state handling for submissions.

*   **Task 3.4: Integrate Coding Challenge Tools into Workflow**
    *   [x] Update tool_node function to handle coding tools.
    *   [x] Add coding stage to the interview process.
    *   [x] Integrate coding challenge state management.

*   **Task 3.5: Update Agent for Q&A and Coding Transitions**
    *   [x] Improve stage transition logic for coding challenges.
    *   [x] Update interviewer prompts for coding guidance.
    *   [x] Add coding-specific context in prompt.

*   **Task 3.6: Add Coding Hint Support**
    *   [x] Implement hint mechanism for coding challenges.
    *   [x] Connect hints to specific challenges.
    *   [x] Track hints provided during challenges.

*   **Task 3.7: Human-in-the-loop for Coding Challenges**
    *   [x] Implement LangGraph's interrupt mechanism for pausing during coding challenges.
    *   [x] Add Command functionality to resume interviews after challenge completion.
    *   [x] Create proper state transitions between interview and coding interface.
    *   [x] Ensure seamless conversation flow when returning from challenges.

### Sprint 4: Basic Evaluation & Reporting (Conceptual MVP)
*   **Task 4.1: Define Simple Rubric (Conceptual)**
    *   [x] Create `rubric.py` with Pydantic models for evaluation criteria
    *   [x] Implement QA and coding evaluation structures
    *   [x] Add trust score calculation

*   **Task 4.2: Implement `EvaluateCandidateResponseTool` (Basic)**
    *   [x] Enhanced evaluation tool with structured scoring
    *   [x] Detailed justifications for each criterion
    *   [x] Trust score calculation for evaluation confidence

*   **Task 4.3: Integrate Evaluation into Workflow**
    *   [x] Update state management for detailed evaluations
    *   [x] Store both QA and coding evaluations
    *   [x] Track evaluation history and trust scores

*   **Task 4.4: Basic Report Generation**
    *   [x] Create report generation tool with JSON and PDF support
    *   [x] Implement performance statistics and visualizations
    *   [x] Add state tracking for report file paths
    *   [x] Integrate report generation into workflow

### Sprint 5: Architecture Refactoring
*   **Task 5.1: Unified LangGraph Class Architecture**
    *   [x] Create a unified AIInterviewer class that encapsulates all components
    *   [x] Follow the gizomobot.py pattern for architecture
    *   [x] Implement clean separation of concerns
    *   [x] Add proper documentation and type hints

*   **Task 5.2: State Management Simplification**
    *   [x] Move to LangGraph's MessagesState for simpler state management
    *   [x] Simplify state transitions to "tools" and "end" paths
    *   [x] Improve persistence with clean MemorySaver integration
    *   [x] Update interview history tracking

*   **Task 5.3: Tool Implementation Update**
    *   [x] Define tools list once and use for both ToolNode and model.bind_tools()
    *   [x] Fix pylint integration in code_quality.py
    *   [x] Update coding_tools.py with proper tool invocation patterns
    *   [x] Improve pair_programming.py with simplified helper functions

*   **Task 5.4: CLI and Entry Point Refactoring**
    *   [x] Create new CLI that uses the updated architecture
    *   [x] Update setup.py with correct entry point
    *   [x] Implement proper transcript saving functionality
    *   [x] Add debugging options to CLI

*   **Task 5.5: Documentation and Testing**
    *   [x] Create comprehensive README with installation and usage instructions
    *   [x] Update tests to work with the new architecture
    *   [x] Organize legacy code by moving unused components to a legacy directory
    *   [x] Create progress-report.md to track development progress

### Sprint 6: Enhanced Features & Polish
*   **Task 6.1: Asynchronous Interview Support**
    *   [x] Implement session management
    *   [x] Add state persistence between sessions
    *   [x] Handle interview resumption

*   **Task 6.2: Improved Coding Evaluation**
    *   [x] Add code quality metrics
    *   [x] Implement more detailed test cases
    *   [x] Enhanced feedback generation

*   **Task 6.3: AI Pair Programming**
    *   [x] Design hint generation system
    *   [x] Implement context-aware suggestions
    *   [x] Add code completion support

### Sprint 7: MongoDB Persistence & FastAPI Integration
*   **Task 7.1: Fix MongoDB Persistence Issues**
    *   [x] Replace custom MongoDB checkpointer with official LangGraph MongoDBSaver
    *   [x] Implement proper connection handling and cleanup
    *   [x] Fix thread_id handling in session management

*   **Task 7.2: FastAPI Backend Implementation**
    *   [x] Create server.py with FastAPI app implementation
    *   [x] Define REST API endpoints for interview interactions
    *   [x] Add proper request/response models with Pydantic
    *   [x] Implement session management endpoints

*   **Task 7.3: API Documentation & Testing**
    *   [x] Add Swagger/OpenAPI documentation
    *   [x] Create API testing scripts
    *   [x] Implement error handling and rate limiting
    *   [x] Add proper logging and monitoring

*   **Task 7.4: Deployment Configuration**
    *   [x] Create Docker container for FastAPI application
    *   [x] Set up environment variables for configuration
    *   [x] Add support for HTTPS with certificates
    *   [x] Implement database connection pooling

## Phase 2: Enhancements & Feature Integration (Iterative)

### Iteration 1: Real-time Conversational Interaction (STT/TTS) - *Post MVP Core Logic*
*   **Task P2.1.1: Research STT/TTS Options**
    *   [x] Identify suitable Python libraries or cloud APIs for Speech-to-Text and Text-to-Speech (e.g., Google Speech-to-Text/Text-to-Speech, Azure Cognitive Services, open-source options like Whisper/Piper).
*   **Task P2.1.2: Integrate STT**
    *   [x] Modify the test chat interface to accept audio input (e.g., record from microphone).
    *   [x] Send audio to STT service and get text.
    *   [x] Pass transcribed text to the LangGraph application.
*   **Task P2.1.3: Integrate TTS**
    *   [x] Take the AI interviewer's text response from LangGraph.
    *   [x] Send text to TTS service to generate audio.
    *   [x] Play back the audio response in the test chat interface.
*   **Task P2.1.4: Refine Interaction Flow**
    *   [x] Adjust agent prompts or interface for voice interaction (e.g., "Speak your answer now").
    *   [x] Handle potential STT/TTS errors gracefully.
*   **Task P2.1.5: Test Voice-Enabled Chat Interface**
    *   [x] Conduct E2E tests using voice input and receiving voice output.

### Iteration 2: Web Frontend Development
*   **Task P2.2.1: Choose Frontend Framework**
    *   [x] Research and select a suitable frontend framework (React, Vue, etc.)
    *   [x] Set up project structure for frontend application
    *   [x] Implement build system and deployment pipeline
*   **Task P2.2.2: Develop Voice-First Interface**
    *   [x] Create microphone input and audio output components
    *   [x] Implement visual indicators for listening/speaking states
    *   [x] Add audio recording controls (start/stop/pause)
    *   [x] Design minimal transcript display for reference
*   **Task P2.2.3: API Integration**
    *   [x] Connect frontend to FastAPI backend endpoints
    *   [x] Implement WebSocket or polling for real-time audio streaming
    *   [x] Add proper error handling for audio/speech services
    *   [x] Integrate with backend session management
*   **Task P2.2.4: User Experience Improvements**
    *   [x] Add voice activity visualization (waveform/amplitude display)
    *   [x] Implement accessibility features for diverse users
    *   [x] Create responsive design for mobile and desktop devices
    *   [x] Add visual cues for interview progress/stages

### Iteration 3: Advanced AI Interviewer & Adaptive Q&A
*   **Task P2.3.1: Enhance `DynamicQuestionGenerationTool`**
    *   [x] Incorporate candidate's previous responses to make follow-up questions more adaptive.
    *   [x] Allow specifying difficulty level or skill areas (from User Story/PRD, e.g., "Python", "Data Structures").
    *   [x] Prompt LLM to ensure questions align with job role profiles (if available).
*   **Task P2.3.2: Deeper Response Analysis**
    *   [x] Enhance `EvaluateCandidateResponseTool` to extract key concepts or assess depth of understanding, not just clarity.
*   **Task P2.3.3: Natural Conversation Flow**
    *   [x] Refine `interview_agent` system prompts for more natural transitions, empathetic responses, and ability to handle digressions or clarifications.
*   **Task P2.3.4: (Optional Long-Term) LLM Fine-tuning Study**
    *   [ ] Research feasibility and requirements for fine-tuning an LLM for interview question generation or evaluation.

### Iteration 4: Job Role Configuration System
*   **Task P2.4.1: Job Role Data Model**
    *   [x] Define JobRole model with fields for role name, description, required skills, seniority level
    *   [x] Create database schema for storing job role templates
    *   [x] Implement API endpoints for CRUD operations on job roles

*   **Task P2.4.2: Backend Integration**
    *   [x] Modify AIInterviewer class to accept job role parameters
    *   [x] Update system prompt template to include job-specific context
    *   [x] Add session metadata for storing job role information
    *   [x] Enhance interview stage transitions based on role requirements

*   **Task P2.4.3: API Endpoint Updates**
    *   [x] Add job_role_id parameter to /api/interview endpoint
    *   [x] Create endpoint for listing available job roles
    *   [x] Implement interview configuration options in API
    *   [x] Add filters for interview sessions by job role

*   **Task P2.4.4: Frontend Job Role Selection**
    *   [x] Create job role selection screen before interview start
    *   [x] Add job role dropdown component with descriptions
    *   [x] Implement custom skill tags for job roles
    *   [x] Create admin interface for managing job roles

*   **Task P2.4.5: Dynamic Interview Content**
    *   [x] Implement dynamic system prompts based on selected job role
    *   [x] Create skill-specific question banks for different roles
    *   [x] Add seniority-based difficulty scaling
    *   [x] Enhance evaluation criteria based on role expectations

### Iteration 5: Interactive Coding Challenge - Execution & AI Assistance
*   **Task P2.4.1: Secure Code Execution Sandbox**
    *   [x] Research and select a code execution sandbox solution (e.g., Docker containers with resource limits, a service like `judge0`, or `RestrictedPython`).
    *   [x] Implement `ExecuteCodeTool`:
        *   `@tool async def execute_candidate_code(language: str, code: str, test_cases: List[Dict]) -> Dict:`
        *   Takes code and test cases, runs it in the sandbox.
        *   Returns results: `{"pass_count": N, "total_tests": M, "outputs": [...], "errors": "..."}`.
*   **Task P2.4.2: Enhance `SubmitCodeTool`**
    *   [x] Replace placeholder logic with a call to `ExecuteCodeTool`.
*   **Task P2.4.3: AI Pair Programming Assistant (Basic)**
    *   [x] Design `AIPairProgrammingHintTool`:
        *   `@tool async def get_coding_hint(problem_description: str, current_code: str, error_message: Optional[str]) -> str:`
        *   Uses an LLM to provide a contextual hint without giving away the solution.
    *   [x] Integrate this tool into the coding challenge flow (e.g., candidate can request a hint).
*   **Task P2.4.4: Capture Code Evolution**
    *   [x] Modify `InterviewState` or logging to store snapshots of candidate's code at submission or hint requests.
*   **Task P2.4.5: Job Role Specific Coding Challenge Initiation (Backend)**
    *   [x] Modify `AIInterviewer._determine_interview_stage` to accept `job_role` (or full `InterviewState`).
    *   [x] Implement logic in `_determine_interview_stage` to check if `job_role` requires coding before initiating a coding challenge.
    *   [x] (Recommended) Add `requires_coding: bool` field to `JobRole` Pydantic model in `server.py` and update default job roles.
*   **Task P2.4.6: Streamlined Coding Submission and AI Feedback Flow (Backend/Frontend Interface)**
    *   [x] Document and ensure frontend sends detailed coding evaluation results (summary from `/api/coding/submit`) within the `message` field of `ChallengeCompleteRequest` to `/api/interview/{session_id}/challenge-complete`.
    *   [x] Clarify the trigger for `CODING_CHALLENGE_WAITING` stage in `AIInterviewer` to primarily align with UI-driven submission confirmation rather than relying on user-typed messages.

### Iteration 6: Automated Problem Generation ("Magic Import")
*   **Task P2.5.1: Design `ProblemGenerationFromJDTool`**
    *  [x] `@tool async def generate_coding_challenge_from_jd(job_description: str, skills_required: List[str], difficulty_level: str = "intermediate") -> Dict:`
    *   Uses an LLM to generate a problem statement, test cases, and reference solution based on input.
*   **Task P2.5.2: Implement Tool Logic**
    *   [x] Develop robust prompts for the LLM to create relevant and solvable problems.
*   **Task P2.5.3: Testing Interface for Problem Generation**
    *   [x] Create a simple script or admin interface to test this tool.

### Iteration 6: Rubric-Based Scoring & Detailed Reporting
*   **Task P2.6.1: Detailed Rubric Implementation**
    *   [ ] Formalize rubric based on PRD (code correctness, efficiency, quality, communication, problem-solving).
*   **Task P2.6.2: Enhance Evaluation Tools**
    *   [ ] Update `EvaluateCandidateResponseTool` and create `EvaluateCodingSubmissionTool` to use the detailed rubric.
    *   [ ] LLM prompts to score against each rubric dimension and provide rationale.
*   **Task P2.6.3: `GenerateDetailedReportTool`**
    *   [ ] Output structured data (JSON or PDF) including scores per dimension, AI rationale, trust score (conceptual for now), transcripts, coding logs.
*   **Task P2.6.4: "Trust Score" Logic (Initial)**
    *   [ ] Develop a simple heuristic or LLM-based assessment for an overall "trust score" based on consistency, clarity, and problem-solving.

### Iteration 7: Supervisor Agent (Quality Control - Optional, based on `gizomobot.py`)
*   **Task P2.7.1: Design Supervisor Agent Logic**
    *   [ ] Define criteria for the supervisor (e.g., is the agent's question relevant? Is the evaluation fair? Is the agent stuck?).
    *   [ ] Create `supervisor_agent(main_agent_state: InterviewState) -> str:` function that calls a separate LLM.
*   **Task P2.7.2: Integrate Supervisor into LangGraph**
    *   [ ] Potentially add a node after the main agent that calls the supervisor.
    *   [ ] Implement re-work loop: if supervisor flags an issue, modify state and re-invoke main agent.

## Addressing System Shortcomings (PRIORITY)

### Iteration S1: Core State Management & Performance Improvements
*   **Task S1.1: Enhanced Conversation State Management**
    *   [x] Review and enhance the `InterviewState` structure for comprehensive data capture
    *   [x] Implement advanced memory mechanisms in LangGraph (e.g., `ConversationBufferWindowMemory`)
    *   [x] Ensure proper loading/saving of all state components in `SessionManager`
    *   [x] Add verification testing for state persistence across complex interview flows
    *   [x] Update the LangGraph state transitions to handle extended context

*   **Task S1.2: System Name Configurability**
    *   [x] Add `SYSTEM_NAME` and related variables to `ai_interviewer/utils/config.py`
    *   [x] Update all hardcoded system name references in prompts and UI
    *   [x] Create admin setting for changing system name
    *   [x] Test name changes propagate through the entire system

*   **Task S1.3: Optimizing LangGraph Responsiveness**
    *   [ ] Profile graph execution to identify bottlenecks
    *   [ ] Optimize tool calls, especially slow ones like `execute_candidate_code`
    *   [ ] Review and optimize conditional edges and transition logic
    *   [ ] Implement asynchronous operations for I/O bound functions
    *   [ ] Add streaming for intermediate steps to improve perceived responsiveness

### Iteration S2: Voice Experience Enhancements
*   **Task S2.1: TTS Naturalness Improvements**
    *   [ ] Experiment with Deepgram voice options and settings
    *   [ ] Refine prompts for more conversational LLM output
    *   [ ] Implement SSML support for better speech synthesis control
    *   [ ] Research and evaluate alternative TTS services if needed
    *   [ ] Create A/B testing mechanism for voice quality comparison

*   **Task S2.2: Gemini Integration for Real-time Audio**
    *   [x] Set up Gemini API and add required dependencies
    *   [x] Modify `server.py` to handle Gemini audio processing
    *   [x] Implement real-time audio streaming:
        *   [x] Client-to-server audio via Gemini
        *   [x] Server-to-Gemini STT streaming
        *   [x] LLM-to-Gemini TTS streaming
        *   [x] Server-to-client audio via Gemini
    *   [x] Update frontend to use Gemini audio endpoints
    *   [x] Measure and optimize latency in audio transmission

### Iteration S3: Security & Quality Improvements
*   **Task S3.1: Code Execution Sandbox Security**
    *   [ ] Update Docker base images to latest secure versions
    *   [ ] Add additional container restrictions (cap_drop, seccomp profiles)
    *   [ ] Review and secure generated runner scripts
    *   [ ] Implement more robust input sanitization
    *   [ ] Phase out or restrict the legacy `CodeExecutor`

*   **Task S3.2: Error Handling and Resilience**
    *   [ ] Replace generic exception handling with specific exceptions
    *   [ ] Implement retry mechanisms with backoff for external API calls
    *   [ ] Define clear error responses for all API endpoints
    *   [ ] Enhance logging for better debugging
    *   [ ] Create recovery mechanisms for common failure scenarios

*   **Task S3.3: Test Coverage Expansion**
    *   [ ] Create unit tests for core utilities and tools
    *   [ ] Implement integration tests for API endpoints
    *   [ ] Add tests for LangGraph flow and state transitions
    *   [ ] Create specific tests for Docker sandbox and code execution
    *   [ ] Set up CI pipeline for automated testing

*   **Task S3.4: Documentation and Comments**
    *   [ ] Review and enhance inline comments for complex logic
    *   [ ] Generate or create architecture diagrams
    *   [ ] Update API documentation with more examples
    *   [ ] Create developer onboarding documentation
    *   [ ] Document common issues and their solutions

## Phase 3: Full System Integration & Production Readiness

### Iteration 1: Authentication & User Management
*   **Task P3.1.1: Implement User Auth**
    *   [x] Basic email/password registration and login
    *   [ ] OAuth integration (Google, GitHub, etc.)
    *   [ ] Password reset and account management
*   **Task P3.1.2: Role-Based Access Control**
    *   [ ] Define user roles (candidate, interviewer, admin)
    *   [ ] Implement permission checks on API endpoints
    *   [ ] Set up secure session management

### Iteration 2: Recruiter Dashboard
*   **Task P3.2.1: Design Recruiter UI**
    *   [ ] View list of completed interviews.
    *   [ ] Detailed view for individual reports (scores, transcripts, code playback if possible).
*   **Task P3.2.2: API Endpoints for Recruiter Data**
    *   [ ] Secure endpoints to fetch interview data and reports.
    *   [ ] Implement filtering and searching capabilities

### Iteration 3: Production Deployment
*   **Task P3.3.1: Containerization**
    *   [ ] Create Docker Compose setup for all components
    *   [ ] Implement environment-specific configurations
    *   [ ] Set up CI/CD pipeline for automated deployment
*   **Task P3.3.2: Monitoring & Logging**
    *   [ ] Implement comprehensive logging system
    *   [ ] Set up monitoring for performance and errors
    *   [ ] Create alerting for critical issues
*   **Task P3.3.3: Security Audit**
    *   [ ] Perform security assessment
    *   [ ] Implement GDPR-compliant data handling
    *   [ ] Set up regular backup procedures

## Cross-Cutting Concerns (To be addressed throughout all phases)
*   **[ ] Logging:** Implement structured logging (e.g., JSON) for easier analysis. Log key events, decisions, tool inputs/outputs, errors.
*   **[ ] Error Handling:** Implement robust error handling in agent, tools, and API layers. Provide user-friendly error messages.
*   **[ ] Security:**
    *   Input validation for all user-provided data and tool arguments.
    *   Secure handling of API keys and secrets (e.g., `python-dotenv`, HashiCorp Vault).
    *   Regular review of dependencies for vulnerabilities.
    *   Secure code execution sandbox.
*   **[ ] Testing:**
    *   Unit tests for individual tools and critical functions.
    *   Integration tests for LangGraph flows (e.g., specific interview scenarios).
    *   E2E tests for user-facing features.
*   **[ ] Documentation:**
    *   Keep `README.md` updated.
    *   Add code comments for complex logic.
    *   Document API endpoints (e.g., Swagger/OpenAPI).
*   **[ ] Configuration Management:**
    *   Use environment variables or config files for LLM model names, API keys, prompts, thresholds.
*   **[ ] Scalability & Performance:**
    *   Monitor LLM API latencies.
    *   Optimize prompts and tool logic for efficiency.
    *   Design database schemas for efficient querying.
*   **[ ] Conventional Commits:** Adhere to conventional commit message format for all changes.
*   **[ ] Regular Refactoring:** Keep the codebase clean and maintainable.

This checklist provides a roadmap. Tasks and priorities may be adjusted based on sprint reviews, feedback, and evolving requirements.