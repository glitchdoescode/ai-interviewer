import React, { useEffect, useRef } from 'react';
import { Box, Flex, Text, Avatar, useColorModeValue, Badge, Button } from '@chakra-ui/react';
import { FaPlay, FaStop } from 'react-icons/fa';

/**
 * Component for displaying a single chat message
 * @param {Object} props - Component props
 * @param {string} props.message - Message content
 * @param {string} props.sender - Message sender ('user' or 'assistant')
 * @param {boolean} props.isLoading - Whether the message is in loading state
 * @param {string} props.audioUrl - Optional URL for audio message
 * @param {boolean} props.isHint - Whether this message is a hint
 */
const ChatMessage = ({ message, sender, isLoading = false, audioUrl, isHint = false }) => {
  const isUser = sender === 'user';
  const audioRef = useRef(null);
  const [isPlaying, setIsPlaying] = React.useState(false);
  const [audioError, setAudioError] = React.useState(null);

  const bgColor = useColorModeValue(
    isUser ? 'blue.50' : isHint ? 'purple.50' : 'gray.50',
    isUser ? 'blue.900' : isHint ? 'purple.900' : 'gray.700'
  );
  const textColor = useColorModeValue(
    isUser ? 'blue.800' : isHint ? 'purple.800' : 'gray.800',
    isUser ? 'blue.100' : isHint ? 'purple.100' : 'gray.100'
  );

  // Loading animation styles
  const loadingStyle = isLoading
    ? {
        position: 'relative',
        overflow: 'hidden',
        '&:after': {
          content: '""',
          position: 'absolute',
          bottom: 0,
          left: 0,
          height: '2px',
          width: '30%',
          animation: 'loading 1.5s infinite',
          background: 'brand.500',
        },
        '@keyframes loading': {
          '0%': { left: '0%', width: '30%' },
          '50%': { left: '70%', width: '30%' },
          '100%': { left: '0%', width: '30%' },
        },
      }
    : {};

  // Handle audio play/pause
  const toggleAudio = () => {
    if (!audioRef.current) return;
    
    console.log('Attempting to play/pause audio:', audioUrl);
    
    if (isPlaying) {
      audioRef.current.pause();
    } else {
      // Clear any previous errors
      setAudioError(null);
      
      // Try to play the audio
      audioRef.current.play().catch(err => {
        console.error('Error playing audio:', err);
        setAudioError('Could not play audio. Please click the play button.');
      });
    }
  };

  // Update isPlaying state based on audio events
  useEffect(() => {
    const audioElement = audioRef.current;
    if (!audioElement) return;

    const handlePlay = () => setIsPlaying(true);
    const handlePause = () => setIsPlaying(false);
    const handleEnded = () => setIsPlaying(false);
    const handleError = (e) => {
      console.error('Audio playback error:', e);
      setIsPlaying(false);
      setAudioError('Error playing audio. Please try again.');
    };

    audioElement.addEventListener('play', handlePlay);
    audioElement.addEventListener('pause', handlePause);
    audioElement.addEventListener('ended', handleEnded);
    audioElement.addEventListener('error', handleError);

    return () => {
      audioElement.removeEventListener('play', handlePlay);
      audioElement.removeEventListener('pause', handlePause);
      audioElement.removeEventListener('ended', handleEnded);
      audioElement.removeEventListener('error', handleError);
    };
  }, []);

  // Fix URL if needed - ensure it starts with /api
  useEffect(() => {
    if (audioUrl && audioUrl.trim() !== '') {
      console.log('Initializing audio with URL:', audioUrl);
      
      // If the URL doesn't start with / or http, ensure it starts with /api
      if (audioRef.current) {
        const formattedUrl = audioUrl.startsWith('/') || audioUrl.startsWith('http') 
          ? audioUrl 
          : `/api/audio/response/${audioUrl}`;
          
        console.log('Using formatted audio URL:', formattedUrl);
        audioRef.current.src = formattedUrl;
        
        // Attempt to load the audio
        audioRef.current.load();
      }
    }
  }, [audioUrl]);

  // Debug when component renders
  useEffect(() => {
    if (audioUrl) {
      console.log('ChatMessage rendered with audioUrl:', audioUrl);
    }
  }, [audioUrl]);

  return (
    <Flex
      width="100%"
      justify={isUser ? 'flex-end' : 'flex-start'}
      mb={4}
    >
      {!isUser && (
        <Avatar 
          size="sm" 
          name="AI Interviewer" 
          bg={isHint ? "purple.500" : "brand.500"} 
          color="white" 
          mr={2} 
        />
      )}
      
      <Box
        maxW={{ base: '90%', md: '70%' }}
        p={3}
        borderRadius="lg"
        bg={bgColor}
        color={textColor}
        boxShadow="sm"
        sx={loadingStyle}
      >
        {isHint && (
          <Badge colorScheme="purple" mb={2}>Hint</Badge>
        )}
        
        <Text whiteSpace="pre-wrap">{message}</Text>
        
        {audioUrl && (
          <Box mt={2}>
            <audio 
              ref={audioRef} 
              style={{ display: 'none' }}
              preload="auto"
            />
            <Flex alignItems="center">
              <Button 
                leftIcon={isPlaying ? <FaStop /> : <FaPlay />}
                size="sm"
                colorScheme={isPlaying ? "red" : "blue"}
                onClick={toggleAudio}
                mr={2}
              >
                {isPlaying ? "Stop" : "Play Response"}
              </Button>
              {audioError && (
                <Text color="red.500" fontSize="sm">{audioError}</Text>
              )}
            </Flex>
          </Box>
        )}
      </Box>
      
      {isUser && (
        <Avatar 
          size="sm" 
          ml={2} 
          name="User" 
          bg="blue.500"
        />
      )}
    </Flex>
  );
};

export default ChatMessage; 