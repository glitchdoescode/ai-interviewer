import React, { useState, useEffect, useRef, useCallback } from 'react';
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
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  Progress,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  Table,
  Thead,
  Tbody,
  Tr,
  Th,
  Td,
  Accordion,
  AccordionItem,
  AccordionButton,
  AccordionPanel,
  AccordionIcon,
} from '@chakra-ui/react';
import { FaArrowLeft, FaCamera, FaPlay, FaStop, FaExclamationTriangle, FaEye, FaShieldAlt } from 'react-icons/fa';
import { Link } from 'react-router-dom';
import FaceAuthenticationManager from '../components/proctoring/FaceAuthenticationManager';
import { useCamera } from '../hooks/useCamera';
import { useFaceAuthentication } from '../hooks/useFaceAuthentication';

/**
 * Test page for Face Authentication System with Phase 3 Advanced Impersonation Detection
 * Allows testing face enrollment, authentication, and advanced detection functionality
 */
const FaceAuthTest = () => {
  const toast = useToast();
  const [isTestActive, setIsTestActive] = useState(false);
  const [authEvents, setAuthEvents] = useState([]);
  const [phase3Stats, setPhase3Stats] = useState(null);
  const processedEventsRef = useRef(new Set()); // Track all processed event IDs

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

  // Direct access to face authentication hook for debugging
  const faceAuthHook = useFaceAuthentication(videoRef, isTestActive && cameraActive);

  // Add hook instance tracking for debugging
  const hookInstanceId = useRef(Math.random().toString(36).substr(2, 9));
  useEffect(() => {
    console.log(`[FaceAuthTest] Hook instance ${hookInstanceId.current} - Events count:`, faceAuthHook.authenticationEvents?.length || 0);
    if (faceAuthHook.authenticationEvents?.length > 0) {
      console.log(`[FaceAuthTest] Hook instance ${hookInstanceId.current} - Latest events:`, faceAuthHook.authenticationEvents.slice(-2));
    }
  }, [faceAuthHook.authenticationEvents]);

  // Update Phase 3 statistics
  useEffect(() => {
    if (faceAuthHook.getAdvancedStats) {
      const stats = faceAuthHook.getAdvancedStats();
      setPhase3Stats(stats);
    }
  }, [faceAuthHook, isTestActive]);

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

  // Debug logging for face authentication
  useEffect(() => {
    console.log('Face Auth debug info:', {
      isLoading: faceAuthHook.isLoading,
      isReady: faceAuthHook.isReady,
      enrollmentStatus: faceAuthHook.enrollmentStatus,
      authenticationStatus: faceAuthHook.authenticationStatus,
      eventsCount: faceAuthHook.authenticationEvents?.length || 0,
      error: faceAuthHook.error,
      // Phase 3 info
      escalationStatus: faceAuthHook.escalationStatus,
      advancedStats: phase3Stats
    });
    
    if (faceAuthHook.authenticationEvents && faceAuthHook.authenticationEvents.length > 0) {
      console.log('Latest face auth events:', faceAuthHook.authenticationEvents.slice(-3));
    }
  }, [
    faceAuthHook.isLoading,
    faceAuthHook.isReady,
    faceAuthHook.enrollmentStatus,
    faceAuthHook.authenticationStatus,
    faceAuthHook.authenticationEvents,
    faceAuthHook.error,
    faceAuthHook.escalationStatus,
    phase3Stats
  ]);

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

  // SIMPLIFIED: Just sync the local events with hook events for display
  useEffect(() => {
    if (faceAuthHook.authenticationEvents) {
      setAuthEvents(faceAuthHook.authenticationEvents.slice(-10)); // Just keep last 10 for display
    }
  }, [faceAuthHook.authenticationEvents]);

  // Enhanced: Handle Phase 3 alerts and events
  useEffect(() => {
    const events = faceAuthHook.authenticationEvents;
    if (!events || events.length === 0) return;
    
    const latestEvent = events[events.length - 1];
    const latestEventId = latestEvent?.id;
    
    // Only process if this is a new event ID
    if (latestEventId && latestEventId !== processedEventsRef.current.values().next().value) {
      processedEventsRef.current.clear();
      processedEventsRef.current.add(latestEventId);
      
      // Handle different Phase 3 events
      switch (latestEvent.type) {
        case 'impersonation_detected':
        case 'impersonation_alert_generated':
          toast({
            title: 'Impersonation Alert',
            description: 'Possible impersonation attempt detected',
            status: 'error',
            duration: 5000,
            isClosable: true,
          });
          break;
          
        case 'multiple_faces_detected':
          toast({
            title: 'Multiple Faces Detected',
            description: `${latestEvent.data?.faceCount || 'Multiple'} faces detected in frame`,
            status: 'warning',
            duration: 4000,
            isClosable: true,
          });
          break;
          
        case 'appearance_change_detected':
          toast({
            title: 'Appearance Change',
            description: 'Sudden appearance change detected',
            status: 'warning',
            duration: 4000,
            isClosable: true,
          });
          break;
          
        case 'suspicious_behavior_detected':
          toast({
            title: 'Suspicious Behavior',
            description: 'Suspicious behavior pattern detected',
            status: 'warning',
            duration: 4000,
            isClosable: true,
          });
          break;
          
        case 'escalation_level_changed':
          const newLevel = latestEvent.data?.newLevel;
          toast({
            title: 'Escalation Level Changed',
            description: `Security level changed to: ${newLevel}`,
            status: newLevel === 'critical' ? 'error' : 'warning',
            duration: 5000,
            isClosable: true,
          });
          break;
      }
    }
  }, [faceAuthHook.authenticationEvents, toast]);

  const handleStartTest = async () => {
    try {
      console.log('Starting camera test...');
      const result = await startCamera();
      console.log('Camera started, result:', result);
      
      setIsTestActive(true);
      setAuthEvents([]);
      // Clear processed events to start fresh
      processedEventsRef.current.clear();
      
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
    // This function is now only used for manual event handling if needed
    console.log('Manual authentication event handling (should not be called during normal flow):', event);
    
    setAuthEvents(prev => {
      // Check if event already exists in local state
      const exists = prev.some(e => e.id === event.id);
      if (exists) {
        console.log('Event already exists in local state, skipping:', event.id);
        return prev;
      }
      return [...prev.slice(-9), event];
    });
  };

  const handleEnrollment = async () => {
    try {
      const result = await faceAuthHook.enrollFace();
      console.log('Enrollment result:', result);
      
      // Show toast based on actual enrollment result
      if (result.success) {
        toast({
          title: 'Face Enrolled Successfully',
          description: 'Your face has been enrolled for authentication',
          status: 'success',
          duration: 3000,
          isClosable: true,
        });
      } else {
        // Only show error toast for actual errors (skip "already enrolled" and "in progress" messages)
        if (result.message && 
            !result.message.includes('already') && 
            !result.message.includes('in progress')) {
          toast({
            title: 'Enrollment Failed',
            description: result.message,
            status: 'error',
            duration: 5000,
            isClosable: true,
          });
        }
      }
    } catch (error) {
      console.error('Error during enrollment:', error);
      toast({
        title: 'Enrollment Error',
        description: 'An unexpected error occurred during enrollment',
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
    if (eventType.includes('multiple_faces')) return 'orange';
    if (eventType.includes('appearance_change')) return 'orange';
    if (eventType.includes('suspicious_behavior')) return 'orange';
    if (eventType.includes('escalation')) return 'purple';
    return 'blue';
  };

  // Phase 3: Helper functions for advanced features
  const getEscalationStatusColor = (status) => {
    switch (status) {
      case 'critical': return 'red';
      case 'warning': return 'orange';
      case 'normal': return 'green';
      default: return 'gray';
    }
  };

  const getEscalationIcon = (status) => {
    switch (status) {
      case 'critical': return FaExclamationTriangle;
      case 'warning': return FaEye;
      case 'normal': return FaShieldAlt;
      default: return FaShieldAlt;
    }
  };

  // Phase 3: Test functions for advanced detection
  const testMultipleFaceDetection = async () => {
    if (!faceAuthHook.detectMultipleFaces) return;
    
    try {
      const result = await faceAuthHook.detectMultipleFaces();
      console.log('Multiple face detection test result:', result);
      
      toast({
        title: 'Multiple Face Detection Test',
        description: `Detected ${result.totalFaceCount} face(s). Multiple faces: ${result.multipleFacesDetected}`,
        status: result.multipleFacesDetected ? 'warning' : 'success',
        duration: 4000,
        isClosable: true,
      });
    } catch (error) {
      console.error('Multiple face detection test error:', error);
      toast({
        title: 'Test Error',
        description: 'Failed to run multiple face detection test',
        status: 'error',
        duration: 4000,
        isClosable: true,
      });
    }
  };

  const testAppearanceChangeDetection = async () => {
    if (!faceAuthHook.detectAppearanceChanges || !videoRef?.current) return;
    
    try {
      // Simulate by running detection on current frame
      const faceResult = await faceAuthHook.detectBestFace?.();
      if (faceResult?.face) {
        const embedding = await faceAuthHook.extractEmbeddingWithCache?.(faceResult.face);
        if (embedding) {
          const result = await faceAuthHook.detectAppearanceChanges(faceResult.face, embedding);
          console.log('Appearance change detection test result:', result);
          
          toast({
            title: 'Appearance Change Detection Test',
            description: `Change detected: ${result.suddenChange}, Score: ${result.changeScore.toFixed(3)}`,
            status: result.suddenChange ? 'warning' : 'success',
            duration: 4000,
            isClosable: true,
          });
        }
      }
    } catch (error) {
      console.error('Appearance change detection test error:', error);
      toast({
        title: 'Test Error',
        description: 'Failed to run appearance change detection test',
        status: 'error',
        duration: 4000,
        isClosable: true,
      });
    }
  };

  const generateTestAlert = async () => {
    if (!faceAuthHook.generateImpersonationAlert) return;
    
    try {
      const result = await faceAuthHook.generateImpersonationAlert('test_alert', {
        severity: 'warning',
        testReason: 'Manual test alert generation',
        timestamp: new Date().toISOString()
      });
      
      console.log('Test alert generation result:', result);
      
      toast({
        title: 'Test Alert Generated',
        description: `Alert ID: ${result.alert.id}, Escalation: ${result.escalationLevel}`,
        status: 'info',
        duration: 4000,
        isClosable: true,
      });
    } catch (error) {
      console.error('Test alert generation error:', error);
      toast({
        title: 'Test Error',
        description: 'Failed to generate test alert',
        status: 'error',
        duration: 4000,
        isClosable: true,
      });
    }
  };

  const captureTestEvidence = async () => {
    if (!faceAuthHook.captureEvidence) return;
    
    try {
      const result = await faceAuthHook.captureEvidence('test_evidence', {
        severity: 'warning',
        testType: 'manual_capture',
        timestamp: new Date().toISOString()
      });
      
      console.log('Test evidence capture result:', result);
      
      toast({
        title: 'Evidence Captured',
        description: `Evidence ID: ${result.id}`,
        status: 'info',
        duration: 4000,
        isClosable: true,
      });
    } catch (error) {
      console.error('Test evidence capture error:', error);
      toast({
        title: 'Test Error',
        description: 'Failed to capture test evidence',
        status: 'error',
        duration: 4000,
        isClosable: true,
      });
    }
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
            {!isTestActive ? (
              <Button
                colorScheme="blue"
                leftIcon={<FaPlay />}
                onClick={handleStartTest}
                isLoading={cameraLoading}
                loadingText="Starting..."
                size="lg"
              >
                Start Test
              </Button>
            ) : (
              <Button
                colorScheme="red"
                leftIcon={<FaStop />}
                onClick={handleStopTest}
                size="lg"
              >
                Stop Test
              </Button>
            )}
          </HStack>
        </HStack>

        {/* System Status */}
        <Alert status={!cameraError && !faceAuthHook.error ? 'success' : 'error'}>
          <AlertIcon />
          <Box>
            <AlertTitle>System Status</AlertTitle>
            <AlertDescription>
              {cameraError ? (
                `Camera Error: ${cameraError}`
              ) : faceAuthHook.error ? (
                `Face Auth Error: ${faceAuthHook.error}`
              ) : (
                'All systems ready'
              )}
            </AlertDescription>
          </Box>
        </Alert>

        <HStack spacing={6} align="start">
          {/* Left Panel - Camera and Face Authentication */}
          <VStack spacing={4} flex={1}>
            {/* Camera Section */}
            <Box w="100%" p={4} borderWidth={1} borderRadius="lg">
              <Heading size="md" mb={4}>Camera Feed</Heading>
              
              <Box position="relative" mb={4}>
                <video
                  ref={videoRef}
                  autoPlay
                  playsInline
                  muted
                  style={{
                    width: '100%',
                    maxWidth: '640px',
                    height: 'auto',
                    borderRadius: '8px',
                    backgroundColor: '#000',
                    display: 'block',
                  }}
                  onLoadedMetadata={(e) => {
                    console.log('Video metadata loaded:', {
                      videoWidth: e.target.videoWidth,
                      videoHeight: e.target.videoHeight,
                      duration: e.target.duration,
                      readyState: e.target.readyState
                    });
                  }}
                />
                
                {/* Camera Status Overlay */}
                {!cameraActive && (
                  <Box
                    position="absolute"
                    top="50%"
                    left="50%"
                    transform="translate(-50%, -50%)"
                    bg="blackAlpha.700"
                    color="white"
                    p={4}
                    borderRadius="md"
                    textAlign="center"
                  >
                    <FaCamera size={32} style={{ margin: '0 auto 8px' }} />
                    <Text>Camera Not Active</Text>
                  </Box>
                )}
              </Box>

              <HStack spacing={3} justify="center">
                <Badge colorScheme={cameraActive ? 'green' : 'gray'}>
                  Camera: {cameraActive ? 'Active' : 'Inactive'}
                </Badge>
                <Badge colorScheme={faceAuthHook.isReady ? 'green' : 'gray'}>
                  Face Detection: {faceAuthHook.isReady ? 'Ready' : 'Loading'}
                </Badge>
              </HStack>
            </Box>

            {/* Face Authentication Section */}
            <Box w="100%" p={4} borderWidth={1} borderRadius="lg">
              <Heading size="md" mb={4}>Face Authentication</Heading>
              
              <VStack spacing={3} align="stretch">
                {/* Status Display */}
                <HStack spacing={4}>
                  <VStack align="start" spacing={1}>
                    <Text fontSize="sm" color="gray.600">Enrollment</Text>
                    <Badge 
                      colorScheme={
                        faceAuthHook.enrollmentStatus === 'enrolled' ? 'green' :
                        faceAuthHook.enrollmentStatus === 'enrolling' ? 'yellow' : 'gray'
                      }
                    >
                      {faceAuthHook.enrollmentStatus}
                    </Badge>
                  </VStack>
                  
                  <VStack align="start" spacing={1}>
                    <Text fontSize="sm" color="gray.600">Authentication</Text>
                    <Badge 
                      colorScheme={
                        faceAuthHook.authenticationStatus === 'authenticated' ? 'green' :
                        faceAuthHook.authenticationStatus === 'failed' ? 'red' : 'gray'
                      }
                    >
                      {faceAuthHook.authenticationStatus}
                    </Badge>
                  </VStack>
                  
                  {faceAuthHook.authenticationScore > 0 && (
                    <VStack align="start" spacing={1}>
                      <Text fontSize="sm" color="gray.600">Score</Text>
                      <Badge colorScheme="blue">
                        {(faceAuthHook.authenticationScore * 100).toFixed(1)}%
                      </Badge>
                    </VStack>
                  )}
                </HStack>

                {/* Action Buttons */}
                <HStack spacing={3}>
                  <Button
                    colorScheme="green"
                    onClick={handleEnrollment}
                    isDisabled={!isTestActive || !faceAuthHook.isReady || faceAuthHook.enrollmentStatus === 'enrolled' || faceAuthHook.enrollmentStatus === 'enrolling'}
                    isLoading={faceAuthHook.enrollmentStatus === 'enrolling'}
                    loadingText="Enrolling..."
                  >
                    Start Face Enrollment
                  </Button>
                  
                  <Button
                    colorScheme="blue"
                    onClick={faceAuthHook.authenticateCurrentFace}
                    isDisabled={!isTestActive || !faceAuthHook.isReady || faceAuthHook.enrollmentStatus !== 'enrolled'}
                  >
                    Authenticate
                  </Button>
                  
                  <Button
                    colorScheme="orange"
                    onClick={faceAuthHook.resetAuthentication}
                    size="sm"
                  >
                    Reset
                  </Button>
                </HStack>

                {/* Debug Actions */}
                <Box bg="yellow.50" p={3} borderRadius="md" border="1px" borderColor="yellow.200">
                  <Text fontSize="sm" fontWeight="bold" mb={2} color="yellow.800">Debug Actions</Text>
                  <HStack spacing={2} wrap="wrap">
                    <Button
                      size="sm"
                      colorScheme="yellow"
                      onClick={() => console.log('Manual camera check:', {
                        stream: !!stream,
                        cameraActive,
                        videoRef: !!videoRef?.current,
                        srcObject: videoRef?.current?.srcObject
                      })}
                    >
                      Log Camera Info
                    </Button>
                    <Button
                      size="sm"
                      colorScheme="yellow"
                      onClick={() => console.log('Manual face auth check:', {
                        isReady: faceAuthHook.isReady,
                        enrollmentStatus: faceAuthHook.enrollmentStatus,
                        authenticationStatus: faceAuthHook.authenticationStatus,
                        eventsCount: faceAuthHook.authenticationEvents?.length
                      })}
                    >
                      Log Face Auth Info
                    </Button>
                    <Button
                      size="sm"
                      colorScheme="orange"
                      onClick={faceAuthHook.runDiagnostics}
                      isDisabled={!faceAuthHook.isReady}
                    >
                      Run MediaPipe Diagnostics
                    </Button>
                    <Button
                      size="sm"
                      colorScheme="purple"
                      onClick={() => faceAuthHook.generateAuthEvent('manual_test', { timestamp: new Date() })}
                    >
                      Generate Test Event
                    </Button>
                  </HStack>
                </Box>
              </VStack>
            </Box>
          </VStack>

          {/* Right Panel - Hook State and Events */}
          <VStack spacing={4} flex={1}>
            {/* Hook State Panel */}
            <Box w="100%" p={4} borderWidth={1} borderRadius="lg">
              <Heading size="md" mb={4}>Hook State</Heading>
              
              <VStack align="start" spacing={2}>
                <HStack>
                  <Text fontWeight="bold" w="120px">Camera:</Text>
                  <Badge colorScheme={cameraActive ? 'green' : 'gray'}>
                    {cameraActive ? 'Active' : 'Inactive'}
                  </Badge>
                </HStack>
                
                <HStack>
                  <Text fontWeight="bold" w="120px">Face Auth:</Text>
                  <Badge colorScheme={faceAuthHook.isReady ? 'green' : 'yellow'}>
                    {faceAuthHook.isLoading ? 'Loading' : faceAuthHook.isReady ? 'Ready' : 'Not Ready'}
                  </Badge>
                </HStack>
                
                <HStack>
                  <Text fontWeight="bold" w="120px">Enrollment:</Text>
                  <Badge 
                    colorScheme={
                      faceAuthHook.enrollmentStatus === 'enrolled' ? 'green' :
                      faceAuthHook.enrollmentStatus === 'enrolling' ? 'yellow' : 'gray'
                    }
                  >
                    {faceAuthHook.enrollmentStatus}
                  </Badge>
                </HStack>
                
                <HStack>
                  <Text fontWeight="bold" w="120px">Authentication:</Text>
                  <Badge 
                    colorScheme={
                      faceAuthHook.authenticationStatus === 'authenticated' ? 'green' :
                      faceAuthHook.authenticationStatus === 'failed' ? 'red' : 'gray'
                    }
                  >
                    {faceAuthHook.authenticationStatus}
                  </Badge>
                </HStack>
                
                {faceAuthHook.lastAuthenticationTime && (
                  <HStack>
                    <Text fontWeight="bold" w="120px">Last Auth:</Text>
                    <Text fontSize="sm">
                      {faceAuthHook.lastAuthenticationTime.toLocaleTimeString()}
                    </Text>
                  </HStack>
                )}
              </VStack>
            </Box>

            {/* Event Log */}
            <Box w="100%" p={4} borderWidth={1} borderRadius="lg">
              <Heading size="md" mb={4}>
                <HStack>
                  <Text>Event Log</Text>
                  {phase3Stats && phase3Stats.escalationLevel !== 'normal' && (
                    <Badge 
                      colorScheme={getEscalationStatusColor(phase3Stats.escalationLevel)}
                      fontSize="xs"
                    >
                      {getEscalationIcon(phase3Stats.escalationLevel)} {phase3Stats.escalationLevel.toUpperCase()}
                    </Badge>
                  )}
                </HStack>
              </Heading>
              
              <VStack spacing={2} align="stretch" maxH="400px" overflowY="auto">
                {authEvents.length > 0 ? (
                  authEvents.slice().reverse().map((event, index) => (
                    <Box key={`event_${event.timestamp}_${index}`} p={3} bg="gray.50" borderRadius="md">
                      <HStack justify="space-between" align="start">
                        <VStack align="start" spacing={1}>
                          <HStack>
                            <Badge colorScheme={getEventBadgeColor(event.type)}>
                              {event.type}
                            </Badge>
                            <Text fontSize="xs" color="gray.600">
                              {new Date(event.timestamp).toLocaleTimeString()}
                            </Text>
                          </HStack>
                          {event.data && Object.keys(event.data).length > 0 && (
                            <Text fontSize="xs" fontFamily="mono" color="gray.700">
                              {JSON.stringify(event.data, null, 1).slice(0, 100)}
                              {JSON.stringify(event.data).length > 100 ? '...' : ''}
                            </Text>
                          )}
                        </VStack>
                      </HStack>
                    </Box>
                  ))
                ) : (
                  <Text color="gray.500" textAlign="center" py={4}>
                    No events yet
                  </Text>
                )}
              </VStack>
            </Box>

            {/* Phase 3: Advanced Features Tab */}
            <Box w="100%" p={4} borderWidth={1} borderRadius="lg">
              <Heading size="md" mb={4}>
                <HStack>
                  <FaShieldAlt />
                  <Text>Phase 3: Advanced Impersonation Detection</Text>
                </HStack>
              </Heading>

              <Tabs variant="enclosed" colorScheme="blue">
                <TabList>
                  <Tab>Overview</Tab>
                  <Tab>Testing</Tab>
                  <Tab>Evidence</Tab>
                  <Tab>Analytics</Tab>
                </TabList>

                <TabPanels>
                  {/* Overview Tab */}
                  <TabPanel>
                    <VStack spacing={4} align="stretch">
                      {/* Escalation Status */}
                      <Box p={3} bg={phase3Stats?.escalationLevel === 'critical' ? 'red.50' : 
                                      phase3Stats?.escalationLevel === 'warning' ? 'yellow.50' : 'green.50'} 
                           borderRadius="md" border="1px" 
                           borderColor={phase3Stats?.escalationLevel === 'critical' ? 'red.200' : 
                                       phase3Stats?.escalationLevel === 'warning' ? 'yellow.200' : 'green.200'}>
                        <HStack justify="space-between">
                          <HStack>
                            <Text fontWeight="bold">Security Level:</Text>
                            <Badge 
                              colorScheme={getEscalationStatusColor(phase3Stats?.escalationLevel || 'normal')}
                              fontSize="md"
                            >
                              {getEscalationIcon(phase3Stats?.escalationLevel || 'normal')} 
                              {(phase3Stats?.escalationLevel || 'normal').toUpperCase()}
                            </Badge>
                          </HStack>
                          <Text fontSize="sm" color="gray.600">
                            Alerts: {phase3Stats?.recentAlertsCount || 0} | 
                            Critical: {phase3Stats?.criticalAlertsCount || 0}
                          </Text>
                        </HStack>
                      </Box>

                      {/* Phase 3 Statistics */}
                      <HStack spacing={4} align="start">
                        <Stat>
                          <StatLabel>Tracked Faces</StatLabel>
                          <StatNumber>{phase3Stats?.trackedFacesCount || 0}</StatNumber>
                          <StatHelpText>Currently monitored</StatHelpText>
                        </Stat>
                        <Stat>
                          <StatLabel>Face History</StatLabel>
                          <StatNumber>{phase3Stats?.faceHistorySize || 0}</StatNumber>
                          <StatHelpText>Snapshots stored</StatHelpText>
                        </Stat>
                        <Stat>
                          <StatLabel>Evidence Items</StatLabel>
                          <StatNumber>{phase3Stats?.evidenceItemsCount || 0}</StatNumber>
                          <StatHelpText>Captured for review</StatHelpText>
                        </Stat>
                      </HStack>

                      {/* Configuration Display */}
                      <Accordion allowToggle>
                        <AccordionItem>
                          <AccordionButton>
                            <Box flex="1" textAlign="left">
                              Detection Thresholds
                            </Box>
                            <AccordionIcon />
                          </AccordionButton>
                          <AccordionPanel pb={4}>
                            <Table size="sm">
                              <Tbody>
                                <Tr>
                                  <Td fontWeight="bold">Impersonation Threshold</Td>
                                  <Td>{((phase3Stats?.impersonationThreshold || 0.5) * 100).toFixed(1)}%</Td>
                                </Tr>
                                <Tr>
                                  <Td fontWeight="bold">Multiple Face Threshold</Td>
                                  <Td>{((phase3Stats?.multipleFaceThreshold || 0.3) * 100).toFixed(1)}%</Td>
                                </Tr>
                                <Tr>
                                  <Td fontWeight="bold">Appearance Change Threshold</Td>
                                  <Td>{((phase3Stats?.appearanceChangeThreshold || 0.4) * 100).toFixed(1)}%</Td>
                                </Tr>
                                <Tr>
                                  <Td fontWeight="bold">Temporal Analysis Window</Td>
                                  <Td>{phase3Stats?.temporalAnalysisWindow || 30} events</Td>
                                </Tr>
                              </Tbody>
                            </Table>
                          </AccordionPanel>
                        </AccordionItem>
                      </Accordion>
                    </VStack>
                  </TabPanel>

                  {/* Testing Tab */}
                  <TabPanel>
                    <VStack spacing={4} align="stretch">
                      <Text fontSize="sm" color="gray.600" textAlign="center">
                        Test Phase 3 advanced detection capabilities
                      </Text>

                      <HStack spacing={3} wrap="wrap" justify="center">
                        <Button
                          colorScheme="orange"
                          size="sm"
                          onClick={testMultipleFaceDetection}
                          isDisabled={!isTestActive || !faceAuthHook.isReady}
                        >
                          Test Multiple Face Detection
                        </Button>
                        
                        <Button
                          colorScheme="purple"
                          size="sm"
                          onClick={testAppearanceChangeDetection}
                          isDisabled={!isTestActive || !faceAuthHook.isReady}
                        >
                          Test Appearance Change
                        </Button>
                        
                        <Button
                          colorScheme="red"
                          size="sm"
                          onClick={generateTestAlert}
                          isDisabled={!isTestActive || !faceAuthHook.isReady}
                        >
                          Generate Test Alert
                        </Button>
                        
                        <Button
                          colorScheme="blue"
                          size="sm"
                          onClick={captureTestEvidence}
                          isDisabled={!isTestActive || !faceAuthHook.isReady}
                        >
                          Capture Test Evidence
                        </Button>
                      </HStack>

                      {/* Test Results Display */}
                      {phase3Stats && (
                        <Box p={3} bg="blue.50" borderRadius="md" border="1px" borderColor="blue.200">
                          <Text fontSize="sm" fontWeight="bold" mb={2} color="blue.800">Test Results</Text>
                          <Text fontSize="xs" color="blue.700">
                            Use the buttons above to trigger Phase 3 detection tests. 
                            Results will appear in the event log and trigger appropriate alerts.
                          </Text>
                        </Box>
                      )}
                    </VStack>
                  </TabPanel>

                  {/* Evidence Tab */}
                  <TabPanel>
                    <VStack spacing={4} align="stretch">
                      {faceAuthHook.getEvidenceCapture && faceAuthHook.getEvidenceCapture().length > 0 ? (
                        <Table size="sm">
                          <Thead>
                            <Tr>
                              <Th>Time</Th>
                              <Th>Type</Th>
                              <Th>Severity</Th>
                              <Th>Details</Th>
                            </Tr>
                          </Thead>
                          <Tbody>
                            {faceAuthHook.getEvidenceCapture().slice(-10).reverse().map((evidence, index) => (
                              <Tr key={evidence.id || index}>
                                <Td fontSize="xs">
                                  {new Date(evidence.timestamp).toLocaleTimeString()}
                                </Td>
                                <Td>
                                  <Badge size="sm" colorScheme={evidence.severity === 'critical' ? 'red' : 'orange'}>
                                    {evidence.type}
                                  </Badge>
                                </Td>
                                <Td>
                                  <Badge size="sm" colorScheme={evidence.severity === 'critical' ? 'red' : 'yellow'}>
                                    {evidence.severity}
                                  </Badge>
                                </Td>
                                <Td fontSize="xs" maxW="200px" overflow="hidden" textOverflow="ellipsis">
                                  {evidence.data ? Object.keys(evidence.data).join(', ') : 'N/A'}
                                </Td>
                              </Tr>
                            ))}
                          </Tbody>
                        </Table>
                      ) : (
                        <Text color="gray.500" textAlign="center" py={4}>
                          No evidence captured yet
                        </Text>
                      )}
                    </VStack>
                  </TabPanel>

                  {/* Analytics Tab */}
                  <TabPanel>
                    <VStack spacing={4} align="stretch">
                      {/* Behavior Patterns */}
                      <Box>
                        <Text fontWeight="bold" mb={2}>Behavior Analysis</Text>
                        {faceAuthHook.getBehaviorPatterns && (
                          <Table size="sm">
                            <Tbody>
                              <Tr>
                                <Td fontWeight="bold">Authentication Events</Td>
                                <Td>{faceAuthHook.getBehaviorPatterns().authenticationTimes?.length || 0}</Td>
                              </Tr>
                              <Tr>
                                <Td fontWeight="bold">Failure Patterns</Td>
                                <Td>{faceAuthHook.getBehaviorPatterns().failurePatterns?.length || 0}</Td>
                              </Tr>
                              <Tr>
                                <Td fontWeight="bold">Analysis Window</Td>
                                <Td>{phase3Stats?.behaviorAnalysisWindow ? 
                                  `${Math.round(phase3Stats.behaviorAnalysisWindow / 60000)} minutes` : 'N/A'}</Td>
                              </Tr>
                            </Tbody>
                          </Table>
                        )}
                      </Box>

                      {/* Impersonation Alerts */}
                      <Box>
                        <Text fontWeight="bold" mb={2}>Recent Alerts</Text>
                        {faceAuthHook.getImpersonationAlerts && faceAuthHook.getImpersonationAlerts().length > 0 ? (
                          <Table size="sm">
                            <Thead>
                              <Tr>
                                <Th>Time</Th>
                                <Th>Type</Th>
                                <Th>Severity</Th>
                                <Th>Status</Th>
                              </Tr>
                            </Thead>
                            <Tbody>
                              {faceAuthHook.getImpersonationAlerts().slice(-5).reverse().map((alert, index) => (
                                <Tr key={alert.id || index}>
                                  <Td fontSize="xs">
                                    {new Date(alert.timestamp).toLocaleTimeString()}
                                  </Td>
                                  <Td fontSize="xs">{alert.type}</Td>
                                  <Td>
                                    <Badge size="sm" colorScheme={alert.severity === 'critical' ? 'red' : 'yellow'}>
                                      {alert.severity}
                                    </Badge>
                                  </Td>
                                  <Td>
                                    <Badge size="sm" colorScheme={alert.resolved ? 'green' : 'red'}>
                                      {alert.resolved ? 'Resolved' : 'Active'}
                                    </Badge>
                                  </Td>
                                </Tr>
                              ))}
                            </Tbody>
                          </Table>
                        ) : (
                          <Text color="gray.500" fontSize="sm">No alerts generated</Text>
                        )}
                      </Box>
                    </VStack>
                  </TabPanel>
                </TabPanels>
              </Tabs>
            </Box>
          </VStack>
        </HStack>
      </VStack>
    </Container>
  );
};

export default FaceAuthTest; 