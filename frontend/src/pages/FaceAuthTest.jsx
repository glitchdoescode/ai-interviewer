import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  VStack,
  HStack,
  Text,
  Button,
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription,
  Heading,
  Badge,
  Divider,
  useToast,
} from '@chakra-ui/react';
import { FaArrowLeft, FaCamera, FaPlay, FaStop } from 'react-icons/fa';
import { Link } from 'react-router-dom';
import FaceAuthenticationManager from '../components/proctoring/FaceAuthenticationManager';
import { useCamera } from '../hooks/useCamera';

/**
 * Test page for Face Authentication System
 * Allows testing face enrollment and authentication functionality
 */
const FaceAuthTest = () => {
  const toast = useToast();
  const [isTestActive, setIsTestActive] = useState(false);
  const [authEvents, setAuthEvents] = useState([]);
  const [lastProcessedEventId, setLastProcessedEventId] = useState(null);

  // Use camera hook for video stream
  const {
    stream,
    isLoading: cameraLoading,
    error: cameraError,
    isActive: cameraActive,
    videoRef,
    startCamera,
    stopCamera,
    permissionGranted,
  } = useCamera();

  // Debug logging for camera
  useEffect(() => {
    console.log('Camera debug info:', {
      stream: !!stream,
      streamId: stream?.id,
      cameraActive,
      videoRefCurrent: !!videoRef?.current,
      videoSrcObject: videoRef?.current?.srcObject,
      permissionGranted,
      cameraError
    });
  }, [stream, cameraActive, videoRef, permissionGranted, cameraError]);

  // Manually assign stream to video element (fix for useCamera hook issue)
  useEffect(() => {
    if (stream && videoRef?.current && !videoRef.current.srcObject) {
      console.log('Manually assigning stream to video element...');
      videoRef.current.srcObject = stream;
      
      // Force video to load and play
      videoRef.current.load();
      videoRef.current.play().catch(error => {
        console.log('Video play failed (this might be normal):', error);
      });
    }
  }, [stream, videoRef]);

  const handleStartTest = async () => {
    try {
      console.log('Starting camera test...');
      const result = await startCamera();
      console.log('Camera started, result:', result);
      
      setIsTestActive(true);
      setAuthEvents([]);
      
      // Additional check for video element
      setTimeout(() => {
        if (videoRef?.current) {
          console.log('Video element check:', {
            videoWidth: videoRef.current.videoWidth,
            videoHeight: videoRef.current.videoHeight,
            readyState: videoRef.current.readyState,
            srcObject: videoRef.current.srcObject
          });
        }
      }, 1000);
      
      toast({
        title: 'Face Authentication Test Started',
        description: 'Camera is now active for testing',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });
    } catch (error) {
      console.error('Error starting test:', error);
      toast({
        title: 'Failed to Start Test',
        description: error.message || 'Could not access camera',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    }
  };

  const handleStopTest = () => {
    stopCamera();
    setIsTestActive(false);
    
    toast({
      title: 'Face Authentication Test Stopped',
      description: 'Camera has been stopped',
      status: 'info',
      duration: 3000,
      isClosable: true,
    });
  };

  const handleAuthenticationEvent = (event) => {
    console.log('Authentication event:', event);
    
    // Prevent duplicate event processing by checking the event ID
    if (event.id && event.id === lastProcessedEventId) {
      console.log('Duplicate event detected, skipping:', event.id);
      return;
    }
    
    // Update last processed event ID
    setLastProcessedEventId(event.id);
    
    // Add event to the list, ensuring we don't exceed reasonable limits
    setAuthEvents(prev => {
      // Check if this exact event already exists in the array
      const isDuplicate = prev.some(existingEvent => existingEvent.id === event.id);
      if (isDuplicate) {
        console.log('Event already exists in array, skipping:', event.id);
        return prev;
      }
      
      return [...prev.slice(-9), event];
    });
    
    // Show toast for significant events
    if (event.type === 'enrollment_success') {
      toast({
        title: 'Face Enrolled Successfully',
        description: 'Your face has been enrolled for authentication',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });
    } else if (event.type === 'impersonation_detected') {
      toast({
        title: 'Impersonation Detected',
        description: 'Possible impersonation attempt detected',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    }
  };

  const getEventBadgeColor = (eventType) => {
    if (eventType.includes('success')) return 'green';
    if (eventType.includes('failed') || eventType.includes('error')) return 'red';
    if (eventType.includes('impersonation')) return 'red';
    return 'blue';
  };

  return (
    <Container maxW="6xl" py={8}>
      <VStack spacing={6} align="stretch">
        {/* Header */}
        <HStack justify="space-between" align="center">
          <HStack spacing={4}>
            <Button
              as={Link}
              to="/"
              variant="outline"
              leftIcon={<FaArrowLeft />}
              size="sm"
            >
              Back to Home
            </Button>
            <Heading size="lg">Face Authentication Test</Heading>
          </HStack>
          
          <HStack spacing={3}>
            <Badge colorScheme={isTestActive ? 'green' : 'gray'}>
              {isTestActive ? 'Active' : 'Inactive'}
            </Badge>
            <Button
              colorScheme={isTestActive ? 'red' : 'green'}
              leftIcon={isTestActive ? <FaStop /> : <FaPlay />}
              onClick={isTestActive ? handleStopTest : handleStartTest}
              isLoading={cameraLoading}
              loadingText="Starting..."
            >
              {isTestActive ? 'Stop Test' : 'Start Test'}
            </Button>
          </HStack>
        </HStack>

        {/* Instructions */}
        <Alert status="info" borderRadius="md">
          <AlertIcon />
          <Box>
            <AlertTitle>Testing Instructions</AlertTitle>
            <AlertDescription>
              This page allows you to test the face authentication system. 
              Start the test to enable your camera, then use the enrollment interface 
              to register your face. The system will periodically re-authenticate 
              and detect potential impersonation attempts.
            </AlertDescription>
          </Box>
        </Alert>

        {/* Debug Info */}
        {isTestActive && (
          <Alert status="info" borderRadius="md">
            <AlertIcon />
            <Box>
              <AlertTitle>Debug Info</AlertTitle>
              <AlertDescription fontSize="sm">
                Stream: {stream ? '✓' : '✗'} | 
                Camera Active: {cameraActive ? '✓' : '✗'} | 
                Video Ref: {videoRef?.current ? '✓' : '✗'} | 
                Permission: {permissionGranted ? '✓' : '✗'}
                {videoRef?.current && (
                  <> | Video Ready: {videoRef.current.readyState}/4</>
                )}
              </AlertDescription>
            </Box>
          </Alert>
        )}

        <HStack spacing={6} align="start">
          {/* Left Panel - Video and Face Authentication */}
          <VStack spacing={4} flex={2}>
            {/* Camera Video */}
            <Box 
              position="relative" 
              w="full" 
              bg="black" 
              borderRadius="lg" 
              overflow="hidden"
              minH="360px"
              display="flex"
              alignItems="center"
              justifyContent="center"
            >
              {cameraActive && stream ? (
                <video
                  ref={videoRef}
                  autoPlay
                  playsInline
                  muted
                  onLoadedMetadata={() => {
                    console.log('Video metadata loaded:', {
                      videoWidth: videoRef.current?.videoWidth,
                      videoHeight: videoRef.current?.videoHeight
                    });
                  }}
                  style={{
                    width: '100%',
                    height: '360px',
                    objectFit: 'cover',
                    backgroundColor: '#000',
                  }}
                />
              ) : (
                <VStack spacing={3} color="gray.400">
                  <FaCamera size={48} />
                  <Text>Camera not active</Text>
                  <Text fontSize="sm">
                    {cameraLoading ? 'Loading camera...' : 'Click "Start Test" to begin'}
                  </Text>
                  {cameraError && (
                    <Text fontSize="sm" color="red.400">
                      Error: {cameraError}
                    </Text>
                  )}
                </VStack>
              )}
              
              {cameraError && (
                <Box
                  position="absolute"
                  top={4}
                  left={4}
                  right={4}
                  bg="red.500"
                  color="white"
                  p={3}
                  borderRadius="md"
                >
                  <Text fontSize="sm" fontWeight="bold">Camera Error</Text>
                  <Text fontSize="xs">{cameraError}</Text>
                </Box>
              )}
            </Box>

            {/* Face Authentication Manager */}
            {isTestActive && stream && (
              <FaceAuthenticationManager
                videoRef={videoRef}
                isActive={cameraActive}
                onAuthenticationEvent={handleAuthenticationEvent}
                showEnrollmentUI={true}
              />
            )}
          </VStack>

          {/* Right Panel - Event Log */}
          <VStack spacing={4} flex={1} align="stretch">
            <Box
              bg="white"
              p={4}
              borderRadius="lg"
              borderWidth={1}
              borderColor="gray.200"
              minH="400px"
            >
              <Heading size="md" mb={4}>Event Log</Heading>
              <Divider mb={4} />
              
              {authEvents.length === 0 ? (
                <Text color="gray.500" fontSize="sm" textAlign="center" mt={8}>
                  No events yet. Start the test and enroll your face to see events.
                </Text>
              ) : (
                <VStack spacing={3} align="stretch">
                  {authEvents.slice().reverse().map((event, index) => (
                    <Box
                      key={event.id || index}
                      p={3}
                      bg="gray.50"
                      borderRadius="md"
                      borderLeft="4px solid"
                      borderLeftColor={`${getEventBadgeColor(event.type)}.400`}
                    >
                      <HStack justify="space-between" mb={1}>
                        <Badge colorScheme={getEventBadgeColor(event.type)} size="sm">
                          {event.type.replace(/_/g, ' ')}
                        </Badge>
                        <Text fontSize="xs" color="gray.500">
                          {new Date(event.timestamp).toLocaleTimeString()}
                        </Text>
                      </HStack>
                      
                      {event.data && Object.keys(event.data).length > 0 && (
                        <Box mt={2}>
                          {event.data.similarity && (
                            <Text fontSize="xs" color="gray.600">
                              Similarity: {Math.round(event.data.similarity * 100)}%
                            </Text>
                          )}
                          {event.data.confidence && (
                            <Text fontSize="xs" color="gray.600">
                              Confidence: {Math.round(event.data.confidence * 100)}%
                            </Text>
                          )}
                          {event.data.attempt && (
                            <Text fontSize="xs" color="gray.600">
                              Attempt: {event.data.attempt}
                            </Text>
                          )}
                          {event.data.error && (
                            <Text fontSize="xs" color="red.600">
                              Error: {event.data.error}
                            </Text>
                          )}
                        </Box>
                      )}
                    </Box>
                  ))}
                </VStack>
              )}
            </Box>
          </VStack>
        </HStack>
      </VStack>
    </Container>
  );
};

export default FaceAuthTest; 