import React, { useEffect, useState, useCallback } from 'react';
import {
  Box,
  VStack,
  HStack,
  Text,
  Badge,
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription,
  Icon,
  useColorModeValue,
} from '@chakra-ui/react';
import { FaShieldAlt, FaClock, FaCheckCircle, FaExclamationTriangle } from 'react-icons/fa';
import { useFaceAuthentication } from '../../hooks/useFaceAuthentication';
import FaceEnrollment from './FaceEnrollment';

/**
 * Face Authentication Manager Component
 * Manages the complete face authentication lifecycle including enrollment,
 * periodic re-authentication, and impersonation detection
 */
const FaceAuthenticationManager = ({
  videoRef,
  isActive = true,
  onAuthenticationEvent,
  showEnrollmentUI = true,
  onInitialEnrollmentSuccess,
  onInitialEnrollmentFailure,
  initialEmbedding,
  initialSessionId,
}) => {
  const [lastCallbackEventId, setLastCallbackEventId] = useState(null);
  const [enrollmentVideoReady, setEnrollmentVideoReady] = useState(false);
  
  const {
    isLoading,
    isReady,
    error,
    enrollmentStatus,
    authenticationStatus,
    authenticationScore,
    lastAuthenticationTime,
    authenticationEvents,
    enrollFace,
    resetAuthentication,
    authConfig,
    getSlidingWindowStats,
    currentEnrollmentAttempt,
  } = useFaceAuthentication(
    videoRef, 
    showEnrollmentUI ? (isActive && enrollmentVideoReady) : isActive, 
    initialSessionId,
    initialEmbedding
  );

  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');

  // Get real-time performance stats
  const performanceStats = getSlidingWindowStats ? getSlidingWindowStats() : {};

  // Handle authentication events callback with deduplication
  useEffect(() => {
    if (onAuthenticationEvent && authenticationEvents.length > 0) {
      const latestEvent = authenticationEvents[authenticationEvents.length - 1];
      
      if (latestEvent.id && latestEvent.id !== lastCallbackEventId) {
        console.log('FaceAuthManager: Calling general event callback for event:', latestEvent.id, latestEvent);
        setLastCallbackEventId(latestEvent.id);
        onAuthenticationEvent(latestEvent);
      } else {
        // console.log('FaceAuthManager: Skipping duplicate general callback for event:', latestEvent.id);
      }
    }
  }, [authenticationEvents, onAuthenticationEvent, lastCallbackEventId]);

  // Calculate enrollment attempts from events
  const enrollmentAttempts = authenticationEvents.filter(
    event => event.type === 'enrollment_failed' || event.type === 'enrollment_success'
  ).length;

  const getAuthenticationStatusBadge = () => {
    if (enrollmentStatus !== 'enrolled') {
      return null;
    }

    const getStatusColor = () => {
      switch (authenticationStatus) {
        case 'authenticated':
          return 'green';
        case 'failed':
          return 'red';
        case 'pending':
          return 'yellow';
        default:
          return 'gray';
      }
    };

    const getStatusText = () => {
      switch (authenticationStatus) {
        case 'authenticated':
          return 'Verified';
        case 'failed':
          return 'Failed';
        case 'pending':
          return 'Pending';
        default:
          return 'Unknown';
      }
    };

    return (
      <Badge colorScheme={getStatusColor()} variant="solid">
        {getStatusText()}
      </Badge>
    );
  };

  const formatLastAuthTime = () => {
    if (!lastAuthenticationTime) return 'Never';
    
    const now = new Date();
    const diff = Math.floor((now - lastAuthenticationTime) / 1000 / 60); // minutes
    
    if (diff < 1) return 'Just now';
    if (diff < 60) return `${diff}m ago`;
    
    const hours = Math.floor(diff / 60);
    return `${hours}h ${diff % 60}m ago`;
  };

  const getNextAuthTime = () => {
    if (!lastAuthenticationTime || enrollmentStatus !== 'enrolled') return null;
    
    const nextAuth = new Date(lastAuthenticationTime.getTime() + authConfig.authenticationInterval);
    const now = new Date();
    const diff = Math.floor((nextAuth - now) / 1000 / 60); // minutes
    
    if (diff <= 0) return 'Due now';
    if (diff < 60) return `${diff}m`;
    
    const hours = Math.floor(diff / 60);
    return `${hours}h ${diff % 60}m`;
  };

  const renderAuthenticationStatus = () => {
    if (enrollmentStatus !== 'enrolled') return null;

    return (
      <Box
        p={4}
        bg={bgColor}
        borderWidth={1}
        borderColor={borderColor}
        borderRadius="md"
        w="full"
      >
        <VStack spacing={3} align="stretch">
          <HStack justify="space-between">
            <HStack>
              <Icon as={FaShieldAlt} color="blue.500" />
              <Text fontWeight="semibold">Authentication Status</Text>
            </HStack>
            {getAuthenticationStatusBadge()}
          </HStack>
          
          <HStack justify="space-between" fontSize="sm">
            <VStack align="start" spacing={1}>
              <Text color="gray.600">Last Verified</Text>
              <HStack>
                <Icon as={FaClock} color="gray.400" boxSize={3} />
                <Text>{formatLastAuthTime()}</Text>
              </HStack>
            </VStack>
            
            <VStack align="end" spacing={1}>
              <Text color="gray.600">Next Check</Text>
              <HStack>
                <Icon as={FaClock} color="gray.400" boxSize={3} />
                <Text>{getNextAuthTime()}</Text>
              </HStack>
            </VStack>
          </HStack>
          
          {authenticationScore > 0 && (
            <HStack justify="space-between" fontSize="sm">
              <Text color="gray.600">Confidence Score</Text>
              <Badge
                colorScheme={authenticationScore >= 0.7 ? 'green' : authenticationScore >= 0.5 ? 'yellow' : 'red'}
              >
                {Math.round(authenticationScore * 100)}%
              </Badge>
            </HStack>
          )}
        </VStack>
      </Box>
    );
  };

  const renderRealTimeVerificationStats = () => {
    if (enrollmentStatus !== 'enrolled' || !performanceStats.windowSize) return null;

    const getStabilityColor = () => {
      if (performanceStats.successRate >= 0.8) return 'green';
      if (performanceStats.successRate >= 0.6) return 'yellow';
      return 'red';
    };

    const getFailureAlertLevel = () => {
      if (performanceStats.consecutiveFailures >= 3) return 'error';
      if (performanceStats.consecutiveFailures >= 2) return 'warning';
      return 'info';
    };

    return (
      <Box
        p={4}
        bg={bgColor}
        borderWidth={1}
        borderColor={borderColor}
        borderRadius="md"
        w="full"
      >
        <VStack spacing={3} align="stretch">
          <HStack>
            <Icon as={FaCheckCircle} color="blue.500" />
            <Text fontWeight="semibold">Real-time Verification</Text>
          </HStack>
          
          <HStack justify="space-between" fontSize="sm">
            <VStack align="start" spacing={1}>
              <Text color="gray.600">Success Rate</Text>
              <Badge colorScheme={getStabilityColor()} variant="solid">
                {Math.round(performanceStats.successRate * 100)}%
              </Badge>
            </VStack>
            
            <VStack align="center" spacing={1}>
              <Text color="gray.600">Avg Confidence</Text>
              <Badge 
                colorScheme={performanceStats.averageSimilarity >= 0.7 ? 'green' : 'yellow'}
                variant="outline"
              >
                {Math.round(performanceStats.averageSimilarity * 100)}%
              </Badge>
            </VStack>
            
            <VStack align="end" spacing={1}>
              <Text color="gray.600">Window Size</Text>
              <Text fontWeight="semibold">{performanceStats.windowSize}/5</Text>
            </VStack>
          </HStack>

          {performanceStats.consecutiveFailures > 0 && (
            <Alert status={getFailureAlertLevel()} size="sm" borderRadius="md">
              <AlertIcon boxSize={3} />
              <Box fontSize="xs">
                <AlertTitle>
                  {performanceStats.consecutiveFailures} consecutive failure{performanceStats.consecutiveFailures > 1 ? 's' : ''}
                </AlertTitle>
                <AlertDescription>
                  {performanceStats.consecutiveFailures >= 3 
                    ? 'Critical: Manual verification may be required'
                    : 'Monitoring authentication stability'
                  }
                </AlertDescription>
              </Box>
            </Alert>
          )}

          <HStack justify="space-between" fontSize="xs" color="gray.500">
            <Text>Cache: {performanceStats.cacheSize}/20 entries</Text>
            <Text>Real-time monitoring: Active</Text>
          </HStack>
        </VStack>
      </Box>
    );
  };

  const renderRecentEvents = () => {
    if (authenticationEvents.length === 0) return null;

    const recentEvents = authenticationEvents.slice(-3).reverse();

    return (
      <Box
        p={4}
        bg={bgColor}
        borderWidth={1}
        borderColor={borderColor}
        borderRadius="md"
        w="full"
      >
        <VStack spacing={3} align="stretch">
          <HStack>
            <Icon as={FaCheckCircle} color="blue.500" />
            <Text fontWeight="semibold">Recent Events</Text>
          </HStack>
          
          <VStack spacing={2} align="stretch">
            {recentEvents.map((event) => {
              const getEventIcon = () => {
                if (event.type.includes('success')) return FaCheckCircle;
                if (event.type.includes('failed') || event.type.includes('error')) return FaExclamationTriangle;
                return FaClock;
              };

              const getEventColor = () => {
                if (event.type.includes('success')) return 'green.500';
                if (event.type.includes('failed') || event.type.includes('error')) return 'red.500';
                if (event.type.includes('impersonation')) return 'red.600';
                return 'blue.500';
              };

              const getEventDescription = () => {
                switch (event.type) {
                  case 'enrollment_success':
                    return 'Face enrolled successfully';
                  case 'enrollment_failed':
                    return `Enrollment failed: ${event.data.error || 'Unknown error'}`;
                  case 'authentication_success':
                    const method = event.data.method === 'real_time' ? ' (real-time)' : '';
                    return `Authentication successful${method} (${Math.round(event.data.similarity * 100)}%)`;
                  case 'authentication_failed':
                    const severity = event.data.severity ? ` [${event.data.severity}]` : '';
                    return `Authentication failed${severity}: ${event.data.reason || 'Low similarity'}`;
                  case 'critical_authentication_failure':
                    return `Critical failure: ${event.data.reason} (${Math.round(event.data.similarity * 100)}%)`;
                  case 'authentication_failure_escalation':
                    return `Authentication escalated: ${event.data.consecutiveFailures} consecutive failures`;
                  case 'impersonation_detected':
                    const rtMethod = event.data.method === 'real_time' ? ' [Real-time]' : '';
                    return `Impersonation detected${rtMethod} (${Math.round(event.data.similarity * 100)}%)`;
                  case 'authentication_error':
                    return `Authentication error: ${event.data.error}`;
                  case 'real_time_verification_error':
                    return `Real-time verification error: ${event.data.error}`;
                  case 'authentication_reset':
                    return 'Authentication reset';
                  default:
                    return event.type.replace(/_/g, ' ');
                }
              };

              return (
                <HStack key={event.id} spacing={3} fontSize="sm">
                  <Icon as={getEventIcon()} color={getEventColor()} boxSize={4} />
                  <VStack align="start" spacing={0} flex={1}>
                    <Text>{getEventDescription()}</Text>
                    <Text color="gray.500" fontSize="xs">
                      {new Date(event.timestamp).toLocaleTimeString()}
                    </Text>
                  </VStack>
                </HStack>
              );
            })}
          </VStack>
        </VStack>
      </Box>
    );
  };

  const handleEnrollmentVideoReady = useCallback(() => {
    setEnrollmentVideoReady(true);
    console.log('FaceAuthManager: Enrollment video element is ready.');
  }, []);

  const handleEnrollmentAttempt = useCallback(async () => {
    if (!enrollFace) return;
    console.log('FaceAuthManager: Attempting enrollment via handleEnrollmentAttempt.');
    try {
      const embedding = await enrollFace();
      console.log('FaceAuthManager: enrollFace call successful, embedding captured.');
      if (onInitialEnrollmentSuccess) {
        onInitialEnrollmentSuccess(embedding);
      }
    } catch (err) {
      console.error('FaceAuthManager: enrollFace call failed.', err);
      if (onInitialEnrollmentFailure) {
        onInitialEnrollmentFailure(err);
      }
    }
  }, [enrollFace, onInitialEnrollmentSuccess, onInitialEnrollmentFailure]);
  
  const handleResetAuth = useCallback(() => {
    if (resetAuthentication) {
      console.log('FaceAuthManager: Resetting authentication.');
      resetAuthentication();
    }
  }, [resetAuthentication]);

  // The FaceEnrollment component should be rendered if showEnrollmentUI is true 
  // and enrollmentStatus is not 'enrolled'. It will receive isLoading and error props.
  if (showEnrollmentUI && enrollmentStatus !== 'enrolled') {
    return (
      <FaceEnrollment
        videoRef={videoRef}
        enrollmentStatus={enrollmentStatus}
        isLoading={isLoading}
        error={typeof error?.message === 'string' ? error.message : error ? String(error) : ''}
        authenticationScore={authenticationScore}
        onEnroll={handleEnrollmentAttempt}
        onReset={handleResetAuth}
        enrollmentAttempts={currentEnrollmentAttempt}
        maxAttempts={authConfig.maxEnrollmentAttempts}
        areModelsReady={isReady}
        isVideoElementReady={enrollmentVideoReady}
        onVideoReady={handleEnrollmentVideoReady}
      />
    );
  }

  // Fallback to rendering the main UI (status, stats, events) if not showing enrollment UI
  // or if already enrolled.
  return (
    <VStack spacing={4} w="full" align="stretch">
      {!showEnrollmentUI && enrollmentStatus === 'enrolled' && renderAuthenticationStatus()}
      {!showEnrollmentUI && enrollmentStatus === 'enrolled' && renderRealTimeVerificationStats()}
      {!showEnrollmentUI && renderRecentEvents()}
      {error && !isLoading && (enrollmentStatus === 'enrolled' || !showEnrollmentUI) && (
        <Alert status="error" borderRadius="md">
          <AlertIcon />
          <AlertTitle>Runtime Error</AlertTitle>
          <AlertDescription>{typeof error?.message === 'string' ? error.message : 'An unexpected runtime error occurred.'}</AlertDescription>
        </Alert>
      )}
    </VStack>
  );
};

export default FaceAuthenticationManager; 