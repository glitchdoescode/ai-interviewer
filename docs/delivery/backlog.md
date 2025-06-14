# Product Backlog

This document contains all Product Backlog Items (PBIs) for the AI Interviewer project, ordered by priority.

## PBI Table

| ID | Actor | User Story | Status | Conditions of Satisfaction (CoS) |
|:---|:------|:-----------|:-------|:----------------------------------|
| 7 | Recruiter/Admin | As a recruiter, I want an AI-powered proctoring system that monitors candidates during interviews to ensure integrity and detect potential cheating behaviors, so that I can trust the authenticity of the interview results. | Agreed | [View Details](./7/prd.md) |
| 8 | Interviewer/Candidate | As a user conducting or participating in interviews, I want low-latency real-time audio processing using Gemini Live API instead of the current STT->LLM->TTS sequential flow, so that conversations feel natural and responsive like a video call | Agreed | 1. Gemini Live API integrated with existing LangGraph interview logic and state transitions<br/>2. Real-time audio streaming with context injection capabilities<br/>3. Frontend converted to video call interface with camera feed and AI interviewer avatar<br/>4. Conversation history, memory management, and session persistence maintained<br/>5. All interview stages (introduction, technical, coding, feedback, conclusion) work seamlessly<br/>6. Old STT/TTS logic completely removed and replaced<br/>7. Compatible with existing MongoDB storage and session management<br/>8. Performance improvement: <2 second response latency vs current 5-10 second delay |
| 10 | Employer/Recruiter | As an employer/recruiter, I want to integrate the AI Interviewer with our ATS, manage job-specific questions, and automatically invite candidates to interviews, so that I can streamline our hiring process and evaluate candidates more efficiently. | Proposed | 1. System can connect to at least one major ATS via API<br/>2. Job descriptions and requirements can be imported from ATS<br/>3. Employers can review and approve interview questions and coding challenges<br/>4. System can automatically send email invitations to shortlisted candidates<br/>5. Interviews are customized based on the job description<br/>6. Interview results are associated with the correct job application<br/>7. Data is properly isolated between organizations<br/> [View Details](./10/prd.md) |

## PBI History Log

| Timestamp | PBI_ID | Event_Type | Details | User |
|:----------|:-------|:-----------|:--------|:-----|
| 2025-01-27 12:00:00 | 7 | create_pbi | Created AI-powered proctoring module PBI | AI_Agent |
| 2025-01-27 12:30:00 | 7 | propose_for_backlog | PBI-7 approved and status changed to Agreed | User | 
| 2025-01-27 10:00:00 | 8 | Created | PBI created for Gemini Live API integration | AI_Agent |
| 2025-01-27 15:00:00 | 8 | propose_for_backlog | PBI-8 approved and status changed to Agreed | User | 
| 2023-07-25 10:00:00 | 10 | create_pbi | Created PBI for multi-user architecture with ATS integration | User |