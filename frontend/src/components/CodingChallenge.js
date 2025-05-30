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
  Select,
  Textarea,
} from '@chakra-ui/react';
import { FaPlay, FaCheck, FaTimes, FaPauseCircle, FaCode, FaRedo } from 'react-icons/fa';
import CodeEditor from './CodeEditor';
import { useInterview } from '../context/InterviewContext';
// import { submitChallengeCode } from '../api/interviewService'; // Comment out for Sprint 1

/**
 * CodingChallenge component for handling coding challenge interactions
 * 
 * @param {Object} props Component props
 * @param {Object} props.challenge Challenge data (title, description, etc.)
 * @param {Function} props.onComplete Callback when challenge is completed
 * @param {Function} props.onRequestHint Callback to request a hint
 * @param {string} props.sessionId Session ID
 * @param {string} props.userId User ID
 */
const CodingChallenge = ({ challenge: initialChallenge, onComplete, onRequestHint, sessionId, userId }) => {
  const [challenge, setChallenge] = useState(initialChallenge);
  const [code, setCode] = useState(initialChallenge?.starter_code || '');
  const [language, setLanguage] = useState(initialChallenge?.language || 'python');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [testResults, setTestResults] = useState(null);
  const [feedback, setFeedback] = useState(null);
  const [isWaitingForUser, setIsWaitingForUser] = useState(true);
  const toast = useToast();
  
  // New state for Run Code functionality
  const [stdin, setStdin] = useState('');
  const [stdout, setStdout] = useState('');
  const [stderr, setStderr] = useState('');
  const [isRunningCode, setIsRunningCode] = useState(false);
  
  const { setInterviewStage, jobDetails } = useInterview();
  
  // Function to fetch a new coding challenge
  const fetchNewChallenge = async () => {
    toast({
      title: 'Fetching New Challenge...',
      status: 'info',
      duration: null, // Keep open until closed manually or by success/error
      isClosable: true,
    });
    try {
      const authToken = localStorage.getItem('authToken');
      if (!authToken) {
        toast({
          title: 'Authentication Error',
          description: 'Auth token not found. Please log in.',
          status: 'error',
          duration: 5000,
          isClosable: true,
        });
        return;
      }

      // TODO: Get these from a more robust source, e.g., job context or props
      const body = {
        job_description: jobDetails?.job_description || "A general software engineering role.",
        skills_required: jobDetails?.required_skills || ["Python", "problem-solving"],
        difficulty_level: jobDetails?.difficulty || "intermediate", // Or derive from seniority
        session_id: sessionId, // Pass session ID for context
      };
      
      // NOTE: The backend currently expects the AI to call generate_coding_challenge_from_jd.
      // This frontend-initiated call is a temporary measure for Sprint 2 testing.
      // We might need a dedicated endpoint or adjust the AI's flow.
      // For now, let's assume an endpoint /api/interview/generate-challenge exists or will be created.
      const response = await fetch('/api/interview/generate-challenge', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`,
        },
        body: JSON.stringify(body),
      });

      const data = await response.json();
      toast.closeAll(); // Close the "Fetching..." toast

      if (!response.ok) {
        throw new Error(data.detail || 'Failed to fetch challenge');
      }

      // The backend's generate_coding_challenge_from_jd tool returns:
      // problem_statement, starter_code, language, title
      setChallenge({
        title: data.title,
        description: data.problem_statement, // Ensure your component uses 'description' for problem_statement
        difficulty: data.difficulty_level || body.difficulty_level, // Or from response if provided
        language: data.language,
        time_limit_mins: 30, // Placeholder
        starter_code: data.starter_code,
        // challenge_id: data.challenge_id // if your backend provides one
      });
      setCode(data.starter_code || '');
      setLanguage(data.language || 'python');
      setTestResults(null);
      setFeedback(null);
      toast({
        title: 'New Challenge Loaded',
        description: data.title,
        status: 'success',
        duration: 5000,
        isClosable: true,
      });
    } catch (error) {
      toast.closeAll(); // Close the "Fetching..." toast
      console.error('Error fetching new challenge:', error);
      toast({
        title: 'Error Fetching Challenge',
        description: error.message || 'Could not connect to the server.',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    }
  };

  // Fetch challenge when component mounts if no initial challenge is provided
  useEffect(() => {
    if (!initialChallenge) {
      fetchNewChallenge();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialChallenge]); // Only re-run if initialChallenge changes

  // Set the interview stage to coding challenge
  useEffect(() => {
    setInterviewStage('coding_challenge');
  }, [setInterviewStage]);
  
  const handleRunCode = async () => {
    if (!code.trim()) {
      toast({
        title: 'Empty Code',
        description: 'Please write some code before running.',
        status: 'warning',
        duration: 3000,
        isClosable: true,
      });
      return;
    }

    setIsRunningCode(true);
    setStdout('');
    setStderr('');
    toast({
      title: 'Running Code...',
      status: 'info',
      duration: null,
      isClosable: false,
    });

    const authToken = localStorage.getItem('authToken');
    if (!authToken) {
      toast.closeAll();
      toast({
        title: 'Authentication Error',
        description: 'Auth token not found. Please log in.',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
      setIsRunningCode(false);
      return;
    }

    try {
      const response = await fetch('/api/coding/run', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`,
        },
        body: JSON.stringify({
          language: language,
          code: code,
          input_str: stdin,
          session_id: sessionId, // Optional: for logging or context on backend
        }),
      });

      toast.closeAll();
      const result = await response.json();

      if (!response.ok) {
        throw new Error(result.detail || `Server error: ${response.status}`);
      }

      setStdout(result.stdout);
      setStderr(result.stderr);

      if (result.status === 'success') {
        toast({
          title: 'Execution Successful',
          status: 'success',
          duration: 3000,
          isClosable: true,
        });
      } else {
        toast({
          title: 'Execution Finished with Errors',
          description: result.stderr ? 'Check the STDERR output for details.' : 'An unknown error occurred.',
          status: 'error',
          duration: 5000,
          isClosable: true,
        });
      }
    } catch (error) {
      toast.closeAll();
      console.error('Error running code:', error);
      toast({
        title: 'Error Running Code',
        description: error.message || 'Could not connect to the server.',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
      setStderr(error.message || 'An unexpected error occurred.');
    } finally {
      setIsRunningCode(false);
    }
  };

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
    
    // SPRINT 1: Submit to the logging endpoint
    setIsSubmitting(true);
    console.log('CodingChallenge: Submitting code for Sprint 1:', { challenge_id: challenge?.challenge_id || challenge?.title, language, code, sessionId, userId });

    const authToken = localStorage.getItem('authToken'); // Or get from AuthContext
    if (!authToken) {
      toast({
        title: 'Authentication Error',
        description: 'Auth token not found. Please log in.',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
      setIsSubmitting(false);
      return;
    }

    try {
      const response = await fetch('/api/coding/submit', { // Ensure API prefix is correct (e.g. /api/v1)
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify({
          challenge_id: challenge?.challenge_id || challenge?.title || "default_challenge_id", // Use challenge.challenge_id if available
          language: language,
          code: code,
          user_id: userId,
          session_id: sessionId
        }),
      });

      const result = await response.json();

      if (!response.ok) {
        console.error('Sprint 1 Submission Error:', response.status, result);
        toast({
          title: 'Submission Failed (Sprint 1)',
          description: result.detail || `Server responded with ${response.status}`,
          status: 'error',
          duration: 5000,
          isClosable: true,
        });
        setTestResults({ error: result.detail || `Server error ${response.status}` });
        setFeedback(null);
      } else {
        console.log('Sprint 1 Submission Response:', result);
        toast({
          title: 'Submission Logged (Sprint 1)',
          description: `Status: ${result.status}`,
          status: 'info',
          duration: 5000,
          isClosable: true,
        });
        // For Sprint 1, display a simple message in testResults and feedback
        setTestResults({ message: result.execution_results?.message || 'Logged, no execution.' });
        setFeedback({ message: result.feedback?.message || 'No specific feedback for Sprint 1.'});
        // Optionally call onComplete if you want to signify the end of this interaction for Sprint 1
        // if (onComplete) onComplete(result); 
      }
    } catch (error) {
      console.error('Error submitting code (Sprint 1):', error);
      toast({
        title: 'Network Error (Sprint 1)',
        description: 'Could not connect to the server. Please try again.',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
      setTestResults({ error: 'Network error during submission.' });
      setFeedback(null);
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
        ? 'Returning control to the AI interviewer.' 
        : 'Take your time to solve the challenge. The AI will wait.',
      status: 'info',
      duration: 3000,
      isClosable: true,
    });
  };
  
  // If no challenge is provided, show a placeholder and a button to fetch one
  if (!challenge) {
    return (
      <Box p={4} borderRadius="md" borderWidth="1px">
        <VStack spacing={4}>
          <Alert status="warning">
            <AlertIcon />
            No coding challenge data available.
          </Alert>
          <Button onClick={fetchNewChallenge} colorScheme="blue" leftIcon={<FaRedo />}>
            Load New Coding Challenge
          </Button>
        </VStack>
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
            <Button size="sm" onClick={fetchNewChallenge} leftIcon={<FaRedo />} colorScheme="gray" variant="outline" mr={2}>
              New Challenge
            </Button>
            <Badge colorScheme={challenge.difficulty_level === 'easy' ? 'green' : challenge.difficulty_level === 'medium' ? 'orange' : 'red'}>
              {challenge.difficulty_level?.toUpperCase() || challenge.difficulty?.toUpperCase() || 'N/A'}
            </Badge>
            <Badge colorScheme="blue">{challenge.language?.toUpperCase() || 'N/A'}</Badge>
            <Badge colorScheme="purple">{challenge.time_limit_mins || 'N/A'} min</Badge>
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
          {/* For Sprint 1, testResults might just be a simple message object */}
          {testResults && <Tab>Results</Tab>}
        </TabList>
        
        <TabPanels>
          {/* Challenge Description Tab */}
          <TabPanel>
            <VStack align="stretch" spacing={4}>
              <Box>
                <Heading size="sm" mb={2}>Problem Description</Heading>
                <Text whiteSpace="pre-wrap">{challenge.problem_statement || challenge.description}</Text>
              </Box>
              
              <Divider />
              
              {/* Test Cases */}
              <Box>
                <Heading size="sm" mb={2}>Example Test Cases</Heading>
                <Accordion allowMultiple>
                  {challenge.test_cases && challenge.test_cases.length > 0 ? (
                    challenge.test_cases.map((testCase, index) => (
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
                    ))
                  ) : (
                    <Text>No visible test cases provided.</Text>
                  )}
                </Accordion>
              </Box>
              
              <Divider />
              
              {/* Evaluation Criteria */}
              <Box>
                <Heading size="sm" mb={2}>Evaluation Criteria</Heading>
                <VStack align="stretch">
                  {challenge.evaluation_criteria && Object.keys(challenge.evaluation_criteria).length > 0 ? (
                    Object.entries(challenge.evaluation_criteria).map(([key, value]) => (
                      <HStack key={key}>
                        <Badge colorScheme="blue">{key}</Badge>
                        <Text>{value}</Text>
                      </HStack>
                    ))
                  ) : (
                    <Text>No evaluation criteria provided.</Text>
                  )}
                </VStack>
              </Box>
            </VStack>
          </TabPanel>
          
          {/* Code Editor Tab */}
          <TabPanel>
            <VStack align="stretch" spacing={4}>
              <Select value={language} onChange={(e) => setLanguage(e.target.value)} mb={2} focusBorderColor="primary.500">
                <option value="python">Python</option>
                <option value="javascript">JavaScript</option>
                <option value="java">Java</option>
                {/* Add more languages as needed */}
              </Select>
              <CodeEditor
                code={code}
                language={language.toLowerCase()}
                onChange={setCode}
              />
              
              {/* Input, Output, and Run Button Area Added/Modified for Sprint 3 */}
              <VStack spacing={3} align="stretch" mt={4}>
                <Text fontWeight="bold">Standard Input (stdin):</Text>
                <Textarea
                  placeholder="Enter input for your code here (optional)"
                  value={stdin}
                  onChange={(e) => setStdin(e.target.value)}
                  fontFamily="monospace"
                  bg="white"
                  isDisabled={isRunningCode || isSubmitting}
                  rows={3}
                />
                <HStack spacing={4} justify="flex-end" width="100%">
                  <Button
                    leftIcon={<FaPlay />}
                    colorScheme="teal"
                    onClick={handleRunCode}
                    isLoading={isRunningCode}
                    loadingText="Running..."
                    isDisabled={isSubmitting || !code.trim()} // Disable if submitting or code is empty
                  >
                    Run Code
                  </Button>
                  <Button
                    leftIcon={<FaPlay />}
                    colorScheme="blue"
                    variant="outline"
                    onClick={runTests} // Existing Run Tests button
                    isDisabled={isRunningCode || isSubmitting}
                  >
                    Run Tests (Local)
                  </Button>
                  <Button
                    leftIcon={<FaCode />}
                    colorScheme="purple"
                    variant="outline"
                    onClick={handleRequestHint}
                    isDisabled={isRunningCode || isSubmitting}
                  >
                    Request Hint
                  </Button>
                  <Button
                    leftIcon={<FaCheck />}
                    colorScheme="green"
                    isLoading={isSubmitting}
                    onClick={handleSubmit}
                    isDisabled={isRunningCode || !code.trim()} // Disable if running or code is empty
                  >
                    Submit Solution
                  </Button>
                </HStack>
                <VStack spacing={2} align="stretch" mt={2}>
                  <Text fontWeight="bold">Standard Output (stdout):</Text>
                  <Box as="pre" p={3} bg="gray.100" borderRadius="md" minH="50px" whiteSpace="pre-wrap" fontFamily="monospace" overflowX="auto">
                    {stdout || (isRunningCode ? 'Executing...' : 'Output will appear here...')}
                  </Box>
                  <Text fontWeight="bold">Standard Error (stderr):</Text>
                  <Box as="pre" p={3} bg={stderr ? "red.50" : "gray.100"} color={stderr ? "red.700" : "inherit"} borderRadius="md" minH="50px" whiteSpace="pre-wrap" fontFamily="monospace" overflowX="auto">
                    {stderr || (isRunningCode ? 'Executing...' : 'Errors will appear here...')}
                  </Box>
                </VStack>
              </VStack>
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