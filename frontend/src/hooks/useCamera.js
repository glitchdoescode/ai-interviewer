import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * Custom hook for managing webcam access and camera operations
 * Provides camera stream management, device enumeration, and error handling
 */
export const useCamera = () => {
  const [stream, setStream] = useState(null);
  const [devices, setDevices] = useState([]);
  const [selectedDeviceId, setSelectedDeviceId] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [permissionGranted, setPermissionGranted] = useState(false);
  const [isActive, setIsActive] = useState(false);
  
  const videoRef = useRef(null);

  useEffect(() => {
    console.log('[useCamera] permissionGranted changed:', permissionGranted);
  }, [permissionGranted]);

  /**
   * Get available camera devices
   */
  const getDevices = useCallback(async () => {
    try {
      const mediaDevices = await navigator.mediaDevices.enumerateDevices();
      const videoDevices = mediaDevices.filter(device => device.kind === 'videoinput');
      setDevices(videoDevices);
      
      // Set default device if none selected
      if (!selectedDeviceId && videoDevices.length > 0) {
        setSelectedDeviceId(videoDevices[0].deviceId);
      }
      
      return videoDevices;
    } catch (err) {
      console.error('Error enumerating devices:', err);
      setError('Failed to get camera devices');
      return [];
    }
  }, [selectedDeviceId]);

  /**
   * Request camera permission and start stream
   */
  const startCamera = useCallback(async (deviceId = null) => {
    setIsLoading(true);
    setError(null);

    try {
      // Check if browser supports getUserMedia
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error('Camera access is not supported in this browser');
      }

      const constraints = {
        video: {
          deviceId: deviceId || selectedDeviceId || undefined,
          width: { ideal: 640 },
          height: { ideal: 480 },
          frameRate: { ideal: 15, max: 30 }
        },
        audio: false
      };

      const mediaStream = await navigator.mediaDevices.getUserMedia(constraints);
      
      setStream(mediaStream);
      console.log('[useCamera] Stream acquired and set:', mediaStream);
      setPermissionGranted(true);
      setIsActive(true);
      
      // Attach stream to video element if available
      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream;
      }

      // Get devices after permission is granted (labels will be available)
      await getDevices();
      
      return mediaStream;
    } catch (err) {
      console.error('Error starting camera:', err);
      
      let errorMessage = 'Failed to start camera';
      if (err.name === 'NotAllowedError') {
        errorMessage = 'Camera permission denied. Please allow camera access and try again.';
      } else if (err.name === 'NotFoundError') {
        errorMessage = 'No camera device found. Please connect a camera and try again.';
      } else if (err.name === 'NotReadableError') {
        errorMessage = 'Camera is already in use by another application.';
      } else if (err.name === 'OverconstrainedError') {
        errorMessage = 'Camera constraints cannot be satisfied.';
      }
      
      setError(errorMessage);
      setPermissionGranted(false);
      setIsActive(false);
      return null;
    } finally {
      setIsLoading(false);
    }
  }, [selectedDeviceId, getDevices]);

  /**
   * Stop camera stream
   */
  const stopCamera = useCallback(() => {
    if (stream) {
      stream.getTracks().forEach(track => {
        track.stop();
      });
      setStream(null);
      setIsActive(false);
      
      // Clear video element
      if (videoRef.current) {
        videoRef.current.srcObject = null;
      }
    }
  }, [stream]);

  /**
   * Switch to a different camera device
   */
  const switchCamera = useCallback(async (deviceId) => {
    if (deviceId === selectedDeviceId) return;
    
    setSelectedDeviceId(deviceId);
    
    if (isActive) {
      stopCamera();
      await startCamera(deviceId);
    }
  }, [selectedDeviceId, isActive, stopCamera, startCamera]);

  /**
   * Toggle camera on/off
   */
  const toggleCamera = useCallback(async () => {
    if (isActive) {
      stopCamera();
    } else {
      await startCamera();
    }
  }, [isActive, stopCamera, startCamera]);

  /**
   * Get current video frame as canvas
   */
  const captureFrame = useCallback(() => {
    if (!videoRef.current || !isActive) return null;
    
    const video = videoRef.current;
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('2d');
    
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    
    return canvas;
  }, [isActive]);

  /**
   * Get video frame as ImageData for processing
   */
  const getVideoFrame = useCallback(() => {
    if (!videoRef.current || !isActive) return null;
    
    const video = videoRef.current;
    const canvas = document.createElement('canvas');
    const context = canvas.getContext('2d');
    
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    
    return context.getImageData(0, 0, canvas.width, canvas.height);
  }, [isActive]);

  // Initialize devices on mount
  useEffect(() => {
    getDevices();
  }, [getDevices]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopCamera();
    };
  }, [stopCamera]);

  // Handle device changes
  useEffect(() => {
    const handleDeviceChange = () => {
      getDevices();
    };

    if (navigator.mediaDevices) {
      navigator.mediaDevices.addEventListener('devicechange', handleDeviceChange);
      
      return () => {
        navigator.mediaDevices.removeEventListener('devicechange', handleDeviceChange);
      };
    }
  }, [getDevices]);

  return {
    // State
    stream,
    devices,
    selectedDeviceId,
    isLoading,
    error,
    permissionGranted,
    isActive,
    videoRef,
    
    // Actions
    startCamera,
    stopCamera,
    switchCamera,
    toggleCamera,
    captureFrame,
    getVideoFrame,
    getDevices,
    
    // Helpers
    isSupported: !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia),
  };
}; 