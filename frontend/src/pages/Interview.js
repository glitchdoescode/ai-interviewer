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
  HStack,
  VStack,
  Icon,
} from '@chakra-ui/react';
import { FaInfoCircle, FaHistory, FaCheckCircle } from 'react-icons/fa';
import Navbar from '../components/Navbar';
import ChatInterface from '../components/ChatInterface';
import CodingChallenge from '../components/CodingChallenge';
import ProctoringPanel from '../components/proctoring/ProctoringPanel';
import { useInterview } from '../context/InterviewContext';
import { checkVoiceAvailability, submitChallengeFeedbackToServer } from '../api/interviewService';
import JobRoleSelector from '../components/JobRoleSelector';
import FaceAuthenticationManager from '../components/proctoring/FaceAuthenticationManager';

/**
 * Interview page component
 */
const Interview = () => {
  const { sessionId: urlSessionId } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const { 
    isOpen: isEndInterviewModalOpen, 
    onOpen: onOpenEndInterviewModal, 
    onClose: onCloseEndInterviewModal 
  } = useDisclosure();

  const { 
    isOpen: isEnrollmentModalOpen, 
    onOpen: onOpenEnrollmentModal, 
    onClose: onCloseEnrollmentModal 
  } = useDisclosure();
  
  const {
    userId,
    sessionId,
    messages,
    loading,
    error,
    interviewStage,
    jobRoleData: selectedJobRole,
    currentCodingChallenge,
    addMessage,
    setSessionId,
    setLoading,
    setError,
    setInterviewStage,
    resetInterview,
    setVoiceMode,
    voiceMode,
    setJobRoleData,
  } = useInterview();

  const [isVoiceAvailable, setIsVoiceAvailable] = useState(true);
  const [showJobSelector, setShowJobSelector] = useState(true);
  const [isInfoModalOpen, setIsInfoModalOpen] = useState(false);
  const [proctoringStatus, setProctoringStatus] = useState({
    isActive: false,
    hasCamera: false,
    hasDetection: false,
    hasWebSocket: false,
  });

  // New state variables for enrollment flow
  const [isEnrolling, setIsEnrolling] = useState(false);
  const [enrollmentProcessComplete, setEnrollmentProcessComplete] = useState(false);
  const [temporaryEmbedding, setTemporaryEmbedding] = useState(null);
  const [proctoringEffectivelyEnabled, setProctoringEffectivelyEnabled] = useState(false);
  
  // Ref for the video element used by face authentication
  const videoRef = React.useRef(null); 
  const proctoringToastShownRef = React.useRef(false);

  // New combined state for enabling the ProctoringPanel and its underlying WebcamMonitor's camera
  const proctoringIsEnabledForPanel = proctoringEffectivelyEnabled || (isEnrollmentModalOpen && isEnrolling);

  // Audio playback function
  const playAudioResponse = (audioUrl) => {
    if (!audioUrl) return;
    
    const audio = new Audio(audioUrl);
    audio.play().catch(err => {
      console.error('Error playing audio:', err);
      toast({
        title: 'Audio Playback Failed',
        description: 'Could not play audio response',
        status: 'warning',
        duration: 3000,
        isClosable: true,
      });
    });
  };

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

  // Handle job role selection
  const handleRoleSelect = (roleData) => {
    setJobRoleData(roleData);
  };
  
  // Handle starting interview with selected role
  const handleStartInterview = () => {
    setShowJobSelector(false);
    setIsEnrolling(true);
    setEnrollmentProcessComplete(false); 
    setTemporaryEmbedding(null);        
    setProctoringEffectivelyEnabled(false); // This will be true later, after session ID and enrollment
    onOpenEnrollmentModal(); 
    
    if (selectedJobRole) {
      toast({
        title: "Interview Started",
        description: `Your interview for ${selectedJobRole.role_name} (${selectedJobRole.seniority_level}) is ready to begin. Please complete face enrollment.`,
        status: "success",
        duration: 5000,
        isClosable: true,
      });
    }
  };

  // New callbacks for enrollment process
  const handleInitialEnrollmentSuccess = (embedding) => {
    toast({
      title: 'Enrollment Successful',
      description: 'Your face has been enrolled.',
      status: 'success',
      duration: 3000,
      isClosable: true,
    });
    setTemporaryEmbedding(embedding);
    setEnrollmentProcessComplete(true);
    setIsEnrolling(false);
    onCloseEnrollmentModal();
  };

  const handleInitialEnrollmentFailure = (errorMsg) => {
    toast({
      title: 'Enrollment Failed',
      description: (errorMsg?.message || String(errorMsg)) || 'Could not enroll face. Please try again.',
      status: 'error',
      duration: 5000,
      isClosable: true,
    });
    // Modal remains open for retry, FaceEnrollment component handles retries
  };
  
  const handleEnrollmentModalClose = () => {
    if (isEnrolling && !enrollmentProcessComplete) { // Check if still enrolling and not completed
      toast({
        title: 'Enrollment Cancelled',
        description: 'Face enrollment was not completed. Proctoring will be disabled.',
        status: 'warning',
        duration: 3000,
        isClosable: true,
      });
      setIsEnrolling(false); // Stop enrollment process
      // Optionally, reset interview or prevent progress if enrollment is mandatory
    }
    onCloseEnrollmentModal();
  };

  // Corrected useEffect for proctoringEffectivelyEnabled. 
  // This enables the *continuous proctoring part* after enrollment and session ID exist.
  useEffect(() => {
    if (sessionId && enrollmentProcessComplete && temporaryEmbedding) {
      setProctoringEffectivelyEnabled(true);
      // Toast moved to ProctoringPanel for when it actually becomes active
      // Reset toast shown flag when proctoring becomes effectively enabled, so it can show again for this session.
      proctoringToastShownRef.current = false; 
    } else {
      setProctoringEffectivelyEnabled(false);
    }
  }, [sessionId, enrollmentProcessComplete, temporaryEmbedding]);

  // Handle proctoring status changes
  const handleProctoringStatusChange = (status) => {
    setProctoringStatus(status);
    
    if (status.isActive && status.hasCamera && status.hasDetection && status.hasWebSocket && !proctoringToastShownRef.current) {
      toast({
        title: 'Proctoring Active',
        description: 'AI proctoring is now monitoring the interview',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });
      proctoringToastShownRef.current = true; // Mark toast as shown for this session
    }
  };
  
  // Handle ending the interview
  const handleEndInterview = () => {
    onCloseEndInterviewModal();
    setProctoringEffectivelyEnabled(false);
    proctoringToastShownRef.current = false; // Reset for next interview
    resetInterview();
    navigate('/');
    
    toast({
      title: 'Interview Ended',
      description: 'Your interview has been completed.',
      status: 'info',
      duration: 3000,
      isClosable: true,
    });
  };

  // New handler to be passed to CodingChallenge for when feedback is submitted
  const handleCodingFeedbackSubmitted = async (detailedMessageToAI, evaluationSummary) => {
    if (!sessionId || !userId) {
      setError('Session ID or User ID is missing. Cannot submit for feedback.');
      toast({
        title: 'Error',
        description: 'Session ID or User ID missing.',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
      return;
    }

    setLoading(true);
    try {
      // This function is from interviewService.js and calls /api/interview/{session_id}/challenge-complete
      const aiFeedbackResponse = await submitChallengeFeedbackToServer(
        sessionId,
        userId,
        detailedMessageToAI,
        evaluationSummary, // Pass the evaluation summary
        true // challenge_completed = true
      );

      console.log('[Interview.js] AI Feedback Response from server:', JSON.stringify(aiFeedbackResponse, null, 2));

      if (aiFeedbackResponse && aiFeedbackResponse.response) {
        const messagePayload = {
          sender: 'ai',
          text: aiFeedbackResponse.response,
          audioUrl: aiFeedbackResponse.audio_response_url, // Get audio URL from response
          timestamp: new Date(),
          isFeedback: true, // Mark this as a feedback message if needed for UI styling
        };
        console.log('[Interview.js] Payload for addMessage:', JSON.stringify(messagePayload, null, 2));

        addMessage(messagePayload);
        setInterviewStage(aiFeedbackResponse.interview_stage || 'feedback'); // Update stage from response
        
        // If audio URL exists, play it
        if (aiFeedbackResponse.audio_response_url && voiceMode) {
          playAudioResponse(aiFeedbackResponse.audio_response_url);
        }
        
        toast({
          title: 'Feedback Received',
          description: 'AI has provided feedback on your coding challenge.',
          status: 'success',
          duration: 3000,
          isClosable: true,
        });
      } else {
        throw new Error(aiFeedbackResponse?.error || 'No response from AI after submitting feedback.');
      }
    } catch (err) {
      console.error("Error in handleCodingFeedbackSubmitted:", err);
      setError(err.message || 'Failed to get feedback from AI.');
      addMessage({
        sender: 'system',
        text: `Error: ${err.message || 'Failed to get feedback from AI.'}`,
        timestamp: new Date(),
      });
      toast({
        title: 'Feedback Error',
        description: err.message || 'Could not retrieve AI feedback.',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setLoading(false);
    }
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
              
              {/* Proctoring Info */}
              <Box mb={6}>
                <Text fontWeight="bold" mb={2}>Proctoring</Text>
                {proctoringEffectivelyEnabled ? (
                  <Badge colorScheme="green">Active</Badge>
                ) : (
                  <Badge colorScheme="red">Inactive</Badge>
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
                  onClick={() => setIsInfoModalOpen(true)}
                >
                  How It Works
                </Button>
              </Box>
              
              {/* History Button */}
              <Box mt="auto">
                <Button
                  width="full"
                  leftIcon={<FaHistory />}
                  onClick={() => navigate('/history')}
                  variant="outline"
                >
                  View Interview History
                </Button>
              </Box>
              
              {/* Proctoring Panel */}
              {!showJobSelector && (
                <Box mt={4}>
                  {/* Render the shared video element here for ProctoringPanel */}
                  {proctoringIsEnabledForPanel && ( 
                    <video
                      ref={videoRef}
                      autoPlay
                      playsInline
                      muted 
                      style={{
                        width: '100%',
                        maxWidth: '320px', // Max width for sidebar
                        height: 'auto',
                        borderRadius: '8px', // chakra 'md'
                        marginBottom: '1rem', // chakra '4'
                        backgroundColor: '#1A202C', // chakra gray.800 - dark placeholder
                        aspectRatio: '16/9', // Maintain aspect ratio
                        display: proctoringEffectivelyEnabled || isEnrolling ? 'block' : 'none', // Show if proctoring or enrolling
                      }}
                    />
                  )}
                  <ProctoringPanel
                    sessionId={sessionId}
                    userId={userId}
                    isEnabled={proctoringIsEnabledForPanel}
                    onStatusChange={handleProctoringStatusChange}
                    temporaryEmbedding={temporaryEmbedding}
                    videoRef={videoRef}
                  />
                </Box>
              )}
            </Box>
          </GridItem>
          
          {/* Main Chat Interface */}
          <GridItem>
            {error && (
              <Alert status="error" mb={4}>
                <AlertIcon />
                {error}
              </Alert>
            )}
            
            <Grid
              templateRows="auto 1fr"
              templateColumns="1fr"
              gap={4}
              height="100%"
            >
              <GridItem>
                <Box display="flex" justifyContent="space-between" alignItems="center">
                  <Box>
                    <Heading size="lg">Technical Interview</Heading>
                    {selectedJobRole && (
                      <Badge colorScheme="green" fontSize="0.8em" ml={2}>
                        {selectedJobRole.role_name} ({selectedJobRole.seniority_level})
                      </Badge>
                    )}
                    {sessionId && (
                      <Text fontSize="sm" color="gray.500">
                        Session ID: {sessionId}
                      </Text>
                    )}
                  </Box>
                  
                  <Button 
                    colorScheme="red" 
                    variant="outline" 
                    size="sm"
                    onClick={onOpenEndInterviewModal}
                  >
                    End Interview
                  </Button>
                </Box>
              </GridItem>
              
              <GridItem overflow="hidden">
                {showJobSelector ? (
                  <JobRoleSelector 
                    onRoleSelect={handleRoleSelect}
                    onStartInterview={handleStartInterview}
                    isLoading={loading}
                  />
                ) : (
                  (interviewStage === 'coding_challenge' || interviewStage === 'coding_challenge_waiting') && currentCodingChallenge ? (
                    <CodingChallenge 
                      challenge={currentCodingChallenge}
                      onComplete={handleCodingFeedbackSubmitted}
                      onRequestHint={() => { /* Implement hint request if needed */ }}
                      sessionId={sessionId}
                      userId={userId}
                    />
                  ) : (interviewStage === 'coding_challenge' || interviewStage === 'coding_challenge_waiting') && !currentCodingChallenge ? (
                    <Box p={5} textAlign="center">
                      <Text fontSize="xl">Loading coding challenge details...</Text>
                    </Box>
                  ) : (
                    <ChatInterface jobRoleData={selectedJobRole} />
                  )
                )}
              </GridItem>
            </Grid>
          </GridItem>
        </Grid>
      </Container>
      
      {/* Info Modal */}
      <Modal isOpen={isInfoModalOpen} onClose={() => setIsInfoModalOpen(false)} size="lg">
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
            <Button colorScheme="brand" onClick={() => setIsInfoModalOpen(false)}>
              Got it
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
      
      {/* End Interview Confirmation Modal */}
      <Modal isOpen={isEndInterviewModalOpen} onClose={onCloseEndInterviewModal}>
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>End Interview</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <Text>Are you sure you want to end this interview session?</Text>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" onClick={onCloseEndInterviewModal}>Cancel</Button>
            <Button colorScheme="red" onClick={handleEndInterview} ml={3}>
              End Interview
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
      
      {/* Enrollment Modal */}
      <Modal isOpen={isEnrollmentModalOpen} onClose={handleEnrollmentModalClose} size="xl" closeOnOverlayClick={false}>
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Face Enrollment</ModalHeader>
          {/* Prevent closing via X button if mid-enrollment and not complete */}
          { !(isEnrolling && !enrollmentProcessComplete) && <ModalCloseButton /> }
          <ModalBody>
            <Box>
              {/* Hidden video element for the hook, if FaceAuthManager doesn't render its own visible one */}
              {/* <video ref={videoRef} style={{ display: 'none' }} playsInline /> */}
              
              {/* 
                WebcamMonitor will render the video feed.
                FaceAuthenticationManager will contain FaceEnrollment and the auth logic.
                WebcamMonitor (via ProctoringPanel's isEnabled) needs to be active to put a stream on videoRef.
              */}
              {isEnrolling && (
                <FaceAuthenticationManager
                  videoRef={videoRef} // Pass the ref here
                  isActive={isEnrolling} 
                  onAuthenticationEvent={(event) => { // This needs refinement in FaceAuthManager
                    if (event.type === 'enrollment_success' && event.embedding) {
                      handleInitialEnrollmentSuccess(event.embedding);
                    } else if (event.type === 'enrollment_failed') {
                      handleInitialEnrollmentFailure(event.message || 'Enrollment attempt failed.');
                    } else if (event.type === 'error' && event.context === 'enrollment') {
                       handleInitialEnrollmentFailure(event.message || 'An error occurred during enrollment.');
                    }
                  }}
                  // To be implemented in FaceAuthenticationManager:
                  // isEnrollmentOnlyMode={true} 
                  onInitialEnrollmentSuccess={handleInitialEnrollmentSuccess} 
                  onInitialEnrollmentFailure={handleInitialEnrollmentFailure} 
                  showEnrollmentUI={true} 
                />
              )}
              {!isEnrolling && enrollmentProcessComplete && (
                <VStack spacing={4} py={6} textAlign="center">
                  <Icon as={FaCheckCircle} boxSize={12} color="green.500" />
                  <Text fontSize="lg" fontWeight="bold">Enrollment Complete!</Text>
                  <Text>You can now proceed with the interview.</Text>
                </VStack>
              )}
               {!isEnrolling && !enrollmentProcessComplete && !isEnrollmentModalOpen && (
                 <Text>Enrollment was not started or was cancelled. Proctoring may be limited.</Text>
               )}
            </Box>
          </ModalBody>
          <ModalFooter>
            <Button 
              onClick={handleEnrollmentModalClose}
              isDisabled={isEnrolling && !enrollmentProcessComplete} // Disable if enrolling and not yet complete
            >
              {enrollmentProcessComplete ? 'Continue to Interview' : 'Cancel Enrollment'}
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Box>
  );
};

export default Interview; 