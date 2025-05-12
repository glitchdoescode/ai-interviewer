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
import { useInterview } from '../context/InterviewContext';
import useAudioRecorder from '../hooks/useAudioRecorder';
import { startInterview, continueInterview, transcribeAndRespond } from '../api/interviewService';


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
    setSessionId,
    addMessage,
    setLoading,
    setError,
    setVoiceMode,
  } = useInterview();

  const [messageInput, setMessageInput] = useState('');
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
        response = await continueInterview(messageInput, sessionId, userId, jobRoleData);
      } else {
        response = await startInterview(messageInput, userId, jobRoleData);
        
        // Set the session ID from the response
        setSessionId(response.session_id);
      }
      
      // Add AI response to chat
      addMessage({
        role: 'assistant',
        content: response.response,
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
          audioUrl: response.audio_response_url
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
      {/* Hidden div for audio recorder reference */}
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
              message={msg.message}
              sender={msg.sender}
              isLoading={loading && idx === messages.length - 1 && msg.sender === 'ai'}
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
              flex="1"
              placeholder="Type your message..."
              value={messageInput}
              onChange={(e) => setMessageInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={loading}
              mr={2}
            />
            <IconButton
              colorScheme="brand"
              aria-label="Send message"
              icon={<FaPaperPlane />}
              isLoading={loading}
              onClick={handleSendMessage}
            />
          </Flex>
        )}
      </Box>
    </Box>
  );
};

export default ChatInterface; 