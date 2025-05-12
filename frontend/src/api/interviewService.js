import axios from 'axios';

// Base URL for API requests
const API_URL = '/api';

// Create axios instance with default config
const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * Start a new interview session
 * @param {string} message - Initial user message
 * @param {string} userId - Optional user ID
 * @returns {Promise} Promise with response data
 */
export const startInterview = async (message, userId = null) => {
  try {
    const response = await api.post('/interview', {
      message,
      user_id: userId
    });
    return response.data;
  } catch (error) {
    console.error('Error starting interview:', error);
    throw error;
  }
};

/**
 * Continue an existing interview session
 * @param {string} sessionId - Interview session ID
 * @param {string} message - User message
 * @param {string} userId - User ID
 * @returns {Promise} Promise with response data
 */
export const continueInterview = async (sessionId, message, userId) => {
  try {
    const response = await api.post(`/interview/${sessionId}`, {
      message,
      user_id: userId
    });
    return response.data;
  } catch (error) {
    console.error('Error continuing interview:', error);
    throw error;
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
    const response = await api.get(`/sessions/${userId}`, {
      params: { include_completed: includeCompleted }
    });
    return response.data;
  } catch (error) {
    console.error('Error getting user sessions:', error);
    throw error;
  }
};

/**
 * Transcribe audio and get a response
 * @param {string} audioBase64 - Base64-encoded audio data
 * @param {string} userId - User ID
 * @param {string} sessionId - Optional session ID
 * @returns {Promise} Promise with response data
 */
export const transcribeAndRespond = async (audioBase64, userId, sessionId = null) => {
  try {
    const response = await api.post('/audio/transcribe', {
      audio_base64: audioBase64,
      user_id: userId,
      session_id: sessionId
    });
    return response.data;
  } catch (error) {
    console.error('Error transcribing audio:', error);
    throw error;
  }
};

/**
 * Check if voice processing is available
 * @returns {Promise<boolean>} Promise with boolean indicating if voice is available
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

// Create a service object to export
const interviewService = {
  startInterview,
  continueInterview,
  getUserSessions,
  transcribeAndRespond,
  checkVoiceAvailability
};

export default interviewService; 