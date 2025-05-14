# AI Interviewer - Voice-Only End-to-End Data Flow

This document details the low-level data flow for a complete voice-only interview session, from the initial user interaction to the conclusion of the interview. It covers how data hits API endpoints and is processed through various backend components.

**Assumptions:**
- The interaction is primarily voice-based. While transcriptions may be displayed, the core input/output is audio.
- The system progresses through standard interview stages (Introduction, Technical Questions, Coding Challenge (conceptual/verbal), Feedback, Conclusion).

## Frontend Components Involved:
- **`interviewService.js`**: Handles API communication for voice interactions.

## Backend Components Involved:
- **`ai_interviewer/server.py`**: FastAPI server, defines API endpoints.
- **`ai_interviewer/core/ai_interviewer.py`**: Core `AIInterviewer` class with LangGraph logic.
- **`ai_interviewer/utils/speech_utils.py`**: `VoiceHandler` for STT/TTS with Deepgram.
- **`ai_interviewer/utils/session_manager.py`**: `SessionManager` for MongoDB session metadata.
- **`ai_interviewer/utils/config.py`**: Configuration loading.
- **`ai_interviewer/tools/*`**: Various tools invokable by the LangGraph agent.
- **`ai_interviewer/models/*`**: Pydantic models for data structures.
- **LangGraph Checkpointer (`MongoDBSaver`)**: For persisting graph state.

## Overall Voice Interaction Loop:

1.  **User Speaks**: Candidate provides a voice input.
2.  **Frontend Captures & Sends Audio**: `interviewService.js` captures audio, converts to Base64, and sends to the backend.
3.  **Backend Transcribes Audio**: `/api/audio/transcribe` endpoint in `server.py` uses `VoiceHandler` for STT.
4.  **Core Logic Processes Text**: `AIInterviewer` processes the transcribed text using the LangGraph workflow.
5.  **Backend Synthesizes Audio Response**: `AIInterviewer` generates a text response, which `server.py` then converts to speech using `VoiceHandler` (TTS) and saves as an audio file.
6.  **Frontend Receives & Plays Audio**: `interviewService.js` receives a URL to the audio response and plays it for the candidate.

---

## Detailed Flow by Interview Stage:

### 1. Interview Initiation & Introduction Stage

This stage covers the first interaction where the user initiates the interview with a voice message.

**A. Frontend: User Records and Sends First Voice Message**

1.  **User Action**: Candidate clicks a "Start Voice Interview" button or similar UI element.
2.  **Audio Recording**: The browser's MediaRecorder API (or a similar library used by the frontend) captures audio input.
3.  **`interviewService.js` - `transcribeAndRespond` function**:
    *   Receives the raw audio data (e.g., as a Blob).
    *   Converts the audio Blob to a Base64 encoded string. It prefixes `data:audio/wav;base64,` (or a similar MIME type based on recording format) if not already present.
    *   Collects `userId`, `sessionId` (which is `null` for the first call), and `jobRoleData` (if selected by the user).
    *   Constructs the `requestBody`:
        ```json
        {
          "audio_data": "data:audio/wav;base64,UklGRi...", // Base64 audio
          "user_id": "some-user-id",
          "session_id": null,
          "sample_rate": 16000, // Default, can be configured
          "channels": 1,        // Default
          "job_role": "Software Engineer", // Optional
          "seniority_level": "Senior",      // Optional
          "required_skills": ["Python", "FastAPI"], // Optional
          "job_description": "Develop backend services..." // Optional
        }
        ```
    *   Makes a `POST` request to `/api/audio/transcribe` using `axios` (`api.post('/audio/transcribe', requestBody, requestConfig)`). `requestConfig` includes a longer timeout (60s) for audio processing.

**B. Backend: `/api/audio/transcribe` Endpoint (First Call)**

1.  **`server.py` - `POST /api/audio/transcribe` route**:
    *   Receives the `AudioTranscriptionRequest` Pydantic model.
    *   Retrieves `VOICE_HANDLER` (instance of `VoiceHandler` from `speech_utils.py`) and `AI_INTERVIEWER` (instance of `AIInterviewer` from `core/ai_interviewer.py`) from app state or dependencies.
2.  **Speech-to-Text (STT)**:
    *   Calls `VOICE_HANDLER.transcribe_audio(audio_data=request.audio_data, sample_rate=request.sample_rate, channels=request.channels)`.
    *   **`VoiceHandler.transcribe_audio` (`speech_utils.py`)**:
        *   Uses `self.stt_service.transcribe_base64(audio_data, encoding=...)`. The `stt_service` is likely `DeepgramSTT`.
        *   **`DeepgramSTT.transcribe_base64`**:
            *   Parses the base64 data URI to extract raw base64 audio and format.
            *   Constructs options for Deepgram API (e.g., `{"model": "nova-2", "smart_format": True, "language": "en-US", ...}`).
            *   Sends a request to Deepgram's STT API with the audio data and options.
            *   Returns the transcribed text (e.g., "Hello, I'm ready for the interview.").
    *   The transcribed text is stored, e.g., `transcribed_text = "Hello, I'm ready for the interview."`.
3.  **Core Interview Logic Invocation**:
    *   Calls `AI_INTERVIEWER.run_interview(...)`:
        ```python
        response_data = await AI_INTERVIEWER.run_interview(
            user_id=request.user_id,
            session_id=request.session_id, # Still null or new
            message=transcribed_text,
            job_role_data={ # Assembled from request
                "role_name": request.job_role,
                "seniority_level": request.seniority_level,
                "required_skills": request.required_skills,
                "job_description": request.job_description
            } if request.job_role else None,
            # output_audio_format is typically "mp3" or "wav"
        )
        ```
4.  **`AIInterviewer.run_interview` (`core/ai_interviewer.py`)**:
    *   **Session Management**:
        *   Calls `self._get_or_create_session(user_id, session_id, job_role_data)`.
        *   **`_get_or_create_session`**:
            *   If `session_id` is `None` or not found, it creates a new session.
            *   `self.session_manager.create_session(user_id, job_role_data)` is called.
            *   **`SessionManager.create_session` (`utils/session_manager.py`)**:
                *   Generates a unique `session_id` (e.g., UUID).
                *   Stores session metadata (user_id, start_time, job_role_info, status: "active") in MongoDB.
                *   Returns the new `session_id`.
            *   The new `session_id` is now available.
    *   **State Initialization/Loading**:
        *   `thread_id = f"thread_{session_id}"`.
        *   `config = {"configurable": {"thread_id": thread_id}}`.
        *   `current_state = self.workflow.get_state(config)`. If new session, state is fresh.
        *   `interview_state_data = current_state.values()`.
        *   Initial `InterviewState` (a TypedDict) might look like:
            ```python
            {
                "messages": [], # Initially empty or with a system prompt
                "interview_id": session_id,
                "user_id": user_id,
                "candidate_name": None,
                "current_question_id": None,
                "current_question_text": None,
                "candidate_responses": [],
                "interview_stage": "greeting", # Initial stage
                "digression_count": 0,
                "job_role_info": job_role_data, # if provided
                # ... other fields
            }
            ```
    *   **Append User Message**: The transcribed user message is added to the `messages` list in the state (e.g., `HumanMessage(content=transcribed_text)`).
    *   **Invoke LangGraph Workflow**:
        *   `final_chunk = None`
        *   `async for chunk in self.workflow.astream(inputs, config=config, stream_mode="values")`:
            *   `inputs = {"messages": [HumanMessage(content=transcribed_text)]}` or `{"input": transcribed_text}` depending on graph input schema.
            *   The workflow executes nodes:
                *   **`call_model` node**:
                    *   Receives current `InterviewState`.
                    *   Calls `self._determine_interview_stage(state_messages)` which likely returns "greeting" or "introduction".
                    *   Generates prompts based on stage (e.g., greeting prompt, request to extract candidate name).
                    *   Invokes the LLM (e.g., `self.llm.ainvoke(prompts)`).
                    *   LLM response is processed. If it contains tool calls, they are prepared.
                    *   Example LLM response (text): "Hello! Welcome to the interview. What is your name?"
                    *   Updates state with `AIMessage`.
                *   **`should_continue` conditional edge**: Determines next step (e.g., if tool call, go to `tool_node`, else finish).
                *   **(No tools likely called in the very first greeting turn by the AI)**
            *   `final_chunk` will hold the last state from the stream.
    *   **Extract AI Response**:
        *   `ai_response_message = final_chunk["messages"][-1]` (assuming `AIMessage` is last).
        *   `ai_text_response = ai_response_message.content` (e.g., "Hello! Welcome to the interview. What is your name?").
    *   **Update Session State**: The `SessionManager` (`self.session_manager.update_session`) might be called here or handled by the `MongoDBSaver` checkpointer automatically. The LangGraph checkpointer (`self.checkpointer`) automatically saves the state of the graph (`final_chunk`) to MongoDB.
    *   **`AIInterviewer.run_interview` returns a dictionary**:
        ```python
        {
            "session_id": session_id,
            "response": ai_text_response, # AI's textual response
            "interview_stage": final_chunk.get("interview_stage", "greeting"), # Updated stage
            "candidate_name": final_chunk.get("candidate_name"), # Might be None initially
            "current_question_id": final_chunk.get("current_question_id"),
            # ... other relevant fields from InterviewState
        }
        ```
        *   If a `candidate_name` was extracted by the LLM (e.g., if the user said "My name is Alex"), it would be in the `final_chunk` and returned.

5.  **Text-to-Speech (TTS) in `server.py`**:
    *   `response_data` from `run_interview` is received.
    *   `ai_text_for_speech = response_data["response"]`.
    *   Calls `VOICE_HANDLER.synthesize_speech(text=ai_text_for_speech, output_format="mp3", voice_name="default_voice_or_config")`.
    *   **`VoiceHandler.synthesize_speech` (`speech_utils.py`)**:
        *   Uses `self.tts_service.synthesize_speech_to_file(text, filename_prefix, output_dir, ...)`. The `tts_service` is likely `DeepgramTTS`.
        *   **`DeepgramTTS.synthesize_speech_to_file`**:
            *   Generates a unique filename (e.g., `audio_responses/response_<uuid>.mp3`).
            *   Constructs options for Deepgram TTS API (e.g., `{"model": "aura-asteria-en", ...}`).
            *   Sends a request to Deepgram's TTS API with the text.
            *   Streams the audio response from Deepgram and saves it to the generated file path.
            *   Returns the path to the saved audio file (e.g., `"audio_responses/response_xyz.mp3"`).
    *   The `audio_file_path` is obtained.
6.  **Prepare and Send JSON Response**:
    *   `server.py` constructs the final JSON response to the frontend:
        ```json
        {
            "session_id": session_id,
            "transcription": transcribed_text, // User's transcribed speech
            "response": ai_text_response,     // AI's textual response
            "audio_response_url": "/api/audio/response_xyz.mp3", // URL to the TTS audio
            "interview_stage": response_data["interview_stage"],
            "candidate_name": response_data["candidate_name"],
            // ... other fields from response_data
        }
        ```
    *   Note: `/api/audio/{filename}` is a route in `server.py` (e.g., `get_audio_response`) that serves static files from the `audio_responses` directory.

**C. Frontend: Receives Response and Plays AI Audio**

1.  **`interviewService.js` - `transcribeAndRespond` (continuation)**:
    *   Receives the JSON response from `/api/audio/transcribe`.
    *   Extracts `audio_response_url`.
    *   Creates an HTML `Audio` element (`new Audio(audio_response_url)`).
    *   Calls `audio.play()` to play the AI's spoken response.
    *   Updates UI with transcription (optional, as per "voice-only" focus), and potentially other state like `sessionId` for subsequent calls.

**Subsequent Turns in Introduction Stage (e.g., User replies with their name):**

The flow is largely the same as A, B, C above, with key differences:
*   **`interviewService.js`**: Now sends the existing `sessionId` obtained from the first response.
*   **`AIInterviewer.run_interview`**:
    *   `_get_or_create_session` will find and load the existing session.
    *   The LangGraph workflow `self.workflow.get_state(config)` will load the persisted state for `thread_id`.
    *   The new user message (e.g., "My name is Alex") is added to the loaded `messages` history.
    *   The `call_model` node might now have a prompt focused on confirming the name or moving to the next part of the introduction (e.g., explaining the interview process).
    *   The `InterviewState`'s `candidate_name` field is likely updated by the LLM/graph if the name is successfully extracted and confirmed.
    *   The `interview_stage` might remain "greeting" or "introduction" or transition if the intro goals are met.

This detailed flow for the initiation and introduction stage sets the pattern for subsequent stages. The core loop of User Audio -> STT -> LangGraph -> TTS -> AI Audio remains, while the specifics of the LangGraph execution (prompts, tool calls, state updates) change based on the `interview_stage`.

---

### 2. Technical Question & Answer (Q&A) Stage

This stage begins after the introduction is complete. The AI asks technical questions, and the candidate responds. The system may use tools to generate questions and analyze responses.

**A. Transition to Q&A Stage**

1.  **`AIInterviewer.run_interview` (`core/ai_interviewer.py`)**:
    *   During a turn in the "introduction" or "greeting" stage, after the candidate provides their name and initial pleasantries, the `call_model` node in LangGraph determines it's time to move to Q&A.
    *   **`_determine_interview_stage`** is called. It might check conditions like `candidate_name` is present, a certain number of turns have passed, or specific keywords indicating the intro is over.
    *   The LLM within `call_model`, guided by a prompt, might decide to ask the first technical question.
    *   **Tool Call for Question Generation (Potential)**:
        *   The LLM might decide to use the `generate_interview_question` tool (from `ai_interviewer/tools/question_tools.py`).
        *   If so, `call_model` returns a message with `tool_calls` (e.g., `AIMessage.tool_calls` will contain an invocation for `generate_interview_question`).
        *   The `should_continue` edge routes to the `tool_node`.
        *   **`tool_node` (`core/ai_interviewer.py`)**: Executes the `generate_interview_question` tool.
            *   **`GenerateInterviewQuestionTool.run()` (`tools/question_tools.py`)**:
                *   Takes arguments like `job_role_info`, `interview_stage` ("technical_qa"), `current_difficulty`, `past_questions`, `topic_category`.
                *   May interact with a question bank (e.g., `QuestionBank` class or `get_questions_from_db` in `question_tools.py`) or use an LLM to generate a question dynamically based on the provided context.
                *   Returns a `Question` object (Pydantic model) or a dictionary with `question_id`, `text`, `category`, `difficulty`.
                *   Example generated question: "Can you explain the difference between a list and a tuple in Python?"
            *   The `tool_node` appends a `ToolMessage` with the question content back to the state's `messages`.
            *   The graph routes back to `call_model`.
        *   **`call_model` (second pass after tool)**:
            *   Now has the generated question from the `ToolMessage`.
            *   The LLM is prompted to present this question to the candidate.
            *   The `InterviewState` is updated: `current_question_id`, `current_question_text`, `interview_stage` becomes "technical_qa".
    *   **Without Tool Call (LLM generates question directly)**:
        *   The LLM in `call_model` directly generates the first technical question as part of its response based on the prompt for the Q&A stage.
        *   `InterviewState` is updated similarly.
    *   The AI's textual response asking the first technical question is generated (e.g., "Great, Alex. Let's start with some technical questions. Can you explain the difference between a list and a tuple in Python?").

2.  **TTS and Frontend Interaction**: Same as steps B.5, B.6, and C in the Introduction Stage. The AI's question is spoken to the candidate.

**B. Candidate Answers Question (Voice Input)**

1.  **User Speaks**: Candidate provides their answer via voice.
2.  **Frontend Captures & Sends Audio**: `interviewService.js` -> `transcribeAndRespond` (sends audio with existing `session_id` and `user_id`).
3.  **Backend Transcribes Audio**: `/api/audio/transcribe` -> `VoiceHandler` STT -> transcribed text of the answer.

**C. Backend Processes Answer & Asks Follow-up/Next Question**

1.  **`AIInterviewer.run_interview` (`core/ai_interviewer.py`)**:
    *   Receives transcribed answer (e.g., "A list is mutable, and a tuple is immutable...").
    *   Loads current session state using `session_id`.
    *   Appends `HumanMessage(content=candidate_answer_text)` to `messages`.
    *   `candidate_responses` list in `InterviewState` is updated with the answer.
    *   **LangGraph Workflow Invocation**:
        *   **`call_model` node**:
            *   `_determine_interview_stage` confirms it's still "technical_qa".
            *   Prompt for LLM now includes: current question, candidate's answer, interview history.
            *   LLM is tasked to: evaluate the answer (implicitly or explicitly), decide on a follow-up, or generate the next question.
            *   **Tool Call for Answer Analysis (Potential)**:
                *   LLM might decide to use `analyze_candidate_response` tool (from `ai_interviewer/tools/question_tools.py`).
                *   `tool_node` executes `AnalyzeCandidateResponseTool.run()`.
                *   **`AnalyzeCandidateResponseTool.run()` (`tools/question_tools.py`)**:
                    *   Takes `question_text`, `candidate_answer`, `expected_keywords`, `rubric`.
                    *   Uses an LLM or defined heuristics to evaluate the answer's correctness, completeness, clarity.
                    *   Returns an analysis (e.g., "Correct on mutability. Could mention performance differences.").
                *   `ToolMessage` with analysis is added to state.
                *   Graph routes back to `call_model`.
            *   **`call_model` (after analysis tool or directly)**:
                *   If analysis was done, LLM uses it to formulate feedback or a follow-up.
                *   LLM decides if the current question is exhausted or if a follow-up is needed. If exhausted, it moves to generate/select the next question (potentially using `generate_interview_question` tool again as described in A.1).
                *   `evaluation_notes` in `InterviewState` might be updated with snippets from the analysis.
                *   AI generates its response (e.g., "That's a good explanation. Can you elaborate on when you'd prefer to use a tuple over a list?" or "Okay, next question: ...").
                *   `InterviewState` updated: `current_question_id` and `current_question_text` change if a new question is asked.
        *   The AI's textual response is generated.

2.  **TTS and Frontend Interaction**: AI's follow-up or next question is spoken.

**D. Loop for Q&A**

*   Steps B and C repeat for several technical questions.
*   The `AIInterviewer` uses `_determine_interview_stage` and potentially a counter or rules (e.g., number of questions asked, time elapsed, candidate performance) to decide when to transition out of the "technical_qa" stage, perhaps to a coding challenge or feedback.

---

### 3. Coding Challenge Stage (Verbal/Conceptual)

In a voice-only context, the coding challenge is presented verbally, and the candidate discusses their approach, pseudo-code, or logic out loud.

**A. Transition to Coding Challenge Stage**

1.  **`AIInterviewer.run_interview` (`core/ai_interviewer.py`)**:
    *   After sufficient Q&A, the `call_model` node, guided by `_determine_interview_stage` and its prompting, decides to initiate a coding challenge.
    *   `_determine_interview_stage` might transition the `interview_stage` to "coding_challenge_setup" or similar.
    *   **Tool Call for Starting Coding Challenge**: The LLM will likely call the `start_coding_challenge` tool (from `ai_interviewer/tools/coding_tools.py`).
        *   `call_model` returns `AIMessage` with `tool_calls` for `start_coding_challenge`.
        *   `should_continue` routes to `tool_node`.
        *   **`tool_node` executes `StartCodingChallengeTool.run()` (`tools/coding_tools.py`)**:
            *   Takes `job_role_info`, `difficulty_level`, `challenge_id` (optional, if a specific one is requested) as arguments.
            *   Retrieves a `CodingChallenge` Pydantic model (from `ai_interviewer/models/coding_challenge.py`) from a database or predefined list (e.g., `SAMPLE_CHALLENGES`). This model contains `title`, `problem_statement`, `examples`, `constraints`.
            *   Returns the details of the selected challenge (e.g., problem statement, examples).
        *   `tool_node` appends a `ToolMessage` with the challenge details to `messages`.
        *   Graph routes back to `call_model`.
    *   **`call_model` (second pass after tool)**:
        *   Has the coding challenge details from the `ToolMessage`.
        *   LLM is prompted to present this challenge to the candidate verbally.
        *   `InterviewState` is updated: `interview_stage` becomes "coding_challenge", `coding_challenge_state` is populated with challenge details (ID, problem statement). `current_question_id` and `current_question_text` might be cleared or repurposed for the challenge context.
    *   AI's textual response presenting the challenge: "Alright, let's move to a coding challenge. I'd like you to think through the following problem: [Problem Statement]... You can describe your approach, the data structures you'd use, and the overall logic. Take your time to think."

2.  **TTS and Frontend Interaction**: AI's verbal presentation of the coding challenge is played to the candidate.

**B. Candidate Verbally Describes Solution/Approach**

1.  **User Speaks**: Candidate explains their thought process, algorithm, pseudo-code, etc., via voice.
2.  **Frontend Captures & Sends Audio**: `interviewService.js` -> `transcribeAndRespond`.
3.  **Backend Transcribes Audio**: `/api/audio/transcribe` -> `VoiceHandler` STT -> transcribed text of the candidate's verbal solution.

**C. Backend Processes Verbal Solution, Provides Hints, or Concludes Challenge**

1.  **`AIInterviewer.run_interview` (`core/ai_interviewer.py`)**:
    *   Receives transcribed verbal solution/discussion.
    *   Appends `HumanMessage(content=candidate_verbal_solution_text)` to `messages`.
    *   `coding_challenge_state` (in `InterviewState`) might be updated with the candidate's transcribed verbal attempts or key points.
    *   **LangGraph Workflow Invocation**:
        *   **`call_model` node**:
            *   `_determine_interview_stage` confirms "coding_challenge".
            *   Prompt for LLM includes: challenge problem, candidate's verbal solution, interview history.
            *   LLM is tasked to: understand the candidate's approach, provide feedback, offer hints if stuck, or guide the candidate.
            *   **Tool Call for Hint Generation (Potential)**: If the candidate is struggling or asks for help, the LLM might call `get_coding_hint` tool (from `ai_interviewer/tools/pair_programming.py` - `HintGeneratorTool`).
                *   `tool_node` executes `HintGeneratorTool.run()`.
                *   **`HintGeneratorTool.run()` (`tools/pair_programming.py`)**: Takes `challenge_id`, `current_attempt_verbal` (the transcribed verbal solution), `error_message` (if any verbalized confusion).
                    *   Uses an LLM to generate a conceptual hint based on the problem and the candidate's verbalized attempt.
                    *   Returns the hint text.
                *   `ToolMessage` with hint is added to state.
                *   Graph routes back to `call_model` to deliver the hint.
            *   **Tool Call for (Verbal) Code Feedback (Conceptual)**: The LLM itself, or a specialized tool like `provide_code_feedback` (conceptually adapted for verbal input), might be used. In `tools/code_feedback.py`, `CodeFeedbackGeneratorTool` normally takes code. For voice, its prompt would be adapted to evaluate a verbalized algorithm/pseudocode against the problem requirements.
                *   If called, `tool_node` executes it.
                *   **`CodeFeedbackGeneratorTool.run()` (adapted for verbal)**: Takes `challenge_id`, `problem_statement`, `candidate_solution_verbal`.
                    *   LLM assesses the verbalized logic for correctness, efficiency, edge cases.
                    *   Returns textual feedback on the verbal solution.
                *   `ToolMessage` with feedback added to state.
            *   **`call_model` (after tools or directly)**:
                *   AI generates its response (e.g., "That sounds like a reasonable approach. How would you handle edge cases like an empty input?" or "Okay, I understand your logic for the main part. What if the input array was already sorted?").
                *   If hints/feedback were generated by tools, the LLM incorporates them into its response.
                *   `coding_challenge_state` (e.g., `progress_notes`, `areas_to_improve_verbal`) and `evaluation_notes` are updated.
        *   The AI's textual response is generated.

2.  **TTS and Frontend Interaction**: AI's guidance, hints, or follow-up questions regarding the verbal solution are spoken.

**D. Concluding the Coding Challenge**

*   The loop of B and C continues as the candidate refines their verbal solution or the AI guides them.
*   The LLM in `call_model`, based on its assessment of the candidate's verbal solution and potentially time limits, decides to conclude the challenge.
*   `InterviewState`'s `coding_challenge_state` is finalized (e.g., `completed_verbally: True/False`, `summary_of_verbal_solution`).
*   The AI might provide a brief summary or transition: "Okay, that gives me a good understanding of your approach to that problem. Let's move on."
*   The `interview_stage` might transition to "coding_challenge_complete" or directly to "feedback"/"conclusion".
*   `AIInterviewer` has a specific method `continue_after_challenge` called by the `/interview/{session_id}/challenge-complete` endpoint (see `server.py`). In a pure voice flow, this might be triggered implicitly by the LangGraph logic determining the challenge part is over, or the AI might explicitly ask "Are you happy to conclude this coding discussion?" and the user's affirmative response triggers this logic path within `run_interview`.

---

### 4. Feedback and Conclusion Stage

After the main technical Q&A and coding challenge (verbal) are complete, the interview moves towards providing feedback and concluding.

**A. Transition to Feedback Stage**

1.  **`AIInterviewer.run_interview` (`core/ai_interviewer.py`)**:
    *   The decision to move to feedback is made within the `call_model` node, guided by `_determine_interview_stage`.
    *   This could be after the coding challenge is marked complete, or after a set number of Q&A questions if no coding challenge was appropriate/selected.
    *   `_determine_interview_stage` transitions `interview_stage` to "feedback".
    *   **Tool Call for Generating Overall Feedback/Report (Potential)**: The LLM might call a tool like `generate_interview_summary_report` (from `ai_interviewer/tools/report_tools.py`) or a similar feedback generation tool.
        *   `call_model` returns `AIMessage` with `tool_calls`.
        *   `should_continue` routes to `tool_node`.
        *   **`tool_node` executes `GenerateInterviewSummaryReportTool.run()` (or similar)**:
            *   Takes `interview_transcript` (or summarized `messages`), `evaluation_notes`, `candidate_responses`, `coding_challenge_summary`, `job_role_info` as input.
            *   Uses an LLM to synthesize all collected information into a structured feedback summary or a preliminary report.
            *   This might include strengths, areas for improvement, and an overall assessment against the job role criteria.
            *   Returns the generated feedback text/structure.
        *   `tool_node` appends a `ToolMessage` with the feedback to `messages`.
        *   Graph routes back to `call_model`.
    *   **`call_model` (second pass after tool or directly if LLM generates feedback)**:
        *   Has the summarized feedback (if a tool was used) or is prompted to generate it based on the entire interview state (`messages`, `evaluation_notes`, `coding_challenge_state`, etc.).
        *   The LLM is prompted to deliver constructive feedback to the candidate verbally.
        *   `InterviewState` is updated: `interview_stage` is firmly "feedback".
    *   AI's textual response for delivering feedback: "Okay, Alex, we're nearing the end of the interview. I'd like to share some feedback based on our conversation... [Feedback details]... Do you have any questions for me about the role or the team?"

2.  **TTS and Frontend Interaction**: AI's verbal feedback and invitation for candidate questions are played.

**B. Candidate Asks Questions / Responds to Feedback (Voice Input)**

1.  **User Speaks**: Candidate might ask clarifying questions about the feedback, or ask their own questions about the role.
2.  **Frontend Captures & Sends Audio**: `interviewService.js` -> `transcribeAndRespond`.
3.  **Backend Transcribes Audio**: `/api/audio/transcribe` -> `VoiceHandler` STT -> transcribed text.

**C. Backend Addresses Candidate Questions / Concludes**

1.  **`AIInterviewer.run_interview` (`core/ai_interviewer.py`)**:
    *   Receives transcribed text.
    *   Appends `HumanMessage` to `messages`.
    *   **LangGraph Workflow Invocation**:
        *   **`call_model` node**:
            *   `_determine_interview_stage` confirms "feedback" or might transition to "conclusion" if the candidate has no more questions.
            *   Prompt for LLM includes: candidate's question/comment.
            *   LLM is tasked to: answer candidate's questions if any, or provide closing remarks.
            *   **Tool Call for Answering Company/Role Specific Questions (Potential)**: If the candidate asks very specific questions the AI wasn't trained on, it might (if designed to) use a RAG tool to fetch information from a document store about the company/role.
                *   E.g., `fetch_company_info_tool.run(query=candidate_question)`.
            *   **`call_model` (after tool or directly)**:
                *   AI generates its response (e.g., answering the question, or "Thank you for your questions. We appreciate you taking the time to interview with us today. Our recruitment team will be in touch regarding the next steps. Have a great day!").
        *   The AI's textual response is generated.
    *   If the conversation indicates conclusion, `interview_stage` transitions to "finished" or "conclusion".
    *   `SessionManager.update_session` is called (or handled by checkpointer) to mark the session status as "completed" in MongoDB, and potentially store final evaluation notes/report ID.

2.  **TTS and Frontend Interaction**: AI's final answers or concluding remarks are spoken.

**D. End of Session**

*   The AI provides its final closing statement.
*   The frontend might disable further recording or navigate the user away.
*   Backend: The session is marked as complete. All data (LangGraph state, session metadata, audio files) is persisted.
*   A final interview report might be generated asynchronously by a separate process using the data stored, if `GenerateInterviewSummaryReportTool` only provided preliminary feedback to the candidate.

---

This completes the detailed voice-only data flow from initiation to conclusion. 