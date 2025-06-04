import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import * as tf from '@tensorflow/tfjs';
import * as faceDetection from '@tensorflow-models/face-detection';

/**
 * Custom hook for face authentication with periodic re-authentication
 * and impersonation detection using face embeddings
 */
export const useFaceAuthentication = (
  videoRef, 
  isActive, 
  initialSessionId = null, 
  initialPersistedEmbedding = null
) => {
  const [isLoading, setIsLoading] = useState(false);
  const [isReady, setIsReady] = useState(false);
  const [error, setError] = useState(null);
  const [enrollmentStatus, setEnrollmentStatus] = useState('not_enrolled'); // not_enrolled, enrolling, enrolled
  const [authenticationStatus, setAuthenticationStatus] = useState('pending'); // pending, authenticated, failed
  const [lastAuthenticationTime, setLastAuthenticationTime] = useState(null);
  const [authenticationScore, setAuthenticationScore] = useState(0);
  const [enrollmentEmbedding, setEnrollmentEmbedding] = useState(null);
  const [authenticationEvents, setAuthenticationEvents] = useState([]);
  const [currentEnrollmentAttempt, setCurrentEnrollmentAttempt] = useState(0);

  // Refs for internal state
  const detectorRef = useRef(null);
  const faceNetModelRef = useRef(null); // If using a separate model for embeddings
  const authIntervalRef = useRef(null);
  const enrollmentAttemptsRef = useRef(0);
  const recentEventsRef = useRef(new Map()); 
  const eventCounterRef = useRef(0); 
  const initializationInProgressRef = useRef(false);
  const currentSessionIdRef = useRef(initialSessionId); // Store sessionId
  
  // Real-time verification refs
  const realTimeMonitoringRef = useRef(null);
  const slidingWindowRef = useRef([]);
  const embeddingCacheRef = useRef(new Map()); // Cache for recent embeddings
  const lastFailureTimeRef = useRef(null);
  const consecutiveFailuresRef = useRef(0);

  // Phase 3: Advanced Impersonation Detection refs
  const faceHistoryRef = useRef([]); // Track face changes over time
  const multipleFaceTrackingRef = useRef(new Map()); // Track multiple faces
  const behaviorPatternRef = useRef({
    authenticationTimes: [],
    failurePatterns: [],
    locationChanges: [],
    deviceChanges: []
  });
  const evidenceCaptureRef = useRef([]);
  const impersonationAlertsRef = useRef([]);
  const escalationStatusRef = useRef('normal'); // normal, warning, critical

  // Phase 0: Constants and Configuration
  const LOG_PREFIX = '[useFaceAuthentication]'; // Standardized log prefix

  // --- GROUP 1: CORE UTILITIES & CONFIG (LOWEST LEVEL) ---
  const AUTH_CONFIG = useMemo(() => ({
    authenticationInterval: 15 * 60 * 1000,
    realTimeVerificationInterval: 5000,
    enrollmentThreshold: 0.85,
    authenticationThreshold: 0.75,
    impersonationThreshold: 0.6,
    multipleFaceThreshold: 0.7,
    appearanceChangeThreshold: 0.65,
    temporalAnalysisThreshold: 0.8,
    slidingWindowSize: 5,
    maxConsecutiveFailures: 3,
    maxTrackedFaces: 3,
    faceHistorySize: 50,
    temporalAnalysisWindow: 5 * 60 * 1000,
    behaviorAnalysisWindow: 5 * 60 * 1000,
    evidenceRetentionTime: 60 * 60 * 1000,
    maxEvidenceItems: 100,
    maxEnrollmentAttempts: 3,
    embeddingCacheTTL: 5 * 60 * 1000,
    embeddingCacheSize: 20,
    realTimeInterval: 30 * 1000,
    slidingWindowThreshold: 0.6,
    immediateAlertThreshold: 0.3,
    eventDeduplicationWindow: 2000,
    embeddingSize: 128,
    minFaceConfidence: 0.5, 
    minFaceSize: 50, 
    escalationThresholds: {
      warning: 3,
      critical: 5,
      timeWindow: 10 * 60 * 1000
    }
  }), []);

  const generateAuthEvent = useCallback((type, data = {}) => {
    const now = Date.now();
    eventCounterRef.current += 1;
    const eventId = `${type}_${now}_${eventCounterRef.current}`;
    const recentEventKey = `${type}_${JSON.stringify(data)}`;
    const lastEventTime = recentEventsRef.current.get(recentEventKey);
    
    if (lastEventTime && (now - lastEventTime) < AUTH_CONFIG.eventDeduplicationWindow) {
      return null;
    }
    recentEventsRef.current.set(recentEventKey, now);
    const cutoffTime = now - (10 * 60 * 1000);
    for (const [key, time] of recentEventsRef.current.entries()) {
      if (time < cutoffTime) {
        recentEventsRef.current.delete(key);
      }
    }
    const event = { id: eventId, type, timestamp: new Date().toISOString(), sessionId: currentSessionIdRef.current, data };
    setAuthenticationEvents(prev => {
      const existingEvent = prev.find(e => 
        e.type === type && 
        Math.abs(new Date(e.timestamp).getTime() - now) < 1000 &&
        JSON.stringify(e.data) === JSON.stringify(data)
      );
      if (existingEvent) return prev;
      return [...prev.slice(-20), event];
    });
    return event;
  }, [AUTH_CONFIG.eventDeduplicationWindow]);

  const extractSimplifiedEmbedding = useCallback(async (faceData) => {
    try {
      const { keypoints, box } = faceData;
      if (!keypoints || keypoints.length === 0) throw new Error('No facial keypoints detected');
      const embedding = new Float32Array(AUTH_CONFIG.embeddingSize);
      const features = [];
      keypoints.forEach((point, index) => {
        if (index < 32) {
          features.push((point.x - box.xMin) / box.width);
          features.push((point.y - box.yMin) / box.height);
        }
      });
      if (keypoints.length >= 6) {
        const eyeDistance = Math.sqrt(Math.pow(keypoints[1].x - keypoints[0].x, 2) + Math.pow(keypoints[1].y - keypoints[0].y, 2));
        features.push(eyeDistance / box.width);
        if (keypoints[2]) {
          const leftEyeToNose = Math.sqrt(Math.pow(keypoints[2].x - keypoints[0].x, 2) + Math.pow(keypoints[2].y - keypoints[0].y, 2));
          features.push(leftEyeToNose / box.width);
        }
        if (keypoints[3]) {
          const mouthToEyeRatio = (keypoints[3].y - keypoints[0].y) / box.height;
          features.push(mouthToEyeRatio);
        }
      }
      for (let i = 0; i < AUTH_CONFIG.embeddingSize; i++) embedding[i] = features[i] || 0;
      const norm = Math.sqrt(embedding.reduce((sum, val) => sum + val * val, 0));
      if (norm > 0) for (let i = 0; i < embedding.length; i++) embedding[i] /= norm;
      return embedding;
    } catch (err) {
      console.error('Error extracting face embedding:', err);
      throw err;
    }
  }, [AUTH_CONFIG.embeddingSize]);

  const calculateSimilarity = useCallback((embedding1, embedding2) => {
    if (!embedding1 || !embedding2 || embedding1.length !== embedding2.length) return 0;
    let dotProduct = 0, norm1 = 0, norm2 = 0;
    for (let i = 0; i < embedding1.length; i++) {
      dotProduct += embedding1[i] * embedding2[i];
      norm1 += embedding1[i] * embedding1[i];
      norm2 += embedding2[i] * embedding2[i];
    }
    const denominator = Math.sqrt(norm1) * Math.sqrt(norm2);
    return denominator === 0 ? 0 : dotProduct / denominator;
  }, []);

  const detectAlternatingPattern = useCallback((events) => {
    if (events.length < 6) return { detected: false, confidence: 0 };
    let alternations = 0;
    for (let i = 1; i < events.length; i++) {
      if (events[i].success !== events[i-1].success) alternations++;
    }
    const alternationRate = alternations / (events.length - 1);
    const detected = alternationRate > 0.6;
    return { detected, confidence: detected ? Math.min(alternationRate, 1.0) : 0 };
  }, []);

  const detectSimilarityDrops = useCallback((events) => {
    if (events.length < 5) return { detected: false, confidence: 0 };
    const similarities = events.map(e => e.similarity);
    let significantDrops = 0;
    for (let i = 1; i < similarities.length; i++) {
      if (similarities[i-1] - similarities[i] > 0.3) significantDrops++;
    }
    const dropRate = significantDrops / (similarities.length - 1);
    const detected = dropRate > 0.3;
    return { detected, confidence: detected ? Math.min(dropRate * 2, 1.0) : 0 };
  }, []);

  const detectTimingIrregularities = useCallback((events) => {
    if (events.length < 5) return { detected: false, confidence: 0 };
    const intervals = [];
    for (let i = 1; i < events.length; i++) intervals.push(events[i].timestamp - events[i-1].timestamp);
    const avgInterval = intervals.reduce((sum, interval) => sum + interval, 0) / intervals.length;
    const deviations = intervals.map(interval => Math.abs(interval - avgInterval));
    const avgDeviation = deviations.reduce((sum, dev) => sum + dev, 0) / deviations.length;
    const coefficientOfVariation = avgInterval > 0 ? avgDeviation / avgInterval : 0;
    const detected = coefficientOfVariation > 0.5;
    return { detected, confidence: detected ? Math.min(coefficientOfVariation, 1.0) : 0 };
  }, []);

  // --- GROUP 2: MID-LEVEL UTILITIES & INITIALIZATION ---
  const initializeModels = useCallback(async () => {
    console.log(`${LOG_PREFIX} initializeModels CALLED. isLoading: ${isLoading}, isReady: ${isReady}, initializationInProgressRef.current: ${initializationInProgressRef.current}, detectorRef.current: ${detectorRef.current ? 'LOADED' : 'NULL'}, videoRef.current: ${videoRef.current ? 'AVAILABLE' : 'MISSING'}`);
    if (initializationInProgressRef.current || (detectorRef.current && (!initialPersistedEmbedding || enrollmentStatus === 'enrolled'))) {
      console.log(`${LOG_PREFIX} Models already loading, loaded, or enrollment resumed. Aborting initialization.`);
      if (initialPersistedEmbedding && enrollmentStatus !== 'enrolled') {
         // Allow re-init if embedding provided but not yet set
      } else {
      return;
    }
    }
    initializationInProgressRef.current = true;
    setIsLoading(true);
    setError(null);
    console.log(`${LOG_PREFIX} initializeModels STARTING. tf.getBackend(): ${tf.getBackend()}`);

    try {
      await tf.ready();
      if (tf.getBackend() === 'cpu' && !window.tfjsCpuWarningShown) {
        console.warn(`${LOG_PREFIX} TensorFlow.js is using CPU backend. Performance may be suboptimal.`); window.tfjsCpuWarningShown = true; 
      }
      console.log(`${LOG_PREFIX} TensorFlow backend ready.`);

      const model = faceDetection.SupportedModels.MediaPipeFaceDetector;
      const detectorConfig = { runtime: 'tfjs', modelType: 'short', maxFaces: 1, refineLandmarks: false };
      detectorRef.current = await faceDetection.createDetector(model, detectorConfig);
      
      console.log(`${LOG_PREFIX} Face detector model loaded successfully.`);
      
      if (initialPersistedEmbedding) {
        console.log(`${LOG_PREFIX} Initial persisted embedding found. Setting enrollment status to 'enrolled'.`);
        setEnrollmentEmbedding(initialPersistedEmbedding); 
        setEnrollmentStatus('enrolled');
        generateAuthEvent('enrollment_resumed', { source: 'initial_props' });
      } else {
        setEnrollmentStatus('not_enrolled');
        console.log(`${LOG_PREFIX} No initial embedding. System ready for new enrollment.`);
        generateAuthEvent('system_ready', { message: 'Face detection models initialized.'});
      }
      setIsReady(true);
      
    } catch (err) {
      let detailedError = err.message;
      if (err.message?.includes("Failed to fetch")) detailedError = "Network error: Failed to load model files. Check network and model paths.";
      else if (err.message?.includes("TFLiteWebModelRunner")) detailedError = "MediaPipe model loading issue. Possible conflict with ad-blocker or network policy.";
      console.error(`${LOG_PREFIX} Error loading models:`, detailedError, err.stack);
      setError(new Error(`Initialization failed: ${detailedError}`));
      generateAuthEvent('initialization_error', { error: detailedError, stack: err.stack });
      setIsReady(false); 
    } finally {
      setIsLoading(false);
      initializationInProgressRef.current = false;
      console.log(`${LOG_PREFIX} initializeModels FINISHED. isReady: ${isReady}, isLoading: ${isLoading}, detectorRef.current: ${detectorRef.current ? 'LOADED' : 'NULL'}`);
    }
  }, [initialPersistedEmbedding, generateAuthEvent, videoRef]);

  const createAlternativeDetector = useCallback(async () => {
    const configurations = [
      { name: 'full_landmarks', config: { runtime: 'tfjs', modelType: 'full', maxFaces: 1, refineLandmarks: true }},{ name: 'short_no_landmarks', config: { runtime: 'tfjs', modelType: 'short', maxFaces: 1, refineLandmarks: false }},{ name: 'basic', config: { runtime: 'tfjs', maxFaces: 1 }}
    ];
    for (const { name, config } of configurations) {
      try {
        const detector = await faceDetection.createDetector(faceDetection.SupportedModels.MediaPipeFaceDetector, config);
        if (videoRef?.current) {
          const testFaces = await detector.estimateFaces(videoRef.current);
          if (testFaces.length > 0) {
            const face = testFaces[0];
            if ((face.box && (face.box.width > 0 || face.box.height > 0)) || (face.keypoints && face.keypoints.some(kp => kp.x !== 0 || kp.y !== 0))) return detector;
          }
        }
      } catch (err) { console.log(`Alt config ${name} failed:`, err.message); }
    }
    throw new Error('All MediaPipe configurations failed');
  }, [videoRef]);
  
  const runDiagnostics = useCallback(async () => {
    if (!videoRef?.current) { console.log('DIAG: No video'); return; }
    const video = videoRef.current;
    console.log('DIAG: Video state:', { readyState: video.readyState, w: video.videoWidth, h: video.videoHeight, paused: video.paused, srcObj: !!video.srcObject });
    console.log('DIAG: TFJS:', { ver: tf.version.tfjs, backend: tf.getBackend(), mem: tf.memory() });
    if (detectorRef.current) {
      try {
        const faces = await detectorRef.current.estimateFaces(video);
        console.log('DIAG: Detector results:', { count: faces.length, faces: faces.map(f => ({ box: !!f.box, boxDim: f.box ? `${f.box.width}x${f.box.height}` : 'N/A', kp: f.keypoints?.length || 0 }))});
      } catch (err) { console.log('DIAG: Detector test failed:', err.message); }
    }
  }, [videoRef]);

  const validateFaceQuality = useCallback((face) => {
    const { box, keypoints } = face;
    const score = face.score || face.confidence || (box && box.probability) || 1.0;
    if (score < AUTH_CONFIG.minFaceConfidence) return { valid: false, reason: 'Low detection confidence' };
    let faceSize = 0;
    if (box && box.width && box.height) faceSize = Math.min(box.width, box.height);
    else if (box && box.xMax && box.xMin && box.yMax && box.yMin) faceSize = Math.min(box.xMax - box.xMin, box.yMax - box.yMin);
    if (faceSize < AUTH_CONFIG.minFaceSize) return { valid: false, reason: `Face too small (${faceSize}px)` };
    if (keypoints && keypoints.length >= 2) {
      const eyeLevel = Math.abs(keypoints[0].y - keypoints[1].y);
      const eyeDistance = Math.abs(keypoints[0].x - keypoints[1].x);
      if (eyeDistance === 0 || eyeLevel / eyeDistance > 0.3) return { valid: false, reason: 'Face not sufficiently frontal' };
      }
    return { valid: true };
  }, [AUTH_CONFIG.minFaceConfidence, AUTH_CONFIG.minFaceSize]);

  const validateVideoElement = useCallback((video) => {
    if (!video) return { valid: false, reason: 'No video element' };
    if (video.readyState < 2) return { valid: false, reason: 'Video not ready' };
    if (video.videoWidth === 0 || video.videoHeight === 0) return { valid: false, reason: 'Video has no dimensions' };
    if (video.paused) return { valid: false, reason: 'Video is paused' };
    return { valid: true };
  }, []);

  /**
   * Try canvas-based face detection as a workaround for MediaPipe coordinate issues
   */
  const detectFaceWithCanvas = useCallback(async (video) => {
    console.log('[detectFaceWithCanvas] Attempting canvas-based detection...');
    
    try {
      // Create a temporary canvas
      const canvas = document.createElement('canvas');
      const ctx = canvas.getContext('2d');
      
      // Set canvas dimensions to match video
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      
      console.log('[detectFaceWithCanvas] Canvas dimensions:', {
        width: canvas.width,
        height: canvas.height,
        videoWidth: video.videoWidth,
        videoHeight: video.videoHeight
      });
      
      // Draw current video frame to canvas
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      
      // Try face detection on canvas
      const faces = await detectorRef.current.estimateFaces(canvas);
      console.log('[detectFaceWithCanvas] Canvas-based detection found', faces.length, 'faces');
      
      if (faces.length > 0) {
        const face = faces[0];
        console.log('[detectFaceWithCanvas] Canvas face data:', JSON.stringify(face, null, 2));
        
        // Check if canvas method returns valid data
        const hasValidBox = face.box && (face.box.width > 0 || face.box.height > 0);
        const hasValidKeypoints = face.keypoints && face.keypoints.some(kp => kp.x !== 0 || kp.y !== 0);
        
        if (hasValidBox || hasValidKeypoints) {
          console.log('[detectFaceWithCanvas] Canvas method returned valid data!');
          return faces;
        }
      }
      
      console.log('[detectFaceWithCanvas] Canvas method also returned invalid data');
      return [];
    } catch (err) {
      console.error('[detectFaceWithCanvas] Canvas detection failed:', err);
      return [];
    }
  }, [detectorRef]); // Added detectorRef dependency

  const waitForVideoReady = useCallback(async (maxAttempts = 5, attemptInterval = 750) => {
    if (!videoRef?.current) {
      console.error(`${LOG_PREFIX} waitForVideoReady: No video element available.`);
      throw new Error('No video element available');
    }
    const video = videoRef.current;
    console.log(`${LOG_PREFIX} waitForVideoReady: Initial video state - readyState: ${video.readyState}, width: ${video.videoWidth}, height: ${video.videoHeight}, paused: ${video.paused}, srcObject: ${!!video.srcObject}`);

    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      const isMediaReady = video.readyState >= 2; // HAVE_CURRENT_DATA or higher
      const hasDimensions = video.videoWidth > 0 && video.videoHeight > 0;
      const isPlaying = !video.paused;

      if (isMediaReady && hasDimensions && isPlaying) {
        console.log(`${LOG_PREFIX} waitForVideoReady: Video became ready on attempt ${attempt + 1}.`);
        return true;
      }
      
      console.warn(`${LOG_PREFIX} waitForVideoReady: Attempt ${attempt + 1}/${maxAttempts} failed. Conditions - isMediaReady: ${isMediaReady} (state: ${video.readyState}), hasDimensions: ${hasDimensions} (w:${video.videoWidth},h:${video.videoHeight}), isPlaying: ${isPlaying}`);
      
      if (video.srcObject && video.paused) {
        console.log(`${LOG_PREFIX} waitForVideoReady: Attempting to play video on attempt ${attempt + 1}.`);
        try {
          await video.play();
          console.log(`${LOG_PREFIX} waitForVideoReady: video.play() promise resolved on attempt ${attempt + 1}.`);
          // Give a brief moment for the state to update after play()
          await new Promise(resolve => setTimeout(resolve, 100)); 
        } catch (e) {
          console.error(`${LOG_PREFIX} waitForVideoReady: Error during video.play() on attempt ${attempt + 1}:`, e);
          // If play fails, it's a significant issue.
          // We will let the loop continue to see if it recovers, but log the error.
        }
      }
      
      if (attempt < maxAttempts - 1) { // Don't wait after the last attempt
        await new Promise(resolve => setTimeout(resolve, attemptInterval));
      }
    }
    
    const finalReason = `readyState: ${video.readyState} (expected >=2), videoWidth: ${video.videoWidth} (expected >0), videoHeight: ${video.videoHeight} (expected >0), paused: ${video.paused} (expected false)`;
    console.error(`${LOG_PREFIX} waitForVideoReady: Video failed to become ready after ${maxAttempts} attempts. Final conditions: ${finalReason}`);
    throw new Error(`Video failed to become ready. Details: ${finalReason}`);
  }, [videoRef]);

  /**
   * Enhanced face detection with multiple fallback strategies
   */
  const detectBestFace = useCallback(async () => {
    console.log('[detectBestFace] Starting face detection...');
    console.log('[detectBestFace] Status check:', {
      detector: !!detectorRef.current,
      videoRef: !!videoRef?.current,
      isActive,
      videoReadyState: videoRef?.current?.readyState
    });
    
    if (!detectorRef.current || !videoRef?.current || !isActive) {
      console.log('[detectBestFace] Missing requirements');
      return null;
    }

    try {
      const video = videoRef.current;
      
      // Validate video element more thoroughly
      const videoValidation = validateVideoElement(video);
      if (!videoValidation.valid) {
        console.log('[detectBestFace] Video validation failed:', videoValidation.reason);
        return { error: videoValidation.reason };
      }
      
      console.log('[detectBestFace] Video validation passed:', {
        dimensions: `${video.videoWidth}x${video.videoHeight}`,
        readyState: video.readyState,
        paused: video.paused,
        currentTime: video.currentTime
      });

      console.log('[detectBestFace] Running face estimation...');
      
      // Strategy 1: Try direct video detection first
      let faces = await detectorRef.current.estimateFaces(video);
      console.log('[detectBestFace] Direct video detection found', faces.length, 'faces');
      
      // Check if direct detection returns valid data
      let hasValidData = false;
      if (faces.length > 0) {
        const face = faces[0];
        const hasValidBox = face.box && (face.box.width > 0 || face.box.height > 0);
        const hasValidKeypoints = face.keypoints && face.keypoints.some(kp => kp.x !== 0 || kp.y !== 0);
        hasValidData = hasValidBox || hasValidKeypoints;
      }
      
      // Strategy 2: If direct detection returns invalid data, try canvas method
      if (!hasValidData && faces.length > 0) {
        console.log('[detectBestFace] Direct detection returned invalid data, trying canvas method...');
        faces = await detectFaceWithCanvas(video);
      }
      
      // Strategy 3: If still no valid data, try alternative detector configurations
      if (faces.length === 0 || !hasValidData) {
        console.log('[detectBestFace] Trying alternative detector configurations...');
        await runDiagnostics();
        
        try {
          const alternativeDetector = await createAlternativeDetector();
          if (alternativeDetector) {
            detectorRef.current = alternativeDetector;
            
            // Try direct detection with alternative detector
            faces = await detectorRef.current.estimateFaces(video);
            console.log('[detectBestFace] Alternative detector (direct) found', faces.length, 'faces');
            
            // If still invalid, try canvas with alternative detector
            if (faces.length > 0) {
              const face = faces[0];
              const hasValidBox = face.box && (face.box.width > 0 || face.box.height > 0);
              const hasValidKeypoints = face.keypoints && face.keypoints.some(kp => kp.x !== 0 || kp.y !== 0);
              
              if (!hasValidBox && !hasValidKeypoints) {
                console.log('[detectBestFace] Alternative detector also invalid, trying canvas...');
                faces = await detectFaceWithCanvas(video);
              }
            }
          }
        } catch (altErr) {
          console.log('[detectBestFace] Alternative detector failed:', altErr.message);
        }
      }
      
      if (faces.length === 0) {
        console.log('[detectBestFace] No face detected after all strategies');
        return { error: 'No face detected' };
      }
      
      if (faces.length > 1) {
        console.log('[detectBestFace] Multiple faces detected:', faces.length);
        return { error: 'Multiple faces detected' };
      }
      
      const face = faces[0];
      console.log('[detectBestFace] Final face data:', JSON.stringify(face, null, 2));
      
      // Final validation: Check if we have any valid data at all
      const hasValidBox = face.box && (face.box.width > 0 || face.box.height > 0);
      const hasValidKeypoints = face.keypoints && face.keypoints.some(kp => kp.x !== 0 || kp.y !== 0);
      
      if (!hasValidBox && !hasValidKeypoints) {
        console.log('[detectBestFace] All detection strategies returned invalid data');
        return { error: 'Face detection returned invalid data after all attempts' };
      }
      
      console.log('[detectBestFace] Face found, validating quality...');
      const qualityCheck = validateFaceQuality(face);
      console.log('[detectBestFace] Quality check result:', qualityCheck);
      
      if (!qualityCheck.valid) {
        console.log('[detectBestFace] Quality check failed:', qualityCheck.reason);
        return { error: qualityCheck.reason };
      }
      
      console.log('[detectBestFace] Face detection successful');
      return { face, video };
    } catch (err) {
      console.error('[detectBestFace] Error detecting face:', err);
      return { error: 'Face detection failed' };
    }
  }, [validateVideoElement, videoRef, isActive, runDiagnostics, createAlternativeDetector, detectFaceWithCanvas, validateFaceQuality, detectorRef]);

  const extractEmbeddingWithCache = useCallback(async (faceData) => {
    try {
      const faceHash = JSON.stringify({ box: faceData.box, keypoints: faceData.keypoints?.slice(0, 6) });
      const now = Date.now();
      if (embeddingCacheRef.current.has(faceHash)) {
        const cached = embeddingCacheRef.current.get(faceHash);
        if (now - cached.timestamp < AUTH_CONFIG.embeddingCacheTTL) return cached.embedding;
        embeddingCacheRef.current.delete(faceHash);
      }
      const embedding = await extractSimplifiedEmbedding(faceData);
      embeddingCacheRef.current.set(faceHash, { embedding, timestamp: now });
      if (embeddingCacheRef.current.size > AUTH_CONFIG.embeddingCacheSize) {
        const entries = Array.from(embeddingCacheRef.current.entries()).sort((a, b) => a[1].timestamp - b[1].timestamp);
        entries.slice(0, entries.length - AUTH_CONFIG.embeddingCacheSize + 1).forEach(([key]) => embeddingCacheRef.current.delete(key));
      }
      return embedding;
    } catch (err) { throw err; }
  }, [extractSimplifiedEmbedding, AUTH_CONFIG.embeddingCacheTTL, AUTH_CONFIG.embeddingCacheSize]);

  const updateSlidingWindow = useCallback((similarity, success) => {
    const entry = { similarity, success, timestamp: Date.now() };
    slidingWindowRef.current.push(entry);
    if (slidingWindowRef.current.length > AUTH_CONFIG.slidingWindowSize) {
      slidingWindowRef.current = slidingWindowRef.current.slice(-AUTH_CONFIG.slidingWindowSize);
    }
    const window = slidingWindowRef.current;
    if (window.length === 0) return { size: 0, successCount: 0, avgSim: 0, successRate: 0, isStable: false };
    const successCount = window.filter(e => e.success).length;
    const avgSim = window.reduce((sum, e) => sum + e.similarity, 0) / window.length;
    const successRate = successCount / window.length;
    return { size: window.length, successCount, avgSim, successRate, isStable: avgSim >= AUTH_CONFIG.slidingWindowThreshold && successRate >= 0.6 };
  }, [AUTH_CONFIG.slidingWindowSize, AUTH_CONFIG.slidingWindowThreshold]);

  const handleAuthenticationFailure = useCallback((similarity, reason) => {
    consecutiveFailuresRef.current += 1;
    lastFailureTimeRef.current = Date.now();
    let severity = 'medium', action = 'retry';
    if (similarity < AUTH_CONFIG.immediateAlertThreshold) { severity = 'critical'; action = 'immediate_alert'; }
    else if (consecutiveFailuresRef.current >= AUTH_CONFIG.maxConsecutiveFailures) { severity = 'high'; action = 'escalate'; }
    generateAuthEvent(action === 'immediate_alert' ? 'critical_authentication_failure' : (action === 'escalate' ? 'authentication_failure_escalation' : 'authentication_failed'), 
      { similarity, reason, consecutiveFailures: consecutiveFailuresRef.current, severity, action });
    return { severity, action, consecutiveFailures: consecutiveFailuresRef.current };
  }, [AUTH_CONFIG.immediateAlertThreshold, AUTH_CONFIG.maxConsecutiveFailures, generateAuthEvent]);

  const handleAuthenticationSuccess = useCallback((similarity, confidence) => {
    consecutiveFailuresRef.current = 0;
    lastFailureTimeRef.current = null;
    generateAuthEvent('authentication_success', { similarity, confidence, method: 'real_time' });
    return { success: true, similarity, confidence };
  }, [generateAuthEvent]);

  // --- GROUP 3: PHASE 3 CORE LOGIC & ALERTING SYSTEM ---
  const calculateCombinedRiskScore = useCallback((similarity, multipleFaces, appearanceAnalysis, behaviorAnalysis) => {
    let riskScore = Math.max(0, (AUTH_CONFIG.authenticationThreshold - similarity) / AUTH_CONFIG.authenticationThreshold) * 0.4;
    if (multipleFaces) riskScore += 0.3;
    if (appearanceAnalysis.suddenChange) riskScore += appearanceAnalysis.changeScore * 0.2;
    if (behaviorAnalysis.suspiciousBehavior) riskScore += behaviorAnalysis.confidence * 0.1;
    return Math.min(riskScore, 1.0);
  }, [AUTH_CONFIG.authenticationThreshold]); 

  const captureEvidence = useCallback(async (evidenceType, data) => {
    const now = Date.now();
    const evidence = { id: `evidence_${now}_${Math.random().toString(36).substr(2, 9)}`, timestamp: now, type: evidenceType, data: { ...data }, severity: data.severity || 'warning' };
    if (videoRef?.current) {
      try {
        const canvas = document.createElement('canvas');
        canvas.width = videoRef.current.videoWidth; canvas.height = videoRef.current.videoHeight;
        canvas.getContext('2d').drawImage(videoRef.current, 0, 0);
        evidence.data.frameCapture = { timestamp: now, width: canvas.width, height: canvas.height, dataUrl: canvas.toDataURL('image/jpeg', 0.8) };
      } catch (err) { console.warn('Could not capture video frame for evidence:', err); }
    }
    evidenceCaptureRef.current.push(evidence);
    evidenceCaptureRef.current = evidenceCaptureRef.current.filter(item => now - item.timestamp <= AUTH_CONFIG.evidenceRetentionTime).slice(-AUTH_CONFIG.maxEvidenceItems);
    generateAuthEvent('evidence_captured', { evidenceId: evidence.id, evidenceType, severity: evidence.severity });
    return evidence;
  }, [videoRef, generateAuthEvent, AUTH_CONFIG.evidenceRetentionTime, AUTH_CONFIG.maxEvidenceItems]);

  const checkEscalationLevel = useCallback(() => {
    const now = Date.now();
    const windowStart = now - AUTH_CONFIG.escalationThresholds.timeWindow;
    const recentAlerts = impersonationAlertsRef.current.filter(alert => alert.timestamp >= windowStart && !alert.resolved);
    const criticalAlerts = recentAlerts.filter(alert => alert.severity === 'critical').length;
    const warningAlerts = recentAlerts.filter(alert => alert.severity === 'warning').length;
    const previousLevel = escalationStatusRef.current;
    let newLevel = 'normal';
    if (criticalAlerts >= 2 || recentAlerts.length >= AUTH_CONFIG.escalationThresholds.critical) newLevel = 'critical';
    else if (criticalAlerts >= 1 || recentAlerts.length >= AUTH_CONFIG.escalationThresholds.warning) newLevel = 'warning';
    return { level: newLevel, previousLevel, shouldEscalate: newLevel !== previousLevel, recentAlerts: recentAlerts.length, criticalAlerts, warningAlerts };
  }, [AUTH_CONFIG.escalationThresholds]); 

  const getRecommendedActions = useCallback((alert, escalation) => {
    const actions = [{ type: 'monitor', description: 'Continue monitoring', priority: 'low' }];
    switch (alert.type) {
      case 'multiple_faces': actions.push({ type: 'verify_single_candidate', description: 'Verify one candidate', priority: 'medium' }); break;
      case 'appearance_change': actions.push({ type: 're_authenticate', description: 'Request re-authentication', priority: 'high' }); break;
      case 'suspicious_behavior': actions.push({ type: 'manual_review', description: 'Flag for manual review', priority: 'high' }); break;
      default: actions.push({ type: 'general_monitoring', description: 'General monitoring', priority: 'low' }); break;
    }
    switch (escalation.level) {
      case 'warning': actions.push({ type: 'increase_monitoring', description: 'Increase monitoring sensitivity', priority: 'medium' }); break;
      case 'critical': 
        actions.push({ type: 'immediate_intervention', description: 'Immediate manual verification/termination', priority: 'critical' });
        actions.push({ type: 'preserve_evidence', description: 'Preserve evidence', priority: 'high' }); 
        break;
      default: break;
    }
    const priorityOrder = { critical: 4, high: 3, medium: 2, low: 1 };
    return actions.sort((a, b) => priorityOrder[b.priority] - priorityOrder[a.priority]);
  }, []);

  const generateImpersonationAlert = useCallback(async (alertType, alertData) => {
    const now = Date.now();
    const alert = { id: `alert_${now}_${Math.random().toString(36).substr(2, 9)}`, timestamp: now, type: alertType, severity: alertData.severity || 'warning', data: alertData, resolved: false };
    impersonationAlertsRef.current.push(alert);
    const evidence = await captureEvidence(`alert_${alertType}`, { alertId: alert.id, ...alertData });
    alert.evidenceId = evidence.id;
    const escalation = checkEscalationLevel();
    if (escalation.shouldEscalate) {
      escalationStatusRef.current = escalation.level;
      generateAuthEvent('escalation_level_changed', { previousLevel: escalation.previousLevel, newLevel: escalation.level, triggerAlert: alert.id });
    }
    generateAuthEvent('impersonation_alert_generated', { alertId: alert.id, alertType, severity: alert.severity, escalationLevel: escalationStatusRef.current });
    return { alert, evidence, escalationLevel: escalationStatusRef.current, recommendedActions: getRecommendedActions(alert, escalation) };
  }, [captureEvidence, generateAuthEvent, checkEscalationLevel, getRecommendedActions]); 

  // --- GROUP 4: PHASE 3 DETECTION FUNCTIONS ---
  const detectMultipleFaces = useCallback(async () => {
    if (!detectorRef.current || !videoRef?.current) return { faces: [], primaryFace: null, multipleFacesDetected: false, totalFaceCount: 0 };
    try {
      const faces = await detectorRef.current.estimateFaces(videoRef.current);
      const now = Date.now();
      const validFaces = faces.filter(f => f.score >= 0.5 && f.box && Math.min(f.box.width || 0, f.box.height || 0) >= AUTH_CONFIG.minFaceSize);
      const trackedFaces = [];
      for (let i = 0; i < Math.min(validFaces.length, AUTH_CONFIG.maxTrackedFaces); i++) {
        const face = validFaces[i];
        trackedFaces.push({ id: `face_${now}_${i}`, face, embedding: await extractSimplifiedEmbedding(face), firstSeen: now, lastSeen: now, confidence: face.score });
      }
      trackedFaces.forEach(tf => multipleFaceTrackingRef.current.set(tf.id, tf));
      for (const [faceId, faceData] of multipleFaceTrackingRef.current.entries()) {
        if (now - faceData.lastSeen > 30000) multipleFaceTrackingRef.current.delete(faceId);
      }
      let primaryFace = null;
      if (enrollmentEmbedding && trackedFaces.length > 0) {
        let maxSimilarity = 0;
        for (const tf of trackedFaces) {
          const sim = calculateSimilarity(enrollmentEmbedding, tf.embedding);
          if (sim > maxSimilarity) { maxSimilarity = sim; primaryFace = tf; }
        }
      } else if (trackedFaces.length > 0) {
        primaryFace = trackedFaces.reduce((prev, curr) => curr.confidence > prev.confidence ? curr : prev);
      }
      const multipleFacesDetected = validFaces.length > 1;
      if (multipleFacesDetected) generateAuthEvent('multiple_faces_detected', { faceCount: validFaces.length, primaryFaceId: primaryFace?.id });
      return { faces: trackedFaces, primaryFace, multipleFacesDetected, totalFaceCount: validFaces.length };
    } catch (err) { return { faces: [], primaryFace: null, multipleFacesDetected: false, totalFaceCount: 0 }; }
  }, [videoRef, enrollmentEmbedding, calculateSimilarity, extractSimplifiedEmbedding, generateAuthEvent, AUTH_CONFIG.minFaceSize, AUTH_CONFIG.maxTrackedFaces]); 

  const detectAppearanceChanges = useCallback(async (currentFace, currentEmbedding) => {
    const now = Date.now();
    faceHistoryRef.current.push({ timestamp: now, embedding: currentEmbedding, confidence: currentFace.score, faceBox: currentFace.box });
    if (faceHistoryRef.current.length > AUTH_CONFIG.faceHistorySize) faceHistoryRef.current.shift();
    const recentHistory = faceHistoryRef.current.filter(s => now - s.timestamp <= 60000);
    if (recentHistory.length < 2) return { suddenChange: false, changeScore: 0, analysis: 'insufficient_history' };
    const similarities = recentHistory.slice(-5).map(s => calculateSimilarity(currentEmbedding, s.embedding));
    if (similarities.length === 0) return { suddenChange: false, changeScore: 0, analysis: 'no_similarities' };
    const avgSim = similarities.reduce((sum, sim) => sum + sim, 0) / similarities.length;
    const minSim = Math.min(...similarities), maxSim = Math.max(...similarities);
    const variability = maxSim - minSim;
    const suddenChange = avgSim < AUTH_CONFIG.appearanceChangeThreshold || variability > 0.4;
    if (suddenChange) generateAuthEvent('appearance_change_detected', { avgSim, variability, severity: avgSim < 0.3 ? 'critical' : 'warning' });
    return { suddenChange, changeScore: 1 - avgSim, analysis: { avgSim, minSim, maxSim, variability, historySize: recentHistory.length }};
  }, [calculateSimilarity, generateAuthEvent, AUTH_CONFIG.faceHistorySize, AUTH_CONFIG.appearanceChangeThreshold]); 

  const performTemporalAnalysis = useCallback((authenticationResult) => {
    const now = Date.now();
    behaviorPatternRef.current.authenticationTimes.push({ timestamp: now, ...authenticationResult });
    behaviorPatternRef.current.authenticationTimes = behaviorPatternRef.current.authenticationTimes.filter(e => e.timestamp >= now - AUTH_CONFIG.behaviorAnalysisWindow);
    const recentEvents = behaviorPatternRef.current.authenticationTimes.slice(-30);
    if (recentEvents.length < 5) return { suspiciousBehavior: false, patterns: [], confidence: 0 };
    const patterns = [];
    const altPattern = detectAlternatingPattern(recentEvents); if (altPattern.detected) patterns.push({ type: 'alternating', ...altPattern });
    const dropPattern = detectSimilarityDrops(recentEvents); if (dropPattern.detected) patterns.push({ type: 'drops', ...dropPattern });
    const timingPattern = detectTimingIrregularities(recentEvents); if (timingPattern.detected) patterns.push({ type: 'timing', ...timingPattern });
    const overallConfidence = patterns.length > 0 ? patterns.reduce((sum, p) => sum + p.confidence, 0) / patterns.length : 0;
    const suspiciousBehavior = overallConfidence >= 0.6;
    if (suspiciousBehavior) generateAuthEvent('suspicious_behavior_detected', { patterns: patterns.map(p=>p.type), overallConfidence });
    return { suspiciousBehavior, patterns, confidence: overallConfidence };
  }, [generateAuthEvent, AUTH_CONFIG.behaviorAnalysisWindow, detectAlternatingPattern, detectSimilarityDrops, detectTimingIrregularities]); 

  // --- GROUP 5: MAIN ACTION FUNCTIONS ---
  const authenticateCurrentFace = useCallback(async () => {
    if (!enrollmentEmbedding || enrollmentStatus !== 'enrolled') return { success: false, message: 'No enrolled face' };
    try {
      const multiFaceResult = await detectMultipleFaces();
      if (multiFaceResult.multipleFacesDetected) {
        await generateImpersonationAlert('multiple_faces', { faceCount: multiFaceResult.totalFaceCount, severity: multiFaceResult.totalFaceCount > 2 ? 'critical' : 'warning' });
      }
      const faceResult = multiFaceResult.primaryFace ? { face: multiFaceResult.primaryFace.face } : await detectBestFace();
      if (faceResult?.error) {
        setAuthenticationStatus('failed');
        const failure = handleAuthenticationFailure(0, faceResult.error); updateSlidingWindow(0, false);
        return { success: false, message: faceResult.error, ...failure };
      }
      const { face } = faceResult;
      const currentEmbedding = await extractEmbeddingWithCache(face);
      const appearanceAnalysis = await detectAppearanceChanges(face, currentEmbedding);
      if (appearanceAnalysis.suddenChange) {
        await generateImpersonationAlert('appearance_change', { changeScore: appearanceAnalysis.changeScore, severity: appearanceAnalysis.changeScore > 0.7 ? 'critical' : 'warning' });
      }
      const similarity = calculateSimilarity(enrollmentEmbedding, currentEmbedding);
      setAuthenticationScore(similarity); setLastAuthenticationTime(new Date());
      const authResultForTemporal = { success: similarity >= AUTH_CONFIG.authenticationThreshold, similarity, confidence: face.score || 0, multipleFacesDetected: multiFaceResult.multipleFacesDetected, appearanceChange: appearanceAnalysis.suddenChange };
      const behaviorAnalysis = performTemporalAnalysis(authResultForTemporal);
      if (behaviorAnalysis.suspiciousBehavior) {
        await generateImpersonationAlert('suspicious_behavior', { patterns: behaviorAnalysis.patterns.map(p=>p.type), confidence: behaviorAnalysis.confidence, severity: behaviorAnalysis.confidence > 0.8 ? 'critical' : 'warning' });
      }

      if (similarity >= AUTH_CONFIG.authenticationThreshold) {
        setAuthenticationStatus('authenticated');
        handleAuthenticationSuccess(similarity, face.score || 0); const windowStats = updateSlidingWindow(similarity, true);
        return { success: true, similarity, message: 'Authentication successful', windowStats, multipleFacesDetected: multiFaceResult.multipleFacesDetected, appearanceChange: appearanceAnalysis.suddenChange, behaviorAnalysis, escalationLevel: escalationStatusRef.current };
      } else if (similarity < AUTH_CONFIG.impersonationThreshold) {
        setAuthenticationStatus('failed');
        await generateImpersonationAlert('low_similarity_impersonation', { similarity, severity: 'critical', factors: { multipleFaces: multiFaceResult.multipleFacesDetected, appearanceChange: appearanceAnalysis.suddenChange, suspiciousBehavior: behaviorAnalysis.suspiciousBehavior }});
        const failure = handleAuthenticationFailure(similarity, 'Possible impersonation'); updateSlidingWindow(similarity, false);
        return { success: false, similarity, message: 'Possible impersonation', ...failure, multipleFacesDetected: multiFaceResult.multipleFacesDetected, appearanceChange: appearanceAnalysis.suddenChange, behaviorAnalysis, escalationLevel: escalationStatusRef.current };
      } else {
        setAuthenticationStatus('failed');
        const failure = handleAuthenticationFailure(similarity, 'Low similarity'); updateSlidingWindow(similarity, false);
        const combinedRisk = calculateCombinedRiskScore(similarity, multiFaceResult.multipleFacesDetected, appearanceAnalysis, behaviorAnalysis);
        if (combinedRisk > 0.6) {
          await generateImpersonationAlert('combined_risk_factors', { similarity, riskScore: combinedRisk, severity: combinedRisk > 0.8 ? 'critical' : 'warning' });
        }
        return { success: false, similarity, message: 'Authentication failed', ...failure, multipleFacesDetected: multiFaceResult.multipleFacesDetected, appearanceChange: appearanceAnalysis.suddenChange, behaviorAnalysis, combinedRisk, escalationLevel: escalationStatusRef.current };
      }
    } catch (err) {
      setAuthenticationStatus('failed');
      await generateImpersonationAlert('authentication_error', { error: err.message, severity: 'warning' });
      generateAuthEvent('authentication_error_main', { error: err.message });
      const failure = handleAuthenticationFailure(0, err.message); updateSlidingWindow(0, false);
      return { success: false, message: 'Authentication error', ...failure, escalationLevel: escalationStatusRef.current };
    }
  }, [
    enrollmentEmbedding, enrollmentStatus, detectMultipleFaces, generateImpersonationAlert, detectBestFace, 
    handleAuthenticationFailure, updateSlidingWindow, extractEmbeddingWithCache, detectAppearanceChanges, 
    calculateSimilarity, performTemporalAnalysis, handleAuthenticationSuccess, calculateCombinedRiskScore,
    AUTH_CONFIG.authenticationThreshold, AUTH_CONFIG.impersonationThreshold, generateAuthEvent
  ]); 

  const enrollFace = useCallback(async () => {
    console.log(`${LOG_PREFIX} enrollFace CALLED. videoRef.current: ${videoRef.current ? 'AVAILABLE' : 'MISSING'}, videoRef.current.readyState: ${videoRef.current ? videoRef.current.readyState : 'N/A'}, isReady: ${isReady}, detectorRef.current: ${detectorRef.current ? 'LOADED' : 'MISSING'}, enrollmentStatus: ${enrollmentStatus}, isLoading: ${isLoading}`);

    if (!videoRef.current || !isReady || !detectorRef.current) {
      const errorMsg = 'Enrollment failed: Service not ready or video unavailable.';
      const detail = {
        videoRefAvailable: !!videoRef.current,
        modelsAreReady: isReady,
        detectorIsLoaded: !!detectorRef.current,
        videoReadyState: videoRef.current ? videoRef.current.readyState : 'N/A'
      };
      console.error(`${LOG_PREFIX} ${errorMsg}`, detail);
      setError(new Error(errorMsg)); // Convert string to Error object
      generateAuthEvent('enrollment_error_prereq', { message: errorMsg, detail });
      setEnrollmentStatus('not_enrolled');
      throw new Error(errorMsg);
    }
    if (enrollmentStatus === 'enrolling') {
      console.warn(`${LOG_PREFIX} Enrollment already in progress. Aborting new enrollFace call.`);
      return; // Or throw new Error('Enrollment already in progress.');
    }
    setEnrollmentStatus('enrolling'); 
    setIsLoading(true); // Use main isLoading
    setError(null);
    enrollmentAttemptsRef.current += 1;
    setCurrentEnrollmentAttempt(enrollmentAttemptsRef.current); // Update state here
    console.log(`${LOG_PREFIX} Starting enrollment attempt #${enrollmentAttemptsRef.current}`);

    try {
      // Ensure video is playable before detection
      if (videoRef.current.paused) {
          try {
              await videoRef.current.play();
          } catch (playError) {
              console.error(`${LOG_PREFIX} Error trying to play video for enrollment:`, playError);
              throw new Error('Video could not be played for enrollment.');
          }
      }
      await waitForVideoReady(); // Wait for video to be truly ready

      const faceResult = await detectBestFace(); // detectBestFace internally handles video validation
      
      if (faceResult?.error || !faceResult?.face) {
        const errorMsg = faceResult?.error || 'No face detected for enrollment.';
        console.error(`${LOG_PREFIX} Enrollment detection failed: ${errorMsg}, attempt: ${enrollmentAttemptsRef.current}`);
        generateAuthEvent('enrollment_failed_detection', { error: errorMsg, attempt: enrollmentAttemptsRef.current });
        setError(new Error(errorMsg)); // Convert string to Error object
        throw new Error(errorMsg);
      }
      
      const { face } = faceResult;
      const qualityCheck = validateFaceQuality(face);
      if (!qualityCheck.valid) {
        const errorMsg = qualityCheck.reason || 'Face quality too low for enrollment.';
        console.error(`${LOG_PREFIX} Enrollment quality check failed: ${errorMsg}, attempt: ${enrollmentAttemptsRef.current}`);
        generateAuthEvent('enrollment_failed_quality', { reason: errorMsg, attempt: enrollmentAttemptsRef.current });
        setError(new Error(errorMsg)); // Convert string to Error object
        throw new Error(errorMsg);
      }
      
      console.log(`${LOG_PREFIX} Face detected and quality validated for enrollment. Extracting embedding.`);
      const capturedEmbedding = await extractSimplifiedEmbedding(face);
      
      const enrollmentScore = AUTH_CONFIG.enrollmentThreshold; // This is a config value, not a dynamic score from quality
      setAuthenticationScore(enrollmentScore); // Perhaps rename this to enrollmentConfidence or similar if it's fixed
      setEnrollmentEmbedding(capturedEmbedding); 
      setEnrollmentStatus('enrolled');
      setLastAuthenticationTime(new Date()); // Or setEnrollmentTime
      console.log(`${LOG_PREFIX} Enrollment successful. Embedding stored. Attempt: ${enrollmentAttemptsRef.current}`);
      generateAuthEvent('enrollment_success', { score: enrollmentScore, attempt: enrollmentAttemptsRef.current });
      resetEnrollmentAttempts(); // Reset attempts on success
      return capturedEmbedding; // Return the embedding for the caller

    } catch (err) {
      console.error(`${LOG_PREFIX} Error during enrollFace attempt #${enrollmentAttemptsRef.current}:`, err.message, err.stack);
      // setError(err.message || 'Enrollment failed.'); // Error is set by the specific throw points
      // No need to generate generic error event if specific ones were already generated.
      // If an error is thrown, it will be caught by the caller of enrollFace.
      // The status is reset by the caller or at the beginning of the next attempt.
      setEnrollmentStatus('not_enrolled'); // Ensure status reflects failure if an error is thrown and not caught internally for retry
      throw err; // Re-throw the error to be handled by the calling component (e.g., FaceAuthenticationManager)
    } finally {
      setIsLoading(false); // Use main isLoading
      // If not throwing, setEnrollmentStatus('not_enrolled') might be here if it didn't succeed.
      // But since we throw, the status is managed by the catch or the caller.
      console.log(`${LOG_PREFIX} enrollFace attempt #${enrollmentAttemptsRef.current} finished. Enrollment status: ${enrollmentStatus}`);
    }
  }, [
    videoRef, isReady, enrollmentStatus, detectBestFace, validateFaceQuality, 
    extractSimplifiedEmbedding, generateAuthEvent, AUTH_CONFIG.enrollmentThreshold,
    waitForVideoReady, // Added
    // Removed authenticationEvents from deps as it caused loops
  ]);

  const performRealTimeVerification = useCallback(async () => {
    if (!enrollmentEmbedding || enrollmentStatus !== 'enrolled' || !isActive) return;
    try {
      const result = await authenticateCurrentFace();
      return result;
    } catch (err) {
      generateAuthEvent('real_time_verification_error', { error: err.message });
    }
  }, [enrollmentEmbedding, enrollmentStatus, isActive, authenticateCurrentFace, generateAuthEvent]);

  // --- GROUP 6: HIGHER-LEVEL CONTROL FUNCTIONS ---
  const startRealTimeMonitoring = useCallback(() => {
    if (realTimeMonitoringRef.current) clearInterval(realTimeMonitoringRef.current);
    realTimeMonitoringRef.current = setInterval(() => {
      if (enrollmentStatus === 'enrolled' && isActive) performRealTimeVerification();
    }, AUTH_CONFIG.realTimeInterval);
  }, [enrollmentStatus, isActive, performRealTimeVerification, AUTH_CONFIG.realTimeInterval]);

  const stopRealTimeMonitoring = useCallback(() => {
    if (realTimeMonitoringRef.current) {
      clearInterval(realTimeMonitoringRef.current);
      realTimeMonitoringRef.current = null;
    }
  }, []);

  const startPeriodicAuthentication = useCallback(() => {
    if (authIntervalRef.current) clearInterval(authIntervalRef.current);
    authIntervalRef.current = setInterval(() => {
      if (enrollmentStatus === 'enrolled' && isActive) authenticateCurrentFace();
    }, AUTH_CONFIG.authenticationInterval);
    startRealTimeMonitoring();
  }, [enrollmentStatus, isActive, authenticateCurrentFace, startRealTimeMonitoring, AUTH_CONFIG.authenticationInterval]);

  const stopPeriodicAuthentication = useCallback(() => {
    if (authIntervalRef.current) {
      clearInterval(authIntervalRef.current);
      authIntervalRef.current = null;
    }
    stopRealTimeMonitoring();
  }, [stopRealTimeMonitoring]);

  const resetAuthentication = useCallback(() => {
    setEnrollmentStatus('not_enrolled'); setAuthenticationStatus('pending');
    setEnrollmentEmbedding(null); setAuthenticationScore(0); setLastAuthenticationTime(null);
    resetEnrollmentAttempts();
    consecutiveFailuresRef.current = 0; lastFailureTimeRef.current = null;
    embeddingCacheRef.current.clear(); slidingWindowRef.current = []; recentEventsRef.current.clear();
    faceHistoryRef.current = []; multipleFaceTrackingRef.current.clear();
    behaviorPatternRef.current = { authenticationTimes: [], failurePatterns: [], locationChanges: [], deviceChanges: [] };
    evidenceCaptureRef.current = []; impersonationAlertsRef.current = []; escalationStatusRef.current = 'normal';
    stopPeriodicAuthentication();
    generateAuthEvent('authentication_reset');
  }, [stopPeriodicAuthentication, generateAuthEvent]);

  // Reset attempts on successful enrollment or full reset
  const resetEnrollmentAttempts = useCallback(() => {
    enrollmentAttemptsRef.current = 0;
    setCurrentEnrollmentAttempt(0);
  }, []);

  // --- GROUP 7: USEEFFECTS AND RETURN ---
  useEffect(() => {
    let didRunMainLogic = false;
    if (isActive && videoRef.current) {
      // Perform internal checks; these states are not dependencies for re-running the effect logic itself,
      // but for gating the call to initializeModels.
      if (!isReady && !isLoading && !initializationInProgressRef.current) { 
        console.log(`${LOG_PREFIX} Main Init useEffect: Calling initializeModels (isActive, videoRef available, not ready/loading/inProgress).`);
        initializeModels();
        didRunMainLogic = true;
    } else {
        console.log(`${LOG_PREFIX} Main Init useEffect: Conditions NOT met for calling initializeModels. isActive: ${isActive}, videoRef: ${!!videoRef.current}, isReady: ${isReady}, isLoading: ${isLoading}, initInProgress: ${initializationInProgressRef.current}`);
      }
    } else {
      console.log(`${LOG_PREFIX} Main Init useEffect: Conditions NOT met for attempting initialization. isActive: ${isActive}, videoRef: ${!!videoRef.current}`);
    }
    
    // This cleanup runs when the component unmounts OR when any dependency in the array changes.
    // We want it to primarily clean up if isActive becomes false or the videoRef fundamentally changes.
    return () => {
      console.log(`${LOG_PREFIX} Cleanup for Main Init useEffect. Current isActive: ${isActive}, didRunMainLogic this cycle: ${didRunMainLogic}.`);
      // Only run full cleanup if isActive is becoming false or if the hook is truly unmounting.
      // The dependency array ensures this runs if isActive changes.
      // If videoRef changes, it implies a new setup, so cleanup is also appropriate.
      if (!isActive) { // Check current isActive, if it's false, then we are deactivating.
        console.log(`${LOG_PREFIX} Cleanup logic: isActive is now false. Stopping periodic auth and resetting attempts.`);
      stopPeriodicAuthentication();
        resetEnrollmentAttempts(); 
      }
      // If didRunMainLogic was true, it means initializeModels was called.
      // However, initializeModels is async. Its completion isn't tied to this effect's lifecycle directly.
      // The stop/reset calls should be robust to being called multiple times or when nothing is active.
    };
  }, [isActive, videoRef, initializeModels, stopPeriodicAuthentication, resetEnrollmentAttempts]);

  useEffect(() => {
    if (enrollmentStatus === 'enrolled' && isActive) startPeriodicAuthentication();
    else stopPeriodicAuthentication();
    return () => stopPeriodicAuthentication();
  }, [enrollmentStatus, isActive, startPeriodicAuthentication, stopPeriodicAuthentication]);
  
  useEffect(() => {
    currentSessionIdRef.current = initialSessionId;
  }, [initialSessionId]);

  // General state change logger
  useEffect(() => {
    console.log(`${LOG_PREFIX} GENERAL STATE CHANGE - isActive: ${isActive}, isReady: ${isReady}, isLoading: ${isLoading}, detectorRef.current: ${detectorRef.current ? 'LOADED' : 'NULL'}, videoRef.current: ${videoRef.current ? 'AVAILABLE' : 'UNAVAILABLE'}, videoRef.readyState: ${videoRef.current?.readyState}, enrollmentStatus: ${enrollmentStatus}, currentEnrollmentAttempt: ${currentEnrollmentAttempt}`);
  }, [isActive, isReady, isLoading, videoRef, enrollmentStatus, currentEnrollmentAttempt]); // detectorRef.current changes won't trigger this, but its status will be logged when other states change.

    return {
    isLoading, isReady, error, enrollmentStatus, authenticationStatus, authenticationScore, lastAuthenticationTime, authenticationEvents,
    currentEnrollmentAttempt, // Return the new state
    enrollFace, authenticateCurrentFace, resetAuthentication,
    performRealTimeVerification, startRealTimeMonitoring, stopRealTimeMonitoring,
    detectMultipleFaces, detectAppearanceChanges, performTemporalAnalysis, generateImpersonationAlert, captureEvidence,
    escalationStatus: escalationStatusRef.current,
    getImpersonationAlerts: () => impersonationAlertsRef.current,
    getEvidenceCapture: () => evidenceCaptureRef.current,
    getFaceHistory: () => faceHistoryRef.current,
    getBehaviorPatterns: () => behaviorPatternRef.current,
    getMultipleFaceTracking: () => Array.from(multipleFaceTrackingRef.current.values()),
    calculateCombinedRiskScore,
    checkEscalationLevel,
    getRecommendedActions: (alert, escalation) => getRecommendedActions(alert, escalation),
    authConfig: AUTH_CONFIG,
    generateAuthEvent,
    runDiagnostics,
    getSlidingWindowStats: () => {
      const window = slidingWindowRef.current;
      if (window.length === 0) return { windowSize: 0, successCount: 0, averageSimilarity: 0, successRate: 0, consecutiveFailures: consecutiveFailuresRef.current, cacheSize: embeddingCacheRef.current.size };
      const successCount = window.filter(entry => entry.success).length;
      const averageSimilarity = window.reduce((sum, entry) => sum + entry.similarity, 0) / window.length;
      const successRate = successCount / window.length;
      return { windowSize: window.length, successCount, averageSimilarity, successRate, consecutiveFailures: consecutiveFailuresRef.current, cacheSize: embeddingCacheRef.current.size };
    },
    getAdvancedStats: () => {
      const now = Date.now();
      const recentAlerts = impersonationAlertsRef.current.filter(alert => now - alert.timestamp <= AUTH_CONFIG.escalationThresholds.timeWindow);
      return {
        escalationLevel: escalationStatusRef.current, recentAlertsCount: recentAlerts.length, criticalAlertsCount: recentAlerts.filter(a => a.severity === 'critical').length,
        trackedFacesCount: multipleFaceTrackingRef.current.size, faceHistorySize: faceHistoryRef.current.length,
        evidenceItemsCount: evidenceCaptureRef.current.length, behaviorEventCount: behaviorPatternRef.current.authenticationTimes.length,
        temporalAnalysisWindow: AUTH_CONFIG.temporalAnalysisWindow, behaviorAnalysisWindow: AUTH_CONFIG.behaviorAnalysisWindow,
        impersonationThreshold: AUTH_CONFIG.impersonationThreshold, multipleFaceThreshold: AUTH_CONFIG.multipleFaceThreshold, appearanceChangeThreshold: AUTH_CONFIG.appearanceChangeThreshold
      };
    }
  };
};