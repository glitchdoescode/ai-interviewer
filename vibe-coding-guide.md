# Advanced Guide to Iterative Project Development with Cursor: The "Vibe-Coding" Approach

This document details an advanced, iterative prompting methodology for leveraging AI (specifically Cursor) to build complex software projects. It's based on the "vibe-coding" principles demonstrated by Deepak, emphasizing deep AI collaboration, structured iteration, rich context, continuous feedback, and strategic use of Cursor's features. This approach aims to make the AI an active partner in development, guided by your evolving understanding and project needs.

## Core Philosophy: "Vibe-Coding" with AI

- **AI as a Pair Programmer**: Treat Cursor not just as a code generator, but as a highly capable, if sometimes naive, pair programmer. You provide the high-level strategy, architectural constraints, and continuous supervision.
- **Iterative Refinement**: Development is not linear. Expect to guide, correct, and refine the AI's output. The process involves constant dialogue and adjustment.
- **Explicit Guidance**: The AI will "wander off" if not given specific, step-by-step instructions and clear boundaries.
- **Context is King**: Continuously feed the AI relevant context using @ mentions for files, architectural references, and evolving planning documents.
- **Own the Understanding**: While the AI writes code, you must understand it. Use the AI to explain if necessary, but never blindly accept its output.

## Phase 1: Strategic Initialization & Detailed Roadmapping

**Goal**: Translate high-level requirements into a granular, actionable checklist for MVP development, explicitly defining the iterative path and architectural foundations.

### 1.1. Initial Broad Stroke - Defining the MVP and Core Architecture:

**Key Prompt Example** (from Deepak's AI Interviewer start):

```
I want you to analyze @user-story.md and @product-requirements.md and then create a detailed checklist.md containing step-by-step tasks following agile methodology and iterative development in order to build an MVP first with a test chat interface to test it completely end-to-end. 

Then, plan to add more features into it in order to completely build the AI interviewer product as an end-to-end solution according to the logic mentioned in the user story document and PRD.

The core LangGraph related architecture must be the same as @gizomobot.py. So, basically:
1. Copy Filtero's (@gizomobot.py's) core LangGraph architecture.
2. Build a test chat endpoint.
3. Focus on the core logic and get it done (achieve MVP).
4. Then integrate STT (Speech-to-Text) and TTS (Text-to-Speech) into it.
5. Then build the frontend.
6. Auth and login, etc., can be done later.
```

**Deepak's Rationale & Low-Level Details**:

- **Analyze Core Documents**: Start by having Cursor ingest @user-story.md and @product-requirements.md.
- **Checklist as the North Star**: This becomes the dynamic plan. 
- **Agile & Iterative**: Explicitly state these methodologies. The AI understands these concepts. 
- **MVP First with Test Interface**: Crucial for early end-to-end testing of core logic before adding complexities like STT/TTS. Deepak emphasized not letting the AI jump to STT/TTS prematurely.
  - *"I didn't integrate speech to text or text to speech in the starting I made it using a test chat endpoint so that instead of giving it voice I will give it chats or text to test it out."*
- **Architectural Pinning**: Reference a stable, known-good architecture (e.g., @gizomobot.py for LangGraph). This provides a concrete foundation.
  - *"Gizmo is actually our product in production... that's why I told it to refer to Gizmo.py in order to learn the LangGraph related architecture... it's actually really really simple... single agent and another agent called supervisor agent."*
- **Phased Feature Rollout**: Clearly sequence post-MVP features (STT/TTS -> Frontend -> Auth). This manages complexity.
- **Focus on Core Files for Analysis**: When asking the AI to analyze the project later (e.g., for rule generation), provide only core files (e.g., server.py, AIinterviewer.py, interview_service.js) to avoid confusion.

### 1.2. Setting Up for AI Understanding (MCP Server for New Tech):

**Problem**: LLMs may not have up-to-date knowledge of recent libraries (e.g., LangGraph).

**Solution**: Model Context Protocol (MCP) Server:
- Set up an MCP server (e.g., mcp-doc from GitHub) that hosts local documentation (llm.txt containing links to specific docs).
- Configure Cursor to connect to this MCP server.
- This allows Cursor to fetch and refer to these specific docs during development.
  - *"It will automatically refer to that document before building something."*

Deepak walked through installing uv, running `uvx mcp-doc serve ./llm.txt --port 8082`, and then setting up the MCP inspector (`npx @mcp/inspector serve --port 6274`). The crucial part was configuring Cursor's MCP settings with the correct local IP (WSL IP) and port for the mcp-doc server.

## Phase 2: Establishing Project Conventions via Cursor Rules

**Goal**: Automate boilerplate, enforce coding standards, and provide reusable logic snippets by defining .cursor/rules.

**Key Prompt Example** (from Deepak):
```
I want you to analyze @checklist.md and then create rules using @create-cursor-rule.mdc which will be required or necessary to build the AI interviewer end-to-end.
```

**Deepak's Rationale & Low-Level Details**:
- **Rule for Creating Rules**: Use a meta-rule (like create-cursor-rule.mdc, sourced from a blog/community) to generate other rules.
- **Context for Rule Generation**: The @checklist.md informs the AI about the types of rules needed.
- **Types of Rules Generated**:
  - `langraph_tool_definition.py.mdc`: Defines schema for creating LangGraph tools.
    - *"It gave it an example Python code about creating tools... it is a rule for creating tools... use this schema... to generate tools."*
  - State management in LangGraph.
  - Git automation (auto-commit on "necessizable amount of changes").
  - API security for endpoints.
- **Auto-Attachment**: Rules can be configured to auto-attach to relevant files (e.g., Python tool definition rule auto-attaches when @some_file.py is mentioned).
- **Importance**: *"Without making rules... development can go off track sometimes."*

## Phase 3: Iterative Implementation, "Vibe-Coding," & Continuous Feedback

**Goal**: Build features step-by-step as per the checklist.md, constantly supervising, testing, and refining with the AI. This is where "vibe-coding" truly happens.

### 3.1. Starting a Task Block:

**Key Prompt Example** (from Deepak):
```
I want you to start implementing the tasks given in the @checklist.md step by step in order to build the AI interviewer completely end-to-end. 

For the LangGraph implementation, check @gizomobot.py and by fetching relevant LangGraph docs from the MCP server.

Also, make progress-report.md in order to track the product's development and also mention next steps in that doc.

Also, update the @checklist.md by marking the tasks which are done.

##codefiles (if starting to modify existing ones)
@cli.py @agent.py @workflow.py
```

**Deepak's Rationale & Low-Level Details**:
- **Checklist as the Driver**: Explicitly refer to it for the current task.
- **Architectural & Doc Reinforcement**: Remind AI about @gizomobot.py and MCP docs for LangGraph.
  - **Cursor's MCP interaction**: Calls list_doc_sources, gets LangGraph URL, calls fetch_docs with llm.txt, then iteratively fetches docs for specific URLs from llm.txt (e.g., "application structure," "flow level concepts").
- **Progress Report**: Crucial for tracking, but more importantly, for defining "Next Steps" for the AI.
  - *"The main thing is the next steps. It actually tells the cursor to what next steps you should take."*
- **Update Checklist**: Keep the plan current.
- **Initial File Structure**: AI might generate initial directories. Be prepared for manual reorganization if it messes up (e.g., coding in root instead of a sub-directory).

### 3.2. The "Vibe-Coding" Loop (Supervise, Test, Correct, Iterate):

1. **AI Generates Code**: Based on the prompt.
2. **Developer Supervises & Analyzes**:
   - *"At whenever cursor does some code analyze what changes are made anal like are they correct? Are they integrated correctly into the system?"*
   - **Understand the Output**: *"Never blindly accept or use AI-generated code. Always understand the reasoning behind changes."*
3. **Developer Tests**:
   - *"Try running it using the command. If it works, then well and good."*
   - **Example**: Deepak tested the chat interface, found regex-based name extraction, and prompted for an LLM-based solution for robustness.
     - *"For extracting names you can use LLMs instead of pattern matching... LLMs can dynamically and intelligently parse anything."*
4. **Developer Corrects/Re-prompts for Refinements or Bug Fixes**:
   - **Example**: If AI generates code with missing dependencies (e.g., cannot import ToolNode), the follow-up might be to instruct it to check requirements.txt or install dependencies. Cursor might then run `pip install -r requirements.txt`.
   - **Example**: If Gemini 2.5 Pro fails to edit a file, *"just say it to do it again like retry again."*
5. **Handling AI "Wandering"**:
   - Deepak noted Claude 3.7 sometimes *"does stuff which you like it is not told to... it goes beyond."*
   - He suggested Gemini 2.5 Pro might be more focused: *"will do only those stuff which you want it won't wander off."*
   - Experiment with models for different tasks (Gemini 2.5 Pro for docs/planning/large context; Cloud 3.7 for coding, using "thinking" mode for logic and "normal" for boilerplate).

### 3.3. Managing Context and Chats:

*"If a chat becomes too long, switch to a new chart because in a fresh chat the context is less so it performs well... that's why I have multiple charts."*

When starting a new chat for a continuing project, re-establish context:
```
## Context for AI Interviewer Project (Continuing Development)
We are building an AI interviewer.
- Current state and progress are in @progress-report.md.
- Outstanding tasks are in @checklist.md.
- Core LangGraph architecture reference: @gizomobot.py
- User requirements: @user-story.md, @product-requirements.md
- Relevant LangGraph documentation should be fetched via the configured MCP server.

##codefiles
@relevant_file1.py @relevant_file2.py

Please continue with the next task from @checklist.md.
```

## Phase 4: Committing Changes and Seamless Continuation

**Goal**: Maintain version control hygiene and smoothly transition to the next development cycle.

**Key Prompt Example** (from Deepak):
```
Make a git commit and then I want you to continue implementing the tasks given in the @checklist.md step by step in order to build the AI interviewer completely end-to-end. 

For the LangGraph implementation, check @gizomobot.py and by fetching relevant LangGraph docs from the MCP server.

Then update @progress-report.md and @checklist.md at the end.

##codefiles
@cli.py @agent.py @workflow.py
```

**Deepak's Rationale & Low-Level Details**:
- **Integrated Commit**: Make committing part of the AI's task flow.
- **Small, Frequent Commits**: *"Please try to do small small commits... after doing a small change make a get commit."* This minimizes loss if a bad commit needs reverting.
- **Update Tracking Docs**: Always end a work block by updating @progress-report.md (especially "Next Steps") and @checklist.md.
- **Git Automation Rule**: The previously defined rule can assist here.

## General Low-Level Tips & Mindset from Deepak:

- **File Attachment with @**: Prefer @filename over copy-pasting code for better context.
- **Restarting if Necessary**: *"If you think you want to restart it again from scratch using new prompting style... you can do that too... it will take you half an hour or one to two hours to do all of this again."* AI-assisted development can make re-dos less painful.
- **Reference Code Organization**: If using external reference code (like filtero-go-gizmo), clone it into a reference/ folder and add that folder to .gitignore.
- **Be Prepared for AI Quirks**:
  - Models might fail to edit files (Gemini 2.5 Pro sometimes).
  - Models might do more than asked (Cloud 3.7 observed).
  - AI might generate code in the wrong place, requiring manual reorganization.
- **Environment Troubleshooting**: Be aware of how local environments (WSL, Python venvs) can affect tool execution (e.g., the UVX path issue resolved by deactivating venv, WSL network access for MCP).