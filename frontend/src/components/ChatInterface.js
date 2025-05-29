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
  continueAfterCodingChallenge,
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
    setSessionId,
    addMessage,
    setLoading,
    setError,
    setVoiceMode,
    setInterviewStage,
  } = useInterview();

  const [messageInput, setMessageInput] = useState('');
  const [currentCodingChallenge, setCurrentCodingChallenge] = useState(null);
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

  // Check for coding challenge instructions in AI messages
  useEffect(() => {
    // Look for coding challenge data in the latest message
    if (messages.length > 0) {
      const lastMessage = messages[messages.length - 1];
      if (lastMessage.role === 'assistant') {
        // Check if the message contains coding challenge data
        // This could be embedded in a tool_call from the LLM
        if (lastMessage.tool_calls && lastMessage.tool_calls.length > 0) {
          // Look for either the old or new coding challenge tool
          const codingChallengeTool = lastMessage.tool_calls.find(
            tool => tool.name === 'start_coding_challenge' || tool.name === 'generate_coding_challenge_from_jd'
          );
          
          if (codingChallengeTool && codingChallengeTool.result) {
            try {
              const challengeData = typeof codingChallengeTool.result === 'string' 
                ? JSON.parse(codingChallengeTool.result) 
                : codingChallengeTool.result;
                
              if (challengeData.status === 'success') {
                setCurrentCodingChallenge(challengeData);
                setIsWaitingForCodingChallenge(true);
              }
            } catch (err) {
              console.error('Error parsing coding challenge data:', err);
            }
          }
        }
      }
    }
  }, [messages]);

  // Monitor interview stage changes and automatically generate coding challenge when needed
  useEffect(() => {
    const handleCodingChallengeStage = async () => {
      // Check if we're in coding challenge stage but don't have a challenge yet
      if (interviewStage === 'coding_challenge' && !currentCodingChallenge && !isWaitingForCodingChallenge) {
        try {
          console.log('Interview stage changed to coding_challenge. Generating coding problem...');
          setLoading(true);
          
          // Generate a coding problem based on the job role
          const problemResponse = await generateCodingProblem(
            jobRoleData?.role_name || 'Software Developer',
            'medium', // Default difficulty
            jobRoleData?.required_skills || ['programming']
          );
          
          if (problemResponse && problemResponse.challenge) {
            // Set the current coding challenge
            setCurrentCodingChallenge(problemResponse.challenge);
            setIsWaitingForCodingChallenge(true);
            
            // Notify the user
            toast({
              title: 'Coding Challenge',
              description: 'A coding challenge has been generated based on your interview progress.',
              status: 'info',
              duration: 5000,
              isClosable: true,
            });
          }
        } catch (err) {
          console.error('Error generating coding challenge:', err);
          setError('Failed to generate coding challenge. Please try again.');
        } finally {
          setLoading(false);
        }
      }
    };
    
    handleCodingChallengeStage();
  }, [interviewStage, currentCodingChallenge, isWaitingForCodingChallenge, jobRoleData, setLoading, setError, toast]);

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
        // Check if we were in a coding challenge
        if (isWaitingForCodingChallenge) {
          response = await continueAfterCodingChallenge(
            messageInput, 
            sessionId, 
            userId, 
            true // assume user is done with challenge when they send a message
          );
          
          // Reset coding challenge state
          setCurrentCodingChallenge(null);
          setIsWaitingForCodingChallenge(false);
        } else {
          response = await continueInterview(messageInput, sessionId, userId, jobRoleData);
        }
      } else {
        response = await startInterview(messageInput, userId, jobRoleData);
        
        // Set the session ID from the response
        setSessionId(response.session_id);
      }
      
      // Add AI response to chat
      addMessage({
        role: 'assistant',
        content: response.response,
        tool_calls: response.tool_calls
      });
      
      // Update interview stage if provided in the response
      if (response.interview_stage) {
        console.log('Updating interview stage to:', response.interview_stage);
        setInterviewStage(response.interview_stage);
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
        const response = await transcribeAndRespond(audioBase64, userId, sessionId, jobRoleData);
        
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
          tool_calls: response.tool_calls
        });

        // Update interview stage if provided in the response
        if (response.interview_stage) {
          console.log('Updating interview stage to:', response.interview_stage);
          setInterviewStage(response.interview_stage);
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
          {messages.map((message, index) => {
            // Check if this is a coding challenge message from the AI
            if (
              message.role === 'assistant' && 
              message.tool_calls && 
              message.tool_calls.some(call => call.name === 'start_coding_challenge' || call.name === 'generate_coding_challenge_from_jd')
            ) {
              // Extract the coding challenge data
              const codingChallenge = message.tool_calls.find(
                call => call.name === 'start_coding_challenge' || call.name === 'generate_coding_challenge_from_jd'
              ).result;
              
              // Store the coding challenge for later use
              if (!currentCodingChallenge) {
                setCurrentCodingChallenge(codingChallenge);
                setIsWaitingForCodingChallenge(true);
              }
              
              // Render both the message and the coding challenge
              return (
                <React.Fragment key={index}>
                  <ChatMessage message={message} />
                   <CodingChallenge 
                     challenge={codingChallenge}
                     onSubmit={(code, isCompleted) => {
                       // Submit the code and continue the interview
                       try {
                         setLoading(true);
                         continueAfterCodingChallenge(
                           code, 
                           sessionId, 
                           userId, 
                           isCompleted
                         ).then(response => {
                           // Add AI response to chat
                           addMessage({
                             role: 'assistant',
                             content: response.response,
                             tool_calls: response.tool_calls
                           });
                           
                           // Reset coding challenge state
                           setIsWaitingForCodingChallenge(false);
                           setCurrentCodingChallenge(null);
                           setLoading(false);
                         }).catch(err => {
                           console.error('Error submitting code:', err);
                           setError('Failed to submit code solution. Please try again.');
                           setLoading(false);
                         });
                       } catch (err) {
                         console.error('Error preparing code submission:', err);
                         setError('Failed to submit code. Please try again.');
                         setLoading(false);
                       }
                     }}
                     onRequestHint={(code) => handleRequestHint(code)}
                     isWaiting={isWaitingForCodingChallenge}
                   />
                </React.Fragment>
              );
            }
            
            // Regular message
            console.log('Rendering ChatMessage with:', { 
              content: message.content, 
              audioUrl: message.audioUrl,
              fullMessage: message 
            });
            return <ChatMessage 
              key={index} 
              message={message.content || message.message || ''} 
              sender={message.role || message.sender || 'assistant'} 
              audioUrl={message.audioUrl || ''} 
              isHint={message.isHint || false} 
              isLoading={message.loading || false} 
            />;
          })}
          
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