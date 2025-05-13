import axios from 'axios';

// Base URL for API requests
const API_URL = '/api';

// Create axios instance with default config
const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  // Add timeout to prevent hanging requests
  timeout: 30000, // 30 seconds
});

// Global error handler function
const handleApiError = (error, customMessage = null) => {
  // Extract the most useful error information
  let errorMessage = customMessage || 'An error occurred';
  
  if (error.response) {
    // The server responded with an error status code
    const serverError = error.response.data?.detail || error.response.statusText;
    errorMessage = `Server error: ${serverError}`;
    console.error('API error response:', {
      status: error.response.status,
      data: error.response.data,
      message: serverError
    });
  } else if (error.request) {
    // The request was made but no response was received
    errorMessage = 'No response from server. Check your network connection.';
    console.error('API no response:', error.request);
  } else {
    // Something else caused the error
    errorMessage = error.message || errorMessage;
    console.error('API request error:', error.message);
  }
  
  // Create an enhanced error object
  const enhancedError = new Error(errorMessage);
  enhancedError.originalError = error;
  enhancedError.status = error.response?.status;
  enhancedError.serverData = error.response?.data;
  
  throw enhancedError;
};

/**
 * Start a new interview session
 * @param {string} message - Initial user message
 * @param {string} userId - Optional user ID
 * @param {Object} jobRoleData - Optional job role configuration
 * @returns {Promise} Promise with response data
 */
export const startInterview = async (message, userId = null, jobRoleData = null) => {
  try {
    const requestBody = {
      message,
      user_id: userId
    };
    
    // Add job role data if provided
    if (jobRoleData) {
      requestBody.job_role = jobRoleData.role_name;
      requestBody.seniority_level = jobRoleData.seniority_level;
      requestBody.required_skills = jobRoleData.required_skills;
      requestBody.job_description = jobRoleData.description;
    }
    
    const response = await api.post('/interview', requestBody);
    return response.data;
  } catch (error) {
    return handleApiError(error, 'Failed to start interview');
  }
};

/**
 * Continue an existing interview session
 * @param {string} message - User message
 * @param {string} sessionId - Interview session ID
 * @param {string} userId - User ID
 * @param {Object} jobRoleData - Optional job role configuration for new sessions
 * @returns {Promise} Promise with response data
 */
export const continueInterview = async (message, sessionId, userId, jobRoleData = null) => {
  try {
    if (!sessionId) {
      throw new Error('Session ID is required');
    }
    
    if (!userId) {
      throw new Error('User ID is required');
    }
    
    const requestBody = {
      message,
      user_id: userId
    };
    
    // Add job role data if provided
    if (jobRoleData) {
      requestBody.job_role = jobRoleData.role_name;
      requestBody.seniority_level = jobRoleData.seniority_level;
      requestBody.required_skills = jobRoleData.required_skills;
      requestBody.job_description = jobRoleData.description;
    }
    
    const response = await api.post(`/interview/${sessionId}`, requestBody);
    return response.data;
  } catch (error) {
    return handleApiError(error, 'Failed to continue interview');
  }
};

/**
 * Get all sessions for a user
 * @param {string} userId - User ID
 * @param {boolean} includeCompleted - Whether to include completed sessions
 * @returns {Promise} Promise with response data
 */
export const getUserSessions = async (userId, includeCompleted = false) => {
  try {
    if (!userId) {
      throw new Error('User ID is required');
    }
    
    const response = await api.get(`/sessions/${userId}`, {
      params: { include_completed: includeCompleted }
    });
    
    return response.data;
  } catch (error) {
    return handleApiError(error, 'Failed to retrieve user sessions');
  }
};

/**
 * Transcribe audio and get a response
 * @param {string} audioBase64 - Base64-encoded audio data
 * @param {string} userId - User ID
 * @param {string} sessionId - Optional session ID
 * @param {Object} jobRoleData - Optional job role configuration
 * @returns {Promise} Promise with response data
 */
export const transcribeAndRespond = async (audioBase64, userId, sessionId = null, jobRoleData = null) => {
  try {
    if (!audioBase64) {
      throw new Error('Audio data is required');
    }
    
    const requestBody = {
      audio_base64: audioBase64,
      user_id: userId || `anon-${Date.now()}`,
      session_id: sessionId,
      sample_rate: 16000,  // Default sample rate
      channels: 1          // Default channels
    };
    
    // Add job role data if provided
    if (jobRoleData) {
      requestBody.job_role = jobRoleData.role_name;
      requestBody.seniority_level = jobRoleData.seniority_level;
      requestBody.required_skills = jobRoleData.required_skills;
      requestBody.job_description = jobRoleData.description;
    }
    
    console.log('Sending audio transcription request...');
    
    const response = await api.post('/audio/transcribe', requestBody);
    
    // Validate response
    if (!response.data || !response.data.transcription) {
      throw new Error('Invalid response from transcription service');
    }
    
    return response.data;
  } catch (error) {
    // Special handling for 501 Not Implemented - voice processing not available
    if (error.response && error.response.status === 501) {
      const enhancedError = new Error('Voice processing is not available on this server');
      enhancedError.isVoiceUnavailable = true;
      throw enhancedError;
    }
    
    // Special handling for 422 Unprocessable Entity - no speech detected
    if (error.response && error.response.status === 422) {
      const enhancedError = new Error('No speech detected or audio could not be transcribed');
      enhancedError.isNoSpeech = true;
      throw enhancedError;
    }
    
    return handleApiError(error, 'Failed to process voice input');
  }
};

/**
 * Check if voice processing is available on the server
 * @returns {Promise<boolean>} Promise resolving to true if voice processing is available, false otherwise
 */
export const checkVoiceAvailability = async () => {
  try {
    const response = await api.get('/health');
    return response.data.voice_processing === 'available';
  } catch (error) {
    console.error('Error checking voice availability:', error);
    return false;
  }
};

/**
 * Submit code for a coding challenge
 * @param {string} challengeId - Challenge ID
 * @param {string} code - Candidate's code
 * @param {string} userId - User ID
 * @param {string} sessionId - Session ID
 * @returns {Promise} Promise with evaluation results
 */
export const submitChallengeCode = async (challengeId, code, userId = null, sessionId = null) => {
  try {
    if (!challengeId) {
      throw new Error('Challenge ID is required');
    }
    
    if (!code || code.trim() === '') {
      throw new Error('Code solution is required');
    }
    
    const requestBody = {
      challenge_id: challengeId,
      code: code,
      user_id: userId,
      session_id: sessionId
    };
    
    const response = await api.post('/coding/submit', requestBody);
    return response.data;
  } catch (error) {
    return handleApiError(error, 'Failed to submit code solution');
  }
};

/**
 * Get a hint for the current coding challenge
 * @param {string} challengeId - Challenge ID
 * @param {string} code - Current code implementation
 * @param {string} userId - User ID
 * @param {string} sessionId - Session ID
 * @param {string} errorMessage - Optional error message to get specific help
 * @returns {Promise} Promise with hints
 */
export const getChallengeHint = async (challengeId, code, userId = null, sessionId = null, errorMessage = null) => {
  try {
    if (!challengeId) {
      throw new Error('Challenge ID is required');
    }
    
    const requestBody = {
      challenge_id: challengeId,
      code: code || '',
      user_id: userId,
      session_id: sessionId,
      error_message: errorMessage
    };
    
    const response = await api.post('/coding/hint', requestBody);
    return response.data;
  } catch (error) {
    return handleApiError(error, 'Failed to get hint');
  }
};

/**
 * Continue after completing a coding challenge
 * @param {string} message - User message (typically about the completed challenge)
 * @param {string} sessionId - Session ID
 * @param {string} userId - User ID
 * @param {boolean} completed - Whether the challenge was completed successfully
 * @returns {Promise} Promise with response data
 */
export const continueAfterCodingChallenge = async (message, sessionId, userId, completed = true) => {
  try {
    if (!sessionId) {
      throw new Error('Session ID is required');
    }
    
    if (!userId) {
      throw new Error('User ID is required');
    }
    
    const requestBody = {
      message,
      user_id: userId,
      challenge_completed: completed
    };
    
    const response = await api.post(`/interview/${sessionId}/challenge-complete`, requestBody);
    return response.data;
  } catch (error) {
    return handleApiError(error, 'Failed to continue after challenge');
  }
};

/**
 * Fetches available job roles for interviews
 * @returns {Promise<Array>} Array of job role objects
 */
export const getJobRoles = async () => {
  try {
    const response = await api.get('/job-roles');
    return response.data;
  } catch (error) {
    return handleApiError(error, 'Failed to fetch job roles');
  }
};

// Set up a response interceptor for global error handling
api.interceptors.response.use(
  response => response,
  error => {
    // Handle rate limiting errors (429)
    if (error.response && error.response.status === 429) {
      console.error('Rate limit exceeded:', error.response.data);
      error.message = 'Too many requests. Please wait a moment before trying again.';
    }
    
    // Handle server errors (500)
    if (error.response && error.response.status >= 500) {
      console.error('Server error:', error.response.data);
      error.message = 'The server encountered an error. Please try again later.';
    }
    
    return Promise.reject(error);
  }
);

// Create a service object to export
const interviewService = {
  startInterview,
  continueInterview,
  getUserSessions,
  transcribeAndRespond,
  checkVoiceAvailability,
  submitChallengeCode,
  getChallengeHint,
  continueAfterCodingChallenge,
  getJobRoles
};

export default interviewService; 