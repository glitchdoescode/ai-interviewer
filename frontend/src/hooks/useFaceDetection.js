import { useState, useEffect, useCallback } from 'react';

/**
 * Temporary mock implementation of face detection while mediapipe is unavailable
 */
export const useFaceDetection = (videoRef, isActive) => {
  const [isLoading, setIsLoading] = useState(false);
  const [isReady, setIsReady] = useState(true);
  const [error, setError] = useState(null);
  const [detectionResults, setDetectionResults] = useState([]);
  const [detectionStats, setDetectionStats] = useState({
    faceCount: 0,
    confidence: 0,
    lastDetectionTime: null,
    consecutiveNoFaceFrames: 0,
    consecutiveMultiFaceFrames: 0,
  });
  const [events, setEvents] = useState([]);

  // Mock implementation that simulates face detection
  const generateEvent = useCallback((type, data = {}) => {
    const event = {
      id: Date.now().toString(),
      type,
      timestamp: Date.now(),
      data: { ...data, isMocked: true }
    };
    setEvents(prev => [...prev, event]);
    return event;
  }, []);

  useEffect(() => {
    if (isActive) {
      generateEvent('mock_detection_enabled', { message: 'Face detection temporarily using mock implementation' });
      // Simulate face detection after a delay
      const timer = setTimeout(() => {
        setDetectionStats({
          faceCount: 1,
          confidence: 0.95,
          lastDetectionTime: Date.now(),
          consecutiveNoFaceFrames: 0,
          consecutiveMultiFaceFrames: 0,
        });
        setDetectionResults([{
          score: 0.95,
          box: { x: 100, y: 100, width: 200, height: 200 }
        }]);
        generateEvent('face_detected', {
          faceCount: 1,
          confidence: 0.95
        });
      }, 1000);
      return () => clearTimeout(timer);
    } else {
      setDetectionStats({
        faceCount: 0,
        confidence: 0,
        lastDetectionTime: null,
        consecutiveNoFaceFrames: 0,
        consecutiveMultiFaceFrames: 0,
      });
      setDetectionResults([]);
    }
  }, [isActive, generateEvent]);

  const startDetection = useCallback(async () => {
    setIsLoading(true);
    await new Promise(resolve => setTimeout(resolve, 500));
    setIsLoading(false);
    generateEvent('detection_started');
    return true;
  }, [generateEvent]);

  const stopDetection = useCallback(async () => {
    setDetectionResults([]);
    setDetectionStats({
      faceCount: 0,
      confidence: 0,
      lastDetectionTime: null,
      consecutiveNoFaceFrames: 0,
      consecutiveMultiFaceFrames: 0,
    });
    generateEvent('detection_stopped');
  }, [generateEvent]);

  const detectFaces = useCallback(async () => {
    const mockResults = [{
      score: 0.95,
      box: { x: 100, y: 100, width: 200, height: 200 }
    }];
    setDetectionResults(mockResults);
    setDetectionStats(prev => ({
      ...prev,
      faceCount: 1,
      confidence: 0.95,
      lastDetectionTime: Date.now()
    }));
    return mockResults;
  }, []);

  return {
    // State
    isLoading,
    isReady,
    error,
    detectionResults,
    detectionStats,
    events,
    
    // Functions
    startDetection,
    stopDetection,
    detectFaces,
    clearEvents: () => setEvents([]),
    generateEvent,
    
    // Config
    isSupported: true,
    detectionConfig: {
      confidenceThreshold: 0.5,
      detectionInterval: 200,
      noFaceThreshold: 5,
      multiFaceThreshold: 3,
      faceAbsenceTimeout: 3000,
    }
  };
}; 