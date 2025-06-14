import React, { useEffect, useRef, useState } from 'react';
import { Box, Flex, Text, Avatar, useColorModeValue, Badge, Button, HStack, Icon, Alert, AlertIcon, AlertTitle, AlertDescription, Spinner, Heading, UnorderedList, OrderedList, ListItem, Code, TableContainer, Table, Thead, Tbody, Tr, Th, Td, useColorMode } from '@chakra-ui/react';
import { FaPlay, FaStop, FaCode, FaLightbulb, FaExclamationCircle, FaPause } from 'react-icons/fa';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { dracula, vs, vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

/**
 * Component for displaying a single chat message
 * @param {Object} props - Component props
 * @param {string} props.text - Message content
 * @param {string} props.sender - Message sender ('user' or 'assistant')
 * @param {boolean} props.isLoading - Whether the message is in loading state
 * @param {string} props.audioUrl - Optional URL for audio message
 * @param {boolean} props.isHint - Whether this message is a hint
 * @param {boolean} props.isFeedback - Whether this message is feedback for coding challenge
 * @param {boolean} props.isGenericResponse - Whether this message is a generic response that should be flagged
 * @param {boolean} props.isError - Whether this message is an error
 * @param {boolean} props.isTransition - Whether this message is a transition message
 */
const ChatMessage = ({ 
  text, 
  sender, 
  isLoading = false, 
  audioUrl, 
  isHint = false,
  isFeedback = false,
  isGenericResponse = false,
  isError = false,
  isTransition = false
}) => {
  const isUser = sender === 'user';
  const [isPlaying, setIsPlaying] = useState(false);
  const [audioError, setAudioError] = useState('');
  const audioRef = useRef(null);
  const { colorMode } = useColorMode();
  
  // Theme colors
  const userMessageBg = useColorModeValue('brand.100', 'brand.700');
  const aiMessageBg = useColorModeValue('gray.100', 'gray.700');
  const feedbackMessageBg = useColorModeValue('cyan.50', 'cyan.900');
  const hintMessageBg = useColorModeValue('yellow.50', 'yellow.900');
  const errorMessageBg = useColorModeValue('red.50', 'red.900');
  const messageTextColor = useColorModeValue('gray.800', 'white');
  const transitionMessageBg = useColorModeValue('purple.50', 'purple.900'); 
  const transitionTextColor = useColorModeValue('purple.800', 'purple.100');
  
  // Additional color values for renderContent
  const feedbackBadgeBg = useColorModeValue('cyan.100', 'cyan.800');
  const hintBadgeBg = useColorModeValue('yellow.100', 'yellow.800');
  const genericResponseBg = useColorModeValue('orange.100', 'orange.800');
  const blockquoteBg = useColorModeValue('gray.50', 'gray.700');
  const inlineCodeBg = useColorModeValue('gray.100', 'gray.700');
  
  // Text colors for different message types
  const errorTextColor = useColorModeValue('red.800', 'red.100');
  const feedbackTextColor = useColorModeValue('cyan.800', 'cyan.100');
  const hintTextColor = useColorModeValue('yellow.800', 'yellow.100');
  
  // Border colors for different message types
  const defaultBorderColor = useColorModeValue('gray.200', 'gray.600');
  const feedbackBorderColor = useColorModeValue('cyan.300', 'cyan.700');
  const hintBorderColor = useColorModeValue('yellow.300', 'yellow.700');
  const errorBorderColor = useColorModeValue('red.300', 'red.700');
  const transitionBorderColor = useColorModeValue('purple.300', 'purple.700');
  
  // Determine background color based on message type
  let bg;
  let textColor = messageTextColor;
  let borderColor = defaultBorderColor;
  
  if (isError) {
    bg = errorMessageBg;
    textColor = errorTextColor;
    borderColor = errorBorderColor;
  } else if (isTransition) {
    bg = transitionMessageBg;
    textColor = transitionTextColor;
    borderColor = transitionBorderColor;
  } else if (isFeedback) {
    bg = feedbackMessageBg;
    textColor = feedbackTextColor;
    borderColor = feedbackBorderColor;
  } else if (isHint) {
    bg = hintMessageBg;
    textColor = hintTextColor;
    borderColor = hintBorderColor;
  } else {
    bg = sender === 'user' ? userMessageBg : aiMessageBg;
  }
  
  // Determine border style for different message types
  let borderStyle = "1px solid";
  if (isTransition) {
    borderStyle = "1px dashed";
  }

  // Animation for loading indicator
  const loadingStyle = isLoading ? {
    '& .typing-indicator': {
      display: 'flex'
    }
  } : {};

  // Handle audio playback
  const togglePlayback = () => {
    if (audioRef.current) {
      if (isPlaying) {
        audioRef.current.pause();
      } else {
        audioRef.current.play();
      }
    }
  };

  // Handle audio events
  const handleAudioEnded = () => {
    setIsPlaying(false);
  };

  // Message content display with proper alerts if needed
  const renderContent = () => {
    if (isLoading) {
      return (
        <HStack spacing={2}>
          <Spinner size="sm" />
          <Text>Thinking...</Text>
        </HStack>
      );
    }
    
    return (
      <Box>
        {/* Special styling for feedback messages */}
        {isFeedback && (
          <Box 
            mb={2} 
            p={1} 
            bg={feedbackBadgeBg} 
            borderRadius="md"
            display="inline-block"
          >
            <Badge colorScheme="cyan" variant="solid" fontSize="xs">
              Code Feedback
            </Badge>
          </Box>
        )}
        
        {/* Special styling for hint messages */}
        {isHint && (
          <Box 
            mb={2} 
            p={1} 
            bg={hintBadgeBg} 
            borderRadius="md"
            display="inline-block"
          >
            <Badge colorScheme="yellow" variant="solid" fontSize="xs">
              Hint
            </Badge>
          </Box>
        )}
        
        {/* Special styling for generic greeting detected */}
        {isGenericResponse && (
          <Box 
            mb={2} 
            p={1} 
            bg={genericResponseBg} 
            borderRadius="md"
            display="inline-block"
          >
            <Badge colorScheme="orange" variant="solid" fontSize="xs">
              Generic Response Detected
            </Badge>
          </Box>
        )}
        
        {/* Audio playback controls if available */}
        {audioUrl && (
          <Box mb={2}>
            <audio ref={audioRef} src={audioUrl} onEnded={handleAudioEnded} />
            <Button 
              size="xs" 
              leftIcon={isPlaying ? <FaPause /> : <FaPlay />}
              onClick={togglePlayback}
              colorScheme="blue"
              variant="outline"
            >
              {isPlaying ? 'Pause' : 'Play Audio'}
            </Button>
          </Box>
        )}
        
        {/* Render Markdown with syntax highlighting */}
        <Box>
          <ReactMarkdown
            components={{
              p: ({ node, ...props }) => <Text mb={2} {...props} />,
              h1: ({ node, ...props }) => <Heading as="h1" size="xl" my={4} {...props} />,
              h2: ({ node, ...props }) => <Heading as="h2" size="lg" my={3} {...props} />,
              h3: ({ node, ...props }) => <Heading as="h3" size="md" my={2} {...props} />,
              ul: ({ node, ...props }) => <UnorderedList mb={2} pl={4} {...props} />,
              ol: ({ node, ...props }) => <OrderedList mb={2} pl={4} {...props} />,
              li: ({ node, ...props }) => <ListItem mb={1} {...props} />,
              blockquote: ({ node, ...props }) => (
                <Box 
                  borderLeft="4px" 
                  borderColor="gray.300" 
                  pl={4} 
                  py={1} 
                  my={2} 
                  bg={blockquoteBg}
                  {...props} 
                />
              ),
              code({node, inline, className, children, ...props}) {
                const match = /language-(\w+)/.exec(className || '');
                return !inline && match ? (
                  <SyntaxHighlighter
                    style={colorMode === 'light' ? vs : vscDarkPlus}
                    language={match[1]}
                    PreTag="div"
                    wrapLines={true}
                    {...props}
                  >
                    {String(children).replace(/\n$/, '')}
                  </SyntaxHighlighter>
                ) : inline ? (
                  <Code
                    px={1}
                    borderRadius="sm"
                    bg={inlineCodeBg}
                    {...props}
                  >
                    {children}
                  </Code>
                ) : (
                  <Box 
                    as="pre" 
                    p={2} 
                    borderRadius="md" 
                    bg={inlineCodeBg}
                    overflowX="auto"
                    {...props}
                  >
                    {children}
                  </Box>
                );
              },
              table: ({node, ...props}) => (
                <TableContainer my={4}>
                  <Table variant="simple" size="sm" {...props} />
                </TableContainer>
              ),
              thead: ({node, ...props}) => <Thead {...props} />,
              tbody: ({node, ...props}) => <Tbody {...props} />,
              tr: ({node, ...props}) => <Tr {...props} />,
              th: ({node, ...props}) => <Th {...props} />,
              td: ({node, ...props}) => <Td {...props} />
            }}
          >
            {text}
          </ReactMarkdown>
        </Box>
      </Box>
    );
  };

  return (
    <Flex
      direction={isUser ? "row-reverse" : "row"}
      alignItems="flex-start"
      mb={4}
      sx={loadingStyle}
    >
      <Avatar 
        size="sm" 
        name={isUser ? "User" : "AI Interviewer"} 
        src={isUser ? null : "/assets/ai-avatar.png"} 
        bg={isUser ? "blue.500" : "transparent"}
        mr={isUser ? 0 : 2}
        ml={isUser ? 2 : 0}
      />
      <Box
        maxW="80%"
        bg={bg}
        p={3}
        borderRadius="lg"
        borderTopLeftRadius={isUser ? "lg" : "sm"}
        borderTopRightRadius={isUser ? "sm" : "lg"}
        boxShadow="md"
        border={borderStyle}
        borderColor={borderColor}
      >
        {renderContent()}
      </Box>
    </Flex>
  );
};

export default ChatMessage; 