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
    try {
      // Reset any previous errors
      setError(null);
      
      // If recorder doesn't exist, initialize it first
      if (!recorder) {
        console.log('No recorder found, initializing first...');
        const initialized = await initRecording();
        if (!initialized) {
          console.log('Failed to initialize recording');
          return false;
        }
        
        // After initialization, wait until next tick to start recording
        return new Promise(resolve => {
          setTimeout(async () => {
            try {
              // Get the current recorder from state
              const currentRecorder = recorder;
              const currentContext = audioContext;
              
              // Double-check we have what we need
              if (!currentRecorder) {
                if (initializationAttempts.current < 3) {
                  console.log('Recorder not ready yet, trying again...');
                  initializationAttempts.current += 1;
                  const success = await startRecording();
                  resolve(success);
                  return;
                } else {
                  throw new Error('Recorder initialization failed after multiple attempts');
                }
              }
              
              if (!currentContext || currentContext.state !== 'running') {
                console.log('AudioContext not running, attempting to resume...');
                if (currentContext) {
                  await currentContext.resume();
                  // Wait for context to fully resume
                  await new Promise(r => setTimeout(r, 500));
                } else {
                  throw new Error('AudioContext not initialized');
                }
              }
              
              // Now we can start recording
              console.log('Starting recording with new recorder');
              recorder.start();
              setIsRecording(true);
              setAudioData(null);
              resolve(true);
            } catch (startErr) {
              console.error('Error starting recorder after init:', startErr);
              setError(`Error starting recording: ${startErr.message}`);
              resolve(false);
            }
          }, 800); // Increased delay to ensure state updates have completed
        });
      }
      
      // If recorder already exists, use it directly
      if (recorder) {
        try {
          console.log('Using existing recorder');
          // Make sure AudioContext is running
          if (audioContext && audioContext.state !== 'running') {
            console.log('Resuming AudioContext...');
            await audioContext.resume();
            // Add a small delay after resuming context
            await new Promise(resolve => setTimeout(resolve, 500));
          }
          
          console.log('Starting recording...');
          recorder.start();
          setIsRecording(true);
          setAudioData(null);
          return true;
        } catch (err) {
          console.error('Error starting existing recorder:', err);
          setError(`Error starting recording: ${err.message}`);
          
          // If starting fails with existing recorder, try to create a new one
          console.log('Recreating recorder...');
          setRecorder(null);
          setAudioContext(null);
          initializationAttempts.current = 0;
          return startRecording(); // Recursive call will go through the initialization path
        }
      }
      
      return false;
    } catch (err) {
      console.error('Error in startRecording:', err);
      setError(`Error starting recording: ${err.message}`);
      return false;
    }
  }, [recorder, initRecording, audioContext]);

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