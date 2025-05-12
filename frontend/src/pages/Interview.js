import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Container,
  Grid,
  GridItem,
  Heading,
  Text,
  Badge,
  Button,
  Alert,
  AlertIcon,
  useToast,
  useDisclosure,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  ModalCloseButton,
} from '@chakra-ui/react';
import { FaInfoCircle, FaHistory } from 'react-icons/fa';
import Navbar from '../components/Navbar';
import ChatInterface from '../components/ChatInterface';
import { useInterview } from '../context/InterviewContext';
import { checkVoiceAvailability } from '../api/interviewService';

/**
 * Interview page component
 */
const Interview = () => {
  const { sessionId: urlSessionId } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const { isOpen, onOpen, onClose } = useDisclosure();
  
  const {
    userId,
    sessionId,
    interviewStage,
    setSessionId,
    setError,
    voiceMode,
    setVoiceMode,
  } = useInterview();

  const [isVoiceAvailable, setIsVoiceAvailable] = useState(true);

  // Check if the requested session ID should be loaded
  useEffect(() => {
    if (urlSessionId && urlSessionId !== sessionId) {
      // Set the session ID from the URL
      setSessionId(urlSessionId);
      
      // Show toast notification
      toast({
        title: 'Session Loaded',
        description: `Resuming interview session: ${urlSessionId}`,
        status: 'info',
        duration: 3000,
        isClosable: true,
      });
    }
  }, [urlSessionId, sessionId, setSessionId, toast]);

  // Check if voice processing is available
  useEffect(() => {
    const checkVoice = async () => {
      try {
        const isAvailable = await checkVoiceAvailability();
        setIsVoiceAvailable(isAvailable);
        
        // If voice is not available but voice mode is enabled, disable it
        if (!isAvailable && voiceMode) {
          setVoiceMode(false);
          toast({
            title: 'Voice Mode Disabled',
            description: 'Voice processing is not available on the server.',
            status: 'warning',
            duration: 5000,
            isClosable: true,
          });
        }
      } catch (err) {
        setError('Error checking voice availability');
        setIsVoiceAvailable(false);
      }
    };
    
    checkVoice();
  }, [setError, setVoiceMode, voiceMode, toast]);

  // Function to handle navigating to session history
  const handleViewHistory = () => {
    navigate('/history');
  };

  // Get stage badge color based on interview stage
  const getStageBadgeColor = (stage) => {
    switch (stage) {
      case 'introduction':
        return 'blue';
      case 'technical_questions':
        return 'purple';
      case 'coding_challenge':
        return 'orange';
      case 'feedback':
        return 'green';
      case 'conclusion':
        return 'red';
      default:
        return 'gray';
    }
  };

  return (
    <Box minH="100vh" bg="gray.50">
      <Navbar />
      
      <Container maxW="container.xl" py={6}>
        <Grid
          templateColumns={{ base: '1fr', lg: '1fr 3fr' }}
          gap={6}
          h={{ base: 'auto', md: 'calc(100vh - 160px)' }}
        >
          {/* Sidebar/Info Panel */}
          <GridItem display={{ base: 'none', lg: 'block' }}>
            <Box
              bg="white"
              p={6}
              borderRadius="md"
              boxShadow="md"
              h="100%"
            >
              <Heading as="h2" size="lg" mb={6} color="brand.600">
                Technical Interview
              </Heading>
              
              {/* Session Info */}
              <Box mb={6}>
                <Text fontWeight="bold" mb={2}>Session Info</Text>
                <Text fontSize="sm" color="gray.600" mb={1}>
                  User ID: {userId || 'Not set'}
                </Text>
                <Text fontSize="sm" color="gray.600" mb={1}>
                  Session ID: {sessionId || 'New session'}
                </Text>
                {interviewStage && (
                  <Box mt={3}>
                    <Text fontSize="sm" fontWeight="bold" mb={1}>Current Stage:</Text>
                    <Badge colorScheme={getStageBadgeColor(interviewStage)}>
                      {interviewStage.replace('_', ' ').toUpperCase()}
                    </Badge>
                  </Box>
                )}
              </Box>
              
              {/* Voice Mode Info */}
              <Box mb={6}>
                <Text fontWeight="bold" mb={2}>Voice Mode</Text>
                {isVoiceAvailable ? (
                  <Badge colorScheme="green">Available</Badge>
                ) : (
                  <Alert status="warning" size="sm" borderRadius="md">
                    <AlertIcon />
                    Voice processing is not available
                  </Alert>
                )}
              </Box>
              
              {/* Help/Info */}
              <Box mb={6}>
                <Text fontWeight="bold" mb={2}>Interview Tips</Text>
                <Text fontSize="sm" color="gray.600" mb={3}>
                  Speak clearly and think through your answers. The AI will guide you through technical questions and coding challenges.
                </Text>
                <Button
                  size="sm"
                  leftIcon={<FaInfoCircle />}
                  colorScheme="blue"
                  variant="outline"
                  onClick={onOpen}
                >
                  How It Works
                </Button>
              </Box>
              
              {/* History Button */}
              <Box mt="auto">
                <Button
                  width="full"
                  leftIcon={<FaHistory />}
                  onClick={handleViewHistory}
                  variant="outline"
                >
                  View Interview History
                </Button>
              </Box>
            </Box>
          </GridItem>
          
          {/* Main Chat Interface */}
          <GridItem>
            <ChatInterface />
          </GridItem>
        </Grid>
      </Container>
      
      {/* Info Modal */}
      <Modal isOpen={isOpen} onClose={onClose} size="lg">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader color="brand.700">How AI Interviewer Works</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <Text mb={4}>
              The AI Interviewer conducts technical interviews simulating real-world scenarios. Here's what to expect:
            </Text>
            
            <Box mb={4}>
              <Heading as="h4" size="sm" mb={2} color="brand.600">
                Interview Stages
              </Heading>
              <Text fontSize="sm" mb={1}>• <b>Introduction:</b> Get comfortable and introduce yourself</Text>
              <Text fontSize="sm" mb={1}>• <b>Technical Questions:</b> Answer questions about software development concepts</Text>
              <Text fontSize="sm" mb={1}>• <b>Coding Challenge:</b> Solve programming problems</Text>
              <Text fontSize="sm" mb={1}>• <b>Feedback:</b> Receive constructive evaluation of your performance</Text>
              <Text fontSize="sm">• <b>Conclusion:</b> Wrap up the interview with final thoughts</Text>
            </Box>
            
            <Box mb={4}>
              <Heading as="h4" size="sm" mb={2} color="brand.600">
                Voice Interaction
              </Heading>
              <Text fontSize="sm">
                You can interact using text or voice (if available). Voice mode lets you speak naturally, just like in a real interview.
              </Text>
            </Box>
            
            <Box>
              <Heading as="h4" size="sm" mb={2} color="brand.600">
                Tips for Success
              </Heading>
              <Text fontSize="sm" mb={1}>• Explain your thought process clearly</Text>
              <Text fontSize="sm" mb={1}>• Ask clarifying questions when needed</Text>
              <Text fontSize="sm" mb={1}>• Take your time with technical problems</Text>
              <Text fontSize="sm">• Learn from feedback to improve for next time</Text>
            </Box>
          </ModalBody>
          <ModalFooter>
            <Button colorScheme="brand" onClick={onClose}>
              Got it
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Box>
  );
};

export default Interview; 