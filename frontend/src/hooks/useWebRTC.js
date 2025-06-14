import { useState, useEffect, useRef, useCallback } from 'react';
import 'webrtc-adapter'; // Ensures cross-browser WebRTC compatibility

/**
 * Custom hook for managing WebRTC camera and microphone access
 * Provides camera feed, audio controls, and permission handling
 */
const useWebRTC = (initialCameraEnabled = true, initialMicEnabled = true) => {
  const [stream, setStream] = useState(null);
  const [cameraEnabled, setCameraEnabled] = useState(initialCameraEnabled);
  const [micEnabled, setMicEnabled] = useState(initialMicEnabled);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [permissionStatus, setPermissionStatus] = useState({
    camera: 'unknown', // 'granted', 'denied', 'prompt', 'unknown'
    microphone: 'unknown'
  });
  
  const streamRef = useRef(null);

  /**
   * Request camera and microphone permissions and initialize stream
   */
  const initializeMedia = useCallback(async (videoEnabled = true, audioEnabled = true) => {
    setIsLoading(true);
    setError(null);

    try {
      const constraints = {
        video: videoEnabled ? {
          width: { ideal: 1280, max: 1920 },
          height: { ideal: 720, max: 1080 },
          frameRate: { ideal: 30 },
          facingMode: 'user'
        } : false,
        audio: audioEnabled ? {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          sampleRate: 44100
        } : false
      };

      const mediaStream = await navigator.mediaDevices.getUserMedia(constraints);
      
      // Store reference for cleanup
      streamRef.current = mediaStream;
      setStream(mediaStream);
      
      // Update permission status
      setPermissionStatus({
        camera: videoEnabled ? 'granted' : 'unknown',
        microphone: audioEnabled ? 'granted' : 'unknown'
      });

      // Set initial track states
      if (mediaStream.getVideoTracks().length > 0) {
        mediaStream.getVideoTracks()[0].enabled = cameraEnabled;
      }
      if (mediaStream.getAudioTracks().length > 0) {
        mediaStream.getAudioTracks()[0].enabled = micEnabled;
      }

    } catch (err) {
      console.error('Error accessing media devices:', err);
      
      // Handle specific error types
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        setPermissionStatus({
          camera: 'denied',
          microphone: 'denied'
        });
        setError('Camera and microphone access denied. Please grant permissions to continue.');
      } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
        setError('No camera or microphone found. Please check your device connections.');
      } else if (err.name === 'NotReadableError' || err.name === 'TrackStartError') {
        setError('Camera or microphone is already in use by another application.');
      } else {
        setError(`Media access error: ${err.message}`);
      }
    } finally {
      setIsLoading(false);
    }
  }, [cameraEnabled, micEnabled]);

  /**
   * Toggle camera on/off
   */
  const toggleCamera = useCallback(() => {
    if (streamRef.current) {
      const videoTracks = streamRef.current.getVideoTracks();
      if (videoTracks.length > 0) {
        const newEnabled = !cameraEnabled;
        videoTracks[0].enabled = newEnabled;
        setCameraEnabled(newEnabled);
      }
    }
  }, [cameraEnabled]);

  /**
   * Toggle microphone on/off
   */
  const toggleMicrophone = useCallback(() => {
    if (streamRef.current) {
      const audioTracks = streamRef.current.getAudioTracks();
      if (audioTracks.length > 0) {
        const newEnabled = !micEnabled;
        audioTracks[0].enabled = newEnabled;
        setMicEnabled(newEnabled);
      }
    }
  }, [micEnabled]);

  /**
   * Stop all media tracks and cleanup
   */
  const stopMedia = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => {
        track.stop();
      });
      streamRef.current = null;
      setStream(null);
    }
  }, []);

  /**
   * Get audio level for visualization
   */
  const getAudioLevel = useCallback(() => {
    if (!streamRef.current) return 0;
    
    const audioTracks = streamRef.current.getAudioTracks();
    if (audioTracks.length === 0) return 0;

    // This is a simplified audio level detection
    // In a real implementation, you would use Web Audio API for more accurate measurements
    return audioTracks[0].enabled ? Math.random() * 0.5 + 0.1 : 0;
  }, []);

  /**
   * Check if devices are available
   */
  const checkDeviceAvailability = useCallback(async () => {
    try {
      const devices = await navigator.mediaDevices.enumerateDevices();
      const hasCamera = devices.some(device => device.kind === 'videoinput');
      const hasMicrophone = devices.some(device => device.kind === 'audioinput');
      
      return { hasCamera, hasMicrophone };
    } catch (err) {
      console.error('Error checking device availability:', err);
      return { hasCamera: false, hasMicrophone: false };
    }
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopMedia();
    };
  }, [stopMedia]);

  // Auto-initialize media on mount if permissions are likely to be granted
  useEffect(() => {
    const autoInit = async () => {
      try {
        // Check if we can query permissions
        if ('permissions' in navigator) {
          const cameraPermission = await navigator.permissions.query({ name: 'camera' });
          const micPermission = await navigator.permissions.query({ name: 'microphone' });
          
          if (cameraPermission.state === 'granted' && micPermission.state === 'granted') {
            initializeMedia(true, true);
          }
        }
      } catch (err) {
        // Permissions API might not be available, skip auto-init
        console.log('Permissions API not available, manual initialization required');
      }
    };

    autoInit();
  }, [initializeMedia]);

  return {
    // State
    stream,
    cameraEnabled,
    micEnabled,
    isLoading,
    error,
    permissionStatus,
    
    // Methods
    initializeMedia,
    toggleCamera,
    toggleMicrophone,
    stopMedia,
    getAudioLevel,
    checkDeviceAvailability,
    
    // Computed values
    hasVideo: stream && stream.getVideoTracks().length > 0,
    hasAudio: stream && stream.getAudioTracks().length > 0,
    isActive: stream !== null
  };
};

export default useWebRTC; 
 
 