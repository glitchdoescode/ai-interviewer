# Implementing a coding panel feature
_Exported on 5/31/2025 at 00:34:19 GMT+5:30 from Cursor (0.50.7)_

---

**User**

when coding round starts, i want the server to open a panel like leetcode containing the starting code where a user can write his code see test cases and test results and submit and run his code take inspiration fromto implement this@leetcode-clone-youtube 
propose an agile and iterative methodology to implement this what files you going to change and add, basically generate a plan after analyzing the query and project also give tests to verify that the thing implemented is working or not


---

**Cursor**

Okay, I understand you want to integrate a LeetCode-like coding panel into the AI Interviewer. This is an exciting feature!

Here's a proposed agile and iterative methodology to implement this, along with the files likely to be affected and a testing strategy.

**Agile & Iterative Methodology**

We'll break this down into several sprints, focusing on delivering value incrementally.

*   **Sprint 1: Basic UI & Backend Hook (Proof of Concept)**
    *   **Goal:** Display a non-functional coding panel on the frontend when the coding challenge starts. Create a backend endpoint that can receive code.
    *   **Frontend:**
        *   Create a new React component, let's call it `CodingChallenge.js`.
        *   This component will initially have a placeholder for the problem statement, a basic text area for code input (we'll add a proper editor later), and a "Submit" button.
        *   Modify the main interview view to render `CodingChallenge.js` when the interview stage is `CODING_CHALLENGE`.
    *   **Backend:**
        *   Define a new API endpoint (e.g., `/api/v1/coding/submit_solution`) that accepts a problem ID, language, and the code string.
        *   For this sprint, this endpoint will just log the received data.
    *   **Testing:**
        *   Manually trigger the coding challenge stage. Verify the `CodingInterface` appears.
        *   Type code and click "Submit." Verify the backend logs the submitted code.

*   **Sprint 2: Code Editor & Problem Display**
    *   **Goal:** Integrate a proper code editor into `CodingChallenge.js` and display the actual problem statement.
    *   **Frontend:**
        *   Integrate a code editor component (like Monaco Editor via `@monaco-editor/react` or CodeMirror via `react-codemirror2`) into `CodingChallenge.js`.
        *   When the coding challenge begins, the AI's message containing the problem description (and potentially starter code) should be passed to and displayed in `CodingChallenge.js`.
    *   **Backend:**
        *   Ensure the `generate_coding_challenge_from_jd` tool's output (which becomes the AI's message) is structured to clearly provide the problem statement, and optionally, starter code and language.
    *   **Testing:**
        *   Verify the problem statement is correctly displayed.
        *   Verify the code editor loads and is usable. If starter code is provided, check it populates the editor.

*   **Sprint 3: Basic Code Execution (No Test Cases Yet)**
    *   **Goal:** Allow the user to "run" their code against simple input, and see stdout/stderr. *Security is paramount here.*
    *   **Frontend:**
        *   Add a "Run" button and a simple input text area in `CodingChallenge.js`.
        *   Add an output area to display results from the backend.
    *   **Backend:**
        *   **Crucial Decision:** How to execute code securely.
            *   **Option A (Recommended for safety):** Integrate with a secure code execution API (e.g., Judge0, Sphere Engine). This offloads the massive security and infrastructure burden.
            *   **Option B (High Risk, Complex):** Build a custom sandboxed environment (e.g., using Docker containers per execution). This requires deep expertise in security and containerization.
        *   The `/api/v1/coding/submit_solution` endpoint (or a new one like `/api/v1/coding/run_code`) will now send the code and input to the execution engine and return the output (stdout, stderr, errors).
        *   The `submit_code_for_generated_challenge` tool in `problem_generation_tool.py` will need to be updated to use this execution logic.
    *   **Testing:**
        *   Submit simple code (e.g., print "hello world", read input and print it) in a supported language. Verify output is displayed.
        *   Test with code that produces errors (compile-time, run-time). Verify errors are shown.
        *   **Security Audit (if Option B):** Rigorous testing for any potential exploits.

*   **Sprint 4: Test Case Integration & Evaluation**
    *   **Goal:** Run submitted code against predefined test cases and show pass/fail results.
    *   **Frontend:**
        *   `CodingChallenge.js` needs to display test cases (e.g., in tabs: Test Case 1, Test Case 2).
        *   Show input, expected output (optional, for user reference), and actual output for each test case.
        *   Display pass/fail status for each test case and an overall summary.
    *   **Backend:**
        *   The `generate_coding_challenge_from_jd` tool must now also return a list of test cases (e.g., `[{input: "...", expected_output: "..."}, ...]`). This information needs to be relayed to the frontend.
        *   The `/api/v1/coding/submit_solution` endpoint will execute the user's code against all provided test cases.
        *   The `submit_code_for_generated_challenge` tool will orchestrate this.
    *   **Testing:**
        *   Create a sample problem with 2-3 test cases.
        *   Submit a correct solution; verify all test cases pass.
        *   Submit an incorrect solution; verify failing test cases are correctly identified.

*   **Sprint 5: UI/UX Polish & Flow Integration**
    *   **Goal:** Refine the `CodingChallenge.js` based on the `leetcode-clone-youtube` inspiration. Ensure smooth transitions within the interview flow.
    *   **Frontend:**
        *   Improve styling, layout, language selection, and potentially themes for the editor.
        *   Handle the "Submit" action: this signals the end of the coding attempt. The UI should likely lock or change state, and inform the backend.
    *   **Backend:**
        *   The AI needs to be aware that the user is in the "coding panel" state. It should likely pause and wait for the submission. The `CODING_CHALLENGE_WAITING` state in `ai_interviewer.py` is key here.
        *   The `should_continue` logic might need to recognize that if the stage is `CODING_CHALLENGE_WAITING`, it should generally `END` the turn for the AI, waiting for an external trigger (like code submission via API).
        *   When the code is submitted, the backend transitions from `CODING_CHALLENGE_WAITING` likely to `FEEDBACK` or a new state where the AI processes the coding results.
    *   **Testing:**
        *   Full end-to-end interview flow.
        *   Usability testing of the coding panel.

*   **Sprint 6 (Optional/Future): Hints, Advanced Feedback**
    *   **Goal:** Allow users to request hints. Provide more detailed feedback on code.
    *   **Frontend:** Add a "Get Hint" button.
    *   **Backend:** Use the `get_hint_for_generated_challenge` tool. The AI might also use `review_code_section` or `suggest_code_improvements` tools based on the submitted code.

**File Changes and Additions**

I'll start by exploring the `leetcode-clone-youtube` project to get a better idea of its structure.


Okay, it seems like `leetcode-clone-youtube/src/components/` would be the most relevant place to find UI components for inspiration. I'll look there.


`Workspace/` sounds promising for the actual coding interface.


And `Playground/` within `Workspace/` seems like the core editor/execution area.


`Playground.tsx` and `EditorFooter.tsx` from `leetcode-clone-youtube/src/components/Workspace/Playground/` and `ProblemDescription` from `leetcode-clone-youtube/src/components/Workspace/` will be very helpful.

**File Changes and Additions (Your Project):**

*   **New Frontend Files (in your `frontend/src/components/` or similar):**
    *   `CodingChallenge.js`: The main component for the LeetCode-like panel. This will be inspired by `Playground.tsx` and `Workspace.tsx` from the LeetCode clone. It will contain:
        *   `ProblemDisplay.jsx`: To show the problem statement, constraints, examples (inspired by `ProblemDescription/` from the clone).
        *   `CodeEditor.jsx`: Wrapper for Monaco/CodeMirror.
        *   `TestCasesPanel.jsx`: To show test cases, inputs, outputs, results.
        *   `EditorControls.jsx`: Buttons for "Run", "Submit", language selection (inspired by `EditorFooter.tsx`).
*   **Modified Frontend Files:**
    *   The main interview view component (where the chat bubbles appear) will need to conditionally render `CodingChallenge.js` instead of the chat input when `interview_stage` is `CODING_CHALLENGE` or `CODING_CHALLENGE_WAITING`.
    *   Frontend API service/utility functions to call the new backend endpoints.
*   **New Backend Files:**
    *   Possibly a new file for code execution logic if you choose Option B (e.g., `ai_interviewer/execution/code_runner.py`). If Option A (using a service like Judge0), this logic might be simpler and integrated into existing tool files.
*   **Modified Backend Files:**
    *   `ai_interviewer/core/ai_interviewer.py`:
        *   The `InterviewStage` enum will likely remain the same, but the usage of `CODING_CHALLENGE` and `CODING_CHALLENGE_WAITING` will be critical.
        *   The `should_continue` method will need to be aware of these stages and potentially `END` turns to allow the user to interact with the coding panel.
        *   The `call_model` method's system prompt might need to guide the AI on how to present the problem if it's going to be displayed in a dedicated panel rather than just in chat.
        *   The mechanism for receiving coding challenge results and transitioning to `FEEDBACK` will be important.
    *   `ai_interviewer/tools/problem_generation_tool.py`:
        *   `generate_coding_challenge_from_jd`: Needs to be updated to return structured problem data, including starter code, language, and test cases (input/output pairs).
        *   `submit_code_for_generated_challenge`: This tool will be the primary orchestrator on the backend. It will receive the code from the frontend, run it against test cases (using the new execution logic/service), and format the results.
    *   `ai_interviewer/server.py` (or your FastAPI router file):
        *   Add new API endpoints for `/api/v1/coding/run_code` and `/api/v1/coding/submit_solution`.
    *   `ai_interviewer/utils/constants.py`: Potentially new constants for API paths or default coding languages.

**Testing Strategy**

*   **Unit Tests:**
    *   For the backend, test the code execution logic in isolation (if custom).
    *   Test the parsing of problem data from the `generate_coding_challenge_from_jd` tool.
    *   Test the logic in `submit_code_for_generated_challenge` for evaluating against test cases.
*   **Integration Tests:**
    *   Test the flow: `generate_coding_challenge_from_jd` -> AI presents problem -> Frontend displays panel -> User submits code -> `submit_code_for_generated_challenge` evaluates -> AI gives feedback.
    *   Test API endpoints directly using a tool like `curl` or Postman.
*   **End-to-End (E2E) Tests (Manual initially, potentially automated later with Cypress/Playwright):**
    *   A user starts an interview.
    *   Progresses to the coding challenge stage.
    *   The coding panel appears with the problem.
    *   The user types code, selects a language.
    *   The user clicks "Run Code" with custom input.
        *   *Verify:* Output is displayed correctly.
    *   The user clicks "Submit Code."
        *   *Verify:* Test case results (pass/fail) are displayed.
        *   *Verify:* The AI receives the results and provides feedback.
    *   Test with various scenarios:
        *   Correct code.
        *   Code with compile errors.
        *   Code with runtime errors.
        *   Code that fails some test cases.
        *   Code that passes all test cases.
        *   Different languages (if supporting multiple).
*   **Security Testing (ESPECIALLY if implementing custom code execution):**
    *   Attempt to break out of the sandbox.
    *   Test for resource exhaustion (e.g., infinite loops, memory bombs).
    *   Input validation for all API endpoints.

This iterative approach allows for regular feedback and adjustments, and ensures that we're building a secure and functional coding environment. The `leetcode-clone-youtube` project will be a great visual and structural reference for the frontend components.

What are your thoughts on this plan? Would you like to start with Sprint 1, focusing on the basic UI and backend hook?

