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

  // Initialize the recorder when the component mounts
  useEffect(() => {
    // Clean up function for when the component unmounts
    return () => {
      if (stream) {
        // Stop all audio tracks
        stream.getTracks().forEach(track => track.stop());
      }
    };
  }, [stream]);

  // Initialize audio recording
  const initRecording = useCallback(async () => {
    try {
      setError(null);
      // Request user permission to access the microphone
      const audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      
      // Create an audio context
      const audioContext = new (window.AudioContext || window.webkitAudioContext)();
      
      // Create a new recorder with the audio context
      const newRecorder = new Recorder(audioContext, {
        onAnalysed: data => {
          // You can use this callback to visualize the audio data
          // console.log('Audio data:', data);
        },
      });

      // Connect the recorder to the stream
      newRecorder.init(audioStream);
      
      // Save the recorder and stream in state
      setRecorder(newRecorder);
      setStream(audioStream);
      return true;
    } catch (err) {
      console.error('Error initializing audio recording:', err);
      setError(`Error accessing microphone: ${err.message}`);
      return false;
    }
  }, []);

  // Start recording
  const startRecording = useCallback(async () => {
    if (!recorder) {
      const initialized = await initRecording();
      if (!initialized) return false;
    }

    try {
      recorder.start();
      setIsRecording(true);
      setAudioData(null);
      return true;
    } catch (err) {
      console.error('Error starting recording:', err);
      setError(`Error starting recording: ${err.message}`);
      return false;
    }
  }, [recorder, initRecording]);

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