\
# AI Interviewer Platform Development Checklist

This document outlines the tasks to build the AI Interviewer Platform, following an agile methodology with iterative development. The primary goal is to first deliver a Minimum Viable Product (MVP) focusing on the core interview logic using a LangGraph architecture similar to `gizomobot.py`, tested via a simple chat interface. Subsequent phases will add more features.

## Phase 1: MVP - Core Logic & Test Chat Interface

### Sprint 1: Foundation & Core LangGraph Setup
*   **Task 1.1: Project Setup**
    *   [x] Create project directory structure.
    *   [x] Initialize Git repository.
    *   [x] Set up Python virtual environment.
    *   [x] Install basic dependencies: `langchain`, `langgraph`, `langchain-google-genai` (or chosen LLM SDK), `python-dotenv`.
    *   [x] Create initial `requirements.txt`.
    *   [x] Create a basic `README.md` with project overview and setup instructions.
*   **Task 1.2: Define Core LangGraph State**
    *   [x] Define `InterviewState` (e.g., subclassing `MessagesState` or custom TypedDict) to hold:
        *   [x] `messages: List[BaseMessage]`
        *   [x] `interview_id: str`
        *   [x] `candidate_id: str` (optional for MVP)
        *   [x] `current_question_id: Optional[str]`
        *   [x] `current_question_text: Optional[str]`
        *   [x] `candidate_responses: List[str]`
        *   [x] `coding_challenge_state: Optional[Dict]` (e.g., problem_id, current_code, status)
        *   [x] `evaluation_notes: List[str]`
        *   [x] `interview_stage: str` (e.g., "greeting", "qa", "coding", "feedback", "finished")
*   **Task 1.3: Implement Basic Agent Node (`interview_agent`)**
    *   [x] Create an agent function `interview_agent(state: InterviewState) -> InterviewState`.
    *   [x] Initial prompt engineering for a greeting and asking a first simple question.
    *   [x] Connect to an LLM (e.g., Gemini via `ChatGoogleGenerativeAI`).
    *   [x] Handle basic conversation flow: receive user message, generate LLM response.
*   **Task 1.4: Implement Basic Tool Node & Placeholder Tools**
    *   [x] Define a placeholder tool: `@tool async def get_next_question(topic: str) -> str: ...`
    *   [x] Define a placeholder tool: `@tool async def submit_answer(answer: str) -> str: ...`
    *   [x] Create `tools = [get_next_question, submit_answer]`.
    *   [x] Create `tool_node = ToolNode(tools)`.
*   **Task 1.5: Define Workflow Graph**
    *   [x] `workflow = StateGraph(InterviewState)`
    *   [x] `workflow.add_node("agent", interview_agent)`
    *   [x] `workflow.add_node("tools", tool_node)`
    *   [x] `workflow.add_edge(START, "agent")`
    *   [x] `workflow.add_conditional_edges("agent", should_continue_or_end_interview, {"tools": "tools", END: END})`
    *   [x] `workflow.add_edge("tools", "agent")`
    *   [x] `app = workflow.compile()` (with MemorySaver for checkpointing)
*   **Task 1.6: Implement `should_continue_or_end_interview` Logic**
    *   [x] Function to check the last AI message for tool calls.
    *   [x] Add logic to end the interview after a certain number of questions or a specific command.
*   **Task 1.7: Create Command-Line Chat Interface**
    *   [x] Simple Python script that takes user input in a loop.
    *   [x] Invokes the compiled LangGraph app.
    *   [x] Prints AI responses and tool outputs/errors.
    *   [x] Manage a unique `thread_id` for each session.
*   **Task 1.8: Basic Logging Setup**
    *   [x] Configure Python's `logging` module for basic console and file logging.

### Sprint 2: Basic Interview Flow & Dynamic Question Generation
*   **Task 2.1: Enhance `InterviewState`**
    *   [x] Add fields like `current_topic: Optional[str]`, `question_history: List[Dict]`.
    *   [x] Add candidate_responses more robust storage.
    *   [x] Improve state persistence between conversation turns.
    *   [x] Fix dict vs. InterviewState handling issues.
*   **Task 2.2: Implement `DynamicQuestionGenerationTool`**
    *   [x] Create LLM-based smart question generator.
    *   [x] Add context-awareness from previous conversation.
    *   [x] Add parameters for topic, skill level, previous questions.
    *   [x] Make questions adapt to candidate's level.
*   **Task 2.3: Integrate `DynamicQuestionGenerationTool`**
    *   [x] Connect to LLM in workflow.
    *   [x] Update the workflow to properly handle the tool.
    *   [x] Improve question storage in state.
*   **Task 2.4: Enhance Agent Node for Interview Management**
    *   [x] Implement stage transitions (greeting → qa → feedback → finished).
    *   [x] Create automatic stage progression.
    *   [x] Improve system prompts for different stages.
*   **Task 2.5: Basic In-Session Context Management**
    *   [x] Track conversation history better.
    *   [x] Track past questions and responses.
    *   [x] Improve session persistence with thread_id.
*   **Task 2.6: Test Adaptive Q&A Flow**
    *   [x] Test dynamic question generation.
    *   [x] Verify candidate name extraction.
    *   [x] Test stage progression.
    *   [x] Add CLI parameters for skill level.

### Sprint 3: Interactive Coding Challenge (Conceptual MVP)
*   **Task 3.1: Define Coding Challenge Structure**
    *   [x] Create data structure for coding problems.
    *   [x] Implement sample hardcoded coding problems.
    *   [x] Define test case structure.
*   **Task 3.2: Implement `StartCodingChallengeTool`**
    *   [x] Create tool for initiating coding challenges.
    *   [x] Add support for challenge selection.
    *   [x] Handle visibility of test cases.
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
    *   [ ] Categories: `answer_clarity`, `coding_attempt_quality` (very basic for MVP).
    *   [ ] Simple scoring: e.g., 1-5 scale or descriptive notes.
*   **Task 4.2: Implement `EvaluateCandidateResponseTool` (Basic)**
    *   [ ] `@tool async def evaluate_candidate_response(question: str, candidate_answer: str, criteria: Optional[List[str]] = None) -> Dict:`
        *   Uses an LLM call to provide a qualitative score/comment on the answer based on general clarity or predefined simple criteria.
        *   Returns `{"score_notes": "...", "clarity_rating": "good/average/poor"}`.
    *   [ ] Update `tools` list and `tool_node`.
*   **Task 4.3: Integrate Evaluation into Workflow**
    *   [ ] `interview_agent` calls `evaluate_candidate_response` after each Q&A or after the coding submission.
    *   [ ] Store evaluation notes in `InterviewState.evaluation_notes`.
*   **Task 4.4: Implement `GenerateSimpleReportTool`**
    *   [ ] `@tool async def generate_simple_interview_report(interview_state: InterviewState) -> str:`
        *   Compiles all `candidate_responses`, `evaluation_notes`, coding submission status into a single formatted string.
    *   [ ] Update `tools` list and `tool_node`.
*   **Task 4.5: Test Evaluation and Report Generation**
    *   [ ] At the end of an interview flow in the chat interface, trigger report generation.
    *   [ ] Verify the text report output.
*   **Task 4.6: MVP End-to-End Test**
    *   [ ] Run through a complete interview: greeting -> Q&A (2-3 questions with evaluation) -> Coding Challenge (start, submit, basic eval) -> Simple Report.
    *   [ ] Refine prompts and agent logic based on test outcomes.
    *   [ ] Ensure basic error handling (e.g., tool failure) is logged.

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
