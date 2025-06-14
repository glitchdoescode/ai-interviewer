import React, { useState, useEffect } from 'react';
import {
  Box,
  Heading,
  Text,
  VStack,
  HStack,
  Grid,
  GridItem,
  Button,
  useColorModeValue,
  Flex,
  Divider,
  Spinner,
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription,
  useToast,
} from '@chakra-ui/react';
import { FaDownload, FaPrint } from 'react-icons/fa';

// Import visualization components
import ScoreChart from './ScoreChart';
import ProgressIndicator from './ProgressIndicator';
import DetailedEvaluationTable from './DetailedEvaluationTable';
import InterviewTimeline from './InterviewTimeline';

/**
 * DetailedReport component that combines all visualization components
 * to create a comprehensive interview report
 */
const DetailedReport = ({
  sessionId,
  candidateName = '',
  jobRole = '',
  reportData = null,
  isLoading = false,
  error = null,
  onPrint = () => {},
  onDownload = () => {},
}) => {
  const bgColor = useColorModeValue('gray.50', 'gray.900');
  const cardBgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');
  const textColor = useColorModeValue('gray.800', 'gray.100');
  const secondaryTextColor = useColorModeValue('gray.600', 'gray.400');
  const toast = useToast();

  // Extract data from reportData
  const {
    summary_statistics = {},
    evaluation_data = {},
    interview_data = {},
    timestamp = new Date().toISOString(),
  } = reportData || {};

  // If the data is in a different format, try to normalize it
  const evaluation = evaluation_data || reportData?.evaluation || {};
  const interviewData = interview_data || reportData?.interview_data || {};
  
  // Ensure summary_statistics has default values
  const safeStats = {
    overall_average: 0,
    qa_average: 0,
    coding_average: 0,
    total_questions: 0,
    questions_answered: 0,
    coding_completed: false,
    trust_score: 0,
    ...summary_statistics
  };

  // Format date for display
  const formattedDate = React.useMemo(() => {
    if (!timestamp) return '';
    try {
      return new Date(timestamp).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch (e) {
      return '';
    }
  }, [timestamp]);

  // Handle print action
  const handlePrint = () => {
    onPrint();
    toast({
      title: 'Preparing print view',
      description: 'The print dialog will open shortly.',
      status: 'info',
      duration: 3000,
      isClosable: true,
    });
  };

  // Handle download action
  const handleDownload = () => {
    onDownload();
    toast({
      title: 'Downloading report',
      description: 'Your report will be downloaded as a PDF.',
      status: 'success',
      duration: 3000,
      isClosable: true,
    });
  };

  // If loading, show spinner
  if (isLoading) {
    return (
      <Flex justify="center" align="center" minH="400px" direction="column">
        <Spinner size="xl" color="blue.500" thickness="4px" speed="0.65s" />
        <Text mt={4} color={textColor}>Loading report data...</Text>
      </Flex>
    );
  }

  // If error, show alert
  if (error) {
    return (
      <Alert
        status="error"
        variant="subtle"
        flexDirection="column"
        alignItems="center"
        justifyContent="center"
        textAlign="center"
        height="400px"
        borderRadius="lg"
      >
        <AlertIcon boxSize="40px" mr={0} />
        <AlertTitle mt={4} mb={1} fontSize="lg">
          Error Loading Report
        </AlertTitle>
        <AlertDescription maxWidth="sm">
          {error.message || 'An error occurred while loading the report data. Please try again.'}
        </AlertDescription>
        <Button mt={4} colorScheme="red" onClick={() => window.location.reload()}>
          Retry
        </Button>
      </Alert>
    );
  }

  // If no data, show message
  if (!reportData) {
    return (
      <Alert
        status="info"
        variant="subtle"
        flexDirection="column"
        alignItems="center"
        justifyContent="center"
        textAlign="center"
        height="400px"
        borderRadius="lg"
      >
        <AlertIcon boxSize="40px" mr={0} />
        <AlertTitle mt={4} mb={1} fontSize="lg">
          No Report Data Available
        </AlertTitle>
        <AlertDescription maxWidth="sm">
          There is no report data available for this interview session.
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <Box bg={bgColor} p={4} borderRadius="lg" width="100%">
      {/* Report Header */}
      <Box
        bg={cardBgColor}
        borderRadius="lg"
        borderWidth="1px"
        borderColor={borderColor}
        p={6}
        mb={6}
        boxShadow="sm"
      >
        <Flex justify="space-between" align="center" wrap="wrap">
          <VStack align="flex-start" spacing={1}>
            <Heading size="lg" color={textColor}>
              Interview Report
            </Heading>
            <Text color={secondaryTextColor}>
              {candidateName ? `Candidate: ${candidateName}` : 'Candidate Report'}
            </Text>
            <Text color={secondaryTextColor}>
              {jobRole ? `Position: ${jobRole}` : 'Interview Assessment'}
            </Text>
            <Text fontSize="sm" color={secondaryTextColor}>
              {formattedDate}
            </Text>
          </VStack>
          
          <HStack spacing={4}>
            <Button
              leftIcon={<FaPrint />}
              colorScheme="blue"
              variant="outline"
              onClick={handlePrint}
            >
              Print
            </Button>
            <Button
              leftIcon={<FaDownload />}
              colorScheme="blue"
              onClick={handleDownload}
            >
              Download PDF
            </Button>
          </HStack>
        </Flex>
      </Box>

      {/* Score Summary and Progress */}
      <Grid
        templateColumns={{ base: "1fr", md: "repeat(2, 1fr)" }}
        gap={6}
        mb={6}
      >
        <GridItem>
          <ScoreChart 
            data={safeStats} 
            title="Performance Scores" 
            type="bar"
          />
        </GridItem>
        <GridItem>
          <ProgressIndicator 
            data={{
              overall_progress: safeStats.overall_average / 5,
              qa_progress: safeStats.qa_average / 5,
              coding_progress: safeStats.coding_average / 5,
              total_questions: safeStats.total_questions,
              questions_answered: safeStats.questions_answered,
              coding_completed: safeStats.coding_completed,
              trust_score: safeStats.trust_score,
            }}
            title="Interview Completion"
          />
        </GridItem>
      </Grid>

      {/* Detailed Evaluation and Timeline */}
      <Grid
        templateColumns={{ base: "1fr", lg: "3fr 1fr" }}
        gap={6}
        mb={6}
      >
        <GridItem>
          <DetailedEvaluationTable 
            evaluation={evaluation} 
            title="Detailed Evaluation"
          />
        </GridItem>
        <GridItem>
          <InterviewTimeline 
            title="Interview Stages" 
            currentStage={evaluation?.current_stage || 'conclusion'}
          />
        </GridItem>
      </Grid>

      {/* Footer */}
      <Box
        bg={cardBgColor}
        borderRadius="lg"
        borderWidth="1px"
        borderColor={borderColor}
        p={4}
        textAlign="center"
      >
        <Text fontSize="sm" color={secondaryTextColor}>
          This report was generated by AI Interviewer. Session ID: {sessionId}
        </Text>
        <Text fontSize="xs" color={secondaryTextColor} mt={1}>
          Trust Score: {safeStats.trust_score?.toFixed(2) || 'N/A'} | 
          Generated on {formattedDate}
        </Text>
      </Box>
    </Box>
  );
};

export default DetailedReport; 