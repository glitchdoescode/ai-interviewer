import React, { useState, useEffect } from 'react';
import {
  Box,
  Text,
  HStack,
  VStack,
  Badge,
  Progress,
  Icon,
  useColorModeValue,
  Flex,
  Divider
} from '@chakra-ui/react';
import {
  FaComments,
  FaMicrophone,
  FaUser,
  FaRobot,
  FaClock,
  FaSignal
} from 'react-icons/fa';
import { AudioLevelVisualizer } from './AudioControls';

/**
 * Conversation indicators component
 * Shows who is speaking, conversation state, and audio levels
 */
const ConversationIndicators = ({
  candidateSpeaking = false,
  aiSpeaking = false,
  candidateAudioLevel = 0,
  aiAudioLevel = 0,
  interviewStage = 'introduction',
  connectionQuality = 'excellent', // 'poor', 'fair', 'good', 'excellent'
  sessionDuration = 0, // in seconds
  messagesCount = 0,
  isListening = false,
  compact = false,
  ...props
}) => {
  const [displayDuration, setDisplayDuration] = useState('00:00');
  
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.600');
  const textColor = useColorModeValue('gray.600', 'gray.300');

  // Format session duration
  useEffect(() => {
    const minutes = Math.floor(sessionDuration / 60);
    const seconds = sessionDuration % 60;
    setDisplayDuration(`${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`);
  }, [sessionDuration]);

  // Get stage display info
  const getStageInfo = (stage) => {
    const stageMap = {
      'introduction': { label: 'Introduction', color: 'blue' },
      'technical_questions': { label: 'Technical Questions', color: 'purple' },
      'coding_challenge': { label: 'Coding Challenge', color: 'orange' },
      'coding_challenge_waiting': { label: 'Coding Challenge', color: 'orange' },
      'feedback': { label: 'Feedback', color: 'green' },
      'behavioral_questions': { label: 'Behavioral Questions', color: 'teal' },
      'conclusion': { label: 'Conclusion', color: 'gray' }
    };
    return stageMap[stage] || { label: 'Interview', color: 'gray' };
  };

  // Get connection quality info
  const getConnectionInfo = (quality) => {
    const qualityMap = {
      'poor': { label: 'Poor', color: 'red', bars: 1 },
      'fair': { label: 'Fair', color: 'orange', bars: 2 },
      'good': { label: 'Good', color: 'yellow', bars: 3 },
      'excellent': { label: 'Excellent', color: 'green', bars: 4 }
    };
    return qualityMap[quality] || qualityMap['good'];
  };

  const stageInfo = getStageInfo(interviewStage);
  const connectionInfo = getConnectionInfo(connectionQuality);

  // Compact layout for mobile/overlay
  if (compact) {
    return (
      <Box
        bg={bgColor}
        p={3}
        borderRadius="md"
        border="1px solid"
        borderColor={borderColor}
        boxShadow="sm"
        {...props}
      >
        <VStack spacing={2} align="stretch">
          {/* Speaking Status */}
          <HStack justify="space-between">
            <HStack spacing={2}>
              {candidateSpeaking && (
                <HStack spacing={1}>
                  <Icon as={FaUser} color="blue.500" boxSize={3} />
                  <Text fontSize="xs" color="blue.500" fontWeight="bold">
                    You're speaking
                  </Text>
                  <AudioLevelVisualizer
                    audioLevel={candidateAudioLevel}
                    isActive={candidateSpeaking}
                    barCount={3}
                    height="12px"
                  />
                </HStack>
              )}
              
              {aiSpeaking && (
                <HStack spacing={1}>
                  <Icon as={FaRobot} color="green.500" boxSize={3} />
                  <Text fontSize="xs" color="green.500" fontWeight="bold">
                    AI Speaking
                  </Text>
                  <AudioLevelVisualizer
                    audioLevel={aiAudioLevel}
                    isActive={aiSpeaking}
                    barCount={3}
                    height="12px"
                  />
                </HStack>
              )}
              
              {!candidateSpeaking && !aiSpeaking && isListening && (
                <HStack spacing={1}>
                  <Icon as={FaMicrophone} color="gray.500" boxSize={3} />
                  <Text fontSize="xs" color="gray.500">
                    Listening...
                  </Text>
                </HStack>
              )}
            </HStack>
            
            <Text fontSize="xs" color={textColor}>
              {displayDuration}
            </Text>
          </HStack>
          
          {/* Stage and Connection */}
          <HStack justify="space-between">
            <Badge colorScheme={stageInfo.color} fontSize="xs">
              {stageInfo.label}
            </Badge>
            <HStack spacing={1}>
              <Icon as={FaSignal} color={`${connectionInfo.color}.500`} boxSize={3} />
              <Text fontSize="xs" color={`${connectionInfo.color}.500`}>
                {connectionInfo.label}
              </Text>
            </HStack>
          </HStack>
        </VStack>
      </Box>
    );
  }

  // Full layout for desktop
  return (
    <Box
      bg={bgColor}
      p={4}
      borderRadius="lg"
      border="1px solid"
      borderColor={borderColor}
      boxShadow="md"
      {...props}
    >
      <VStack spacing={4} align="stretch">
        {/* Header */}
        <HStack justify="space-between" align="center">
          <HStack spacing={2}>
            <Icon as={FaComments} color="primary.500" />
            <Text fontWeight="bold" color="primary.500">
              Conversation
            </Text>
          </HStack>
          
          <HStack spacing={4}>
            <HStack spacing={1}>
              <Icon as={FaClock} color={textColor} boxSize={4} />
              <Text fontSize="sm" fontWeight="mono" color={textColor}>
                {displayDuration}
              </Text>
            </HStack>
            
            <HStack spacing={1}>
              <Icon as={FaComments} color={textColor} boxSize={4} />
              <Text fontSize="sm" color={textColor}>
                {messagesCount}
              </Text>
            </HStack>
          </HStack>
        </HStack>

        <Divider />

        {/* Speaking Status */}
        <VStack spacing={3} align="stretch">
          <Text fontSize="sm" fontWeight="medium" color={textColor}>
            Speaking Status
          </Text>
          
          {/* Candidate Speaking */}
          <HStack justify="space-between" align="center">
            <HStack spacing={3}>
              <Icon 
                as={FaUser} 
                color={candidateSpeaking ? 'blue.500' : 'gray.400'} 
                boxSize={5}
              />
              <VStack align="start" spacing={0}>
                <Text 
                  fontSize="sm" 
                  fontWeight={candidateSpeaking ? 'bold' : 'normal'}
                  color={candidateSpeaking ? 'blue.500' : textColor}
                >
                  You
                </Text>
                <Text fontSize="xs" color={textColor}>
                  {candidateSpeaking ? 'Speaking' : 'Listening'}
                </Text>
              </VStack>
            </HStack>
            
            <AudioLevelVisualizer
              audioLevel={candidateAudioLevel}
              isActive={candidateSpeaking}
              barCount={5}
              height="20px"
            />
          </HStack>
          
          {/* AI Speaking */}
          <HStack justify="space-between" align="center">
            <HStack spacing={3}>
              <Icon 
                as={FaRobot} 
                color={aiSpeaking ? 'green.500' : 'gray.400'} 
                boxSize={5}
              />
              <VStack align="start" spacing={0}>
                <Text 
                  fontSize="sm" 
                  fontWeight={aiSpeaking ? 'bold' : 'normal'}
                  color={aiSpeaking ? 'green.500' : textColor}
                >
                  AI Interviewer
                </Text>
                <Text fontSize="xs" color={textColor}>
                  {aiSpeaking ? 'Speaking' : 'Listening'}
                </Text>
              </VStack>
            </HStack>
            
            <AudioLevelVisualizer
              audioLevel={aiAudioLevel}
              isActive={aiSpeaking}
              barCount={5}
              height="20px"
            />
          </HStack>
        </VStack>

        <Divider />

        {/* Interview Progress */}
        <VStack spacing={2} align="stretch">
          <HStack justify="space-between">
            <Text fontSize="sm" fontWeight="medium" color={textColor}>
              Interview Stage
            </Text>
            <Badge colorScheme={stageInfo.color} fontSize="xs">
              {stageInfo.label}
            </Badge>
          </HStack>
        </VStack>

        <Divider />

        {/* Connection Quality */}
        <VStack spacing={2} align="stretch">
          <HStack justify="space-between">
            <Text fontSize="sm" fontWeight="medium" color={textColor}>
              Connection Quality
            </Text>
            <HStack spacing={1}>
              <Icon as={FaSignal} color={`${connectionInfo.color}.500`} />
              <Text fontSize="sm" color={`${connectionInfo.color}.500`}>
                {connectionInfo.label}
              </Text>
            </HStack>
          </HStack>
          
          {/* Connection bars */}
          <HStack spacing={1}>
            {[1, 2, 3, 4].map(bar => (
              <Box
                key={bar}
                w={2}
                h={bar * 2 + 2}
                bg={bar <= connectionInfo.bars ? `${connectionInfo.color}.500` : 'gray.300'}
                borderRadius="sm"
                transition="all 0.2s"
              />
            ))}
          </HStack>
        </VStack>
      </VStack>
    </Box>
  );
};

/**
 * Simple speaking indicator for overlay use
 */
export const SpeakingIndicator = ({ 
  isActive = false, 
  speaker = 'candidate', // 'candidate' or 'ai'
  compact = false 
}) => {
  if (!isActive) return null;

  const speakerInfo = {
    candidate: { icon: FaUser, color: 'blue', label: 'You' },
    ai: { icon: FaRobot, color: 'green', label: 'AI' }
  };

  const info = speakerInfo[speaker];

  return (
    <HStack
      spacing={2}
      bg="blackAlpha.700"
      color="white"
      px={3}
      py={1}
      borderRadius="full"
      animation="pulse 1.5s infinite"
    >
      <Icon as={info.icon} boxSize={3} />
      <Text fontSize={compact ? "xs" : "sm"} fontWeight="bold">
        {info.label} Speaking
      </Text>
      <AudioLevelVisualizer
        audioLevel={0.7}
        isActive={true}
        barCount={3}
        height={compact ? "8px" : "12px"}
      />
    </HStack>
  );
};

export default ConversationIndicators; 
 
 