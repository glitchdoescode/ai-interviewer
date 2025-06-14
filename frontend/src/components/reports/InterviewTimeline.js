import React from 'react';
import {
  Box,
  Heading,
  Text,
  VStack,
  HStack,
  Circle,
  Divider,
  useColorModeValue,
  Icon,
  Flex,
} from '@chakra-ui/react';
import { 
  FaUserAlt, 
  FaCode, 
  FaComment, 
  FaCheck, 
  FaChartBar,
  FaQuestionCircle,
  FaLightbulb,
} from 'react-icons/fa';

/**
 * InterviewTimeline component for displaying the progression of an interview
 * Shows key stages and events in chronological order
 */
const InterviewTimeline = ({
  title = 'Interview Timeline',
  events = [],
  currentStage = '',
}) => {
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');
  const textColor = useColorModeValue('gray.800', 'gray.100');
  const secondaryTextColor = useColorModeValue('gray.600', 'gray.400');
  const accentColor = useColorModeValue('blue.500', 'blue.300');
  const completedColor = useColorModeValue('green.500', 'green.300');
  const pendingColor = useColorModeValue('gray.300', 'gray.600');

  // Default stages if no events provided
  const defaultStages = [
    {
      id: 'introduction',
      title: 'Introduction',
      description: 'Getting to know the candidate',
      icon: FaUserAlt,
      timestamp: '',
    },
    {
      id: 'technical_questions',
      title: 'Technical Questions',
      description: 'Assessing technical knowledge',
      icon: FaQuestionCircle,
      timestamp: '',
    },
    {
      id: 'coding_challenge',
      title: 'Coding Challenge',
      description: 'Evaluating coding skills',
      icon: FaCode,
      timestamp: '',
    },
    {
      id: 'behavioral_questions',
      title: 'Behavioral Questions',
      description: 'Exploring soft skills and experience',
      icon: FaLightbulb,
      timestamp: '',
    },
    {
      id: 'feedback',
      title: 'Feedback',
      description: 'Providing evaluation and insights',
      icon: FaChartBar,
      timestamp: '',
    },
    {
      id: 'conclusion',
      title: 'Conclusion',
      description: 'Wrapping up the interview',
      icon: FaCheck,
      timestamp: '',
    },
  ];

  // Use provided events or default stages
  const timelineItems = events.length > 0 ? events : defaultStages;

  // Determine if a stage is completed, active, or pending
  const getStageStatus = (stageId) => {
    if (!currentStage) return 'pending';
    
    const stageOrder = defaultStages.map(stage => stage.id);
    const currentIndex = stageOrder.indexOf(currentStage);
    const stageIndex = stageOrder.indexOf(stageId);
    
    if (currentIndex === -1 || stageIndex === -1) return 'pending';
    
    if (stageIndex < currentIndex) return 'completed';
    if (stageIndex === currentIndex) return 'active';
    return 'pending';
  };

  return (
    <Box
      bg={bgColor}
      borderRadius="lg"
      borderWidth="1px"
      borderColor={borderColor}
      p={4}
      boxShadow="sm"
      width="100%"
    >
      {title && (
        <Heading size="md" mb={4} textAlign="center" color={textColor}>
          {title}
        </Heading>
      )}

      <VStack spacing={0} align="stretch">
        {timelineItems.map((item, index) => {
          const status = getStageStatus(item.id);
          const isCompleted = status === 'completed';
          const isActive = status === 'active';
          
          // Determine colors based on status
          const circleColor = isCompleted ? completedColor : isActive ? accentColor : pendingColor;
          const iconColor = isCompleted || isActive ? 'white' : 'gray.500';
          const itemTextColor = isActive ? accentColor : isCompleted ? textColor : secondaryTextColor;
          
          return (
            <React.Fragment key={item.id || index}>
              <HStack spacing={4} py={3}>
                {/* Timeline node */}
                <Flex direction="column" align="center">
                  <Circle size="40px" bg={circleColor} color="white">
                    <Icon as={item.icon} color={iconColor} />
                  </Circle>
                  {index < timelineItems.length - 1 && (
                    <Box
                      height="30px"
                      width="2px"
                      bg={isCompleted ? completedColor : pendingColor}
                      mt={2}
                    />
                  )}
                </Flex>
                
                {/* Content */}
                <Box>
                  <HStack>
                    <Text fontWeight="bold" color={itemTextColor}>
                      {item.title}
                    </Text>
                    {item.timestamp && (
                      <Text fontSize="sm" color={secondaryTextColor}>
                        {item.timestamp}
                      </Text>
                    )}
                  </HStack>
                  <Text color={secondaryTextColor} fontSize="sm">
                    {item.description}
                  </Text>
                </Box>
              </HStack>
            </React.Fragment>
          );
        })}
      </VStack>
    </Box>
  );
};

export default InterviewTimeline; 