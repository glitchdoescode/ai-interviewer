import React, { useState, useCallback } from 'react';
import {
  Box,
  Button,
  Text,
  VStack,
  HStack,
  Progress,
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription,
  Badge,
  Circle,
  Icon,
  useColorModeValue,
} from '@chakra-ui/react';
import { CheckIcon, WarningIcon, InfoIcon } from '@chakra-ui/icons';
import { FaUser, FaCamera, FaShieldAlt } from 'react-icons/fa';

/**
 * Face Enrollment Component
 * Guides users through the face enrollment process for authentication
 */
const FaceEnrollment = ({
  enrollmentStatus,
  isLoading,
  error,
  authenticationScore,
  onEnroll,
  onReset,
  enrollmentAttempts = 0,
  maxAttempts = 3,
  areModelsReady,
  isVideoElementReady,
  onVideoReady,
  videoRef,
}) => {
  const [showInstructions, setShowInstructions] = useState(true);
  
  // Move all useColorModeValue calls to component level
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');
  const successColor = useColorModeValue('green.500', 'green.300');
  const warningColor = useColorModeValue('orange.500', 'orange.300');
  const errorColor = useColorModeValue('red.500', 'red.300');
  const blueCardBg = useColorModeValue('blue.50', 'blue.900');
  const greenCardBg = useColorModeValue('green.50', 'green.900');

  const handleEnroll = useCallback(() => {
    setShowInstructions(false);
    onEnroll();
  }, [onEnroll]);

  const handleReset = useCallback(() => {
    setShowInstructions(true);
    onReset();
  }, [onReset]);

  const getStatusColor = () => {
    switch (enrollmentStatus) {
      case 'enrolled':
        return successColor;
      case 'enrolling':
        return warningColor;
      case 'not_enrolled':
        return enrollmentAttempts > 0 ? errorColor : 'gray.400';
      default:
        return 'gray.400';
    }
  };

  const getStatusIcon = () => {
    switch (enrollmentStatus) {
      case 'enrolled':
        return CheckIcon;
      case 'enrolling':
        return InfoIcon;
      case 'not_enrolled':
        return enrollmentAttempts > 0 ? WarningIcon : FaUser;
      default:
        return FaUser;
    }
  };

  const renderInstructions = () => (
    <VStack spacing={4} align="center" textAlign="center">
      <Icon as={FaShieldAlt} boxSize={12} color="blue.500" />
      
      <Text fontSize="xl" fontWeight="bold">
        Face Authentication Setup
      </Text>
      
      <Text color="gray.600" maxW="400px">
        We'll capture your face profile to enable secure authentication during your interview. 
        This helps ensure interview integrity and prevents impersonation.
      </Text>
      
      <Box
        p={4}
        bg={blueCardBg}
        borderRadius="md"
        borderWidth={1}
        borderColor="blue.200"
        maxW="400px"
      >
        <VStack spacing={2} align="start">
          <Text fontSize="sm" fontWeight="semibold" color="blue.700">
            📸 For best results:
          </Text>
          <Text fontSize="sm" color="blue.600">
            • Look directly at the camera
          </Text>
          <Text fontSize="sm" color="blue.600">
            • Ensure good lighting on your face
          </Text>
          <Text fontSize="sm" color="blue.600">
            • Remove glasses if possible
          </Text>
          <Text fontSize="sm" color="blue.600">
            • Keep your face centered in the frame
          </Text>
        </VStack>
      </Box>
      
      <Button
        colorScheme="blue"
        size="lg"
        leftIcon={<Icon as={FaCamera} />}
        onClick={handleEnroll}
        isLoading={isLoading}
        isDisabled={isLoading || !areModelsReady || !isVideoElementReady}
        loadingText={!areModelsReady || !isVideoElementReady ? "Preparing system..." : (isLoading ? "Initializing..." : "Start Face Enrollment")}
      >
        {(!areModelsReady || !isVideoElementReady) && isLoading ? "Preparing system..." : (isLoading && enrollmentStatus === 'enrolling' ? 'Processing...' : 'Start Face Enrollment')}
      </Button>
      
      <Text fontSize="xs" color="gray.500" maxW="350px">
        Your face data is processed locally and securely. No images are stored, 
        only mathematical representations for comparison.
      </Text>
    </VStack>
  );

  const renderEnrollmentProgress = () => (
    <VStack spacing={4} align="center" textAlign="center">
      <Circle size={16} bg={getStatusColor()} color="white">
        <Icon as={getStatusIcon()} boxSize={8} />
      </Circle>
      
      <VStack spacing={2}>
        <Text fontSize="lg" fontWeight="bold">
          {enrollmentStatus === 'enrolling' && 'Capturing Face Profile...'}
          {enrollmentStatus === 'enrolled' && 'Enrollment Successful!'}
          {enrollmentStatus === 'not_enrolled' && enrollmentAttempts > 0 && 'Enrollment Failed'}
        </Text>
        
        {enrollmentStatus === 'enrolling' && (
          <Text color="gray.600">
            Please look directly at the camera and stay still
          </Text>
        )}
        
        {enrollmentStatus === 'enrolled' && (
          <VStack spacing={2}>
            <Text color="gray.600">
              Your face has been successfully enrolled for authentication
            </Text>
            <HStack>
              <Badge colorScheme="green">
                Confidence: {Math.round(authenticationScore * 100)}%
              </Badge>
            </HStack>
          </VStack>
        )}
      </VStack>
      
      {enrollmentStatus === 'enrolling' && (
        <Box w="full" maxW="300px">
          <Progress
            isIndeterminate
            colorScheme="blue"
            size="sm"
            borderRadius="md"
          />
        </Box>
      )}
      
      {error && (
        <Alert status="error" borderRadius="md" maxW="400px">
          <AlertIcon />
          <Box>
            <AlertTitle fontSize="sm">Enrollment Failed</AlertTitle>
            <AlertDescription fontSize="sm">{typeof error?.message === 'string' ? error.message : 'An enrollment error occurred.'}</AlertDescription>
          </Box>
        </Alert>
      )}
      
      {enrollmentAttempts > 0 && enrollmentStatus === 'not_enrolled' && (
        <Box maxW="400px">
          <Text fontSize="sm" color="gray.600" mb={2}>
            Attempt {enrollmentAttempts} of {maxAttempts}
          </Text>
          
          <Progress
            value={(enrollmentAttempts / maxAttempts) * 100}
            colorScheme={enrollmentAttempts >= maxAttempts ? 'red' : 'orange'}
            size="sm"
            borderRadius="md"
          />
          
          {enrollmentAttempts < maxAttempts && (
            <Button
              mt={3}
              colorScheme="blue"
              variant="outline"
              size="sm"
              onClick={handleEnroll}
              isLoading={isLoading}
              isDisabled={isLoading || !areModelsReady || !isVideoElementReady}
              loadingText={isLoading ? "Processing..." : "Try Again"}
            >
              Try Again
            </Button>
          )}
          
          {enrollmentAttempts >= maxAttempts && (
            <Alert status="warning" mt={3}>
              <AlertIcon />
              <Box>
                <AlertTitle fontSize="sm">Maximum Attempts Reached</AlertTitle>
                <AlertDescription fontSize="sm">
                  Please check your camera setup and lighting, then reset to try again.
                </AlertDescription>
              </Box>
            </Alert>
          )}
        </Box>
      )}
    </VStack>
  );

  const renderEnrolledState = () => (
    <VStack spacing={4} align="center" textAlign="center">
      <Circle size={16} bg={successColor} color="white">
        <Icon as={CheckIcon} boxSize={8} />
      </Circle>
      
      <VStack spacing={2}>
        <Text fontSize="lg" fontWeight="bold" color={successColor}>
          Face Authentication Active
        </Text>
        <Text color="gray.600">
          Your identity will be verified periodically during the interview
        </Text>
      </VStack>
      
      <Box
        p={3}
        bg={greenCardBg}
        borderRadius="md"
        borderWidth={1}
        borderColor="green.200"
        maxW="350px"
      >
        <VStack spacing={2}>
          <HStack>
            <Icon as={FaShieldAlt} color="green.600" />
            <Text fontSize="sm" fontWeight="semibold" color="green.700">
              Security Features Enabled
            </Text>
          </HStack>
          <Text fontSize="xs" color="green.600">
            • Periodic identity verification every 10 minutes
          </Text>
          <Text fontSize="xs" color="green.600">
            • Real-time impersonation detection
          </Text>
          <Text fontSize="xs" color="green.600">
            • Secure biometric comparison
          </Text>
        </VStack>
      </Box>
      
      <Button
        variant="outline"
        size="sm"
        colorScheme="gray"
        onClick={handleReset}
      >
        Reset Authentication
      </Button>
    </VStack>
  );

  return (
    <Box
      p={6}
      bg={bgColor}
      borderWidth={1}
      borderColor={borderColor}
      borderRadius="lg"
      maxW="500px"
      mx="auto"
    >
      {/* Conditionally render video element if not enrolled */}
      {enrollmentStatus !== 'enrolled' && (
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          style={{ 
            width: '100%', 
            maxWidth: '300px', 
            borderRadius: 'md', 
            margin: '10px auto',
            display: 'block'
          }}
          onCanPlay={() => {
            console.log('FaceEnrollment: Video onCanPlay fired.');
            if (videoRef && videoRef.current) {
              console.log('FaceEnrollment: videoRef.current IS available. video state:', videoRef.current.readyState, 'Calling onVideoReady.');
              if (onVideoReady) {
                onVideoReady();
              }
            } else {
              console.error('FaceEnrollment: videoRef.current is NOT available in onCanPlay. NOT calling onVideoReady.');
            }
          }}
          onError={(e) => {
            console.error('FaceEnrollment: Video element error:', e);
          }}
        />
      )}
      
      {showInstructions && enrollmentStatus === 'not_enrolled' && enrollmentAttempts === 0 && renderInstructions()}
      
      {(enrollmentStatus === 'enrolling' || 
        (enrollmentStatus === 'not_enrolled' && enrollmentAttempts > 0)) && 
        renderEnrollmentProgress()}
      
      {enrollmentStatus === 'enrolled' && renderEnrolledState()}
    </Box>
  );
};

export default FaceEnrollment; 