# PBI-7: AI-Powered Proctoring Module

[View in Backlog](../backlog.md#user-content-7)

## Overview

This PBI implements a comprehensive AI-powered proctoring system for the AI Interviewer platform to ensure interview integrity and detect potential cheating behaviors. The system will use computer vision, browser APIs, and real-time monitoring to provide automated proctoring capabilities.

## Problem Statement

Current AI interviews lack integrity verification mechanisms, making it difficult for recruiters to trust that candidates are completing interviews honestly without external assistance. There's no way to detect:
- Candidates looking away from the screen (potentially reading from other sources)
- Multiple people in the room providing assistance
- Tab switching or copy-paste activities
- Candidate impersonation
- External assistance through audio cues

## User Stories

### Primary User Story
As a recruiter, I want an AI-powered proctoring system that monitors candidates during interviews to ensure integrity and detect potential cheating behaviors, so that I can trust the authenticity of the interview results.

### Secondary User Stories
- As a candidate, I want to be clearly informed about proctoring features and provide consent before the interview starts
- As an administrator, I want to configure proctoring sensitivity levels and rules based on interview requirements
- As a recruiter, I want to receive a comprehensive proctoring report with evidence and probability scores for any detected anomalies

## Technical Approach

### Core Components
1. **Frontend Proctoring Engine** (React/TypeScript with WebRTC)
   - WebRTC integration for real-time video feed
   - TensorFlow.js/MediaPipe for face and gaze tracking
   - Browser event monitoring for tab switches and window focus
   - Real-time anomaly detection and logging

2. **Backend Proctoring Service** (FastAPI Python)
   - Proctoring session management
   - Anomaly aggregation and scoring
   - Report generation with evidence compilation
   - Real-time WebSocket communication for alerts

3. **Computer Vision Pipeline**
   - Face detection and tracking
   - Gaze direction estimation
   - Multiple face detection
   - Presence/absence detection
   - Periodic face authentication

4. **Activity Monitoring**
   - Browser tab switching detection
   - Copy-paste activity monitoring
   - Window focus/blur events
   - Keyboard shortcut detection

5. **Audio Analysis** (Optional)
   - Background voice detection
   - Multiple speaker identification
   - Ambient noise analysis

### Technology Stack
- **Frontend**: React, TypeScript, WebRTC, TensorFlow.js, MediaPipe
- **Backend**: FastAPI, Python, OpenCV, WebSocket
- **Real-time Communication**: WebSocket for live monitoring alerts
- **Storage**: MongoDB for proctoring session data and evidence
- **Privacy**: Strict data handling with user consent mechanisms

## UX/UI Considerations

### Consent and Privacy
- Clear proctoring consent screen before interview start
- Detailed explanation of what will be monitored
- Option to review and delete proctoring data post-interview
- Transparent privacy policy for data handling

### User Experience
- Minimal visual indicators during monitoring (small camera preview)
- Non-intrusive alerts for technical issues
- Clear setup instructions for optimal camera positioning
- Graceful degradation if proctoring features fail

### Accessibility
- Support for users with visual impairments
- Alternative verification methods for users unable to use webcam
- Clear visual and audio cues for all proctoring interactions

## Acceptance Criteria

### Core Functionality
1. **Webcam Monitoring**
   - ✅ Continuously track candidate's face and eyes
   - ✅ Detect gaze aversion (looking away from screen)
   - ✅ Identify presence of multiple faces in frame
   - ✅ Alert when candidate is absent from frame

2. **Screen Activity Monitoring**
   - ✅ Detect and log tab switches with timestamps
   - ✅ Monitor copy-paste actions in real-time
   - ✅ Track new window openings
   - ✅ Log all activity with precise timestamps

3. **Face Authentication**
   - ✅ Perform initial face enrollment
   - ✅ Re-authenticate candidate periodically (every 10-15 minutes)
   - ✅ Detect potential impersonation attempts
   - ✅ Generate alerts for authentication failures

4. **Real-time Anomaly Detection**
   - ✅ Flag excessive head movement or gaze aversion
   - ✅ Detect multiple voices in audio stream (if enabled)
   - ✅ Log suspicious tab switching patterns
   - ✅ Generate real-time alerts with evidence

5. **Proctoring Report Generation**
   - ✅ Auto-generate structured proctoring report
   - ✅ Include all flags with detailed timestamps
   - ✅ Capture screenshots during anomalies
   - ✅ Calculate overall cheating probability score
   - ✅ Provide evidence summary with recommendations

### Privacy and Compliance
1. **Data Privacy**
   - ✅ Implement explicit user consent mechanisms
   - ✅ Provide clear data usage explanations
   - ✅ Allow users to review collected data
   - ✅ Implement secure data deletion options

2. **Compliance**
   - ✅ GDPR-compliant data handling
   - ✅ Secure storage of biometric data
   - ✅ Audit trail for all proctoring activities
   - ✅ Clear data retention policies

### Technical Requirements
1. **Performance**
   - ✅ Real-time processing with <200ms latency
   - ✅ Minimal impact on interview system performance
   - ✅ Graceful degradation when resources are limited
   - ✅ Support for various device capabilities

2. **Integration**
   - ✅ Seamless integration with existing interview flow
   - ✅ Compatible with voice-enabled interviews
   - ✅ Works with coding challenge sessions
   - ✅ Maintains session state consistency

## Dependencies

### External Dependencies
- TensorFlow.js or MediaPipe for computer vision
- WebRTC APIs for video streaming
- Browser APIs for activity monitoring
- OpenCV Python libraries for backend processing

### Internal Dependencies
- Existing FastAPI backend architecture
- React frontend framework
- MongoDB session management
- WebSocket communication infrastructure

### Infrastructure Dependencies
- Enhanced server resources for real-time processing
- Additional storage for proctoring evidence
- Potential CDN for efficient video streaming

## Open Questions

1. **Privacy Regulations**: What specific privacy regulations need to be considered for different geographical regions?
2. **False Positive Handling**: How should the system handle false positives in anomaly detection?
3. **Device Compatibility**: What minimum device requirements should be set for proctoring features?
4. **Data Retention**: How long should proctoring evidence be retained, and what are the deletion policies?
5. **Integration Testing**: How should proctoring be tested with existing voice and coding features?

## Related Tasks

[View Tasks](./tasks.md) 