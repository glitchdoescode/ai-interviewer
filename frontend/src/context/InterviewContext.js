import React, { createContext, useContext, useReducer, useCallback } from 'react';
import { v4 as uuidv4 } from 'uuid';

// Create context
const InterviewContext = createContext();

// Define initial state
const initialState = {
  userId: `user-${uuidv4()}`,
  sessionId: null,
  messages: [],
  loading: false,
  error: null,
  voiceMode: false,
  interviewStage: 'introduction',
  jobRoleData: null,
  currentCodingChallenge: null,
};

// Define reducer actions
const ACTIONS = {
  SET_USER_ID: 'set_user_id',
  SET_SESSION_ID: 'set_session_id',
  SET_MESSAGES: 'set_messages',
  ADD_MESSAGE: 'add_message',
  SET_LOADING: 'set_loading',
  SET_ERROR: 'set_error',
  SET_VOICE_MODE: 'set_voice_mode',
  SET_INTERVIEW_STAGE: 'set_interview_stage',
  SET_JOB_ROLE_DATA: 'set_job_role_data',
  SET_CURRENT_CODING_CHALLENGE: 'set_current_coding_challenge',
  RESET: 'reset',
};

// Reducer function to handle state updates
const reducer = (state, action) => {
  switch (action.type) {
    case ACTIONS.SET_USER_ID:
      return { ...state, userId: action.payload };
    case ACTIONS.SET_SESSION_ID:
      return { ...state, sessionId: action.payload };
    case ACTIONS.SET_MESSAGES:
      return { ...state, messages: action.payload };
    case ACTIONS.ADD_MESSAGE:
      return { ...state, messages: [...state.messages, action.payload] };
    case ACTIONS.SET_LOADING:
      return { ...state, loading: action.payload };
    case ACTIONS.SET_ERROR:
      return { ...state, error: action.payload };
    case ACTIONS.SET_VOICE_MODE:
      return { ...state, voiceMode: action.payload };
    case ACTIONS.SET_INTERVIEW_STAGE:
      return { ...state, interviewStage: action.payload };
    case ACTIONS.SET_JOB_ROLE_DATA:
      return { ...state, jobRoleData: action.payload };
    case ACTIONS.SET_CURRENT_CODING_CHALLENGE:
      return { ...state, currentCodingChallenge: action.payload };
    case ACTIONS.RESET:
      return {
        ...initialState,
        userId: `user-${uuidv4()}`, // Generate fresh user ID
        messages: [], // Reset messages
        currentCodingChallenge: null, // Reset coding challenge on full reset
      };
    default:
      return state;
  }
};

/**
 * Interview Provider component
 * Provides interview state management context
 */
export const InterviewProvider = ({ children }) => {
  const [state, dispatch] = useReducer(reducer, initialState);
  
  // Define action dispatchers as callbacks
  const setUserId = useCallback((userId) => {
    dispatch({ type: ACTIONS.SET_USER_ID, payload: userId });
  }, []);
  
  const setSessionId = useCallback((sessionId) => {
    dispatch({ type: ACTIONS.SET_SESSION_ID, payload: sessionId });
  }, []);
  
  const setMessages = useCallback((messages) => {
    dispatch({ type: ACTIONS.SET_MESSAGES, payload: messages });
  }, []);
  
  const addMessage = useCallback((message) => {
    console.log('Adding message to context:', message);
    dispatch({ type: ACTIONS.ADD_MESSAGE, payload: message });
  }, []);
  
  const setLoading = useCallback((loading) => {
    dispatch({ type: ACTIONS.SET_LOADING, payload: loading });
  }, []);
  
  const setError = useCallback((error) => {
    dispatch({ type: ACTIONS.SET_ERROR, payload: error });
  }, []);
  
  const setVoiceMode = useCallback((voiceMode) => {
    dispatch({ type: ACTIONS.SET_VOICE_MODE, payload: voiceMode });
  }, []);
  
  const setInterviewStage = useCallback((stage) => {
    dispatch({ type: ACTIONS.SET_INTERVIEW_STAGE, payload: stage });
  }, []);
  
  const setJobRoleData = useCallback((jobRoleData) => {
    dispatch({ type: ACTIONS.SET_JOB_ROLE_DATA, payload: jobRoleData });
  }, []);
  
  const setCurrentCodingChallenge = useCallback((challengeData) => {
    dispatch({ type: ACTIONS.SET_CURRENT_CODING_CHALLENGE, payload: challengeData });
  }, []);
  
  const resetInterview = useCallback(() => {
    dispatch({ type: ACTIONS.RESET });
  }, []);
  
  // Create context value object with state and action dispatchers
  const value = {
    ...state,
    setUserId,
    setSessionId,
    setMessages,
    addMessage,
    setLoading,
    setError,
    setVoiceMode,
    setInterviewStage,
    setJobRoleData,
    setCurrentCodingChallenge,
    resetInterview,
  };
  
  // Provide context to children
  return (
    <InterviewContext.Provider value={value}>
      {children}
    </InterviewContext.Provider>
  );
};

// Custom hook for accessing interview context
export const useInterview = () => {
  const context = useContext(InterviewContext);
  
  if (context === undefined) {
    throw new Error('useInterview must be used within an InterviewProvider');
  }
  
  return context;
};

export default InterviewContext; 