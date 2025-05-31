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
  timeout: 120000, // 120 seconds (increased from 30 seconds)
});

// Add a request interceptor to include the auth token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('authToken');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
      console.log('Interceptor: Token added to Authorization header'); // For debugging
    } else {
      console.log('Interceptor: No token found in localStorage'); // For debugging
    }
    return config;
  },
  (error) => {
    console.error('Interceptor Error:', error); // For debugging
    return Promise.reject(error);
  }
);

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
    return {
      ...response.data,
      codingChallengeDetail: response.data.coding_challenge_detail
    };
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
    return {
      ...response.data,
      codingChallengeDetail: response.data.coding_challenge_detail
    };
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
      console.error('DEBUG: Audio data is missing or empty');
      throw new Error('Audio data is required');
    }
    
    // Enhanced debugging for audio data
    const isFullDataUri = audioBase64.startsWith('data:audio/');
    const dataLength = audioBase64.length;
    
    console.log('DEBUG: Audio data stats:', {
      totalLength: dataLength,
      isDataUri: isFullDataUri,
      prefix: audioBase64.substring(0, 30) + '...',
      suffix: '...' + audioBase64.substring(audioBase64.length - 30)
    });
    
    // Validate audio data format
    if (!isFullDataUri && !audioBase64.match(/^[A-Za-z0-9+/=]+$/)) {
      console.warn('DEBUG: Audio data does not appear to be valid base64 or data URI');
    }
    
    // Ensure we use the full data URI for the backend
    let formattedAudioData = audioBase64;
    if (!isFullDataUri) {
      // If we just got the base64 part, add the data URI prefix
      console.log('DEBUG: Adding data URI prefix to raw base64 data');
      formattedAudioData = `data:audio/wav;base64,${audioBase64}`;
    }
    
    const requestBody = {
      audio_data: formattedAudioData,
      user_id: userId || `anon-${Date.now()}`,
      session_id: sessionId,
      sample_rate: 16000,  // Default sample rate
      channels: 1          // Default channels
    };
    
    // Log request size for debugging
    console.log(`DEBUG: Sending transcription request with ${Math.round(formattedAudioData.length/1024)}KB audio data`);
    
    // Add job role data if provided
    if (jobRoleData) {
      requestBody.job_role = jobRoleData.role_name;
      requestBody.seniority_level = jobRoleData.seniority_level;
      requestBody.required_skills = jobRoleData.required_skills;
      requestBody.job_description = jobRoleData.description;
    }
    
    console.log('DEBUG: Sending audio transcription request...');
    
    // Create a custom config for the axios request with longer timeout
    const requestConfig = {
      timeout: 60000, // 60 seconds for audio processing
      headers: {
        'Content-Type': 'application/json',
      }
    };
    
    try {
      const response = await api.post('/audio/transcribe', requestBody, requestConfig);
      
      // Validate response
      if (!response.data || !response.data.transcription) {
        console.error('DEBUG: Invalid response structure:', response.data);
        throw new Error('Invalid response from transcription service');
      }
      
      console.log('DEBUG: Transcription successful:', response.data.transcription);
      return response.data;
    } catch (requestError) {
      console.error('DEBUG: Transcription request failed:', requestError);
      
      // Capture response data if available
      if (requestError.response) {
        console.error('DEBUG: Server response:', {
          status: requestError.response.status,
          data: requestError.response.data
        });
      }
      
      throw requestError;
    }
  } catch (error) {
    // Special handling for 501 Not Implemented - voice processing not available
    if (error.response && error.response.status === 501) {
      console.error('DEBUG: Voice processing not available (501)');
      const enhancedError = new Error('Voice processing is not available on this server');
      enhancedError.isVoiceUnavailable = true;
      throw enhancedError;
    }
    
    // Special handling for 422 Unprocessable Entity - no speech detected
    if (error.response && error.response.status === 422) {
      console.error('DEBUG: No speech detected or transcription failed (422)');
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

/**
 * Test audio transcription with a synthetic test tone
 * This function creates a test audio file with a clear beep sound and attempts to transcribe it
 * Useful for debugging if the transcription service is working properly
 * @returns {Promise} Promise with test results
 */
export const testAudioTranscription = async () => {
  console.log('DEBUG: Starting audio transcription test');
  
  try {
    // Create a test audio context
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const oscillator = audioContext.createOscillator();
    const gainNode = audioContext.createGain();
    const destination = audioContext.createMediaStreamDestination();
    
    // Set up a clear beep tone
    oscillator.type = 'sine';
    oscillator.frequency.setValueAtTime(440, audioContext.currentTime); // A4 note
    gainNode.gain.setValueAtTime(0.8, audioContext.currentTime); // Loud enough to hear
    
    // Connect the nodes
    oscillator.connect(gainNode);
    gainNode.connect(destination);
    
    // Start the oscillator
    oscillator.start();
    
    console.log('DEBUG: Created test tone generator');
    
    // Create a media recorder
    const mediaRecorder = new MediaRecorder(destination.stream, {
      mimeType: 'audio/webm',
      audioBitsPerSecond: 128000
    });
    
    const chunks = [];
    mediaRecorder.ondataavailable = (e) => {
      console.log('DEBUG: Test audio chunk received, size:', e.data.size);
      chunks.push(e.data);
    };
    
    // Record for 3 seconds
    console.log('DEBUG: Recording test audio for 3 seconds');
    
    await new Promise((resolve) => {
      mediaRecorder.onstop = resolve;
      mediaRecorder.start();
      
      // Generate a sequence of tones for better recognition
      setTimeout(() => oscillator.frequency.setValueAtTime(523.25, audioContext.currentTime), 1000); // C5
      setTimeout(() => oscillator.frequency.setValueAtTime(659.25, audioContext.currentTime), 2000); // E5
      
      setTimeout(() => {
        oscillator.stop();
        mediaRecorder.stop();
        console.log('DEBUG: Test audio recording completed');
      }, 3000);
    });
    
    // Create a blob from the chunks
    const blob = new Blob(chunks, { type: 'audio/webm' });
    console.log('DEBUG: Test audio blob created, size:', blob.size, 'bytes');
    
    // Convert the blob to base64
    const base64 = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(blob);
    });
    
    console.log('DEBUG: Test audio converted to base64, length:', base64.length);
    
    // Create a temporary audio element for debugging
    const audio = new Audio(URL.createObjectURL(blob));
    console.log('DEBUG: Test audio available at temporary URL:', audio.src);
    
    // Try to transcribe the test audio
    console.log('DEBUG: Sending test audio for transcription');
    const userId = 'test-user-' + Date.now();
    
    try {
      const result = await transcribeAndRespond(base64, userId);
      console.log('DEBUG: Test transcription successful!', result);
      return {
        success: true,
        transcription: result.transcription,
        audioSize: blob.size,
        base64Length: base64.length
      };
    } catch (transcribeError) {
      console.error('DEBUG: Test transcription failed', transcribeError);
      return {
        success: false,
        error: transcribeError.message,
        errorData: transcribeError.serverData,
        audioSize: blob.size,
        base64Length: base64.length
      };
    } finally {
      // Clean up
      audioContext.close();
    }
  } catch (error) {
    console.error('DEBUG: Error creating test audio:', error);
    return {
      success: false,
      error: error.message,
      stage: 'audio_creation'
    };
  }
};

/**
 * Generate a coding problem for the interview
 * @param {string} jobRole - Job role for which to generate the problem
 * @param {string} difficulty - Difficulty level (easy, medium, hard)
 * @param {Array} skills - Array of skills to target
 * @returns {Promise} Promise with response data containing the generated problem
 */
export const generateCodingProblem = async (jobRole, difficulty = 'medium', skills = []) => {
  try {
    const requestBody = {
      job_role: jobRole,
      difficulty: difficulty,
      skills: skills,
      problem_type: 'algorithmic' // Default to algorithmic problems
    };
    
    const response = await api.post('/coding/generate-problem', requestBody);
    return response.data;
  } catch (error) {
    return handleApiError(error, 'Failed to generate coding problem');
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
  getJobRoles,
  testAudioTranscription,
  generateCodingProblem
};

export default interviewService; 