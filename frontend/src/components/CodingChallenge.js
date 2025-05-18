import React, { useState, useEffect } from 'react';
import {
  Box,
  Button,
  Text,
  Heading,
  VStack,
  HStack,
  Badge,
  Divider,
  useToast,
  Alert,
  AlertIcon,
  Tabs,
  TabList,
  TabPanels,
  Tab,
  TabPanel,
  Accordion,
  AccordionItem,
  AccordionButton,
  AccordionPanel,
  AccordionIcon,
} from '@chakra-ui/react';
import { FaPlay, FaCheck, FaTimes, FaPauseCircle, FaCode } from 'react-icons/fa';
import CodeEditor from './CodeEditor';
import { useInterview } from '../context/InterviewContext';
import { submitChallengeCode } from '../api/interviewService';
import { useConfig } from '../context/ConfigContext';

/**
 * CodingChallenge component for handling coding challenge interactions
 * 
 * @param {Object} props Component props
 * @param {Object} props.challenge Challenge data (title, description, etc.)
 * @param {Function} props.onComplete Callback when challenge is completed
 * @param {Function} props.onRequestHint Callback to request a hint
 */
const CodingChallenge = ({ challenge, onComplete, onRequestHint }) => {
  const [code, setCode] = useState(challenge?.starter_code || '');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [testResults, setTestResults] = useState(null);
  const [feedback, setFeedback] = useState(null);
  const [isWaitingForUser, setIsWaitingForUser] = useState(true);
  const toast = useToast();
  
  const { setInterviewStage } = useInterview();
  const { systemName } = useConfig();
  
  // Set the interview stage to coding challenge
  useEffect(() => {
    setInterviewStage('coding_challenge');
  }, [setInterviewStage]);
  
  // Run test cases locally for immediate feedback
  const runTests = async () => {
    // For now, just inform the user this is a local test
    toast({
      title: 'Running Tests',
      description: 'Tests are running locally. This does not submit your solution.',
      status: 'info',
      duration: 3000,
      isClosable: true,
    });
    
    // This would be expanded to actually run tests in the future
  };
  
  // Submit the solution to the AI for evaluation
  const handleSubmit = async () => {
    if (!code.trim()) {
      toast({
        title: 'Empty Solution',
        description: 'Please write some code before submitting.',
        status: 'warning',
        duration: 3000,
        isClosable: true,
      });
      return;
    }
    
    try {
      setIsSubmitting(true);
      
      // Submit the code to the API
      const result = await submitChallengeCode(challenge.challenge_id, code);
      
      setTestResults(result.execution_results);
      setFeedback(result.feedback);
      
      // If the challenge is passed, call the onComplete callback
      if (result.evaluation?.passed) {
        onComplete && onComplete(result);
      }
      
      // Show toast notification with result
      toast({
        title: result.evaluation?.passed ? 'Challenge Passed!' : 'Submission Received',
        description: result.evaluation?.passed 
          ? 'Great job! Your solution passed all test cases.' 
          : 'Your solution has been evaluated. Check the feedback for details.',
        status: result.evaluation?.passed ? 'success' : 'info',
        duration: 5000,
        isClosable: true,
      });
    } catch (error) {
      console.error('Error submitting code:', error);
      toast({
        title: 'Submission Error',
        description: 'There was an error submitting your code. Please try again.',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setIsSubmitting(false);
    }
  };
  
  // Request a hint from the AI
  const handleRequestHint = () => {
    onRequestHint && onRequestHint(code);
  };
  
  // Toggle between AI and user mode
  const toggleWaitingState = () => {
    setIsWaitingForUser(!isWaitingForUser);
    
    toast({
      title: isWaitingForUser ? 'Resuming Interview' : 'Paused for Coding',
      description: isWaitingForUser 
        ? `Returning control to the ${systemName}.` 
        : 'Take your time to solve the challenge. The AI will wait.',
      status: 'info',
      duration: 3000,
      isClosable: true,
    });
  };
  
  // If no challenge is provided, show a placeholder
  if (!challenge) {
    return (
      <Box p={4} borderRadius="md" borderWidth="1px">
        <Alert status="warning">
          <AlertIcon />
          No coding challenge data available.
        </Alert>
      </Box>
    );
  }
  
  return (
    <Box 
      borderWidth="1px" 
      borderRadius="lg" 
      overflow="hidden" 
      bg="white"
      boxShadow="md"
    >
      {/* Challenge Header */}
      <Box bg="brand.50" p={4} borderBottomWidth="1px">
        <HStack justifyContent="space-between" mb={2}>
          <Heading size="md">{challenge.title}</Heading>
          <HStack>
            <Badge colorScheme={challenge.difficulty === 'easy' ? 'green' : challenge.difficulty === 'medium' ? 'orange' : 'red'}>
              {challenge.difficulty.toUpperCase()}
            </Badge>
            <Badge colorScheme="blue">{challenge.language}</Badge>
            <Badge colorScheme="purple">{challenge.time_limit_mins} min</Badge>
          </HStack>
        </HStack>
        
        {/* Waiting Status */}
        <Alert status={isWaitingForUser ? 'success' : 'warning'} mb={2} size="sm">
          <AlertIcon />
          {isWaitingForUser 
            ? 'The AI is waiting for you to solve this challenge.' 
            : 'The AI is currently engaged. Click "Pause for Coding" to take your time.'}
        </Alert>
        
        {/* Toggle Button */}
        <Button
          size="sm"
          colorScheme={isWaitingForUser ? 'blue' : 'orange'}
          leftIcon={isWaitingForUser ? <FaPlay /> : <FaPauseCircle />}
          onClick={toggleWaitingState}
          mb={2}
        >
          {isWaitingForUser ? 'Resume Interview' : 'Pause for Coding'}
        </Button>
      </Box>
      
      {/* Challenge Content */}
      <Tabs isFitted variant="enclosed">
        <TabList>
          <Tab>Challenge</Tab>
          <Tab>Code Editor</Tab>
          {testResults && <Tab>Results</Tab>}
        </TabList>
        
        <TabPanels>
          {/* Challenge Description Tab */}
          <TabPanel>
            <VStack align="stretch" spacing={4}>
              <Box>
                <Heading size="sm" mb={2}>Problem Description</Heading>
                <Text whiteSpace="pre-wrap">{challenge.description}</Text>
              </Box>
              
              <Divider />
              
              {/* Test Cases */}
              <Box>
                <Heading size="sm" mb={2}>Example Test Cases</Heading>
                <Accordion allowMultiple>
                  {challenge.visible_test_cases.map((testCase, index) => (
                    <AccordionItem key={index}>
                      <h2>
                        <AccordionButton>
                          <Box flex="1" textAlign="left">
                            Test Case {index + 1}
                          </Box>
                          <AccordionIcon />
                        </AccordionButton>
                      </h2>
                      <AccordionPanel pb={4}>
                        <VStack align="stretch" spacing={2}>
                          <Box>
                            <Text fontWeight="bold">Input:</Text>
                            <Box bg="gray.100" p={2} borderRadius="md">
                              <Text fontFamily="monospace">{JSON.stringify(testCase.input)}</Text>
                            </Box>
                          </Box>
                          <Box>
                            <Text fontWeight="bold">Expected Output:</Text>
                            <Box bg="gray.100" p={2} borderRadius="md">
                              <Text fontFamily="monospace">{JSON.stringify(testCase.expected_output)}</Text>
                            </Box>
                          </Box>
                          {testCase.explanation && (
                            <Box>
                              <Text fontWeight="bold">Explanation:</Text>
                              <Text>{testCase.explanation}</Text>
                            </Box>
                          )}
                        </VStack>
                      </AccordionPanel>
                    </AccordionItem>
                  ))}
                </Accordion>
              </Box>
              
              <Divider />
              
              {/* Evaluation Criteria */}
              <Box>
                <Heading size="sm" mb={2}>Evaluation Criteria</Heading>
                <VStack align="stretch">
                  {Object.entries(challenge.evaluation_criteria).map(([key, value]) => (
                    <HStack key={key}>
                      <Badge colorScheme="blue">{key}</Badge>
                      <Text>{value}</Text>
                    </HStack>
                  ))}
                </VStack>
              </Box>
            </VStack>
          </TabPanel>
          
          {/* Code Editor Tab */}
          <TabPanel>
            <VStack align="stretch" spacing={4}>
              <CodeEditor
                code={code}
                language={challenge.language.toLowerCase()}
                onChange={setCode}
              />
              
              <HStack spacing={4} justify="flex-end">
                <Button
                  leftIcon={<FaPlay />}
                  colorScheme="blue"
                  variant="outline"
                  onClick={runTests}
                >
                  Run Tests
                </Button>
                <Button
                  leftIcon={<FaCode />}
                  colorScheme="purple"
                  variant="outline"
                  onClick={handleRequestHint}
                >
                  Request Hint
                </Button>
                <Button
                  leftIcon={<FaCheck />}
                  colorScheme="green"
                  isLoading={isSubmitting}
                  onClick={handleSubmit}
                >
                  Submit Solution
                </Button>
              </HStack>
            </VStack>
          </TabPanel>
          
          {/* Results Tab */}
          {testResults && (
            <TabPanel>
              <VStack align="stretch" spacing={4}>
                {/* Overall Results */}
                <Box>
                  <Heading size="sm" mb={2}>Overall Results</Heading>
                  <Alert
                    status={testResults.all_passed ? 'success' : 'warning'}
                    borderRadius="md"
                  >
                    <AlertIcon />
                    {testResults.all_passed
                      ? 'All test cases passed!'
                      : `${testResults.passed_count || 0} out of ${testResults.test_cases?.length || 0} test cases passed.`}
                  </Alert>
                </Box>
                
                {/* Test Case Results */}
                {testResults.test_cases && (
                  <Box>
                    <Heading size="sm" mb={2}>Test Case Results</Heading>
                    <VStack align="stretch" spacing={2}>
                      {testResults.test_cases.map((testCase, index) => (
                        <Box
                          key={index}
                          p={3}
                          borderRadius="md"
                          borderWidth="1px"
                          borderColor={testCase.passed ? 'green.200' : 'red.200'}
                          bg={testCase.passed ? 'green.50' : 'red.50'}
                        >
                          <HStack justify="space-between" mb={1}>
                            <Text fontWeight="bold">Test Case {index + 1}</Text>
                            {testCase.passed ? (
                              <Badge colorScheme="green">Passed</Badge>
                            ) : (
                              <Badge colorScheme="red">Failed</Badge>
                            )}
                          </HStack>
                          
                          {!testCase.passed && testCase.error && (
                            <Box mt={2}>
                              <Text fontWeight="bold" color="red.500">Error:</Text>
                              <Box bg="red.100" p={2} borderRadius="md" mt={1}>
                                <Text fontFamily="monospace" fontSize="sm">
                                  {testCase.error}
                                </Text>
                              </Box>
                            </Box>
                          )}
                          
                          {!testCase.passed && testCase.actual_output !== undefined && (
                            <Box mt={2}>
                              <Text fontWeight="bold">Your Output:</Text>
                              <Box bg="gray.100" p={2} borderRadius="md" mt={1}>
                                <Text fontFamily="monospace" fontSize="sm">
                                  {JSON.stringify(testCase.actual_output)}
                                </Text>
                              </Box>
                            </Box>
                          )}
                        </Box>
                      ))}
                    </VStack>
                  </Box>
                )}
                
                {/* Feedback */}
                {feedback && (
                  <Box>
                    <Heading size="sm" mb={2}>Feedback</Heading>
                    <VStack align="stretch" spacing={3}>
                      <Box>
                        <Text fontWeight="bold">Summary:</Text>
                        <Text>{feedback.summary}</Text>
                      </Box>
                      
                      {feedback.strengths && feedback.strengths.length > 0 && (
                        <Box>
                          <Text fontWeight="bold">Strengths:</Text>
                          <VStack align="stretch" spacing={1} pl={4}>
                            {feedback.strengths.map((strength, i) => (
                              <Text key={i}>• {strength}</Text>
                            ))}
                          </VStack>
                        </Box>
                      )}
                      
                      {feedback.areas_for_improvement && feedback.areas_for_improvement.length > 0 && (
                        <Box>
                          <Text fontWeight="bold">Areas for Improvement:</Text>
                          <VStack align="stretch" spacing={1} pl={4}>
                            {feedback.areas_for_improvement.map((area, i) => (
                              <Text key={i}>• {area}</Text>
                            ))}
                          </VStack>
                        </Box>
                      )}
                      
                      {feedback.suggestions && feedback.suggestions.length > 0 && (
                        <Box>
                          <Text fontWeight="bold">Suggestions:</Text>
                          <VStack align="stretch" spacing={1} pl={4}>
                            {feedback.suggestions.map((suggestion, i) => (
                              <Text key={i}>• {suggestion}</Text>
                            ))}
                          </VStack>
                        </Box>
                      )}
                    </VStack>
                  </Box>
                )}
              </VStack>
            </TabPanel>
          )}
        </TabPanels>
      </Tabs>
    </Box>
  );
};

export default CodingChallenge; 