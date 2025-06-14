import { useState, useEffect, useRef, useCallback, useMemo } from 'react';

/**
 * Temporary mock implementation of face authentication while mediapipe is unavailable
 */
export const useFaceAuthentication = (
  videoRef, 
  isActive, 
  initialSessionId = null, 
  initialPersistedEmbedding = null
) => {
  const [isLoading, setIsLoading] = useState(false);
  const [isReady, setIsReady] = useState(true);
  const [error, setError] = useState(null);
  const [enrollmentStatus, setEnrollmentStatus] = useState('not_enrolled');
  const [authenticationStatus, setAuthenticationStatus] = useState('not_authenticated');
  const [lastAuthenticationTime, setLastAuthenticationTime] = useState(null);
  const [authenticationScore, setAuthenticationScore] = useState(0);
  const [enrollmentEmbedding, setEnrollmentEmbedding] = useState(null);
  const [authenticationEvents, setAuthenticationEvents] = useState([]);
  const [currentEnrollmentAttempt, setCurrentEnrollmentAttempt] = useState(0);

  // Add a counter to ensure unique IDs
  const eventCounter = useRef(0);

  // Mock implementation that simulates enrollment flow
  const generateAuthEvent = useCallback((type, data = {}) => {
    eventCounter.current += 1;
    const event = {
      id: `${Date.now()}-${eventCounter.current}`,
      type,
      timestamp: Date.now(),
      data: { ...data, isMocked: true }
    };
    setAuthenticationEvents(prev => [...prev, event]);
    return event;
  }, []);

  useEffect(() => {
    if (isActive) {
      generateAuthEvent('mock_auth_enabled', { message: 'Face authentication temporarily using mock implementation' });
    }
  }, [isActive, generateAuthEvent]);

  const enrollFace = useCallback(async () => {
    try {
      setIsLoading(true);
      setEnrollmentStatus('enrolling');
      
      // Simulate enrollment process
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      // Simulate successful enrollment
      const mockEmbedding = new Float32Array(128).fill(1);
      setEnrollmentEmbedding(mockEmbedding);
      setEnrollmentStatus('enrolled');
      setAuthenticationStatus('authenticated');
      setAuthenticationScore(0.95);
      setLastAuthenticationTime(Date.now());
      
      generateAuthEvent('enrollment_success', { 
        embedding: mockEmbedding,
        score: 0.95
      });
      
      return {
        success: true,
        embedding: mockEmbedding
      };
    } catch (error) {
      setError(error);
      setEnrollmentStatus('not_enrolled');
      generateAuthEvent('enrollment_failed', { error: error.message });
      throw error;
    } finally {
      setIsLoading(false);
    }
  }, [generateAuthEvent]);

  const resetAuthentication = useCallback(() => {
    setEnrollmentStatus('not_enrolled');
    setAuthenticationStatus('not_authenticated');
    setLastAuthenticationTime(null);
    setAuthenticationScore(0);
    setEnrollmentEmbedding(null);
    setCurrentEnrollmentAttempt(0);
    generateAuthEvent('auth_reset', { message: 'Authentication reset' });
  }, [generateAuthEvent]);

  return {
    // State
    isLoading,
    isReady,
    error,
    enrollmentStatus,
    authenticationStatus,
    lastAuthenticationTime,
    authenticationScore,
    enrollmentEmbedding,
    authenticationEvents,
    currentEnrollmentAttempt,
    
    // Functions
    enrollFace,
    resetAuthentication,
    startAuthentication: () => Promise.resolve(true),
    stopAuthentication: () => Promise.resolve(),
    generateAuthEvent,
    
    // Configuration
    isSupported: true,
    authConfig: {
      authenticationInterval: 15 * 60 * 1000,
      enrollmentThreshold: 0.85,
      authenticationThreshold: 0.75,
      maxEnrollmentAttempts: 3
    }
  };
};