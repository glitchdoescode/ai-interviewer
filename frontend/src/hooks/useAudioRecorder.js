import { useState, useEffect, useCallback, useRef } from 'react';
import Recorder from 'recorder-js';

/**
 * Custom hook for audio recording functionality
 * @returns {Object} Object containing recording state and functions
 */
const useAudioRecorder = () => {
  const [recorder, setRecorder] = useState(null);
  const [stream, setStream] = useState(null);
  const [isRecording, setIsRecording] = useState(false);
  const [audioData, setAudioData] = useState(null);
  const [error, setError] = useState(null);
  const [audioContext, setAudioContext] = useState(null);
  const [permissionGranted, setPermissionGranted] = useState(false);
  const [isInitializing, setIsInitializing] = useState(false);
  const recorderRef = useRef(null);
  const audioContextRef = useRef(null);

  // Clean up audio resources when the component unmounts
  useEffect(() => {
    return () => {
      if (stream) {
        // Stop all audio tracks
        stream.getTracks().forEach(track => track.stop());
      }
      
      // Close audio context if it exists
      if (audioContext && audioContext.state !== 'closed') {
        audioContext.close();
      }
    };
  }, [stream, audioContext]);

  // Initialize audio recording with clearer error handling
  const initRecording = useCallback(async () => {
    // Prevent multiple initializations
    if (isInitializing) {
      console.log('Already initializing audio...');
      return false;
    }

    try {
      setIsInitializing(true);
      setError(null);
      
      console.log('DEBUG: Requesting microphone permission...');
      
      // Request user permission to access the microphone
      const audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      console.log('DEBUG: Microphone permission granted, got stream:', !!audioStream);
      setStream(audioStream);
      setPermissionGranted(true);
      
      console.log('DEBUG: Creating audio context...');
      
      // Create an audio context
      let context;
      try {
        // Safari requires prefix
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        context = new AudioContext();
        console.log('DEBUG: Audio context created, state:', context.state);
        
        // Ensure the context is running
        if (context.state !== 'running') {
          console.log('DEBUG: Audio context not running, attempting to resume...');
          // Play a silent sound to unlock audio context (mobile browsers often need this)
          const silentBuffer = context.createBuffer(1, 1, 22050);
          const source = context.createBufferSource();
          source.buffer = silentBuffer;
          source.connect(context.destination);
          source.start(0);
          
          await context.resume();
          console.log('DEBUG: Audio context resumed, new state:', context.state);
        }
        
        setAudioContext(context);
        audioContextRef.current = context;
        
        // Create a new recorder with the audio context
        console.log('DEBUG: Creating recorder instance...');
        const newRecorder = new Recorder(context);
        
        // Connect the recorder to the stream
        console.log('DEBUG: Initializing recorder with stream...');
        await newRecorder.init(audioStream);
        console.log('DEBUG: Recorder initialized successfully');
        
        setRecorder(newRecorder);
        recorderRef.current = newRecorder;
        
        console.log('DEBUG: Audio recording setup complete');
        return true;
      } catch (contextError) {
        console.error('DEBUG: Error with audio context:', contextError);
        throw contextError;
      }
    } catch (err) {
      console.error('DEBUG: Error initializing audio recording:', err.name, err.message);
      
      // Provide specific error messages based on the error type
      if (err.name === 'NotAllowedError') {
        setError('Microphone permission denied. Please allow access in your browser settings.');
      } else if (err.name === 'NotFoundError') {
        setError('No microphone detected. Please check your device settings.');
      } else if (err.name === 'AbortError') {
        setError('Recording permission request was aborted. Please try again.');
      } else if (err.name === 'NotReadableError') {
        setError('Microphone is already in use by another application.');
      } else {
        setError(`Error accessing microphone: ${err.message}`);
      }
      
      return false;
    } finally {
      setIsInitializing(false);
    }
  }, [isInitializing]);

  // Start recording with improved error handling
  const startRecording = useCallback(async () => {
    try {
      setError(null);
      
      // Using refs to avoid timing issues with state updates
      let currentRecorder = recorderRef.current || recorder;
      let currentContext = audioContextRef.current || audioContext;
      
      // Initialize recording if needed
      if (!currentRecorder || !currentContext) {
        console.log('DEBUG: No recorder or context, initializing...');
        const initialized = await initRecording();
        if (!initialized) {
          console.log('DEBUG: Failed to initialize recording');
          return false;
        }
        
        // Get updated refs after initialization
        currentRecorder = recorderRef.current;
        currentContext = audioContextRef.current;
        
        // Safety check
        if (!currentRecorder || !currentContext) {
          console.error('DEBUG: Still no recorder or context after initialization');
          setError('Failed to initialize audio system correctly.');
          return false;
        }
        
        console.log('DEBUG: Successfully initialized recording components');
      }
      
      // Ensure audio context is running
      if (currentContext.state !== 'running') {
        console.log(`DEBUG: Audio context not running (state: ${currentContext.state}), attempting to resume...`);
        
        // Try to unblock audio context (common issue on mobile)
        const silentBuffer = currentContext.createBuffer(1, 1, 22050);
        const source = currentContext.createBufferSource();
        source.buffer = silentBuffer;
        source.connect(currentContext.destination);
        source.start(0);
        
        await currentContext.resume();
        console.log(`DEBUG: Audio context after resume: ${currentContext.state}`);
        
        if (currentContext.state !== 'running') {
          console.error('DEBUG: Context still not running after resume');
          setError('Could not activate audio system. Try clicking once anywhere on the page and try again.');
          return false;
        }
      }
      
      // Start recording
      console.log('DEBUG: Starting recorder...');
      try {
        await currentRecorder.start();
        console.log('DEBUG: Recording started successfully');
        setIsRecording(true);
        setAudioData(null);
        return true;
      } catch (startError) {
        console.error('DEBUG: Error calling start():', startError);
        setError(`Recording failed to start: ${startError.message}`);
        return false;
      }
    } catch (err) {
      console.error('DEBUG: General error in startRecording:', err);
      setError(`Could not start recording: ${err.message}`);
      return false;
    }
  }, [recorder, audioContext, initRecording]);

  // Stop recording and get the audio data
  const stopRecording = useCallback(async () => {
    const currentRecorder = recorderRef.current || recorder;
    
    if (!currentRecorder || !isRecording) {
      console.log('DEBUG: No recorder available or not recording');
      return null;
    }

    try {
      console.log('DEBUG: Stopping recording...');
      const { blob, buffer } = await currentRecorder.stop();
      console.log('DEBUG: Recording stopped, got blob:', !!blob, 'buffer:', !!buffer);
      setIsRecording(false);
      setAudioData({ blob, buffer });
      return { blob, buffer };
    } catch (err) {
      console.error('DEBUG: Error stopping recording:', err);
      setError(`Error stopping recording: ${err.message}`);
      return null;
    }
  }, [recorder, isRecording]);

  // Convert audio blob to base64
  const getAudioBase64 = useCallback(async (audioBlob) => {
    return new Promise((resolve, reject) => {
      console.log('DEBUG: Converting audio blob to base64, size:', audioBlob.size);
      const reader = new FileReader();
      reader.onloadend = () => {
        // Extract the base64 data from the result
        // The result is like "data:audio/wav;base64,UklGRiXiAABXQVZF..."
        const base64Data = reader.result.split(',')[1];
        console.log('DEBUG: Converted blob to base64, length:', base64Data?.length);
        resolve(base64Data);
      };
      reader.onerror = (err) => {
        console.error('DEBUG: Error reading blob:', err);
        reject(err);
      };
      reader.readAsDataURL(audioBlob);
    });
  }, []);

  // Cancel recording
  const cancelRecording = useCallback(() => {
    const currentRecorder = recorderRef.current || recorder;
    if (currentRecorder && isRecording) {
      currentRecorder.cancel();
      setIsRecording(false);
    }
    setAudioData(null);
  }, [recorder, isRecording]);
  
  // Check permission status
  const checkPermissionStatus = useCallback(async () => {
    try {
      console.log('DEBUG: Checking microphone permission status...');
      // Try a permission query first if supported
      if (navigator.permissions && navigator.permissions.query) {
        try {
          const permissionStatus = await navigator.permissions.query({ name: 'microphone' });
          console.log('DEBUG: Permission status:', permissionStatus.state);
          
          if (permissionStatus.state === 'granted') {
            return true;
          } else if (permissionStatus.state === 'denied') {
            setError('Microphone access has been denied. Please update your browser settings.');
            return false;
          }
          // If 'prompt', we'll fall through to enumerate devices
        } catch (permErr) {
          console.log('DEBUG: Permission query not supported:', permErr);
          // Fall through to enumerate devices
        }
      }
      
      // Enumerate devices as a fallback
      const devices = await navigator.mediaDevices.enumerateDevices();
      const audioDevices = devices.filter(device => device.kind === 'audioinput');
      
      console.log('DEBUG: Found audio input devices:', audioDevices.length);
      
      if (audioDevices.length === 0) {
        setError('No audio input devices found.');
        return false;
      }
      
      return true;
    } catch (err) {
      console.error('DEBUG: Error checking permission status:', err);
      setError(`Error checking microphone access: ${err.message}`);
      return false;
    }
  }, []);

  return {
    isRecording,
    audioData,
    error,
    permissionGranted,
    isInitializing,
    initRecording,
    startRecording,
    stopRecording,
    cancelRecording,
    getAudioBase64,
    checkPermissionStatus
  };
};

export default useAudioRecorder; 