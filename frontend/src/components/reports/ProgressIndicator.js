import React from 'react';
import {
  Box,
  Heading,
  Text,
  CircularProgress,
  CircularProgressLabel,
  Stack,
  Flex,
  useColorModeValue,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText,
  StatGroup,
} from '@chakra-ui/react';

/**
 * ProgressIndicator component for displaying interview completion metrics
 * Shows circular progress indicators and stats for different interview aspects
 */
const ProgressIndicator = ({
  title = 'Interview Progress',
  data = {},
  showStats = true,
}) => {
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');
  const textColor = useColorModeValue('gray.800', 'gray.100');
  const secondaryTextColor = useColorModeValue('gray.600', 'gray.400');

  // Extract progress values with defaults
  const {
    overall_progress = 0,
    qa_progress = 0,
    coding_progress = 0,
    total_questions = 0,
    questions_answered = 0,
    coding_completed = false,
    trust_score = 0,
  } = data;

  // Format trust score as percentage
  const trustScorePercent = Math.round((trust_score || 0) * 100);

  // Calculate overall completion percentage
  const overallPercent = Math.round(overall_progress * 100);
  const qaPercent = Math.round(qa_progress * 100);
  const codingPercent = coding_completed ? 100 : Math.round(coding_progress * 100);

  // Color mapping based on percentage
  const getColorScheme = (percent) => {
    if (percent >= 80) return 'green';
    if (percent >= 50) return 'blue';
    if (percent >= 30) return 'yellow';
    return 'red';
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

      {/* Progress Indicators */}
      <Flex justify="space-around" align="center" wrap="wrap" mb={showStats ? 6 : 0}>
        <Box textAlign="center" p={2}>
          <CircularProgress
            value={overallPercent}
            size="120px"
            thickness="8px"
            color={getColorScheme(overallPercent)}
          >
            <CircularProgressLabel>{`${overallPercent}%`}</CircularProgressLabel>
          </CircularProgress>
          <Text mt={2} color={textColor} fontWeight="medium">
            Overall
          </Text>
        </Box>

        <Box textAlign="center" p={2}>
          <CircularProgress
            value={qaPercent}
            size="120px"
            thickness="8px"
            color={getColorScheme(qaPercent)}
          >
            <CircularProgressLabel>{`${qaPercent}%`}</CircularProgressLabel>
          </CircularProgress>
          <Text mt={2} color={textColor} fontWeight="medium">
            Q&A
          </Text>
        </Box>

        <Box textAlign="center" p={2}>
          <CircularProgress
            value={codingPercent}
            size="120px"
            thickness="8px"
            color={getColorScheme(codingPercent)}
          >
            <CircularProgressLabel>{`${codingPercent}%`}</CircularProgressLabel>
          </CircularProgress>
          <Text mt={2} color={textColor} fontWeight="medium">
            Coding
          </Text>
        </Box>

        <Box textAlign="center" p={2}>
          <CircularProgress
            value={trustScorePercent}
            size="120px"
            thickness="8px"
            color={getColorScheme(trustScorePercent)}
          >
            <CircularProgressLabel>{`${trustScorePercent}%`}</CircularProgressLabel>
          </CircularProgress>
          <Text mt={2} color={textColor} fontWeight="medium">
            Trust Score
          </Text>
        </Box>
      </Flex>

      {/* Stats */}
      {showStats && (
        <StatGroup>
          <Stat>
            <StatLabel color={secondaryTextColor}>Questions</StatLabel>
            <StatNumber color={textColor}>{questions_answered || 0}</StatNumber>
            <StatHelpText color={secondaryTextColor}>
              of {total_questions || 0} total
            </StatHelpText>
          </Stat>

          <Stat>
            <StatLabel color={secondaryTextColor}>Coding Challenge</StatLabel>
            <StatNumber color={textColor}>
              {coding_completed ? 'Completed' : 'In Progress'}
            </StatNumber>
            <StatHelpText color={secondaryTextColor}>
              {coding_completed ? '100%' : `${codingPercent}% complete`}
            </StatHelpText>
          </Stat>

          <Stat>
            <StatLabel color={secondaryTextColor}>Trust Score</StatLabel>
            <StatNumber color={textColor}>{(trust_score || 0).toFixed(2)}</StatNumber>
            <StatHelpText color={secondaryTextColor}>out of 1.0</StatHelpText>
          </Stat>
        </StatGroup>
      )}
    </Box>
  );
};

export default ProgressIndicator; 