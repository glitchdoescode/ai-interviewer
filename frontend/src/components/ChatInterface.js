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
  } = useAudioRecorder();

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
        await stopRecording();
        
        // Get base64-encoded audio
        const audioBase64 = await getAudioBase64();
        
        if (!audioBase64) {
          throw new Error('Failed to get audio data.');
        }
        
        // Set loading state
        setLoading(true);
        
        // Add user message with loading indicator
        addMessage({
          role: 'user',
          content: '🎤 Recording...',
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
        
        // Clear any errors
        setError(null);
      } catch (err) {
        console.error('Error processing voice:', err);
        setError('Failed to process voice recording. Please try again or switch to text mode.');
        
        // Remove the loading message
        addMessage({
          role: 'user',
          content: '❌ Voice recording failed. Please try again.',
          error: true,
        });
      } finally {
        setLoading(false);
      }
    } else {
      // Start recording
      try {
        const success = await startRecording();
        if (!success) {
          throw new Error('Could not start recording');
        }
      } catch (err) {
        console.error('Error starting recording:', err);
        setError('Could not start recording. Please check microphone permissions.');
        
        toast({
          title: 'Recording Error',
          description: 'Could not start recording. Please check microphone permissions.',
          status: 'error',
          duration: 5000,
          isClosable: true,
        });
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
    <Box
      height="100%"
      display="flex"
      flexDirection="column"
      bg="white"
      borderRadius="md"
      boxShadow="md"
      p={4}
    >
      {/* Hidden div for audio recording */}
      <div id="recorder-instance" style={{ display: 'none' }}></div>
      
      {/* Chat Header */}
      <Flex
        alignItems="center"
        justifyContent="space-between"
        p={2}
        mb={4}
        borderBottom="1px"
        borderColor="gray.200"
      >
        <Text fontSize="lg" fontWeight="bold">
          Technical Interview
        </Text>
        
        <Button
          size="sm"
          colorScheme={voiceMode ? 'brand' : 'gray'}
          leftIcon={<FaMicrophone />}
          onClick={() => setVoiceMode(!voiceMode)}
        >
          {voiceMode ? 'Voice Mode' : 'Text Mode'}
        </Button>
      </Flex>

      {/* Messages Container */}
      <VStack
        flex="1"
        overflowY="auto"
        spacing={4}
        p={2}
        mb={4}
        align="stretch"
      >
        {messages.length === 0 ? (
          <Box textAlign="center" color="gray.500" mt={10}>
            <Text>Start your technical interview by saying hello!</Text>
          </Box>
        ) : (
          messages.map((msg, idx) => (
            <ChatMessage
              key={idx}
              message={msg.content}
              sender={msg.role}
              isLoading={loading && idx === messages.length - 1 && msg.role === 'assistant'}
              audioUrl={msg.audioUrl}
              isHint={msg.isHint}
            />
          ))
        )}
        
        {/* Loading message if no messages displayed yet */}
        {loading && messages.length === 0 && (
          <Flex justify="center" align="center" my={6}>
            <Spinner color="brand.500" mr={3} />
            <Text>Starting interview...</Text>
          </Flex>
        )}
        
        {/* Error alert */}
        {error && (
          <Alert status="error" borderRadius="md">
            <AlertIcon />
            {error}
          </Alert>
        )}
        
        {/* Coding Challenge Component */}
        {currentCodingChallenge && (
          <Box my={4}>
            <CodingChallenge 
              challenge={currentCodingChallenge}
              onComplete={handleChallengeComplete}
              onRequestHint={handleRequestHint}
            />
          </Box>
        )}
        
        {/* Invisible element for auto-scrolling */}
        <div ref={messagesEndRef} />
      </VStack>

      {/* Message Input */}
      <Box mt="auto">
        {voiceMode ? (
          <Button
            width="100%"
            height="50px"
            colorScheme={isRecording ? 'red' : 'brand'}
            leftIcon={isRecording ? <FaStop /> : <FaMicrophone />}
            isLoading={loading}
            onClick={handleVoiceRecording}
          >
            {isRecording ? 'Stop Recording' : 'Start Recording'}
          </Button>
        ) : (
          <Flex>
            <Input
              value={messageInput}
              onChange={(e) => setMessageInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type your message..."
              size="md"
              mr={2}
              disabled={loading || isWaitingForCodingChallenge}
            />
            <IconButton
              colorScheme="brand"
              aria-label="Send message"
              icon={<FaPaperPlane />}
              onClick={handleSendMessage}
              isLoading={loading}
              isDisabled={!messageInput.trim() || isWaitingForCodingChallenge}
            />
          </Flex>
        )}
        
        {/* Coding Challenge Active Indicator */}
        {isWaitingForCodingChallenge && (
          <Alert status="info" mt={2} size="sm" borderRadius="md">
            <AlertIcon />
            Please complete the coding challenge above before continuing the interview.
          </Alert>
        )}
      </Box>
    </Box>
  );
};

export default ChatInterface; 