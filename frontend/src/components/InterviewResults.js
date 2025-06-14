import React from 'react';
import {
  Box,
  VStack,
  HStack,
  Text,
  Button,
  Badge,
  Divider,
  Icon,
  useColorModeValue
} from '@chakra-ui/react';
import { useNavigate } from 'react-router-dom';
import { FaCheckCircle, FaClock, FaComments, FaUser, FaChartBar } from 'react-icons/fa';

/**
 * Interview Results component
 * Shows completion status and session statistics
 */
const InterviewResults = ({ 
  sessionData, 
  duration = 0, 
  messagesCount = 0 
}) => {
  const navigate = useNavigate();
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');

  // Debug session data
  console.log('InterviewResults received sessionData:', sessionData);
  console.log('Session ID from props:', sessionData?.session_id || sessionData?.sessionId);

  const formatDuration = (seconds) => {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
  };

  const handleReturnHome = () => {
    navigate('/');
  };

  const handleStartNewInterview = () => {
    navigate('/interview');
  };

  const handleViewDetailedReport = () => {
    // Use either session_id or sessionId property, whichever is available
    const sessionId = sessionData?.session_id || sessionData?.sessionId;
    
    // If we have a session ID, use it; otherwise, try to get it from localStorage or use a fallback
    if (sessionId) {
      navigate(`/report/${sessionId}`);
    } else {
      // Try to get session ID from localStorage as a fallback
      const storedSessionId = localStorage.getItem('lastSessionId');
      if (storedSessionId) {
        navigate(`/report/${storedSessionId}`);
      } else {
        // Alert the user if no session ID is available
        alert('Session ID not available. Please try accessing reports from the history page.');
        navigate('/history');
      }
    }
  };

  return (
    <Box
      minH="100vh"
      bg={useColorModeValue('gray.50', 'gray.900')}
      display="flex"
      alignItems="center"
      justifyContent="center"
      p={6}
    >
      <Box
        bg={bgColor}
        borderRadius="xl"
        border="1px solid"
        borderColor={borderColor}
        boxShadow="lg"
        p={8}
        maxW="md"
        w="100%"
        textAlign="center"
      >
        <VStack spacing={6}>
          {/* Success Icon */}
          <Icon as={FaCheckCircle} w={16} h={16} color="green.500" />
          
          {/* Title */}
          <VStack spacing={2}>
            <Text fontSize="2xl" fontWeight="bold" color="green.600">
              Interview Complete!
            </Text>
            <Text fontSize="md" color="gray.600">
              Thank you for participating in the AI interview
            </Text>
          </VStack>

          <Divider />

          {/* Session Statistics */}
          <VStack spacing={4} w="100%">
            <Text fontSize="lg" fontWeight="semibold">
              Session Summary
            </Text>
            
            <HStack justify="space-between" w="100%">
              <HStack spacing={2}>
                <Icon as={FaClock} color="blue.500" />
                <Text fontSize="sm" color="gray.600">Duration:</Text>
              </HStack>
              <Badge colorScheme="blue" fontSize="sm">
                {formatDuration(duration)}
              </Badge>
            </HStack>

            <HStack justify="space-between" w="100%">
              <HStack spacing={2}>
                <Icon as={FaComments} color="purple.500" />
                <Text fontSize="sm" color="gray.600">Messages:</Text>
              </HStack>
              <Badge colorScheme="purple" fontSize="sm">
                {messagesCount}
              </Badge>
            </HStack>

            {(sessionData?.sessionId || sessionData?.session_id) && (
              <HStack justify="space-between" w="100%">
                <HStack spacing={2}>
                  <Icon as={FaUser} color="orange.500" />
                  <Text fontSize="sm" color="gray.600">Session ID:</Text>
                </HStack>
                <Badge colorScheme="orange" fontSize="xs">
                  {(sessionData?.sessionId || sessionData?.session_id).slice(-8)}
                </Badge>
              </HStack>
            )}
          </VStack>

          <Divider />

          {/* Action Buttons */}
          <VStack spacing={3} w="100%">
            {/* Always show the button, we'll handle missing session IDs in the click handler */}
            <Button
              colorScheme="blue"
              size="lg"
              w="100%"
              leftIcon={<FaChartBar />}
              onClick={handleViewDetailedReport}
            >
              View Detailed Report
            </Button>
            
            <Button
              colorScheme="primary"
              size="lg"
              w="100%"
              onClick={handleStartNewInterview}
            >
              Start New Interview
            </Button>
            
            <Button
              variant="outline"
              size="md"
              w="100%"
              onClick={handleReturnHome}
            >
              Return to Home
            </Button>
          </VStack>

          {/* Footer Text */}
          <Text fontSize="xs" color="gray.500" textAlign="center">
            Your interview responses have been recorded for evaluation.
            You will be contacted with next steps if your application moves forward.
          </Text>
        </VStack>
      </Box>
    </Box>
  );
};

export default InterviewResults; 
 
 