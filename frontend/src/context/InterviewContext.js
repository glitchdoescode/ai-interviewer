import React, { createContext, useContext, useReducer, useEffect } from 'react';

// Initialize context
const InterviewContext = createContext();

// Action types
const ACTION_TYPES = {
  SET_USER_ID: 'SET_USER_ID',
  SET_SESSION_ID: 'SET_SESSION_ID',
  SET_LOADING: 'SET_LOADING',
  SET_MESSAGES: 'SET_MESSAGES',
  ADD_MESSAGE: 'ADD_MESSAGE',
  SET_INTERVIEW_STAGE: 'SET_INTERVIEW_STAGE',
  SET_ERROR: 'SET_ERROR',
  CLEAR_ERROR: 'CLEAR_ERROR',
  SET_VOICE_MODE: 'SET_VOICE_MODE',
};

// Initial state
const initialState = {
  userId: localStorage.getItem('userId') || null,
  sessionId: null,
  messages: [],
  loading: false,
  interviewStage: null,
  error: null,
  voiceMode: false
};

// Reducer function
function interviewReducer(state, action) {
  switch (action.type) {
    case ACTION_TYPES.SET_USER_ID:
      return { ...state, userId: action.payload };
    case ACTION_TYPES.SET_SESSION_ID:
      return { ...state, sessionId: action.payload };
    case ACTION_TYPES.SET_LOADING:
      return { ...state, loading: action.payload };
    case ACTION_TYPES.SET_MESSAGES:
      return { ...state, messages: action.payload };
    case ACTION_TYPES.ADD_MESSAGE:
      return { 
        ...state, 
        messages: [...state.messages, action.payload] 
      };
    case ACTION_TYPES.SET_INTERVIEW_STAGE:
      return { ...state, interviewStage: action.payload };
    case ACTION_TYPES.SET_ERROR:
      return { ...state, error: action.payload };
    case ACTION_TYPES.CLEAR_ERROR:
      return { ...state, error: null };
    case ACTION_TYPES.SET_VOICE_MODE:
      return { ...state, voiceMode: action.payload };
    default:
      return state;
  }
}

// Provider component
export function InterviewProvider({ children }) {
  const [state, dispatch] = useReducer(interviewReducer, initialState);

  // Persist userId to localStorage
  useEffect(() => {
    if (state.userId) {
      localStorage.setItem('userId', state.userId);
    }
  }, [state.userId]);

  // Context value
  const value = {
    ...state,
    setUserId: (userId) => {
      dispatch({ type: ACTION_TYPES.SET_USER_ID, payload: userId });
    },
    setSessionId: (sessionId) => {
      dispatch({ type: ACTION_TYPES.SET_SESSION_ID, payload: sessionId });
    },
    setLoading: (isLoading) => {
      dispatch({ type: ACTION_TYPES.SET_LOADING, payload: isLoading });
    },
    setMessages: (messages) => {
      dispatch({ type: ACTION_TYPES.SET_MESSAGES, payload: messages });
    },
    addMessage: (message) => {
      dispatch({ type: ACTION_TYPES.ADD_MESSAGE, payload: message });
    },
    setInterviewStage: (stage) => {
      dispatch({ type: ACTION_TYPES.SET_INTERVIEW_STAGE, payload: stage });
    },
    setError: (error) => {
      dispatch({ type: ACTION_TYPES.SET_ERROR, payload: error });
    },
    clearError: () => {
      dispatch({ type: ACTION_TYPES.CLEAR_ERROR });
    },
    setVoiceMode: (enabled) => {
      dispatch({ type: ACTION_TYPES.SET_VOICE_MODE, payload: enabled });
    }
  };

  return (
    <InterviewContext.Provider value={value}>
      {children}
    </InterviewContext.Provider>
  );
}

// Custom hook for using the context
export function useInterview() {
  const context = useContext(InterviewContext);
  if (context === undefined) {
    throw new Error('useInterview must be used within an InterviewProvider');
  }
  return context;
}

export default InterviewContext; 