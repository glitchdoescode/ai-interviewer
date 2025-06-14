import React, { useRef, useEffect, useState } from 'react';
import {
  Box,
  Text,
  Icon,
  Spinner,
  VStack,
  Alert,
  AlertIcon,
  Button
} from '@chakra-ui/react';
import { FaCamera, FaVideoSlash, FaUser } from 'react-icons/fa';

/**
 * Camera feed component for displaying video streams
 * Handles both candidate and AI interviewer video display
 */
const CameraFeed = ({
  stream = null,
  isEnabled = true,
  isLoading = false,
  error = null,
  placeholder = 'candidate',
  showControls = false,
  onRetry = null,
  width = '100%',
  height = '100%',
  borderRadius = 'lg',
  isSpeaking = false,
  ...props
}) => {
  const videoRef = useRef(null);
  const [videoError, setVideoError] = useState(null);

  // Set up video element with stream
  useEffect(() => {
    if (videoRef.current && stream) {
      try {
        videoRef.current.srcObject = stream;
        setVideoError(null);
      } catch (err) {
        console.error('Error setting video stream:', err);
        setVideoError('Failed to display video');
      }
    }
  }, [stream]);

  // Handle video element errors
  const handleVideoError = (event) => {
    console.error('Video element error:', event);
    setVideoError('Video playback error');
  };

  // Render loading state
  if (isLoading) {
    return (
      <Box
        width={width}
        height={height}
        bg="gray.100"
        borderRadius={borderRadius}
        display="flex"
        alignItems="center"
        justifyContent="center"
        border="2px solid"
        borderColor="gray.200"
        {...props}
      >
        <VStack spacing={3}>
          <Spinner size="lg" color="primary.500" />
          <Text fontSize="sm" color="gray.600">
            Connecting to camera...
          </Text>
        </VStack>
      </Box>
    );
  }

  // Render error state
  if (error || videoError) {
    return (
      <Box
        width={width}
        height={height}
        bg="red.50"
        borderRadius={borderRadius}
        display="flex"
        alignItems="center"
        justifyContent="center"
        border="2px solid"
        borderColor="red.200"
        p={4}
        {...props}
      >
        <VStack spacing={3} textAlign="center">
          <Icon as={FaVideoSlash} w={8} h={8} color="red.500" />
          <Alert status="error" borderRadius="md" size="sm">
            <AlertIcon boxSize="4" />
            <Text fontSize="sm">{error || videoError}</Text>
          </Alert>
          {onRetry && (
            <Button
              size="sm"
              colorScheme="red"
              variant="outline"
              onClick={onRetry}
            >
              Retry Camera
            </Button>
          )}
        </VStack>
      </Box>
    );
  }

  // Render placeholder when no stream or camera disabled
  if (!stream || !isEnabled) {
    const placeholderIcon = placeholder === 'ai' ? FaUser : FaCamera;
    const placeholderText = placeholder === 'ai' 
      ? 'AI Interviewer' 
      : 'Camera Off';

    return (
      <Box
        width={width}
        height={height}
        bg={placeholder === 'ai' ? 'primary.50' : 'gray.100'}
        borderRadius={borderRadius}
        display="flex"
        alignItems="center"
        justifyContent="center"
        border="2px solid"
        borderColor={placeholder === 'ai' ? 'primary.200' : 'gray.200'}
        position="relative"
        {...props}
      >
        <VStack spacing={3}>
          <Icon 
            as={placeholderIcon} 
            w={12} 
            h={12} 
            color={placeholder === 'ai' ? 'primary.500' : 'gray.500'} 
          />
          <Text 
            fontSize="md" 
            fontWeight="medium"
            color={placeholder === 'ai' ? 'primary.700' : 'gray.600'}
          >
            {placeholderText}
          </Text>
        </VStack>
        
        {/* Speaking indicator for AI */}
        {placeholder === 'ai' && isSpeaking && (
          <Box
            position="absolute"
            top={2}
            right={2}
            bg="green.500"
            color="white"
            px={2}
            py={1}
            borderRadius="full"
            fontSize="xs"
            fontWeight="bold"
            animation="pulse 1.5s infinite"
          >
            Speaking
          </Box>
        )}
      </Box>
    );
  }

  // Render video stream
  return (
    <Box
      width={width}
      height={height}
      position="relative"
      borderRadius={borderRadius}
      overflow="hidden"
      border="2px solid"
      borderColor={isSpeaking ? "green.400" : "gray.200"}
      boxShadow={isSpeaking ? "0 0 20px rgba(72, 187, 120, 0.5)" : "sm"}
      transition="all 0.3s ease"
      {...props}
    >
      <video
        ref={videoRef}
        autoPlay
        muted={placeholder === 'candidate'} // Mute candidate's own video to avoid feedback
        playsInline
        onError={handleVideoError}
        style={{
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          transform: placeholder === 'candidate' ? 'scaleX(-1)' : 'none', // Mirror candidate video
        }}
      />
      
      {/* Speaking indicator overlay */}
      {isSpeaking && (
        <Box
          position="absolute"
          top={3}
          left={3}
          bg="green.500"
          color="white"
          px={3}
          py={1}
          borderRadius="full"
          fontSize="sm"
          fontWeight="bold"
          display="flex"
          alignItems="center"
          gap={2}
          animation="pulse 1.5s infinite"
        >
          <Box
            w={2}
            h={2}
            bg="white"
            borderRadius="full"
            animation="ping 1s infinite"
          />
          Speaking
        </Box>
      )}
      
      {/* Camera status indicator */}
      <Box
        position="absolute"
        bottom={3}
        right={3}
        bg="blackAlpha.700"
        color="white"
        p={2}
        borderRadius="md"
        display="flex"
        alignItems="center"
        gap={2}
      >
        <Icon as={isEnabled ? FaCamera : FaVideoSlash} w={3} h={3} />
        <Text fontSize="xs">
          {isEnabled ? 'ON' : 'OFF'}
        </Text>
      </Box>
    </Box>
  );
};

export default CameraFeed; 
 
 