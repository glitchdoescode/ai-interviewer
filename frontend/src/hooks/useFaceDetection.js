import { useState, useEffect, useRef, useCallback } from 'react';
import * as tf from '@tensorflow/tfjs';
import * as faceDetection from '@tensorflow-models/face-detection';

/**
 * Custom hook for real-time face detection using TensorFlow.js
 * Provides face detection, tracking, and event generation for proctoring
 */
export const useFaceDetection = (videoRef, isActive) => {
  const [isLoading, setIsLoading] = useState(false);
  const [isReady, setIsReady] = useState(false);
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

  const detectorRef = useRef(null);
  const animationFrameRef = useRef(null);
  const lastEventRef = useRef({});
  const statsRef = useRef({
    faceCount: 0,
    confidence: 0,
    lastDetectionTime: null,
    consecutiveNoFaceFrames: 0,
    consecutiveMultiFaceFrames: 0,
  });

  // Constants for detection thresholds
  const DETECTION_CONFIG = {
    model: faceDetection.SupportedModels.MediaPipeFaceDetector,
    detectorConfig: {
      runtime: 'tfjs',
      refineLandmarks: false,
      maxFaces: 5,
    },
    confidenceThreshold: 0.5,
    detectionInterval: 200, // ms between detections
    noFaceThreshold: 5, // consecutive frames to trigger no-face event
    multiFaceThreshold: 3, // consecutive frames to trigger multi-face event
    faceAbsenceTimeout: 3000, // ms without face to trigger absence event
  };

  /**
   * Initialize TensorFlow.js and face detection model
   */
  const initializeDetector = useCallback(async () => {
    if (detectorRef.current) return detectorRef.current;
    
    setIsLoading(true);
    setError(null);

    try {
      // Initialize TensorFlow.js backend
      await tf.ready();
      console.log('TensorFlow.js backend:', tf.getBackend());
      
      // Create face detector
      const detector = await faceDetection.createDetector(
        DETECTION_CONFIG.model,
        DETECTION_CONFIG.detectorConfig
      );
      
      detectorRef.current = detector;
      setIsReady(true);
      
      console.log('Face detection model loaded successfully');
      return detector;
    } catch (err) {
      console.error('Error initializing face detector:', err);
      setError('Failed to load face detection model');
      return null;
    } finally {
      setIsLoading(false);
    }
  }, []);

  /**
   * Generate proctoring event
   */
  const generateEvent = useCallback((type, data = {}) => {
    const now = new Date();
    const event = {
      id: `${type}_${now.getTime()}`,
      type,
      timestamp: now.toISOString(),
      severity: data.severity || 'medium',
      confidence: data.confidence || 0,
      description: data.description || '',
      metadata: {
        faceCount: statsRef.current.faceCount,
        detectionConfidence: statsRef.current.confidence,
        consecutiveFrames: data.consecutiveFrames || 0,
        ...data.metadata,
      },
    };

    // Avoid duplicate events of the same type within a short time
    const lastEvent = lastEventRef.current[type];
    if (lastEvent && (now.getTime() - lastEvent.timestamp) < 1000) {
      return null;
    }

    lastEventRef.current[type] = { timestamp: now.getTime() };
    
    setEvents(prev => [...prev.slice(-50), event]); // Keep last 50 events
    return event;
  }, []);

  /**
   * Process detection results and generate events
   */
  const processDetectionResults = useCallback((faces) => {
    const now = new Date();
    const faceCount = faces.length;
    const confidence = faces.length > 0 
      ? faces.reduce((sum, face) => sum + (face.score || 0), 0) / faces.length 
      : 0;

    // Update stats
    const newStats = {
      faceCount,
      confidence,
      lastDetectionTime: now,
      consecutiveNoFaceFrames: faceCount === 0 
        ? statsRef.current.consecutiveNoFaceFrames + 1 
        : 0,
      consecutiveMultiFaceFrames: faceCount > 1 
        ? statsRef.current.consecutiveMultiFaceFrames + 1 
        : 0,
    };

    statsRef.current = newStats;
    setDetectionStats(newStats);

    // Generate events based on detection results
    if (faceCount === 0) {
      // No face detected
      if (newStats.consecutiveNoFaceFrames >= DETECTION_CONFIG.noFaceThreshold) {
        generateEvent('no_face_detected', {
          severity: 'high',
          description: 'No face detected in video stream',
          consecutiveFrames: newStats.consecutiveNoFaceFrames,
          metadata: { duration: newStats.consecutiveNoFaceFrames * DETECTION_CONFIG.detectionInterval },
        });
      }
    } else if (faceCount === 1) {
      // Single face detected (normal)
      if (statsRef.current.consecutiveNoFaceFrames > 0 || 
          statsRef.current.consecutiveMultiFaceFrames > 0) {
        generateEvent('face_detected', {
          severity: 'low',
          confidence,
          description: 'Single face detected (normal)',
          metadata: { faceId: faces[0].id || 'unknown' },
        });
      }
    } else {
      // Multiple faces detected
      if (newStats.consecutiveMultiFaceFrames >= DETECTION_CONFIG.multiFaceThreshold) {
        generateEvent('multiple_faces_detected', {
          severity: 'high',
          confidence,
          description: `${faceCount} faces detected in video stream`,
          consecutiveFrames: newStats.consecutiveMultiFaceFrames,
          metadata: { 
            detectedFaces: faces.map(face => ({
              id: face.id || 'unknown',
              score: face.score,
              boundingBox: face.box,
            }))
          },
        });
      }
    }

    // Check for face absence timeout
    if (statsRef.current.lastDetectionTime) {
      const timeSinceLastFace = now.getTime() - statsRef.current.lastDetectionTime.getTime();
      if (faceCount === 0 && timeSinceLastFace > DETECTION_CONFIG.faceAbsenceTimeout) {
        generateEvent('face_absence_timeout', {
          severity: 'critical',
          description: 'Face absent for extended period',
          metadata: { absenceDuration: timeSinceLastFace },
        });
      }
    }

    // Low confidence detection
    if (faceCount > 0 && confidence < DETECTION_CONFIG.confidenceThreshold) {
      generateEvent('low_confidence_detection', {
        severity: 'medium',
        confidence,
        description: 'Face detection with low confidence',
        metadata: { threshold: DETECTION_CONFIG.confidenceThreshold },
      });
    }

    return newStats;
  }, [generateEvent]);

  /**
   * Perform face detection on current video frame
   */
  const detectFaces = useCallback(async () => {
    if (!detectorRef.current || !videoRef?.current || !isActive) {
      return [];
    }

    try {
      const video = videoRef.current;
      
      // Check if video is ready
      if (video.readyState < 2) {
        return [];
      }

      // Perform face detection
      const faces = await detectorRef.current.estimateFaces(video);
      
      // Filter faces by confidence threshold
      const validFaces = faces.filter(
        face => (face.score || 0) >= DETECTION_CONFIG.confidenceThreshold
      );

      setDetectionResults(validFaces);
      processDetectionResults(validFaces);
      
      return validFaces;
    } catch (err) {
      console.error('Error during face detection:', err);
      setError('Face detection failed');
      return [];
    }
  }, [videoRef, isActive, processDetectionResults]);

  /**
   * Start continuous face detection
   */
  const startDetection = useCallback(async () => {
    if (!detectorRef.current) {
      await initializeDetector();
    }

    const detectLoop = async () => {
      if (isActive && detectorRef.current) {
        await detectFaces();
        
        // Schedule next detection
        animationFrameRef.current = setTimeout(() => {
          detectLoop();
        }, DETECTION_CONFIG.detectionInterval);
      }
    };

    detectLoop();
  }, [isActive, initializeDetector, detectFaces]);

  /**
   * Stop face detection
   */
  const stopDetection = useCallback(() => {
    if (animationFrameRef.current) {
      clearTimeout(animationFrameRef.current);
      animationFrameRef.current = null;
    }
    
    setDetectionResults([]);
    setDetectionStats({
      faceCount: 0,
      confidence: 0,
      lastDetectionTime: null,
      consecutiveNoFaceFrames: 0,
      consecutiveMultiFaceFrames: 0,
    });
    
    statsRef.current = {
      faceCount: 0,
      confidence: 0,
      lastDetectionTime: null,
      consecutiveNoFaceFrames: 0,
      consecutiveMultiFaceFrames: 0,
    };
  }, []);

  /**
   * Clear events history
   */
  const clearEvents = useCallback(() => {
    setEvents([]);
    lastEventRef.current = {};
  }, []);

  // Initialize detector when component mounts
  useEffect(() => {
    initializeDetector();
    
    return () => {
      stopDetection();
    };
  }, [initializeDetector, stopDetection]);

  // Start/stop detection based on isActive
  useEffect(() => {
    if (isActive && isReady) {
      startDetection();
    } else {
      stopDetection();
    }

    return () => {
      stopDetection();
    };
  }, [isActive, isReady, startDetection, stopDetection]);

  return {
    // State
    isLoading,
    isReady,
    error,
    detectionResults,
    detectionStats,
    events,
    
    // Actions
    startDetection,
    stopDetection,
    detectFaces,
    clearEvents,
    generateEvent,
    
    // Config
    isSupported: !!(window.tf || window.MediaPipe),
    detectionConfig: DETECTION_CONFIG,
  };
}; 