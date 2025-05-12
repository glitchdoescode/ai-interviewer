import { useState, useEffect, useCallback } from 'react';
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
      setError(null);
      
      // Request user permission to access the microphone
      const audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      setStream(audioStream);
      
      // Create an audio context
      let context;
      try {
        context = new (window.AudioContext || window.webkitAudioContext)();
        setAudioContext(context);
      } catch (contextError) {
        console.error('Error creating AudioContext:', contextError);
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
      return true;
    } catch (err) {
      console.error('Error initializing audio recording:', err);
      setError(`Error accessing microphone: ${err.message}`);
      return false;
    }
  }, []);

  // Start recording
  const startRecording = useCallback(async () => {
    try {
      // Reset any previous errors
      setError(null);
      
      // If recorder doesn't exist, initialize it first
      if (!recorder) {
        const initialized = await initRecording();
        if (!initialized) {
          return false;
        }
        
        // Return a new promise that will resolve after the recorder is initialized
        return new Promise(resolve => {
          // Need to delay until next render cycle when recorder state is updated
          setTimeout(() => {
            try {
              // Get the recorder from a closure as the state hasn't updated in this callback
              const recorderInstance = document.querySelector('#recorder-instance');
              
              // Instead of relying on the state, we'll check for the AudioContext status
              if (!audioContext || audioContext.state !== 'running') {
                throw new Error('AudioContext not ready or running');
              }
              
              // Instead of directly using recorder state which might not be updated yet,
              // we'll get a fresh reference through the AudioContext
              const audioCtx = audioContext;
              const recNode = audioCtx.createGain(); // Just a dummy node to verify context is working
              
              if (!stream) {
                throw new Error('Audio stream not available');
              }
              
              // Try to resume the AudioContext if it's suspended
              if (audioCtx.state === 'suspended') {
                audioCtx.resume();
              }
              
              // Manually trigger recorder init again to ensure it's connected
              const newRecorder = new Recorder(audioCtx);
              newRecorder.init(stream);
              setRecorder(newRecorder);
              
              // Start recording with the new recorder
              newRecorder.start();
              setIsRecording(true);
              setAudioData(null);
              resolve(true);
            } catch (startErr) {
              console.error('Error starting recorder after init:', startErr);
              setError(`Error starting recording: ${startErr.message}`);
              resolve(false);
            }
          }, 300); // Increased delay to ensure state updates have completed
        });
      }
      
      // If recorder already exists, use it directly
      if (recorder) {
        try {
          // Make sure AudioContext is running
          if (audioContext && audioContext.state === 'suspended') {
            await audioContext.resume();
          }
          
          recorder.start();
          setIsRecording(true);
          setAudioData(null);
          return true;
        } catch (err) {
          console.error('Error starting existing recorder:', err);
          setError(`Error starting recording: ${err.message}`);
          
          // If starting fails with existing recorder, try to create a new one
          setRecorder(null);
          return startRecording(); // Recursive call will go through the initialization path
        }
      }
      
      return false;
    } catch (err) {
      console.error('Error in startRecording:', err);
      setError(`Error starting recording: ${err.message}`);
      return false;
    }
  }, [recorder, initRecording, stream, audioContext]);

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
    initRecording,
    startRecording,
    stopRecording,
    cancelRecording,
    getAudioBase64,
  };
};

export default useAudioRecorder; 