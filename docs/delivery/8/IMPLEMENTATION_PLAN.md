# PBI-8 Implementation Plan: Gemini Live API Integration

## Executive Summary

This document outlines the complete implementation plan for integrating Gemini Live API to replace the current STT->LLM->TTS sequential flow with real-time audio processing. The goal is to reduce latency from 5-10 seconds to <2 seconds while maintaining all existing interview logic.

## Current Architecture Analysis

### Existing Flow
```
Frontend → Audio Recording → transcribe_audio_gemini() → LangGraph (ai_interviewer.py) → synthesize_speech_gemini() → Audio Playback
Latency: 5-10 seconds per turn
```

### Context Injection Current Method
The system currently uses a comprehensive `INTERVIEW_SYSTEM_PROMPT` that includes:
- System name, job role, seniority level
- Required skills, job description, coding requirements
- Interview stage and candidate information
- Conversation summary and memory management
- Tool usage instructions and stage-specific guidance

### Key Components Identified
1. **AIInterviewer class** (`ai_interviewer/core/ai_interviewer.py`) - Main LangGraph orchestrator
2. **InterviewState** - Custom state extending MessagesState with interview context
3. **Session Management** - MongoDB-based persistence with memory management
4. **Tool Integration** - Coding challenges, feedback tools, analysis tools
5. **Frontend** - React-based chat interface with voice mode support

## New Architecture Design

### Target Flow
```
Frontend ↔ Gemini Live API ↔ Context Injection Service ↔ LangGraph Integration Bridge ↔ Session Management
Latency: <2 seconds with streaming
```

### Core Components

#### 1. Gemini Live Audio Adapter (`ai_interviewer/services/gemini_live_adapter.py`)
- **Purpose**: Real-time bidirectional audio streaming
- **Based on**: `geminicode1.py` BatchedContextAudioLoop pattern
- **Features**: 
  - Silent context injection without conversation interruption
  - Callback system for audio/text responses
  - Session lifecycle management
  - Error handling and recovery

#### 2. Context Injection Service (`ai_interviewer/services/context_injection_service.py`)
- **Purpose**: Bridge LangGraph state with Gemini Live API
- **Features**:
  - Convert `InterviewState` to silent context updates
  - Monitor stage transitions and inject them as context
  - Handle tool call results and memory updates
  - Batch context updates for efficiency

#### 3. Video Call Interface (`frontend/src/components/VideoCallInterface.js`)
- **Purpose**: Replace chat interface with video call experience
- **Features**:
  - Candidate camera feed (left panel)
  - AI interviewer avatar (right panel)
  - Real-time audio controls (mute, volume, connection status)
  - Mobile-responsive design

## Implementation Strategy

### Phase 1: Core Audio Streaming (Critical Path)
**Tasks**: 8-1, 8-2
**Timeline**: Week 1-2
**Deliverables**:
- Working Gemini Live API adapter with bidirectional audio
- Context injection service with silent updates
- Basic integration with existing session management

### Phase 2: LangGraph Integration (High Priority)
**Tasks**: 8-3, 8-4
**Timeline**: Week 2-3
**Deliverables**:
- Bridge between Gemini Live API and existing interview logic
- Preservation of interview stages, tool calls, memory management
- MongoDB session storage compatibility

### Phase 3: Frontend Transformation (Medium Priority)
**Tasks**: 8-5, 8-6
**Timeline**: Week 3-4
**Deliverables**:
- Video call interface replacing chat interface
- AI interviewer avatar with speaking indicators
- Camera permissions and mobile optimization

### Phase 4: Legacy Cleanup & Testing (Low Priority)
**Tasks**: 8-7, 8-8
**Timeline**: Week 4-5
**Deliverables**:
- Removal of old STT/TTS code
- Comprehensive E2E testing
- Performance validation and optimization

## Key Technical Decisions

### 1. Context Injection Approach
**Decision**: Use silent context injection pattern from `geminicode1.py`
**Rationale**: 
- Preserves conversation flow without interrupting user speech
- Allows dynamic context updates during ongoing conversation
- Compatible with Gemini Live API's text input capabilities

**Implementation**:
```python
silent_context = f"[SYSTEM CONTEXT - DO NOT RESPOND OR ACKNOWLEDGE - ABSORB SILENTLY]: {context_text}"
await session.send_realtime_input(text=silent_context)
```

### 2. LangGraph Integration Strategy
**Decision**: Create adapter layer instead of replacing LangGraph
**Rationale**:
- Preserves all existing interview logic and tool integrations
- Maintains session management and memory features
- Allows gradual migration with fallback capabilities

### 3. Frontend Architecture
**Decision**: Replace ChatInterface with VideoCallInterface component
**Rationale**:
- Modern video call experience aligns with user expectations
- Visual engagement improves interview experience
- Maintains existing routing and session management

## Risk Mitigation

### 1. Latency Requirements
**Risk**: May not achieve <2 second latency target
**Mitigation**: 
- Implement latency monitoring and alerting
- Optimize context injection frequency and size
- Consider fallback to traditional flow for poor connections

### 2. Context Size Limits
**Risk**: Gemini Live API may have context size limitations
**Mitigation**:
- Implement context truncation and summarization
- Prioritize most recent and critical context information
- Use conversation summaries for long interviews

### 3. Tool Call Integration
**Risk**: Complex tool calls may not work well with real-time flow
**Mitigation**:
- Design hybrid approach for tool calls (pause real-time, execute, resume)
- Implement tool result injection as silent context
- Maintain fallback to traditional flow for complex tool sequences

## Success Metrics

### Performance Targets
- **Audio Latency**: <2 seconds (vs current 5-10 seconds)
- **Context Injection**: <100ms processing time
- **Video Interface Load**: <3 seconds
- **Session Reliability**: 99%+ uptime during 30+ minute interviews

### Functional Requirements
- All interview stages work seamlessly
- Tool calls (coding challenges, feedback) function properly
- Session management and memory preservation maintained
- Mobile responsive design across target devices

### Quality Assurance
- Cross-browser compatibility (Chrome, Firefox, Safari, Edge)
- Mobile device testing (iOS Safari, Android Chrome)
- Audio quality validation (no dropouts, clear speech)
- Error handling and recovery testing

## Dependencies & Prerequisites

### External Dependencies
- Gemini Live API access and stable connection
- Camera/microphone permissions in browsers
- WebRTC support for video functionality

### Internal Dependencies
- Existing MongoDB session management
- LangGraph interview logic and tools
- Current session persistence and memory management

### Technical Prerequisites
- Python 3.11+ for asyncio.TaskGroup support
- Updated google-genai package with Live API support
- PyAudio for local audio processing
- Modern browser with WebRTC capabilities

## Next Steps

1. **Immediate**: Start Task 8-1 (Gemini Live API Adapter) implementation
2. **Week 1**: Parallel development of Task 8-2 (Context Injection Service)
3. **Week 2**: Begin integration testing with existing LangGraph logic
4. **Week 3**: Start frontend video interface development
5. **Week 4**: End-to-end testing and performance optimization

## Questions for Stakeholder Review

1. **Priority**: Should we maintain fallback to old STT/TTS system for unreliable connections?
2. **Scope**: Are there specific interview stages or tools that are highest priority for initial release?
3. **Performance**: Is <2 second latency target firm, or can we accept slightly higher for better reliability?
4. **Mobile**: What's the priority level for mobile optimization vs desktop-first approach?

---

**Document Version**: 1.0  
**Last Updated**: 2025-01-27  
**Next Review**: Upon completion of Task 8-1