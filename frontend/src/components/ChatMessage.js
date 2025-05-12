import React from 'react';
import { Box, Flex, Text, Avatar, useColorModeValue } from '@chakra-ui/react';

/**
 * Component for displaying a single chat message
 * @param {Object} props - Component props
 * @param {string} props.message - Message content
 * @param {string} props.sender - Message sender ('user' or 'ai')
 * @param {boolean} props.isLoading - Whether the message is in loading state
 */
const ChatMessage = ({ message, sender, isLoading = false }) => {
  const isUser = sender === 'user';
  const bgColor = useColorModeValue(
    isUser ? 'blue.50' : 'gray.50',
    isUser ? 'blue.900' : 'gray.700'
  );
  const textColor = useColorModeValue(
    isUser ? 'blue.800' : 'gray.800',
    isUser ? 'blue.100' : 'gray.100'
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
          bg="brand.500" 
          color="white" 
          mr={2} 
          icon={<></>}
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
        <Text>{message}</Text>
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