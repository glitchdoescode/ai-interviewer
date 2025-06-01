import React, { useState, useRef, useEffect } from 'react';
import {
  Box,
  Flex,
  Input,
  IconButton,
  VStack,
  Text,
  Button,
  Spinner,
  Alert,
  AlertIcon,
  useToast,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  useDisclosure,
  Divider
} from '@chakra-ui/react';
import { FaPaperPlane, FaMicrophone, FaStop, FaExclamationTriangle } from 'react-icons/fa';
import ChatMessage from './ChatMessage';
import CodingChallenge from './CodingChallenge';
import { useInterview } from '../context/InterviewContext';
import useAudioRecorder from '../hooks/useAudioRecorder';
import { 
  startInterview, 
  continueInterview, 
  transcribeAndRespond,
  getChallengeHint,
  generateCodingProblem
} from '../api/interviewService';
import { Link } from 'react-router-dom';


/**
 * Chat interface component for interview interactions
 * 
 * @param {Object} props Component props
 * @param {Object} props.jobRoleData Optional job role configuration data
 */
const ChatInterface = ({ jobRoleData }) => {
  const {
    userId,
    sessionId,
    messages,
    loading,
    error,
    voiceMode,
    interviewStage,
    jobRoleData: contextJobRoleData,
    currentCodingChallenge,
    addMessage,
    setSessionId,
    setLoading,
    setError,
    setInterviewStage,
    setCurrentCodingChallenge,
    setVoiceMode
  } = useInterview();

  const [messageInput, setMessageInput] = useState('');
  const [isWaitingForCodingChallenge, setIsWaitingForCodingChallenge] = useState(false);
  const [showPermissionHelp, setShowPermissionHelp] = useState(false);
  const messagesEndRef = useRef(null);
  const toast = useToast();
  const { isOpen, onOpen, onClose } = useDisclosure();

  // Audio recording functionality
  const {
    isRecording,
    error: audioError,
    startRecording,
    stopRecording,
    getAudioBase64,
    isInitializing,
    permissionGranted,
    initRecording,
    checkPermissionStatus
  } = useAudioRecorder();

  // Initialize audio on component mount for better user experience
  useEffect(() => {
    if (voiceMode) {
      // Pre-initialize audio in voice mode
      checkPermissionStatus().then(hasAccess => {
        if (!hasAccess && !permissionGranted) {
          setShowPermissionHelp(true);
        }
      }).catch(err => {
        console.error('Failed to check microphone permissions:', err);
      });
    }
  }, [voiceMode, checkPermissionStatus, permissionGranted]);

  // Show permission help modal when needed
  useEffect(() => {
    if (showPermissionHelp) {
      onOpen();
    }
  }, [showPermissionHelp, onOpen]);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Update local isWaitingForCodingChallenge based on context
  useEffect(() => {
    if (interviewStage === 'coding_challenge' && currentCodingChallenge) {
      setIsWaitingForCodingChallenge(true);
    } else if (interviewStage !== 'coding_challenge') {
      setIsWaitingForCodingChallenge(false);
      // If currentCodingChallenge from context is cleared by another component (e.g. Interview.js after navigation),
      // this component's local waiting state should also be reset.
      if (!currentCodingChallenge) {
        setIsWaitingForCodingChallenge(false);
      }
    }
  }, [interviewStage, currentCodingChallenge]);

  // Show toast for audio errors
  useEffect(() => {
    if (audioError) {
      // Show more user-friendly error messages
      let errorMessage = audioError;
      if (audioError.includes('permission denied') || audioError.includes('NotAllowedError')) {
        errorMessage = 'Microphone access was denied. Please check your browser settings.';
        setShowPermissionHelp(true);
      }

      toast({
        title: 'Audio Error',
        description: errorMessage,
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    }
  }, [audioError, toast]);

  // Function to handle sending a new message
  const handleSendMessage = async () => {
    // Don't send empty messages
    if (!messageInput.trim()) return;

    try {
      // Set loading state
      setLoading(true);
      
      // Add user message to chat
      addMessage({
        role: 'user',
        content: messageInput,
      });
      
      // Clear the input field
      setMessageInput('');
      
      let response;
      
      // If we have a session ID, continue the interview, otherwise start a new one
      if (sessionId) {
        response = await continueInterview(messageInput, sessionId, userId, contextJobRoleData);
      } else {
        response = await startInterview(messageInput, userId, contextJobRoleData);
        
        // Set the session ID from the response
        if (response && response.session_id) {
          setSessionId(response.session_id);
        }
      }
      
      // Add AI response to chat
      if (response && response.response) {
        addMessage({
          role: 'assistant',
          content: response.response,
          tool_calls: response.tool_calls,
          audioUrl: response.audio_response_url
        });
      }
      
      // Update interview stage and coding challenge if provided in the response
      if (response && response.interview_stage) {
        console.log('ChatInterface.js: API response received. Full response:', JSON.stringify(response, null, 2));
        console.log('ChatInterface.js: Updating interview stage to:', response.interview_stage);
        setInterviewStage(response.interview_stage);
        
        // Log the details before the conditional check
        console.log('ChatInterface.js: Raw API response.codingChallengeDetail from service:', JSON.stringify(response.codingChallengeDetail, null, 2));
        console.log('ChatInterface.js: API response.interview_stage for challenge check:', response.interview_stage);

        // Check for coding challenge data if stage is coding_challenge or coding_challenge_waiting
        if ((response.interview_stage === 'coding_challenge' || response.interview_stage === 'coding_challenge_waiting') && response.codingChallengeDetail) {
          console.log(`ChatInterface.js: Stage is '${response.interview_stage}' AND response.codingChallengeDetail is TRUTHY.`);
          console.log("ChatInterface.js: Inspecting response.codingChallengeDetail before calling setCurrentCodingChallenge:", JSON.stringify(response.codingChallengeDetail, null, 2));
          
          setCurrentCodingChallenge(response.codingChallengeDetail);
          console.log("ChatInterface.js: setCurrentCodingChallenge CALLED with:", JSON.stringify(response.codingChallengeDetail, null, 2));
        } else {
          console.log(`ChatInterface.js: Stage is '${response.interview_stage}' OR response.codingChallengeDetail is FALSY.`);
          if (response.interview_stage === 'coding_challenge' || response.interview_stage === 'coding_challenge_waiting') {
            console.warn(`ChatInterface.js: Stage IS '${response.interview_stage}', but response.codingChallengeDetail is FALSY. Value:`, response.codingChallengeDetail);
            // If stage indicates challenge but no details, might clear existing if any, or rely on Interview.js to show loading
            // setCurrentCodingChallenge(null); // Optionally clear if stage is challenge but no details given
          }
        }
      }
      
      // Clear any errors
      setError(null);
    } catch (err) {
      console.error('Error sending message:', err);
      setError('Failed to send message. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  // Function to handle voice recording
  const handleVoiceRecording = async () => {
    if (isRecording) {
      try {
        // Stop recording
        const audioData = await stopRecording();
        
        if (!audioData || !audioData.blob) {
          throw new Error('Failed to get audio data.');
        }
        
        // Get base64-encoded audio
        const audioBase64 = await getAudioBase64(audioData.blob);
        
        if (!audioBase64) {
          throw new Error('Failed to encode audio data.');
        }
        
        // Set loading state
        setLoading(true);
        
        // Add user message with loading indicator
        addMessage({
          role: 'user',
          content: '🎤 Transcribing audio...',
          loading: true,
        });
        
        // Send audio for transcription and get response
        const response = await transcribeAndRespond(audioBase64, userId, sessionId, contextJobRoleData);
        
        // Update the user message with the transcribed text
        // Find the last user message and update it
        const updatedMessages = [...messages];
        for (let i = updatedMessages.length - 1; i >= 0; i--) {
          if (updatedMessages[i].role === 'user' && updatedMessages[i].loading) {
            updatedMessages[i] = {
              role: 'user',
              content: response.transcription || '(No speech detected)',
            };
            break;
          }
        }
        
        // Update messages with transcription
        if (updatedMessages.length !== messages.length) {
          console.error('Failed to update transcription message.');
        }
        
        // Add AI response
        addMessage({
          role: 'assistant',
          content: response.response,
          tool_calls: response.tool_calls,
          audioUrl: response.audio_response_url
        });

        // Update interview stage if provided in the response
        if (response.interview_stage) {
          console.log('Updating interview stage (voice) to:', response.interview_stage);
          setInterviewStage(response.interview_stage);

          // Check for coding challenge data if stage is coding_challenge
          if (response.interview_stage === 'coding_challenge' && response.coding_challenge_detail) {
            console.log("Received structured coding challenge data (voice):", response.coding_challenge_detail);
            setCurrentCodingChallenge(response.coding_challenge_detail);
          } else if (response.interview_stage !== 'coding_challenge') {
             if (currentCodingChallenge) {
                console.log("Interview stage is not coding_challenge (voice), clearing any active challenge.");
                setCurrentCodingChallenge(null);
            }
          }
        }
        
        // Clear any errors
        setError(null);
      } catch (err) {
        console.error('Error processing voice input:', err);
        
        // Update the temporary message with error info
        const updatedMessages = [...messages];
        for (let i = updatedMessages.length - 1; i >= 0; i--) {
          if (updatedMessages[i].role === 'user' && updatedMessages[i].loading) {
            updatedMessages[i] = {
              role: 'user',
              content: err.isNoSpeech 
                ? '(No speech detected. Please try again.)' 
                : '(Error transcribing audio. Please try again.)',
              error: true
            };
            break;
          }
        }
        
        // Set error message
        setError(err.isVoiceUnavailable 
          ? 'Voice processing is not available.' 
          : 'Failed to process voice input. Please try again.'
        );
      } finally {
        setLoading(false);
      }
    } else {
      // Start recording
      try {
        await initRecording();
        startRecording();
      } catch (err) {
        console.error('Error starting recording:', err);
        setError('Failed to start recording. Please check microphone permissions.');
        
        // If permission issues, show help
        if (err.name === 'NotAllowedError' || err.message.includes('permission')) {
          setShowPermissionHelp(true);
        }
      }
    }
  };

  // Function to handle retrying microphone access
  const handleRetryMicrophoneAccess = async () => {
    setShowPermissionHelp(false);
    onClose();
    
    try {
      setLoading(true);
      const initialized = await initRecording();
      
      if (initialized) {
        toast({
          title: 'Success',
          description: 'Microphone access granted!',
          status: 'success',
          duration: 3000,
        });
      }
    } catch (err) {
      console.error('Error during microphone retry:', err);
    } finally {
      setLoading(false);
    }
  };

  // Handle coding challenge hint request
  const handleRequestHint = async (currentCode) => {
    if (!currentCodingChallenge) return;
    
    try {
      setLoading(true);
      
      const hintResponse = await getChallengeHint(
        currentCodingChallenge.challenge_id,
        currentCode,
        userId,
        sessionId
      );
      
      // Add hint as an AI message
      if (hintResponse.hints && hintResponse.hints.length > 0) {
        addMessage({
          role: 'assistant',
          content: `Hint: ${hintResponse.hints.join('\n\n')}`,
          isHint: true
        });
      } else {
        addMessage({
          role: 'assistant',
          content: "I don't have a specific hint for this code at the moment. Try breaking down the problem into smaller steps.",
          isHint: true
        });
      }
    } catch (err) {
      console.error('Error getting hint:', err);
      
      toast({
        title: 'Hint Error',
        description: 'Failed to get a hint. Please try again later.',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setLoading(false);
    }
  };

  // No need for handleKeyDown as we use onKeyPress directly in the Input component

  return (
    <Flex direction="column" h="100vh" overflow="hidden">
      <Box flex="1" overflow="auto" p={4}>
        <VStack spacing={4} align="stretch">
          {messages.map((msg, index) => (
            <ChatMessage 
              key={index} 
              message={msg.text || msg.content || ''}
              sender={msg.role || msg.sender || 'assistant'} 
              audioUrl={msg.audioUrl || ''} 
              isHint={msg.isHint || false} 
              isLoading={msg.loading || false} 
              toolCalls={msg.tool_calls || msg.toolCalls} 
            />
          ))}
          
          {/* Conditionally render CodingChallenge based on stage and data */}
          {interviewStage === 'coding_challenge' && currentCodingChallenge && (
            <Box mt={4} mb={4} p={4} bg="gray.50" borderRadius="md">
              <CodingChallenge 
                challenge={currentCodingChallenge} // Use the state variable
                sessionId={sessionId}
                userId={userId}
                onComplete={(code, evaluationResults) => {
                  console.log('Challenge completed/submitted in ChatInterface', code, evaluationResults);
                  // This is where you might send the code to the backend via continueAfterCodingChallenge
                  // For now, let's assume CodingChallenge handles its own submission via its handleSubmit
                  // and this onComplete is more for signaling ChatInterface if needed.
                  // We might remove/refactor this specific onComplete if CodingChallenge.handleSubmit is sufficient.
                  setIsWaitingForCodingChallenge(false); // User is no longer just waiting, challenge UI might change
                  // Potentially, the AI will respond after submission, handled by normal message flow
                }}
                onRequestHint={(code) => handleRequestHint(code)}
                // isWaiting prop might not be needed directly on CodingChallenge if its internal state manages UI
              />
            </Box>
          )}
          
          {/* Loading indicator */}
          {loading && (
            <Flex justifyContent="center" p={4}>
              <Spinner size="md" color="blue.500" mr={2} />
              <Text>{isInitializing ? 'Initializing audio...' : 'Processing...'}</Text>
            </Flex>
          )}
          
          {/* Error display */}
          {(error || audioError) && (
            <Alert status="error" variant="left-accent" my={2}>
              <AlertIcon />
              <Text>{error || audioError}</Text>
              {(error?.includes('permission') || audioError?.includes('permission')) && (
                <Button size="sm" ml={2} onClick={() => setShowPermissionHelp(true)}>
                  Help
                </Button>
              )}
            </Alert>
          )}
          
          <div ref={messagesEndRef} />
        </VStack>
      </Box>

      {/* Input area */}
      <Flex 
        p={4} 
        borderTop="1px" 
        borderColor="gray.200"
        alignItems="center"
        backgroundColor="white"
      >
        <Input
          placeholder="Type your message..."
          value={messageInput}
          onChange={(e) => setMessageInput(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
          mr={2}
          disabled={loading || isWaitingForCodingChallenge}
        />
        
        <IconButton
          icon={<FaPaperPlane />}
          colorScheme="blue"
          aria-label="Send message"
          onClick={handleSendMessage}
          mr={2}
          isDisabled={loading || !messageInput.trim() || isWaitingForCodingChallenge}
        />
        
        <IconButton
          icon={isRecording ? <FaStop /> : <FaMicrophone />}
          colorScheme={isRecording ? "red" : "blue"}
          aria-label={isRecording ? "Stop recording" : "Start recording"}
          onClick={handleVoiceRecording}
          isDisabled={(loading && !isRecording) || isWaitingForCodingChallenge || isInitializing}
          isLoading={isInitializing}
        />
        
        {voiceMode ? (
          <Button 
            variant="outline" 
            size="sm" 
            ml={2} 
            onClick={() => setVoiceMode(false)}
          >
            Text Mode
          </Button>
        ) : (
          <Button 
            variant="outline" 
            size="sm" 
            ml={2} 
            onClick={() => setVoiceMode(true)}
          >
            Voice Mode
          </Button>
        )}
      </Flex>

      {/* Microphone Permission Help Modal */}
      <Modal isOpen={isOpen} onClose={onClose}>
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Microphone Access Required</ModalHeader>
          <ModalBody>
            <VStack spacing={4} align="stretch">
              <Alert status="info">
                <AlertIcon />
                <Text>Voice mode requires microphone access to function properly.</Text>
              </Alert>
              
              <Text fontWeight="bold">How to enable microphone access:</Text>
              
              <VStack align="start" spacing={2} pl={4}>
                <Text>1. Look for the microphone icon in your browser's address bar</Text>
                <Text>2. Click on it and select "Allow"</Text>
                <Text>3. If not visible, go to your browser settings</Text>
                <Text>4. Find "Site Settings" or "Privacy & Security"</Text>
                <Text>5. Locate "Microphone" permissions and allow for this site</Text>
              </VStack>
              
              <Alert status="warning">
                <AlertIcon as={FaExclamationTriangle} />
                <Text>After enabling permissions, you may need to refresh the page.</Text>
              </Alert>
              
              <Divider />
              
              <Box>
                <Text fontWeight="bold" mb={2}>Still having issues?</Text>
                <Button 
                  as={Link} 
                  to="/microphone-test" 
                  colorScheme="teal" 
                  size="sm" 
                  width="full"
                  onClick={onClose}
                >
                  Open Microphone Troubleshooter
                </Button>
                <Text fontSize="sm" mt={2}>
                  The troubleshooter will help diagnose and fix microphone issues.
                </Text>
              </Box>
            </VStack>
          </ModalBody>
          <ModalFooter>
            <Button colorScheme="blue" mr={3} onClick={handleRetryMicrophoneAccess}>
              Try Again
            </Button>
            <Button variant="ghost" onClick={onClose}>Close</Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Flex>
  );
};

export default ChatInterface; 