import React, { useEffect, useState } from 'react';
import {
  Box,
  Button,
  VStack,
  Text,
  useToast,
  IconButton,
  HStack,
  Spinner,
  Badge
} from '@chakra-ui/react';
import { FaMicrophone, FaMicrophoneSlash } from 'react-icons/fa';
import { useLiveKitClient } from '../hooks/useLiveKitClient';

/**
 * Real-time interview interface component using LiveKit for audio streaming
 */
export const InterviewInterfaceRealtime = ({
  userId,
  userName,
  interviewId,
  onError
}) => {
  const toast = useToast();
  
  const {
    isConnecting,
    isConnected,
    error,
    isMicrophoneEnabled,
    connect,
    disconnect,
    toggleMicrophone
  } = useLiveKitClient(userId, userName, interviewId);

  // Handle LiveKit errors
  useEffect(() => {
    if (error) {
      toast({
        title: 'Connection Error',
        description: error,
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
      onError?.(error);
    }
  }, [error, toast, onError]);

  // Connection status badge
  const ConnectionStatus = () => (
    <Badge
      colorScheme={isConnected ? 'green' : isConnecting ? 'yellow' : 'red'}
      variant="subtle"
      px={3}
      py={1}
      borderRadius="full"
    >
      {isConnected ? 'Connected' : isConnecting ? 'Connecting...' : 'Disconnected'}
    </Badge>
  );

  return (
    <Box
      p={4}
      borderWidth="1px"
      borderRadius="lg"
      shadow="sm"
      bg="white"
    >
      <VStack spacing={4} align="stretch">
        {/* Connection Status */}
        <HStack justifyContent="space-between" alignItems="center">
          <Text fontSize="lg" fontWeight="medium">Real-time Interview</Text>
          <ConnectionStatus />
        </HStack>

        {/* Controls */}
        <HStack spacing={4} justifyContent="center">
          {/* Connect/Disconnect Button */}
          <Button
            colorScheme={isConnected ? 'red' : 'green'}
            onClick={isConnected ? disconnect : connect}
            isLoading={isConnecting}
            loadingText="Connecting..."
            leftIcon={isConnecting ? <Spinner size="sm" /> : null}
          >
            {isConnected ? 'Disconnect' : 'Connect'}
          </Button>

          {/* Microphone Toggle */}
          <IconButton
            aria-label="Toggle microphone"
            icon={isMicrophoneEnabled ? <FaMicrophone /> : <FaMicrophoneSlash />}
            onClick={toggleMicrophone}
            isDisabled={!isConnected}
            colorScheme={isMicrophoneEnabled ? 'green' : 'gray'}
          />
        </HStack>

        {/* Status Messages */}
        {error && (
          <Text color="red.500" fontSize="sm">
            Error: {error}
          </Text>
        )}
      </VStack>
    </Box>
  );
}; 