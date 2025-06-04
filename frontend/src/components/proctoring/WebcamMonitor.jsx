import React, { useEffect, useState } from 'react';
import {
  Box,
  VStack,
  HStack,
  Button,
  Text,
  Badge,
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription,
  Select,
  Switch,
  FormControl,
  FormLabel,
  Progress,
  useToast,
} from '@chakra-ui/react';
import { FaVideo, FaVideoSlash, FaCog, FaEye, FaEyeSlash } from 'react-icons/fa';
import { useCamera } from '../../hooks/useCamera';
import { useProctoringWebSocket } from '../../hooks/useProctoringWebSocket';
import FaceAuthenticationManager from './FaceAuthenticationManager';

/**
 * WebcamMonitor component for proctoring
 * Provides webcam access, face detection, and real-time monitoring
 */
const WebcamMonitor = ({ 
  sessionId, 
  userId, 
  isEnabled = false,
  onStatusChange = () => {},
  onEventGenerated = () => {},
  initialEmbedding,
  videoRef: externalVideoRef,
}) => {
  const toast = useToast();
  const [showControls, setShowControls] = useState(false);
  const [isMonitoringActive, setIsMonitoringActive] = useState(false);

  // Camera hook
  const {
    stream,
    devices,
    selectedDeviceId,
    isLoading: cameraLoading,
    error: cameraError,
    permissionGranted,
    isActive: cameraIsActive,
    startCamera,
    stopCamera,
    switchCamera,
    isSupported: cameraSupported,
  } = useCamera();

  // WebSocket hook
  const {
    connectionStatus,
    error: wsError,
    alerts,
    isConnected: wsConnected,
    sendEvent,
  } = useProctoringWebSocket(sessionId, userId, isMonitoringActive && isEnabled);

  // Combined loading state
  const isLoading = cameraLoading;

  // Combined error state
  const combinedError = cameraError || wsError;

  // Effect to manage the stream on the external video ref
  useEffect(() => {
    console.log('[WebcamMonitor] External video ref effect triggered. Stream available:', !!stream, 'Camera isActive:', cameraIsActive, 'externalVideoRef.current available:', !!externalVideoRef?.current);
    if (externalVideoRef && externalVideoRef.current) {
      if (stream && cameraIsActive) {
        if (externalVideoRef.current.srcObject !== stream) {
          console.log('[WebcamMonitor] Attaching stream to externalVideoRef.current');
          externalVideoRef.current.srcObject = stream;
          externalVideoRef.current.playsInline = true; 
          externalVideoRef.current.autoplay = true; 
          externalVideoRef.current.muted = true; 
          externalVideoRef.current.play().then(() => {
            console.log('[WebcamMonitor] externalVideoRef.current.play() successful');
          }).catch(e => console.warn("[WebcamMonitor] Error playing external video ref:", e));
        } else {
          console.log('[WebcamMonitor] Stream already attached to externalVideoRef or no change needed.');
        }
      } else {
        console.log('[WebcamMonitor] Stream not available or camera not active for externalVideoRef. Not attaching/clearing stream.');
        // Consider if srcObject should be cleared here if we are solely responsible for it.
        // externalVideoRef.current.srcObject = null; // Example if needed
      }
    } else {
      console.log('[WebcamMonitor] externalVideoRef or externalVideoRef.current is not available.');
    }
  }, [stream, cameraIsActive, externalVideoRef]);

  const handleFaceAuthEvent = (event) => {
    onEventGenerated(event); // Pass all events up to ProctoringPanel -> InterviewPage

    let newStatus = {
        isActive: isMonitoringActive && isEnabled,
        hasCamera: cameraIsActive,
        hasDetection: false, // Default, will be updated based on event
        hasWebSocket: wsConnected,
    };

    switch (event.type) {
        case 'enrollment_resumed':
        case 'authentication_success':
        case 'system_ready': // Assuming this means detection models are loaded and ready
            newStatus.hasDetection = true;
            break;
        case 'enrollment_failed': // Should not happen here as showEnrollmentUI is false
        case 'authentication_failed':
            newStatus.hasDetection = false; // Or reflect last known good state?
      toast({
                title: `Auth: ${event.type.replace('_', ' ')}`,
                description: event.message || 'An issue occurred with face authentication.',
                status: 'warning',
        duration: 3000,
        isClosable: true,
      });
            break;
        case 'error': // General errors from useFaceAuthentication
            newStatus.hasDetection = false;
      toast({
                title: `Face Auth Error: ${event.context || 'General'}`,
                description: event.message || 'An error occurred.',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
            break;
        default:
            // For other events, we might not change hasDetection status immediately
            // or we can infer it if needed.
            // Check if there was a prior success to keep hasDetection true
            if (onStatusChange.currentStatus && onStatusChange.currentStatus.hasDetection) {
                 newStatus.hasDetection = true; // Maintain if previously true and event isn't a hard failure
            }
            break;
    }
    onStatusChange(newStatus); // Update overall status in ProctoringPanel
  };

  // Initial status update and effect for onStatusChange prop
  useEffect(() => {
    const currentOverallStatus = {
        isActive: isMonitoringActive && isEnabled && cameraIsActive,
        hasCamera: cameraIsActive,
        // hasDetection is now primarily driven by FaceAuthenticationManager events
        // For an initial state, if we have an embedding, we can assume detection will attempt to be active.
        hasDetection: !!initialEmbedding, 
        hasWebSocket: wsConnected,
    };
    onStatusChange(currentOverallStatus);
  }, [isMonitoringActive, isEnabled, cameraIsActive, wsConnected, initialEmbedding, onStatusChange]);

  // Start/Stop Monitoring Logic (Camera part)
  useEffect(() => {
    console.log(`[WebcamMonitor] Enable/Camera Activation effect triggered. isEnabled: ${isEnabled}, cameraIsActive: ${cameraIsActive}, selectedDeviceId: ${selectedDeviceId}`);
    if (isEnabled) {
      if (!cameraIsActive) {
        console.log("[WebcamMonitor] isEnabled is TRUE and camera is NOT active. Calling startCamera...");
        startCamera(selectedDeviceId).then(() => {
            console.log("[WebcamMonitor] call to startCamera() in WebcamMonitor SUCCEEDED.");
            setIsMonitoringActive(true); 
        }).catch(err => {
            console.error("[WebcamMonitor] call to startCamera() in WebcamMonitor FAILED:", err);
            toast({ title: 'Camera Start Error', description: err.message || 'Failed to start camera.', status: 'error' });
            setIsMonitoringActive(false);
        });
      } else {
         console.log("[WebcamMonitor] isEnabled is TRUE and camera is ALREADY active. Ensuring isMonitoringActive is true.");
         setIsMonitoringActive(true);
      }
    } else { // isEnabled is false
      if (cameraIsActive || isMonitoringActive) {
        console.log("[WebcamMonitor] isEnabled is FALSE. Stopping camera and local monitoring state.");
        stopCamera();
        setIsMonitoringActive(false);
      } else {
        console.log("[WebcamMonitor] isEnabled is FALSE and camera/monitoring is already inactive.");
      }
    }
  // We remove permissionGranted from this dependency array as startCamera itself will handle it.
  // cameraIsActive is important to prevent re-calling startCamera if it's already active.
  }, [isEnabled, cameraIsActive, selectedDeviceId, startCamera, stopCamera, toast]);

  const getStatusColor = () => {
    if (combinedError) return 'red'; // General error (camera, ws)
    if (isLoading) return 'yellow'; // Camera loading
    // Status of FaceAuthenticationManager will be handled via its own UI elements / events
    if (isMonitoringActive && cameraIsActive && wsConnected && initialEmbedding) return 'green'; // Fully active with enrollment
    if (isMonitoringActive && cameraIsActive) return 'orange'; // Active but maybe no WS or no enrollment yet
    return 'gray'; // Inactive
  };

  const getStatusText = () => {
    if (combinedError) return `Error: ${combinedError.split('.')[0]}`;
    if (isLoading) return 'Camera Loading...';
    if (isMonitoringActive && cameraIsActive && wsConnected && initialEmbedding) return 'Monitoring Active';
    if (isMonitoringActive && cameraIsActive && !initialEmbedding) return 'Enrollment Pending';
    if (isMonitoringActive && cameraIsActive) return 'Camera Active';
    return 'Inactive';
  };

  // Check browser support
  if (!cameraSupported) {
    return (
      <Alert status="error">
        <AlertIcon />
        <AlertTitle>Browser Not Supported</AlertTitle>
        <AlertDescription>
          Your browser doesn't support webcam access.
          Please use a modern browser like Chrome, Firefox, or Edge.
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <Box bg="gray.50" p={4} borderRadius="md" border="1px" borderColor="gray.200">
      <VStack spacing={4} align="stretch">
        {/* Header */}
        <HStack justify="space-between">
          <HStack spacing={2}>
            <FaEye color={isMonitoringActive && isEnabled ? 'green' : 'gray'} />
            <Text fontSize="lg" fontWeight="bold">
              Webcam Monitor
            </Text>
            <Badge colorScheme={getStatusColor()}>
              {getStatusText()}
            </Badge>
          </HStack>
          
          <HStack spacing={2}>
            <Button
              size="sm"
              variant="outline"
              leftIcon={<FaCog />}
              onClick={() => setShowControls(!showControls)}
            >
              Settings
            </Button>
            
            <Button
              size="sm"
              colorScheme={isMonitoringActive && isEnabled ? 'red' : 'green'}
              leftIcon={isMonitoringActive && isEnabled ? <FaVideoSlash /> : <FaVideo />}
              onClick={() => {
                  // This button should reflect the parent `isEnabled` state or be removed if Interview.js controls this.
                  // For now, let's assume it toggles the local desire to monitor, which then respects `isEnabled`.
                  if (isMonitoringActive) {
                      stopCamera(); // This will also trigger useEffect to set isMonitoringActive to false
                      setIsMonitoringActive(false);
                  } else if (isEnabled) {
                      startCamera(selectedDeviceId).then(() => setIsMonitoringActive(true)).catch(e => toast({title: 'Error', description: e.message, status: 'error'}));
                  } else {
                      toast({title: 'Info', description: 'Proctoring is currently disabled for the interview.', status: 'info'});
                  }
              }}
              isDisabled={isLoading || !permissionGranted} // Disable if loading or no permission
              loadingText={isLoading ? (isMonitoringActive ? 'Stopping...' : 'Starting...') : undefined}
            >
              {isMonitoringActive && isEnabled ? 'Stop Monitor' : 'Start Monitor'}
            </Button>
          </HStack>
        </HStack>

        {/* Error Display */}
        {combinedError && (
          <Alert status="error">
            <AlertIcon />
            <AlertDescription>{combinedError}</AlertDescription>
          </Alert>
        )}

        {/* Video Display - THIS ENTIRE BLOCK WILL BE REMOVED */}
        {/* {isEnabled && (
          <>
            <Box 
              id="webcam-monitor-video-container"
              width="100%"
              bg="black" 
              borderRadius="md" 
              position="relative"
              minHeight="240px" 
              sx={{ '& video': { width: '100% !important', height: 'auto !important', borderRadius: 'md' } }}
            >
              {cameraIsActive ? 
                (<Text position="absolute" top="2" left="2" color="white" fontSize="xs" bg="blackAlpha.600" p="1" borderRadius="sm">Camera Feed</Text>) : 
                (<Text textAlign="center" p="4">Camera not active or not started.</Text>)
              }
            </Box>

            {cameraError && (
              <Alert status="error" mt={2}>
                <AlertIcon />
                <AlertTitle>Camera Error</AlertTitle>
                <AlertDescription>{cameraError}</AlertDescription>
              </Alert>
            )}
            
            {isMonitoringActive && initialEmbedding && cameraIsActive && isEnabled && (
              <FaceAuthenticationManager
                videoRef={externalVideoRef} 
                isActive={isMonitoringActive && isEnabled} 
                onAuthenticationEvent={handleFaceAuthEvent}
                showEnrollmentUI={false} 
                initialEmbedding={initialEmbedding} 
                initialSessionId={sessionId}    
              />
            )}
             {!initialEmbedding && isEnabled && isMonitoringActive && (
                <Alert status="warning" mt={2}>
                    <AlertIcon />
                    <AlertTitle>Face Not Enrolled</AlertTitle>
                    <AlertDescription>
                        Face enrollment was not completed. Continuous authentication is disabled.
                    </AlertDescription>
                </Alert>
            )}
          </>
        )} */}
        {/* END OF BLOCK TO BE REMOVED */}
        
        {/* The FaceAuthenticationManager and related alerts should remain, but not the video box itself */}
        {isEnabled && (
          <>
            {cameraError && (
              <Alert status="error" mt={2}>
                <AlertIcon />
                <AlertTitle>Camera Error</AlertTitle>
                <AlertDescription>{cameraError}</AlertDescription>
              </Alert>
            )}
            
            {isMonitoringActive && initialEmbedding && cameraIsActive && isEnabled && (
              <FaceAuthenticationManager
                videoRef={externalVideoRef} 
                isActive={isMonitoringActive && isEnabled} 
                onAuthenticationEvent={handleFaceAuthEvent}
                showEnrollmentUI={false} 
                initialEmbedding={initialEmbedding} 
                initialSessionId={sessionId}    
              />
            )}
             {!initialEmbedding && isEnabled && isMonitoringActive && !cameraError && ( // Added !cameraError here
                <Alert status="warning" mt={2}>
                    <AlertIcon />
                    <AlertTitle>Face Not Enrolled</AlertTitle>
                    <AlertDescription>
                        Face enrollment was not completed. Continuous authentication is disabled.
                    </AlertDescription>
                </Alert>
            )}
          </>
        )}
         {!isEnabled && (
          <Text color="gray.500" textAlign="center" p={4}>Webcam monitoring is currently disabled by the interview controller.</Text>
        )}

        {/* Controls */}
        {showControls && (
          <VStack spacing={3} align="stretch" bg="white" p={3} borderRadius="md">
            {/* Camera Selection */}
            {devices.length > 1 && (
              <FormControl>
                <FormLabel fontSize="sm">Camera Device</FormLabel>
                <Select
                  size="sm"
                  value={selectedDeviceId}
                  onChange={(e) => switchCamera(e.target.value)}
                >
                  {devices.map((device) => (
                    <option key={device.deviceId} value={device.deviceId}>
                      {device.label || `Camera ${device.deviceId.slice(0, 8)}`}
                    </option>
                  ))}
                </Select>
              </FormControl>
            )}

            {/* Monitoring Toggle */}
            <FormControl display="flex" alignItems="center">
              <FormLabel htmlFor="monitoring-switch" mb="0" fontSize="sm">
                Auto-monitoring
              </FormLabel>
              <Switch
                id="monitoring-switch"
                isChecked={isMonitoringActive}
                onChange={(e) => e.target.checked ? startCamera(selectedDeviceId).then(() => setIsMonitoringActive(true)) : stopCamera()}
                colorScheme="green"
              />
            </FormControl>
          </VStack>
        )}

        {/* Recent Alerts */}
        {alerts.length > 0 && (
          <VStack spacing={2} align="stretch">
            <Text fontSize="sm" fontWeight="bold" color="orange.600">
              Recent Alerts ({alerts.length})
            </Text>
            {alerts.slice(-3).map((alert) => (
              <Alert key={alert.id} status="warning" size="sm">
                <AlertIcon />
                <AlertDescription fontSize="sm">
                  {alert.message}
                </AlertDescription>
              </Alert>
            ))}
          </VStack>
        )}
      </VStack>
    </Box>
  );
};

export default WebcamMonitor; 