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
 */
const ChatInterface = () => {
  const {
    userId,
    sessionId,
    messages,
    loading,
    error,
    voiceMode,
    setUserId,
    setSessionId,
    setMessages,
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
    audioData,
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

  // Handle sending a text message
  const handleSendMessage = async () => {
    if (!messageInput.trim()) return;
    
    try {
      setLoading(true);
      
      // Add user message to UI immediately
      addMessage({ sender: 'user', message: messageInput });
      
      // Clear input
      setMessageInput('');
      
      let response;
      
      // Either start a new interview or continue an existing one
      if (!sessionId) {
        response = await startInterview(messageInput, userId);
        setSessionId(response.session_id);
        if (!userId) {
          // If we didn't have a userId, the API generated one for us
          setUserId(response.user_id || 'anonymous');
        }
      } else {
        response = await continueInterview(sessionId, messageInput, userId);
      }
      
      // Add AI's response to the chat
      addMessage({ sender: 'ai', message: response.response });
      
    } catch (err) {
      setError(err.message || 'Error sending message');
      toast({
        title: 'Error',
        description: err.message || 'Error sending message',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setLoading(false);
    }
  };

  // Handle voice recording toggle
  const handleVoiceRecording = async () => {
    if (isRecording) {
      setLoading(true);
      
      // Stop recording
      const audio = await stopRecording();
      
      if (audio && audio.blob) {
        try {
          // Convert audio to base64
          const base64Audio = await getAudioBase64(audio.blob);
          
          // Send audio to transcribe and get response
          const response = await transcribeAndRespond(base64Audio, userId, sessionId);
          
          // Add transcription as user message
          addMessage({ sender: 'user', message: response.transcription });
          
          // Add AI response
          addMessage({ sender: 'ai', message: response.response });
          
          // Update session info
          setSessionId(response.session_id);
          
          // Play audio response if available
          if (response.audio_response_url) {
            const audio = new Audio(response.audio_response_url);
            audio.play();
          }
        } catch (err) {
          setError(err.message || 'Error processing voice');
          toast({
            title: 'Error',
            description: err.message || 'Error processing voice',
            status: 'error',
            duration: 5000,
            isClosable: true,
          });
        } finally {
          setLoading(false);
        }
      } else {
        setLoading(false);
      }
    } else {
      // Start recording
      const success = await startRecording();
      if (!success) {
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