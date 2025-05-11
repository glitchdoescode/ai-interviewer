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
    *   [ ] Implement session management
    *   [ ] Add state persistence between sessions
    *   [ ] Handle interview resumption

*   **Task 6.2: Improved Coding Evaluation**
    *   [ ] Add code quality metrics
    *   [ ] Implement more detailed test cases
    *   [ ] Enhanced feedback generation

*   **Task 6.3: AI Pair Programming**
    *   [ ] Design hint generation system
    *   [ ] Implement context-aware suggestions
    *   [ ] Add code completion support

## Phase 2: Enhancements & Feature Integration (Iterative)

### Iteration 1: Real-time Conversational Interaction (STT/TTS) - *Post MVP Core Logic*
*   **Task P2.1.1: Research STT/TTS Options**
    *   [ ] Identify suitable Python libraries or cloud APIs for Speech-to-Text and Text-to-Speech (e.g., Google Speech-to-Text/Text-to-Speech, Azure Cognitive Services, open-source options like Whisper/Piper).
*   **Task P2.1.2: Integrate STT**
    *   [ ] Modify the test chat interface to accept audio input (e.g., record from microphone).
    *   [ ] Send audio to STT service and get text.
    *   [ ] Pass transcribed text to the LangGraph application.
*   **Task P2.1.3: Integrate TTS**
    *   [ ] Take the AI interviewer's text response from LangGraph.
    *   [ ] Send text to TTS service to generate audio.
    *   [ ] Play back the audio response in the test chat interface.
*   **Task P2.1.4: Refine Interaction Flow**
    *   [ ] Adjust agent prompts or interface for voice interaction (e.g., "Speak your answer now").
    *   [ ] Handle potential STT/TTS errors gracefully.
*   **Task P2.1.5: Test Voice-Enabled Chat Interface**
    *   [ ] Conduct E2E tests using voice input and receiving voice output.

### Iteration 2: Advanced AI Interviewer & Adaptive Q&A
*   **Task P2.2.1: Enhance `DynamicQuestionGenerationTool`**
    *   [ ] Incorporate candidate's previous responses to make follow-up questions more adaptive.
    *   [ ] Allow specifying difficulty level or skill areas (from User Story/PRD, e.g., "Python", "Data Structures").
    *   [ ] Prompt LLM to ensure questions align with job role profiles (if available).
*   **Task P2.2.2: Deeper Response Analysis**
    *   [ ] Enhance `EvaluateCandidateResponseTool` to extract key concepts or assess depth of understanding, not just clarity.
*   **Task P2.2.3: Natural Conversation Flow**
    *   [ ] Refine `interview_agent` system prompts for more natural transitions, empathetic responses, and ability to handle digressions or clarifications.
*   **Task P2.2.4: (Optional Long-Term) LLM Fine-tuning Study**
    *   [ ] Research feasibility and requirements for fine-tuning an LLM for interview question generation or evaluation.

### Iteration 3: Interactive Coding Challenge - Execution & AI Assistance
*   **Task P2.3.1: Secure Code Execution Sandbox**
    *   [ ] Research and select a code execution sandbox solution (e.g., Docker containers with resource limits, a service like `judge0`, or `RestrictedPython`).
    *   [ ] Implement `ExecuteCodeTool`:
        *   `@tool async def execute_candidate_code(language: str, code: str, test_cases: List[Dict]) -> Dict:`
        *   Takes code and test cases, runs it in the sandbox.
        *   Returns results: `{"pass_count": N, "total_tests": M, "outputs": [...], "errors": "..."}`.
*   **Task P2.3.2: Enhance `SubmitCodeTool`**
    *   [ ] Replace placeholder logic with a call to `ExecuteCodeTool`.
*   **Task P2.3.3: AI Pair Programming Assistant (Basic)**
    *   [ ] Design `AIPairProgrammingHintTool`:
        *   `@tool async def get_coding_hint(problem_description: str, current_code: str, error_message: Optional[str]) -> str:`
        *   Uses an LLM to provide a contextual hint without giving away the solution.
    *   [ ] Integrate this tool into the coding challenge flow (e.g., candidate can request a hint).
*   **Task P2.3.4: Capture Code Evolution**
    *   [ ] Modify `InterviewState` or logging to store snapshots of candidate's code at submission or hint requests.

### Iteration 4: Automated Problem Generation ("Magic Import")
*   **Task P2.4.1: Design `ProblemGenerationFromJDTool`**
    *   `@tool async def generate_coding_challenge_from_jd(job_description: str, skills_required: List[str]) -> Dict:`
    *   Uses an LLM to generate a problem statement, test cases, and reference solution based on input.
*   **Task P2.4.2: Implement Tool Logic**
    *   [ ] Develop robust prompts for the LLM to create relevant and solvable problems.
*   **Task P2.4.3: Testing Interface for Problem Generation**
    *   [ ] Create a simple script or admin interface to test this tool.

### Iteration 5: Rubric-Based Scoring & Detailed Reporting
*   **Task P2.5.1: Detailed Rubric Implementation**
    *   [ ] Formalize rubric based on PRD (code correctness, efficiency, quality, communication, problem-solving).
*   **Task P2.5.2: Enhance Evaluation Tools**
    *   [ ] Update `EvaluateCandidateResponseTool` and create `EvaluateCodingSubmissionTool` to use the detailed rubric.
    *   [ ] LLM prompts to score against each rubric dimension and provide rationale.
*   **Task P2.5.3: `GenerateDetailedReportTool`**
    *   [ ] Output structured data (JSON or PDF) including scores per dimension, AI rationale, trust score (conceptual for now), transcripts, coding logs.
*   **Task P2.5.4: "Trust Score" Logic (Initial)**
    *   [ ] Develop a simple heuristic or LLM-based assessment for an overall "trust score" based on consistency, clarity, and problem-solving.

### Iteration 6: Supervisor Agent (Quality Control - Optional, based on `gizomobot.py`)
*   **Task P2.6.1: Design Supervisor Agent Logic**
    *   [ ] Define criteria for the supervisor (e.g., is the agent's question relevant? Is the evaluation fair? Is the agent stuck?).
    *   [ ] Create `supervisor_agent(main_agent_state: InterviewState) -> str:` function that calls a separate LLM.
*   **Task P2.6.2: Integrate Supervisor into LangGraph**
    *   [ ] Potentially add a node after the main agent that calls the supervisor.
    *   [ ] Implement re-work loop: if supervisor flags an issue, modify state and re-invoke main agent.

### Iteration 7: Persistent Context Management & History
*   **Task P2.7.1: Select and Setup Database**
    *   [ ] Choose a database (e.g., MongoDB, PostgreSQL, Firestore) for storing interview sessions, user data.
    *   [ ] Define schemas for interview state, user profiles, etc.
*   **Task P2.7.2: Implement Persistence Logic**
    *   [ ] Create functions `load_interview_context(interview_id: str) -> InterviewState` and `save_interview_context(state: InterviewState)`.
    *   [ ] Replace `MemorySaver` with a custom checkpointer or integrate database calls within agent/tool nodes to persist state at key points.
*   **Task P2.7.3: Link Sessions to Users**
    *   [ ] (Prerequisite for auth) Associate interview sessions with user IDs.

## Phase 3: Frontend, Auth, and Full System Integration - *Post Core Logic & Key AI Features*

### Iteration 1: Basic Web Frontend
*   **Task P3.1.1: Choose Frontend Framework**
    *   [ ] Decide on React, Vue, Angular, or other suitable framework.
*   **Task P3.1.2: Develop Candidate Chat UI**
    *   [ ] Interface for text chat (and later voice) with AI interviewer.
    *   [ ] Display for coding problems, editor for code input.
*   **Task P3.1.3: API Endpoints for Frontend-Backend Communication**
    *   [ ] Use FastAPI, Flask, or similar to expose LangGraph app.
    *   [ ] Endpoints for: starting interview, sending message/code, getting updates.
    *   [ ] Consider WebSockets for real-time communication.

### Iteration 2: Candidate Authentication & Session Management
*   **Task P3.2.1: Implement User Auth**
    *   [ ] Basic email/password registration and login.
    *   [ ] (Later) SSO options like OAuth (Google, LinkedIn).
*   **Task P3.2.2: Secure Session Management**
    *   [ ] JWTs or server-side sessions.
*   **Task P3.2.3: Link LangGraph Sessions to Authenticated Users**
    *   [ ] Pass user context to the backend.

### Iteration 3: Recruiter Dashboard - Report Viewing
*   **Task P3.3.1: Design Recruiter UI**
    *   [ ] View list of completed interviews.
    *   [ ] Detailed view for individual reports (scores, transcripts, code playback if possible).
*   **Task P3.3.2: API Endpoints for Recruiter Data**
    *   [ ] Secure endpoints to fetch interview data and reports.

### Subsequent Iterations (High-Level)
*   [ ] **Interview Scheduling Interface (Candidate & Recruiter)**
*   [ ] **ATS/HRIS Integration (APIs, Webhooks)**
*   [ ] **System Admin Features (Configuration, Monitoring, User Management)**
*   [ ] **Advanced Analytics & Candidate Comparison Dashboard**
*   [ ] **Multi-tenancy and Role-Based Access Control (RBAC)**
*   [ ] **Full Compliance Features (GDPR, SOC2 Logging/Auditing)**
*   [ ] **Scalability Enhancements (Load Balancing, K8s deployment)**
*   [ ] **Accessibility (WCAG compliance)**

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
 