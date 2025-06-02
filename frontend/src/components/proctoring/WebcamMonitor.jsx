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
import { useFaceDetection } from '../../hooks/useFaceDetection';
import { useProctoringWebSocket } from '../../hooks/useProctoringWebSocket';

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
}) => {
  const toast = useToast();
  const [showControls, setShowControls] = useState(false);
  const [isMonitoring, setIsMonitoring] = useState(false);

  // Camera hook
  const {
    stream,
    devices,
    selectedDeviceId,
    isLoading: cameraLoading,
    error: cameraError,
    permissionGranted,
    isActive: cameraActive,
    videoRef,
    startCamera,
    stopCamera,
    switchCamera,
    toggleCamera,
    isSupported: cameraSupported,
  } = useCamera();

  // Face detection hook
  const {
    isLoading: detectionLoading,
    isReady: detectionReady,
    error: detectionError,
    detectionResults,
    detectionStats,
    events: detectionEvents,
    clearEvents,
    isSupported: detectionSupported,
  } = useFaceDetection(videoRef, cameraActive && isMonitoring);

  // WebSocket hook
  const {
    connectionStatus,
    error: wsError,
    alerts,
    isConnected: wsConnected,
    sendEvent,
    clearAlerts,
  } = useProctoringWebSocket(sessionId, userId, isMonitoring);

  // Combined loading state
  const isLoading = cameraLoading || detectionLoading;

  // Combined error state
  const error = cameraError || detectionError || wsError;

  /**
   * Start monitoring process
   */
  const startMonitoring = async () => {
    try {
      // Start camera first
      await startCamera();
      setIsMonitoring(true);
      
      toast({
        title: 'Proctoring Started',
        description: 'Webcam monitoring is now active',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });

      onStatusChange({ 
        isActive: true, 
        hasCamera: true, 
        hasDetection: detectionReady,
        hasWebSocket: wsConnected,
      });
    } catch (err) {
      console.error('Error starting monitoring:', err);
      toast({
        title: 'Failed to Start Monitoring',
        description: err.message || 'Could not start proctoring',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    }
  };

  /**
   * Stop monitoring process
   */
  const stopMonitoring = () => {
    stopCamera();
    setIsMonitoring(false);
    clearEvents();
    clearAlerts();
    
    toast({
      title: 'Proctoring Stopped',
      description: 'Webcam monitoring has been disabled',
      status: 'info',
      duration: 3000,
      isClosable: true,
    });

    onStatusChange({ 
      isActive: false, 
      hasCamera: false, 
      hasDetection: false,
      hasWebSocket: false,
    });
  };

  /**
   * Handle camera device change
   */
  const handleDeviceChange = (deviceId) => {
    switchCamera(deviceId);
  };

  /**
   * Get status badge color
   */
  const getStatusColor = () => {
    if (error) return 'red';
    if (isLoading) return 'yellow';
    if (isMonitoring && cameraActive && detectionReady && wsConnected) return 'green';
    if (isMonitoring) return 'orange';
    return 'gray';
  };

  /**
   * Get status text
   */
  const getStatusText = () => {
    if (error) return 'Error';
    if (isLoading) return 'Loading';
    if (isMonitoring && cameraActive && detectionReady && wsConnected) return 'Active';
    if (isMonitoring) return 'Starting';
    return 'Inactive';
  };

  // Send detection events to backend
  useEffect(() => {
    if (detectionEvents.length > 0 && wsConnected) {
      const latestEvent = detectionEvents[detectionEvents.length - 1];
      const sent = sendEvent(latestEvent);
      
      if (sent) {
        onEventGenerated(latestEvent);
      }
    }
  }, [detectionEvents, wsConnected, sendEvent, onEventGenerated]);

  // Handle enabled/disabled state
  useEffect(() => {
    if (isEnabled && !isMonitoring) {
      // Auto-start monitoring when enabled
      startMonitoring();
    } else if (!isEnabled && isMonitoring) {
      // Auto-stop monitoring when disabled
      stopMonitoring();
    }
  }, [isEnabled]); // eslint-disable-line react-hooks/exhaustive-deps

  // Check browser support
  if (!cameraSupported || !detectionSupported) {
    return (
      <Alert status="error">
        <AlertIcon />
        <AlertTitle>Browser Not Supported</AlertTitle>
        <AlertDescription>
          Your browser doesn't support webcam access or face detection.
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
            <FaEye color={isMonitoring ? 'green' : 'gray'} />
            <Text fontSize="lg" fontWeight="bold">
              Proctoring Monitor
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
              colorScheme={isMonitoring ? 'red' : 'green'}
              leftIcon={isMonitoring ? <FaVideoSlash /> : <FaVideo />}
              onClick={isMonitoring ? stopMonitoring : startMonitoring}
              isLoading={isLoading}
              loadingText={isMonitoring ? 'Stopping...' : 'Starting...'}
            >
              {isMonitoring ? 'Stop' : 'Start'}
            </Button>
          </HStack>
        </HStack>

        {/* Error Display */}
        {error && (
          <Alert status="error">
            <AlertIcon />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Video Display */}
        {(cameraActive || isLoading) && (
          <Box position="relative" bg="black" borderRadius="md" overflow="hidden">
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              style={{
                width: '100%',
                height: '240px',
                objectFit: 'cover',
              }}
            />
            
            {/* Face Detection Overlay */}
            {detectionResults.length > 0 && (
              <Box
                position="absolute"
                top={0}
                left={0}
                width="100%"
                height="100%"
                pointerEvents="none"
              >
                {detectionResults.map((face, index) => (
                  <Box
                    key={index}
                    position="absolute"
                    border="2px solid"
                    borderColor={face.score > 0.8 ? 'green.400' : 'yellow.400'}
                    borderRadius="md"
                    style={{
                      left: `${(face.box.xMin / videoRef.current?.videoWidth) * 100}%`,
                      top: `${(face.box.yMin / videoRef.current?.videoHeight) * 100}%`,
                      width: `${(face.box.width / videoRef.current?.videoWidth) * 100}%`,
                      height: `${(face.box.height / videoRef.current?.videoHeight) * 100}%`,
                    }}
                  />
                ))}
              </Box>
            )}
            
            {/* Loading Overlay */}
            {isLoading && (
              <Box
                position="absolute"
                top={0}
                left={0}
                width="100%"
                height="100%"
                bg="blackAlpha.600"
                display="flex"
                alignItems="center"
                justifyContent="center"
                color="white"
              >
                <VStack spacing={2}>
                  <Progress size="sm" isIndeterminate width="200px" />
                  <Text fontSize="sm">
                    {cameraLoading ? 'Starting camera...' : 'Loading face detection...'}
                  </Text>
                </VStack>
              </Box>
            )}
          </Box>
        )}

        {/* Detection Stats */}
        {isMonitoring && detectionReady && (
          <HStack spacing={4} fontSize="sm" color="gray.600">
            <Text>
              Faces: <strong>{detectionStats.faceCount}</strong>
            </Text>
            <Text>
              Confidence: <strong>{(detectionStats.confidence * 100).toFixed(1)}%</strong>
            </Text>
            <Text>
              WebSocket: <strong className={wsConnected ? 'text-green-600' : 'text-red-600'}>
                {connectionStatus}
              </strong>
            </Text>
          </HStack>
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
                  onChange={(e) => handleDeviceChange(e.target.value)}
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
                isChecked={isMonitoring}
                onChange={(e) => e.target.checked ? startMonitoring() : stopMonitoring()}
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