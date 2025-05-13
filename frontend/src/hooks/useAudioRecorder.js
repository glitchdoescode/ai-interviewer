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
  const streamRef = useRef(null);

  // Check if we're on a mobile device
  const isMobile = useRef(/iPhone|iPad|iPod|Android/i.test(navigator.userAgent));

  // Clean up audio resources when the component unmounts
  useEffect(() => {
    return () => {
      // Clean up function
      const cleanupResources = () => {
        console.log("DEBUG: Cleaning up audio resources");

        // Stop all tracks in the stream if it exists
        if (streamRef.current) {
          streamRef.current.getTracks().forEach(track => {
            console.log(`DEBUG: Stopping track: ${track.kind}`);
            track.stop();
          });
          streamRef.current = null;
        }
        
        // Close audio context if it exists
        if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
          console.log(`DEBUG: Closing AudioContext (state: ${audioContextRef.current.state})`);
          audioContextRef.current.close().catch(err => {
            console.error("DEBUG: Error closing AudioContext:", err);
          });
          audioContextRef.current = null;
        }

        // Release recorder resources if any
        if (recorderRef.current) {
          console.log("DEBUG: Cleaning up recorder");
          recorderRef.current = null;
        }

        // Clear state
        setStream(null);
        setRecorder(null);
        setAudioContext(null);
        setIsRecording(false);
      };

      try {
        cleanupResources();
      } catch (err) {
        console.error("DEBUG: Error during cleanup:", err);
      }
    };
  }, []);

  // Helper function to unlock audio context (especially on mobile)
  const unlockAudioContext = useCallback(async (context) => {
    console.log(`DEBUG: Attempting to unlock AudioContext (state: ${context.state})`);
    
    if (context.state === 'suspended') {
      // Create and play a silent sound (crucial for iOS)
      try {
        const buffer = context.createBuffer(1, 1, 22050);
        const source = context.createBufferSource();
        source.buffer = buffer;
        source.connect(context.destination);
        source.start(0);
        
        // Try user interaction simulation for Safari/iOS
        if (isMobile.current) {
          console.log("DEBUG: Applying mobile-specific audio unlocking");
          
          // Use both timeout and direct resume for better chances
          setTimeout(() => {
            context.resume().catch(e => console.log("DEBUG: Delayed resume failed:", e));
          }, 100);
          
          // Some browsers need direct user gesture to work
          document.documentElement.addEventListener('touchend', function unlock() {
            context.resume().then(() => {
              document.documentElement.removeEventListener('touchend', unlock);
              console.log("DEBUG: TouchEnd unlocked AudioContext");
            }).catch(e => console.log("DEBUG: TouchEnd resume failed:", e));
          }, { once: true });
        }
        
        console.log("DEBUG: Direct resume attempt");
        await context.resume();
        console.log(`DEBUG: AudioContext after unlock attempt: ${context.state}`);
        return context.state === 'running';
      } catch (err) {
        console.error("DEBUG: Error unlocking audio context:", err);
        return false;
      }
    }
    return context.state === 'running';
  }, []);

  // Initialize audio recording with clearer error handling
  const initRecording = useCallback(async () => {
    // Prevent multiple initializations
    if (isInitializing) {
      console.log('DEBUG: Already initializing audio...');
      return false;
    }

    try {
      setIsInitializing(true);
      setError(null);
      
      console.log('DEBUG: Requesting microphone permission...');
      
      // Request user permission to access the microphone
      const audioStream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        } 
      });
      
      console.log('DEBUG: Microphone permission granted, got stream:', !!audioStream);
      setStream(audioStream);
      streamRef.current = audioStream;
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
          console.log('DEBUG: Audio context not running, attempting to unlock...');
          await unlockAudioContext(context);
        }
        
        // Store the context references
        setAudioContext(context);
        audioContextRef.current = context;
        
        // Create a new recorder with the audio context
        console.log('DEBUG: Creating recorder instance...');
        const newRecorder = new Recorder(context);
        
        // Connect the recorder to the stream
        console.log('DEBUG: Initializing recorder with stream...');
        await newRecorder.init(audioStream);
        console.log('DEBUG: Recorder initialized successfully');
        
        // Store the recorder references
        setRecorder(newRecorder);
        recorderRef.current = newRecorder;
        
        console.log('DEBUG: Audio recording setup complete');
        return true;
      } catch (contextError) {
        console.error('DEBUG: Error with audio context:', contextError);
        
        // Try to release the stream since we failed
        if (streamRef.current) {
          streamRef.current.getTracks().forEach(track => track.stop());
        }
        
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
      } else if (err.name === 'SecurityError') {
        setError('Security error accessing microphone. Try using HTTPS.');
      } else {
        setError(`Error accessing microphone: ${err.message}`);
      }
      
      return false;
    } finally {
      setIsInitializing(false);
    }
  }, [isInitializing, unlockAudioContext]);

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
        
        const unlocked = await unlockAudioContext(currentContext);
        
        if (!unlocked) {
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
        
        // Try to re-initialize on certain errors
        if (startError.name === 'InvalidStateError') {
          // Recorder might be in a bad state - reinitialize
          console.log('DEBUG: Recorder in invalid state, attempting to reinitialize...');
          
          // Clean up existing resources
          if (currentRecorder) {
            console.log('DEBUG: Cleaning up existing recorder');
            recorderRef.current = null;
            setRecorder(null);
          }
          
          // Try to initialize again
          const reInitialized = await initRecording();
          if (reInitialized) {
            console.log('DEBUG: Successfully reinitialized, trying to start again');
            await recorderRef.current.start();
            setIsRecording(true);
            setAudioData(null);
            return true;
          }
        }
        
        setError(`Recording failed to start: ${startError.message}`);
        return false;
      }
    } catch (err) {
      console.error('DEBUG: General error in startRecording:', err);
      setError(`Could not start recording: ${err.message}`);
      return false;
    }
  }, [recorder, audioContext, initRecording, unlockAudioContext]);

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
      
      // Add detailed debug info about the audio quality
      console.log('DEBUG: Audio blob size:', blob.size, 'bytes');
      console.log('DEBUG: Audio duration:', currentRecorder.duration || 'unknown', 'seconds');
      
      // Log potentially silent recordings
      if (blob.size < 1000) {
        console.warn('DEBUG: WARNING - Audio blob is very small, might be silent or corrupt');
      }
      
      // Analyze audio buffer amplitude if available
      if (buffer && buffer.length > 0 && buffer[0] && buffer[0].length > 0) {
        const channel = buffer[0];
        let maxAmplitude = 0;
        let sumAmplitude = 0;
        
        // Sample the buffer to find max and average amplitude
        for (let i = 0; i < channel.length; i += 100) {
          const amplitude = Math.abs(channel[i] || 0);
          maxAmplitude = Math.max(maxAmplitude, amplitude);
          sumAmplitude += amplitude;
        }
        
        const avgAmplitude = sumAmplitude / (channel.length / 100);
        console.log('DEBUG: Audio max amplitude:', maxAmplitude, 'avg amplitude:', avgAmplitude);
        
        if (maxAmplitude < 0.01) {
          console.warn('DEBUG: WARNING - Audio appears to be mostly silent (max amplitude < 0.01)');
        }
      }
      
      setIsRecording(false);
      setAudioData({ blob, buffer });
      return { blob, buffer };
    } catch (err) {
      console.error('DEBUG: Error stopping recording:', err);
      setError(`Error stopping recording: ${err.message}`);
      setIsRecording(false); // Force recording state to false
      return null;
    }
  }, [recorder, isRecording]);

  // Convert audio blob to base64
  const getAudioBase64 = useCallback(async (audioBlob) => {
    return new Promise((resolve, reject) => {
      console.log('DEBUG: Converting audio blob to base64, size:', audioBlob.size);
      
      // Log audio blob type and create a URL for debugging
      console.log('DEBUG: Audio MIME type:', audioBlob.type);
      const blobUrl = URL.createObjectURL(audioBlob);
      console.log('DEBUG: Temporary blob URL (for debugging):', blobUrl);
      
      const reader = new FileReader();
      reader.onloadend = () => {
        // Extract the base64 data from the result
        // The result is like "data:audio/wav;base64,UklGRiXiAABXQVZF..."
        const base64Data = reader.result.split(',')[1];
        console.log('DEBUG: Converted blob to base64, length:', base64Data?.length);
        
        // Add validation check for the base64 data
        if (!base64Data || base64Data.length < 100) {
          console.error('DEBUG: Generated base64 data is too small or missing');
        }
        
        // Log first and last few characters of base64
        if (base64Data) {
          console.log('DEBUG: Base64 prefix:', base64Data.substring(0, 50));
          console.log('DEBUG: Base64 suffix:', base64Data.substring(base64Data.length - 50));
        }
        
        resolve(reader.result); // Return full data URI instead of just base64 part
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
      try {
        currentRecorder.cancel();
        console.log('DEBUG: Recording cancelled');
      } catch (err) {
        console.error('DEBUG: Error cancelling recording:', err);
      }
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
      
      // Check if any devices have labels (indicates permission was granted)
      const hasLabels = audioDevices.some(device => device.label && device.label.length > 0);
      console.log('DEBUG: Device labels available:', hasLabels);
      
      return true;
    } catch (err) {
      console.error('DEBUG: Error checking permission status:', err);
      setError(`Error checking microphone access: ${err.message}`);
      return false;
    }
  }, []);

  // Reset the audio recorder (useful after errors)
  const resetRecorder = useCallback(async () => {
    console.log('DEBUG: Resetting audio recorder');
    
    // Stop any active tracks
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
    
    // Close audio context
    if (audioContextRef.current) {
      try {
        await audioContextRef.current.close();
      } catch (err) {
        console.error('DEBUG: Error closing audio context:', err);
      }
      audioContextRef.current = null;
    }
    
    // Clear state
    recorderRef.current = null;
    setStream(null);
    setRecorder(null);
    setAudioContext(null);
    setIsRecording(false);
    setError(null);
    
    return true;
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
    checkPermissionStatus,
    resetRecorder,
    isMobileDevice: isMobile.current
  };
};

export default useAudioRecorder; 