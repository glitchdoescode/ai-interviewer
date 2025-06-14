import React, { useState, useEffect } from 'react';
import {
  HStack,
  IconButton,
  Text,
  Box,
  Progress,
  Tooltip,
  Badge,
  VStack,
  useColorModeValue
} from '@chakra-ui/react';
import {
  FaMicrophone,
  FaMicrophoneSlash,
  FaVideo,
  FaVideoSlash,
  FaPhone,
  FaPhoneSlash,
  FaVolumeUp,
  FaVolumeMute
} from 'react-icons/fa';

/**
 * Audio controls component for video call interface
 * Provides mute/unmute, camera toggle, and connection status
 */
const AudioControls = ({
  micEnabled = true,
  cameraEnabled = true,
  onToggleMic = () => {},
  onToggleCamera = () => {},
  onEndCall = () => {},
  audioLevel = 0,
  connectionStatus = 'connected', // 'connecting', 'connected', 'disconnected', 'error'
  isLoading = false,
  disabled = false,
  showAudioLevel = true,
  showConnectionStatus = true,
  compact = false,
  ...props
}) => {
  const [audioLevelDisplay, setAudioLevelDisplay] = useState(0);
  
  // Smooth audio level animation
  useEffect(() => {
    const interval = setInterval(() => {
      setAudioLevelDisplay(current => {
        const target = micEnabled ? audioLevel : 0;
        const diff = target - current;
        return current + diff * 0.3; // Smooth transition
      });
    }, 50);

    return () => clearInterval(interval);
  }, [audioLevel, micEnabled]);

  // Color scheme based on connection status
  const getConnectionColor = () => {
    switch (connectionStatus) {
      case 'connected':
        return 'green';
      case 'connecting':
        return 'yellow';
      case 'disconnected':
      case 'error':
        return 'red';
      default:
        return 'gray';
    }
  };

  const connectionColor = getConnectionColor();
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');

  // Compact layout for mobile
  if (compact) {
    return (
      <HStack
        spacing={2}
        bg={bgColor}
        p={2}
        borderRadius="full"
        border="1px solid"
        borderColor={borderColor}
        boxShadow="lg"
        {...props}
      >
        <IconButton
          aria-label={micEnabled ? 'Mute microphone' : 'Unmute microphone'}
          icon={micEnabled ? <FaMicrophone /> : <FaMicrophoneSlash />}
          colorScheme={micEnabled ? 'green' : 'red'}
          size="sm"
          isRound
          onClick={onToggleMic}
          disabled={disabled || isLoading}
        />
        
        <IconButton
          aria-label={cameraEnabled ? 'Turn off camera' : 'Turn on camera'}
          icon={cameraEnabled ? <FaVideo /> : <FaVideoSlash />}
          colorScheme={cameraEnabled ? 'blue' : 'gray'}
          size="sm"
          isRound
          onClick={onToggleCamera}
          disabled={disabled || isLoading}
        />
        
        <IconButton
          aria-label="End interview"
          icon={<FaPhoneSlash />}
          colorScheme="red"
          size="sm"
          isRound
          onClick={onEndCall}
          disabled={disabled || isLoading}
        />
      </HStack>
    );
  }

  // Full layout for desktop
  return (
    <HStack
      spacing={6}
      bg={bgColor}
      p={4}
      borderRadius="xl"
      border="1px solid"
      borderColor={borderColor}
      boxShadow="lg"
      align="center"
      {...props}
    >
      {/* Microphone Control */}
      <VStack spacing={1}>
        <Tooltip
          label={micEnabled ? 'Mute microphone' : 'Unmute microphone'}
          placement="top"
        >
          <IconButton
            aria-label={micEnabled ? 'Mute microphone' : 'Unmute microphone'}
            icon={micEnabled ? <FaMicrophone /> : <FaMicrophoneSlash />}
            colorScheme={micEnabled ? 'green' : 'red'}
            size="lg"
            isRound
            onClick={onToggleMic}
            disabled={disabled || isLoading}
            isLoading={isLoading}
          />
        </Tooltip>
        
        {/* Audio Level Indicator */}
        {showAudioLevel && (
          <Box width="40px" height="4px">
            <Progress
              value={audioLevelDisplay * 100}
              colorScheme={micEnabled ? 'green' : 'gray'}
              size="sm"
              borderRadius="full"
              bg="gray.200"
            />
          </Box>
        )}
        
        <Text fontSize="xs" color="gray.600">
          {micEnabled ? 'Mic' : 'Muted'}
        </Text>
      </VStack>

      {/* Camera Control */}
      <VStack spacing={1}>
        <Tooltip
          label={cameraEnabled ? 'Turn off camera' : 'Turn on camera'}
          placement="top"
        >
          <IconButton
            aria-label={cameraEnabled ? 'Turn off camera' : 'Turn on camera'}
            icon={cameraEnabled ? <FaVideo /> : <FaVideoSlash />}
            colorScheme={cameraEnabled ? 'blue' : 'gray'}
            size="lg"
            isRound
            onClick={onToggleCamera}
            disabled={disabled || isLoading}
            isLoading={isLoading}
          />
        </Tooltip>
        
        <Text fontSize="xs" color="gray.600">
          {cameraEnabled ? 'Camera' : 'Off'}
        </Text>
      </VStack>

      {/* Connection Status */}
      {showConnectionStatus && (
        <VStack spacing={1}>
          <Box
            w={4}
            h={4}
            bg={`${connectionColor}.500`}
            borderRadius="full"
            animation={connectionStatus === 'connecting' ? 'pulse 1.5s infinite' : 'none'}
          />
          <Badge
            colorScheme={connectionColor}
            variant="subtle"
            fontSize="xs"
            textTransform="capitalize"
          >
            {connectionStatus}
          </Badge>
        </VStack>
      )}

      {/* Spacer */}
      <Box flex={1} />

      {/* End Call Button */}
      <VStack spacing={1}>
        <Tooltip label="End interview" placement="top">
          <IconButton
            aria-label="End interview"
            icon={<FaPhoneSlash />}
            colorScheme="red"
            size="lg"
            isRound
            onClick={onEndCall}
            disabled={disabled || isLoading}
            isLoading={isLoading}
          />
        </Tooltip>
        
        <Text fontSize="xs" color="red.600">
          End Call
        </Text>
      </VStack>
    </HStack>
  );
};

/**
 * Audio level visualizer component
 * Shows real-time audio levels as animated bars
 */
export const AudioLevelVisualizer = ({ 
  audioLevel = 0, 
  isActive = true, 
  barCount = 5,
  height = "20px",
  ...props 
}) => {
  const bars = Array.from({ length: barCount }, (_, i) => i);
  const threshold = i => (i + 1) / barCount;

  return (
    <HStack spacing={1} height={height} align="end" {...props}>
      {bars.map(i => (
        <Box
          key={i}
          width="3px"
          height={audioLevel > threshold(i) && isActive ? "100%" : "20%"}
          bg={audioLevel > threshold(i) && isActive ? "green.500" : "gray.300"}
          borderRadius="full"
          transition="all 0.1s ease"
        />
      ))}
    </HStack>
  );
};

export default AudioControls; 
 
 