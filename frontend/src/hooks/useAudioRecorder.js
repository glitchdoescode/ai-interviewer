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
      
      console.log('Requesting microphone permission...');
      
      // Request user permission to access the microphone
      const audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      setStream(audioStream);
      setPermissionGranted(true);
      
      console.log('Microphone permission granted, creating audio context...');
      
      // Create an audio context
      const context = new (window.AudioContext || window.webkitAudioContext)();
      
      // Ensure the context is running
      if (context.state !== 'running') {
        await context.resume();
      }
      
      setAudioContext(context);
      console.log(`AudioContext created and state is: ${context.state}`);
      
      // Create a new recorder with the audio context
      const newRecorder = new Recorder(context);

      // Connect the recorder to the stream
      await newRecorder.init(audioStream);
      setRecorder(newRecorder);
      
      console.log('Audio recording initialized successfully');
      return true;
    } catch (err) {
      console.error('Error initializing audio recording:', err);
      
      // Provide specific error messages based on the error type
      if (err.name === 'NotAllowedError') {
        setError('Microphone permission denied. Please allow access in your browser settings.');
      } else if (err.name === 'NotFoundError') {
        setError('No microphone detected. Please check your device settings.');
      } else if (err.name === 'AbortError') {
        setError('Recording permission request was aborted. Please try again.');
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
      
      // Initialize recording if needed
      if (!recorder || !audioContext) {
        console.log('Recorder not initialized, initializing...');
        const initialized = await initRecording();
        if (!initialized) {
          return false;
        }
        
        // Need a brief pause after initialization
        await new Promise(resolve => setTimeout(resolve, 300));
      }
      
      // Ensure audio context is running
      if (audioContext.state !== 'running') {
        console.log('Resuming audio context...');
        await audioContext.resume();
        
        // Wait for resume to take effect
        await new Promise(resolve => setTimeout(resolve, 100));
        
        if (audioContext.state !== 'running') {
          setError('Could not activate audio context. Please try clicking the button again.');
          return false;
        }
      }
      
      // Start recording
      console.log('Starting recorder...');
      await recorder.start();
      setIsRecording(true);
      setAudioData(null);
      console.log('Recording started successfully.');
      return true;
    } catch (err) {
      console.error('Error starting recording:', err);
      setError(`Could not start recording: ${err.message}`);
      return false;
    }
  }, [recorder, audioContext, initRecording]);

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
  
  // Check permission status
  const checkPermissionStatus = useCallback(async () => {
    try {
      const devices = await navigator.mediaDevices.enumerateDevices();
      const audioDevices = devices.filter(device => device.kind === 'audioinput');
      
      if (audioDevices.length === 0) {
        setError('No audio input devices found.');
        return false;
      }
      
      return true;
    } catch (err) {
      console.error('Error checking permission status:', err);
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