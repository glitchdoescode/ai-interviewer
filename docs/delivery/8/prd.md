# PBI-8: Low-Latency Real-Time Audio Processing with Gemini Live API

[View in Backlog](../backlog.md#user-content-8)

## Overview

This PBI transforms the AI interviewer from a sequential STT->LLM->TTS flow to a real-time conversational experience using Gemini Live API. The goal is to eliminate the 5-10 second response delays and create a natural, video call-like interview experience.

## Problem Statement

The current implementation processes audio sequentially:
1. Record audio → 2. STT (transcribe_audio_gemini) → 3. LLM processing (LangGraph) → 4. TTS (synthesize_speech_gemini) → 5. Play audio

This creates significant latency (5-10 seconds) that makes conversations feel unnatural and disrupts the interview flow. Modern users expect real-time responsiveness similar to video calling platforms.

## User Stories

- **As an interviewer (AI)**, I want to respond to candidate speech in real-time so that the conversation feels natural and engaging
- **As a candidate**, I want immediate audio feedback when I speak so that I know the AI is actively listening and processing my responses
- **As a candidate**, I want visual cues (video interface) so that the interview feels more human-like and professional
- **As a system**, I want to maintain all existing interview logic, state transitions, and memory management while improving performance

## Technical Approach

### Current Architecture Analysis
```
Current Flow:
Frontend → Audio Recording → STT API → LangGraph → TTS API → Audio Playback
Latency: 5-10 seconds per turn

Context Injection:
- System prompt with job_role, seniority_level, required_skills, job_description
- Interview stage awareness (introduction, technical, coding, feedback, conclusion)
- Session memory and conversation summaries
- Tool integration (coding challenges, feedback tools)
```

### New Architecture
```
New Flow:
Frontend ↔ Gemini Live API ↔ Context Injection Service ↔ LangGraph Integration
Latency: <2 seconds with streaming

Components:
1. Real-time audio streaming (bidirectional)
2. Context injection service (silent context updates)
3. LangGraph integration adapter
4. Video call interface
5. Session persistence layer
```

### Integration Strategy

1. **Gemini Live API Implementation**
   - Use `geminicode1.py` as base for real-time audio processing
   - Implement silent context injection for interview state and job details
   - Maintain bidirectional audio streaming

2. **LangGraph Integration**
   - Create adapter layer between Gemini Live API and existing LangGraph logic
   - Inject interview context through silent text updates
   - Preserve interview stage transitions and tool usage

3. **Frontend Transformation**
   - Convert chat interface to video call interface
   - Add candidate camera feed and AI interviewer avatar
   - Maintain existing session management and routing

## UX/UI Considerations

### Video Call Interface Design
- **Left panel**: Candidate camera feed (real-time)
- **Right panel**: AI interviewer avatar (static image with speaking animations)
- **Bottom panel**: Interview controls (mute, end interview, stage indicator)
- **Side panel**: Session info, current stage, coding challenge display

### Audio Experience
- Real-time bidirectional audio with minimal latency
- Visual speaking indicators during conversations
- Seamless transitions between interview stages
- Background context injection without audio interruption

### Mobile Responsiveness
- Maintain responsive design for mobile devices
- Touch-friendly controls for interview interaction
- Optimized camera positioning for mobile interviews

## Acceptance Criteria

1. **Real-time Audio Processing**
   - Audio latency reduced from 5-10 seconds to <2 seconds
   - Bidirectional audio streaming works reliably
   - Context injection happens silently without interrupting conversation flow

2. **LangGraph Integration Maintained**
   - All interview stages work: introduction, technical_questions, coding_challenge, feedback, conclusion
   - Tool calls function properly (coding challenges, feedback tools)
   - Interview state transitions occur correctly

3. **Frontend Video Interface**
   - Video call interface replaces chat interface
   - Candidate camera feed displays properly
   - AI interviewer avatar with speaking indicators
   - All existing routes and navigation preserved

4. **Session Management Preserved**
   - MongoDB session storage continues to work
   - Conversation history and summaries maintained
   - Memory management functions across sessions
   - Session resumption works correctly

5. **Performance Requirements**
   - Audio response latency: <2 seconds (vs current 5-10 seconds)
   - Video interface loads within 3 seconds
   - No audio dropouts or connection issues during 30+ minute interviews
   - Memory usage remains stable during long sessions

6. **Legacy Cleanup**
   - Old STT/TTS logic completely removed from codebase
   - Unused audio utilities cleaned up
   - No dead code or deprecated endpoints

## Dependencies

- **External**: Gemini Live API access and stable connection
- **Internal**: Existing LangGraph interview logic, MongoDB setup, session management
- **Frontend**: Camera permissions, audio permissions, WebRTC capabilities

## Open Questions

1. How to handle tool calls (coding challenges) within the Gemini Live API context?
2. Should we maintain a fallback to the old STT/TTS system for unreliable connections?
3. How to handle context size limits in Gemini Live API for long interviews?
4. What's the optimal strategy for injecting interview stage transitions as silent context?

## Related Tasks

[View task list](./tasks.md) 