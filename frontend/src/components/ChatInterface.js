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
} from '@chakra-ui/react';
import { FaPaperPlane, FaMicrophone, FaStop } from 'react-icons/fa';
import ChatMessage from './ChatMessage';
import CodingChallenge from './CodingChallenge';
import { useInterview } from '../context/InterviewContext';
import useAudioRecorder from '../hooks/useAudioRecorder';
import { 
  startInterview, 
  continueInterview, 
  transcribeAndRespond,
  continueAfterCodingChallenge,
  getChallengeHint
} from '../api/interviewService';


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
  } = useInterview();

  const [messageInput, setMessageInput] = useState('');
  const [currentCodingChallenge, setCurrentCodingChallenge] = useState(null);
  const [isWaitingForCodingChallenge, setIsWaitingForCodingChallenge] = useState(false);
  const messagesEndRef = useRef(null);
  const toast = useToast();

  // Audio recording functionality
  const {
    isRecording,
    error: audioError,
    startRecording,
    stopRecording,
    getAudioBase64,
    isInitializing,
    permissionGranted,
    initRecording
  } = useAudioRecorder();

  // Initialize audio on component mount for better user experience
  useEffect(() => {
    if (voiceMode) {
      // Pre-initialize audio in voice mode
      initRecording().catch(err => {
        console.error('Failed to initialize audio on mount:', err);
      });
    }
  }, [voiceMode, initRecording]);

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Show toast for audio errors
  useEffect(() => {
    if (audioError) {
      toast({
        title: 'Audio Error',
        description: audioError,
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
          const startCodingChallengeTool = lastMessage.tool_calls.find(
            tool => tool.name === 'start_coding_challenge'
          );
          
          if (startCodingChallengeTool && startCodingChallengeTool.result) {
            try {
              const challengeData = typeof startCodingChallengeTool.result === 'string' 
                ? JSON.parse(startCodingChallengeTool.result) 
                : startCodingChallengeTool.result;
                
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
        
        // Update user message with transcription
        addMessage({
          role: 'user',
          content: response.transcription,
        });
        
        // If we don't have a session ID yet, set it
        if (!sessionId) {
          setSessionId(response.session_id);
        }
        
        // Add AI response
        addMessage({
          role: 'assistant',
          content: response.response,
          audioUrl: response.audio_response_url,
          tool_calls: response.tool_calls
        });
      } catch (err) {
        console.error('Error processing voice recording:', err);
        setError('Failed to process audio. Please try again.');
        // Add error message
        addMessage({
          role: 'system',
          content: `Error: ${err.message || 'Failed to process audio'}`,
          isError: true,
        });
      } finally {
        setLoading(false);
      }
    } else {
      // Start recording
      try {
        setLoading(true);
        
        // Show initialization message
        if (!permissionGranted) {
          addMessage({
            role: 'system',
            content: 'Requesting microphone permission...',
            isSystem: true,
          });
        }
        
        const started = await startRecording();
        
        if (!started) {
          throw new Error(audioError || 'Failed to start recording');
        }
        
        // Show recording started message
        addMessage({
          role: 'system',
          content: 'Recording started. Speak now and click the stop button when finished.',
          isSystem: true,
        });
      } catch (err) {
        console.error('Error starting voice recording:', err);
        setError(`Failed to start recording: ${err.message}`);
        
        // Show a helpful message based on the error
        let errorMessage = 'Could not start recording.';
        if (err.message?.includes('permission')) {
          errorMessage = 'Microphone permission denied. Please enable it in your browser settings.';
        } else if (err.message?.includes('AudioContext')) {
          errorMessage = 'Audio system initialization failed. Try clicking the button again.';
        }
        
        // Add error message to chat
        addMessage({
          role: 'system',
          content: `Error: ${errorMessage}`,
          isError: true,
        });
      } finally {
        setLoading(false);
      }
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

  // Handle completion of coding challenge
  const handleChallengeComplete = async (result) => {
    try {
      setLoading(true);
      
      // Send message that challenge was completed
      const response = await continueAfterCodingChallenge(
        "I've completed the coding challenge.",
        sessionId,
        userId,
        result.evaluation.passed
      );
      
      // Add AI response
      addMessage({
        role: 'assistant',
        content: response.response,
        tool_calls: response.tool_calls
      });
      
      // Reset coding challenge state
      setCurrentCodingChallenge(null);
      setIsWaitingForCodingChallenge(false);
    } catch (err) {
      console.error('Error completing challenge:', err);
      setError('Failed to process challenge completion. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  // Handle keyboard shortcuts (Enter to send message)
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  return (
    <Flex direction="column" h="100vh" overflow="hidden">
      <Box flex="1" overflow="auto" p={4}>
        <VStack spacing={4} align="stretch">
          {messages.map((message, index) => {
            // Check if this is a coding challenge message from the AI
            if (
              message.role === 'assistant' && 
              message.tool_calls && 
              message.tool_calls.some(call => call.name === 'start_coding_challenge')
            ) {
              // Extract the coding challenge data
              const codingChallenge = message.tool_calls.find(
                call => call.name === 'start_coding_challenge'
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
            return <ChatMessage key={index} message={message} />;
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
    </Flex>
  );
};

export default ChatInterface; 