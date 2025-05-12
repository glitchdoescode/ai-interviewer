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
  const initializationAttempts = useRef(0);

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

  // Initialize audio recording
  const initRecording = useCallback(async () => {
    try {
      // Prevent multiple initializations running simultaneously
      if (isInitializing) {
        console.log('Already initializing audio...');
        return false;
      }

      setIsInitializing(true);
      setError(null);
      initializationAttempts.current += 1;
      console.log(`Initializing audio recording (attempt ${initializationAttempts.current})...`);
      
      // Request user permission to access the microphone
      const audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      setStream(audioStream);
      setPermissionGranted(true);
      
      // Create an audio context
      let context;
      try {
        context = new (window.AudioContext || window.webkitAudioContext)();
        
        // Ensure the context is running
        if (context.state !== 'running') {
          await context.resume();
        }
        
        setAudioContext(context);
        console.log(`AudioContext created and state is: ${context.state}`);
      } catch (contextError) {
        console.error('Error creating AudioContext:', contextError);
        setIsInitializing(false);
        throw new Error(`Could not create audio context: ${contextError.message}`);
      }
      
      // Create a new recorder with the audio context
      const newRecorder = new Recorder(context, {
        onAnalysed: data => {
          // You can use this callback to visualize the audio data
          // console.log('Audio data:', data);
        },
      });

      // Connect the recorder to the stream
      await newRecorder.init(audioStream);
      
      // Save the recorder in state
      setRecorder(newRecorder);
      setIsInitializing(false);
      console.log('Audio recording initialized successfully');
      return true;
    } catch (err) {
      console.error('Error initializing audio recording:', err);
      setError(`Error accessing microphone: ${err.message}`);
      setIsInitializing(false);
      return false;
    }
  }, [isInitializing]);

  // Start recording
  const startRecording = useCallback(async () => {
    setIsInitializing(true); // Indicate initialization/start process
    setError(null);
    initializationAttempts.current = 0;

    try {
      let currentRecorder = recorder;
      let currentContext = audioContext;

      // Loop to handle initialization and context resuming
      while (initializationAttempts.current < 3) {
        initializationAttempts.current++;
        console.log(`Attempt ${initializationAttempts.current} to start recording...`);

        // 1. Initialize if necessary
        if (!currentRecorder || !currentContext) {
          console.log('Recorder or context missing, running initRecording...');
          const initialized = await initRecording();
          if (!initialized) {
            console.log('Initialization failed during start attempt.');
            setError(prev => prev || 'Failed to initialize audio system.');
            continue; // Try again if attempts remain
          }
          // Re-fetch state after initialization
          currentRecorder = recorder;
          currentContext = audioContext;
          // Need a brief pause after initialization for state propagation
          await new Promise(resolve => setTimeout(resolve, 300));
        }

        // 2. Ensure context is running
        if (currentContext && currentContext.state !== 'running') {
          console.log(`AudioContext state is ${currentContext.state}, attempting to resume...`);
          try {
            await currentContext.resume();
            // Wait for resume to potentially take effect
            await new Promise(resolve => setTimeout(resolve, 500)); 
            console.log(`AudioContext state after resume attempt: ${currentContext.state}`);
            if (currentContext.state !== 'running') {
              setError('Failed to resume AudioContext. Please interact with the page and try again.');
              continue; // Try again if attempts remain
            }
          } catch (resumeError) {
            console.error('Error resuming AudioContext:', resumeError);
            setError(`Error resuming audio context: ${resumeError.message}`);
            continue; // Try again if attempts remain
          }
        }

        // 3. Try starting the recorder
        if (currentRecorder && currentContext && currentContext.state === 'running') {
          try {
            console.log('Attempting to start recorder...');
            await currentRecorder.start();
            setIsRecording(true);
            setAudioData(null);
            setIsInitializing(false);
            console.log('Recording started successfully.');
            return true; // Success!
          } catch (startError) {
            console.error(`Error starting recorder on attempt ${initializationAttempts.current}:`, startError);
            setError(`Error starting recording: ${startError.message}`);
            // Reset recorder for next attempt
            setRecorder(null);
            setAudioContext(null);
            currentRecorder = null;
            currentContext = null;
            await new Promise(resolve => setTimeout(resolve, 200)); // Brief pause before retrying
          }
        } else {
           console.log('Conditions not met for starting recorder, retrying...');
           // Reset if context didn't resume or recorder didn't init
           setRecorder(null);
           setAudioContext(null);
           currentRecorder = null;
           currentContext = null;
           await new Promise(resolve => setTimeout(resolve, 200));
        }
      }

      // If loop finishes without success
      console.error('Failed to start recording after multiple attempts.');
      setError(prev => prev || 'Could not start recording after multiple attempts. Please check permissions or refresh the page.');
      setIsInitializing(false);
      return false;

    } catch (err) {
      console.error('Unexpected error in startRecording:', err);
      setError(`Unexpected error: ${err.message}`);
      setIsInitializing(false);
      return false;
    }
  }, [recorder, audioContext, initRecording]); // Dependencies updated

  // Stop recording and get the audio data
  const stopRecording = useCallback(async () => {
    if (!recorder || !isRecording) return null;

    try {
      const { blob, buffer } = await recorder.stop();
      setIsRecording(false);
      setAudioData({ blob, buffer });
      return { blob, buffer };
    } catch (err) {
      console.error('Error stopping recording:', err);
      setError(`Error stopping recording: ${err.message}`);
      return null;
    }
  }, [recorder, isRecording]);

  // Convert audio blob to base64
  const getAudioBase64 = useCallback(async (audioBlob) => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onloadend = () => {
        // Extract the base64 data from the result
        // The result is like "data:audio/wav;base64,UklGRiXiAABXQVZF..."
        const base64Data = reader.result.split(',')[1];
        resolve(base64Data);
      };
      reader.onerror = reject;
      reader.readAsDataURL(audioBlob);
    });
  }, []);

  // Cancel recording
  const cancelRecording = useCallback(() => {
    if (recorder && isRecording) {
      recorder.cancel();
      setIsRecording(false);
    }
    setAudioData(null);
  }, [recorder, isRecording]);

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
  };
};

export default useAudioRecorder; 