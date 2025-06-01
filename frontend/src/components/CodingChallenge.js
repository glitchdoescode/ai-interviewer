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
  Switch,
  FormControl,
  FormLabel,
  Icon,
} from '@chakra-ui/react';
import { FaPlay, FaCheck, FaTimes, FaPauseCircle, FaCode, FaRedo, FaCommentDots } from 'react-icons/fa';
import CodeEditor from './CodeEditor';
import { useInterview } from '../context/InterviewContext';
import { submitCodingChallengeForEvaluation } from '../api/interviewService';

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
const CodingChallenge = ({ challenge: initialChallengeData, onComplete, onRequestHint, sessionId, userId }) => {
  const [currentChallengeDetails, setCurrentChallengeDetails] = useState(initialChallengeData);
  const [code, setCode] = useState(initialChallengeData?.starter_code || '');
  const [language, setLanguage] = useState(initialChallengeData?.language || 'python');
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  const [isWaitingForUser, setIsWaitingForUser] = useState(true);
  const toast = useToast();
  
  // State for Run Code functionality (Sprint 3)
  const [stdin, setStdin] = useState('');
  const [stdout, setStdout] = useState('');
  const [stderr, setStderr] = useState('');
  const [isRunningCode, setIsRunningCode] = useState(false);

  // New state for Sprint 4: Test Case Evaluation
  const [evaluationResult, setEvaluationResult] = useState(null);
  const [isEvaluating, setIsEvaluating] = useState(false);
  
  // State for CodeMirror theme (Sprint 5 UI/UX)
  const [editorTheme, setEditorTheme] = useState(() => {
    const savedTheme = localStorage.getItem('editorTheme');
    return savedTheme || 'light'; // Default to light if no saved theme
  });
  
  const { 
    setInterviewStage, 
    jobDetails, 
    interviewStage, 
    addMessage,
    playAudioResponse
  } = useInterview();
  
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
      // problem_statement, starter_code, language, title, test_cases, etc.
      // We should store the whole object.
      // setCurrentChallengeDetails({
      //   title: data.title,
      //   description: data.problem_statement, 
      //   difficulty: data.difficulty_level || body.difficulty_level, 
      //   language: data.language,
      //   time_limit_mins: 30, 
      //   starter_code: data.starter_code,
      //   test_cases: data.test_cases, // IMPORTANT: Assuming backend sends this
      //   challenge_id: data.challenge_id // IMPORTANT
      // });
      setCurrentChallengeDetails(data); // Assuming data is the full challenge object from backend
      
      setCode(data.starter_code || '');
      setLanguage(data.language || 'python');
      // setTestResults(null); // Clear old results
      // setFeedback(null); // Clear old feedback
      setEvaluationResult(null); // Clear old evaluation results
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
    if (!initialChallengeData) {
      fetchNewChallenge();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialChallengeData]); // Only re-run if initialChallengeData changes

  // Update currentChallengeDetails when initialChallengeData (from context/prop) changes
  useEffect(() => {
    if (initialChallengeData && initialChallengeData.challenge_id) { // Ensure challenge_id exists
      console.log("CodingChallenge.js: (useEffect for initialChallengeData) Prop updated:", JSON.stringify(initialChallengeData, null, 2));
      setCurrentChallengeDetails(initialChallengeData); 
      // Ensure language and starter_code are also set from initialChallengeData if they exist
      if (initialChallengeData.language) {
        setLanguage(initialChallengeData.language);
      }
      if (initialChallengeData.starter_code) {
        const newStarterCode = initialChallengeData.starter_code;
        console.log("CodingChallenge.js: (useEffect for initialChallengeData) Preparing to setCode with:", newStarterCode);
        setCode(newStarterCode);
      }
      setEvaluationResult(null); // Clear previous evaluation results
    } else if (!initialChallengeData && currentChallengeDetails) {
      // If initialChallengeData becomes null (e.g. interview reset), clear local state if needed
      // setCurrentChallengeDetails(null); // Or handle as appropriate
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialChallengeData]); // React to changes in initialChallengeData from context

  // Set the interview stage to coding challenge waiting
  useEffect(() => {
    // Only set if a challenge is loaded and the stage isn't already reflecting a waiting/active coding state
    if (currentChallengeDetails && interviewStage !== 'coding_challenge_waiting') {
      console.log("CodingChallenge.js: Setting interview stage to coding_challenge_waiting");
      setInterviewStage('coding_challenge_waiting'); 
    }
  }, [setInterviewStage, currentChallengeDetails, interviewStage]); // Added currentChallengeDetails and interviewStage to dependencies
  
  // Effect to save theme to localStorage when it changes
  useEffect(() => {
    localStorage.setItem('editorTheme', editorTheme);
  }, [editorTheme]);

  const handleThemeChange = (event) => {
    setEditorTheme(event.target.checked ? 'dark' : 'light');
  };

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
        title: 'Empty Code',
        description: 'Please write some code before submitting.',
        status: 'warning',
        duration: 3000,
        isClosable: true,
      });
      return;
    }

    if (!currentChallengeDetails || !currentChallengeDetails.challenge_id) {
      toast({
        title: 'Error',
        description: 'Challenge details are missing. Cannot submit.',
        status: 'error',
        duration: 3000,
        isClosable: true,
      });
      return;
    }

    setIsEvaluating(true); // Use isEvaluating for this button
    // setTestResults(null); // Clear previous results
    setEvaluationResult(null); // Clear previous full evaluation
    // setFeedback(null); // Clear previous feedback
    toast({
      title: 'Submitting Code for Evaluation...',
      status: 'info',
      duration: null, 
      isClosable: false,
    });

    try {
      const submissionPayload = {
        challenge_id: currentChallengeDetails.challenge_id,
        language: language,
        code: code,
        user_id: userId,
        session_id: sessionId,
      };
      
      // This calls /api/coding/submit
      const result = await submitCodingChallengeForEvaluation(submissionPayload);
      toast.closeAll();

      if (result && result.status) { // Check if result and result.status exist
        // STORE THE ENTIRE RESULT which includes:
        // status, challenge_id, execution_results, feedback, evaluation, overall_summary
        setEvaluationResult(result); 
        
        // Display success/failure based on overall_summary or status
        const summary = result.overall_summary;
        if (summary && summary.all_tests_passed) {
          toast({
            title: 'Evaluation Complete: All Tests Passed!',
            description: summary.status_text || 'All tests passed successfully.',
            status: 'success',
            duration: 5000,
            isClosable: true,
          });
        } else if (summary) {
          toast({
            title: 'Evaluation Complete: Some Tests Failed',
            description: summary.status_text || `${summary.pass_count || 0}/${summary.total_tests || 0} tests passed.`,
            status: 'warning',
            duration: 5000,
            isClosable: true,
          });
        } else { // Fallback if overall_summary is not as expected
            toast({
                title: `Evaluation Status: ${result.status}`,
                description: 'Code submitted and evaluated.',
                status: result.status === 'success' ? 'success' : 'info', // Adjust status based on general status
                duration: 5000,
                isClosable: true,
            });
        }
      } else {
        throw new Error(result?.error || 'Unknown error during code evaluation.');
      }
    } catch (error) {
      toast.closeAll();
      console.error('Error submitting code for evaluation:', error);
      // setTestResults({ error: error.message });
      setEvaluationResult({ error: error.message }); // Store error in evaluationResult
      toast({
        title: 'Submission Error',
        description: error.message || 'Could not submit or evaluate code.',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setIsEvaluating(false);
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
  
  const handleReturnToInterviewer = async () => {
    if (!evaluationResult) {
      toast({
        title: 'No Evaluation Data',
        description: 'Please submit your code for evaluation first.',
        status: 'warning',
        duration: 3000,
        isClosable: true,
      });
      return;
    }
    if (evaluationResult.error) {
        toast({
            title: 'Evaluation Error',
            description: `Cannot return to interviewer. Previous evaluation failed: ${evaluationResult.error}`,
            status: 'error',
            duration: 5000,
            isClosable: true,
        });
        return;
    }

    setIsSubmitting(true); // Indicate loading state for this action
    toast({
      title: 'Returning to Interviewer...',
      description: 'Preparing your submission for feedback.',
      status: 'info',
      duration: null,
      isClosable: false,
    });

    // Construct the detailed message for the AI, including all relevant parts from evaluationResult
    // This message will be passed to the AIInterviewer's run_interview method
    // The AI prompt for FEEDBACK stage expects: candidate_code, execution_results, Structured Feedback Analysis
    
    const candidateCode = code; // The current code in the editor
    const executionResultsSummary = evaluationResult.overall_summary || {}; // From /api/coding/submit
    // The detailed structured feedback should be in evaluationResult.feedback or evaluationResult.evaluation
    const structuredFeedbackAnalysis = evaluationResult.feedback || evaluationResult.evaluation || {}; 

    let detailedMessageToAI = `System: The candidate has completed the coding challenge and is ready for feedback.
Challenge ID: ${currentChallengeDetails?.challenge_id || 'N/A'}
Language: ${language}

Candidate Code (language: ${language}):
\`\`\`${language}
${candidateCode}
\`\`\`

Execution Results:
Status: ${executionResultsSummary.status_text || 'N/A'}
Passed: ${executionResultsSummary.pass_count !== undefined ? executionResultsSummary.pass_count : 'N/A'} / ${executionResultsSummary.total_tests !== undefined ? executionResultsSummary.total_tests : 'N/A'}
All Tests Passed: ${executionResultsSummary.all_tests_passed !== undefined ? executionResultsSummary.all_tests_passed : 'N/A'}
Error Message (if any): ${executionResultsSummary.error_message || 'None'}

Structured Feedback Analysis (from automated tools):
${JSON.stringify(structuredFeedbackAnalysis, null, 2)}

Interviewer, please provide comprehensive feedback to the candidate based on all the information above.
Focus on their approach, code quality, correctness, and the automated analysis.
`;

    try {
      // onComplete is handleCodingFeedbackSubmitted from Interview.js
      // It expects (detailedMessageToAI, evaluationSummary)
      // We pass overall_summary as the evaluationSummary for the ChallengeCompleteRequest model
      await onComplete(detailedMessageToAI, executionResultsSummary); 
      
      toast.closeAll(); // Close the "Returning..." toast
      // Success toast will be shown by Interview.js's handleCodingFeedbackSubmitted
      
      // Optionally, you might want to disable further actions on the coding challenge here,
      // or change the UI to indicate feedback is being/has been given.
      // This might involve setting a new local state or relying on interviewStage changes from context.

    } catch (error) {
      toast.closeAll();
      console.error('Error returning to interviewer for feedback:', error);
      setIsSubmitting(false);
      toast({
        title: 'Error Returning to Interviewer',
        description: error.message || 'Could not process your request for feedback.',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      // setIsSubmitting(false); // setLoading(false) is handled by Interview.js's handler
    }
  };
  
  // If no challenge is provided, show a placeholder and a button to fetch one
  if (!currentChallengeDetails) {
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
  
  console.log("CodingChallenge.js: Rendering with 'code' state:", code, "and currentChallengeDetails?.id:", currentChallengeDetails?.id);
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
          <Heading size="md">{currentChallengeDetails.title}</Heading>
          <HStack>
            <Button size="sm" onClick={fetchNewChallenge} leftIcon={<FaRedo />} colorScheme="gray" variant="outline" mr={2}>
              New Challenge
            </Button>
            <Badge colorScheme={currentChallengeDetails.difficulty_level === 'easy' ? 'green' : currentChallengeDetails.difficulty_level === 'medium' ? 'orange' : 'red'}>
              {currentChallengeDetails.difficulty_level?.toUpperCase() || currentChallengeDetails.difficulty?.toUpperCase() || 'N/A'}
            </Badge>
            <Badge colorScheme="blue">{currentChallengeDetails.language?.toUpperCase() || 'N/A'}</Badge>
            <Badge colorScheme="purple">{currentChallengeDetails.time_limit_mins || 'N/A'} min</Badge>
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
          {/* For Sprint 1, evaluationResult might just be a simple message object */}
          {evaluationResult && <Tab>Results</Tab>}
        </TabList>
        
        <TabPanels>
          {/* Challenge Description Tab */}
          <TabPanel>
            <VStack align="stretch" spacing={4}>
              <Box>
                <Heading size="sm" mb={2}>Problem Statement</Heading>
                {/* Using Text component with whiteSpace to preserve formatting like newlines */}
                <Text whiteSpace="pre-wrap">{currentChallengeDetails.description || currentChallengeDetails.problem_statement}</Text>
              </Box>
              <Divider />
              {currentChallengeDetails.input_format && (
                <Box>
                  <Heading size="xs" mb={1}>Input Format</Heading>
                  <Text whiteSpace="pre-wrap">{currentChallengeDetails.input_format}</Text>
                </Box>
              )}
              {currentChallengeDetails.output_format && (
                <Box>
                  <Heading size="xs" mb={1}>Output Format</Heading>
                  <Text whiteSpace="pre-wrap">{currentChallengeDetails.output_format}</Text>
                </Box>
              )}
              {currentChallengeDetails.constraints && (
                <Box>
                  <Heading size="xs" mb={1}>Constraints</Heading>
                  <Text whiteSpace="pre-wrap">{currentChallengeDetails.constraints}</Text>
                </Box>
              )}
              {/* Display evaluation criteria if available from the new structure */}
              {currentChallengeDetails.evaluation_criteria && (
                <Box>
                  <Heading size="xs" mb={1}>Evaluation Criteria</Heading>
                  <VStack align="start">
                    {Object.entries(currentChallengeDetails.evaluation_criteria).map(([key, value]) => (
                      <Text key={key}><strong>{key.charAt(0).toUpperCase() + key.slice(1)}:</strong> {value}</Text>
                    ))}
                  </VStack>
                </Box>
              )}
              <Divider />
              <Heading size="sm" mb={2}>Visible Test Cases</Heading>
              <Accordion allowMultiple defaultIndex={[0]}>
                {(currentChallengeDetails.visible_test_cases || currentChallengeDetails.test_cases || []).map((tc, index) => (
                  <AccordionItem key={index}>
                    <h2>
                      <AccordionButton>
                        <Box flex="1" textAlign="left">
                          Test Case {index + 1} {tc.is_hidden ? "(Hidden)" : ""}
                        </Box>
                        <AccordionIcon />
                      </AccordionButton>
                    </h2>
                    <AccordionPanel pb={4}>
                      <VStack align="stretch" spacing={2}>
                        <Box>
                          <Text fontWeight="bold">Input:</Text>
                          <Text as="pre" p={2} bg="gray.50" borderRadius="md" whiteSpace="pre-wrap">
                            {typeof tc.input === 'object' ? JSON.stringify(tc.input, null, 2) : String(tc.input)}
                          </Text>
                        </Box>
                        <Box>
                          <Text fontWeight="bold">Expected Output:</Text>
                          <Text as="pre" p={2} bg="gray.50" borderRadius="md" whiteSpace="pre-wrap">
                            {typeof tc.expected_output === 'object' ? JSON.stringify(tc.expected_output, null, 2) : String(tc.expected_output)}
                          </Text>
                        </Box>
                        {tc.explanation && (
                           <Box>
                             <Text fontWeight="bold">Explanation:</Text>
                             <Text whiteSpace="pre-wrap">{tc.explanation}</Text>
                           </Box>
                        )}
                      </VStack>
                    </AccordionPanel>
                  </AccordionItem>
                ))}
              </Accordion>
            </VStack>
          </TabPanel>

          {/* Code Editor Tab */}
          <TabPanel>
            <VStack spacing={4} align="stretch">
              <FormControl display="flex" alignItems="center" justifyContent="flex-end">
                <FormLabel htmlFor="theme-switcher" mb="0">
                  Dark Mode
                </FormLabel>
                <Switch 
                  id="theme-switcher" 
                  isChecked={editorTheme === 'dark'} 
                  onChange={handleThemeChange} 
                />
              </FormControl>

              <HStack>
                <Text>Language:</Text>
                <Select 
                  value={language} 
                  onChange={(e) => setLanguage(e.target.value)}
                  size="sm"
                  maxW="150px"
                  isDisabled={isEvaluating}
                >
                  <option value="python">Python</option>
                  <option value="javascript">JavaScript</option>
                  <option value="java">Java</option>
                  {/* Add more languages as supported by CodeEditor.js */}
                </Select>
              </HStack>

              <CodeEditor
                key={currentChallengeDetails?.challenge_id || currentChallengeDetails?.id || 'default-editor-key'}
                code={code}
                language={language}
                onChange={(newCode) => setCode(newCode)}
                theme={editorTheme === 'dark' ? 'materialDark' : 'light'}
                height="400px"
                readOnly={isEvaluating || isRunningCode}
              />
              <HStack justifyContent="flex-end" spacing={4}>
                {/* <Button 
                  colorScheme="teal" 
                  variant="outline"
                  onClick={handleRequestHint}
                  isLoading={isSubmitting} // Consider a separate loading state for hints
                  leftIcon={<FaQuestionCircle />}
                >
                  Request Hint
                </Button> */}
                <Button 
                  colorScheme="blue" 
                  onClick={handleRunCode}
                  isLoading={isRunningCode}
                  leftIcon={<FaPlay />}
                  isDisabled={isEvaluating} // UI Lock: Disable Run Code during evaluation
                >
                  Run Code
                </Button>
                <Button 
                  colorScheme="green" 
                  onClick={handleSubmit}
                  isLoading={isEvaluating} // Use isEvaluating for submission button
                  leftIcon={<FaCheck />}
                >
                  Submit Solution
                </Button>
              </HStack>
              
              {/* Input/Output for Run Code (Sprint 3) */}
              <Heading size="sm" mt={4}>Custom Input (for Run Code)</Heading>
              <Textarea 
                placeholder="Enter standard input for your code when using 'Run Code'"
                value={stdin}
                onChange={(e) => setStdin(e.target.value)}
                fontFamily="monospace"
                rows={3}
              />
              <HStack spacing={4} align="stretch">
                <Box flex={1}>
                  <Heading size="sm">STDOUT</Heading>
                  <Textarea 
                    value={stdout} 
                    isReadOnly 
                    placeholder="Standard output will appear here..." 
                    bg="gray.50"
                    fontFamily="monospace"
                    rows={5}
                  />
                </Box>
                <Box flex={1}>
                  <Heading size="sm">STDERR</Heading>
                  <Textarea 
                    value={stderr} 
                    isReadOnly 
                    placeholder="Standard error will appear here..." 
                    bg="gray.50"
                    color="red.500"
                    fontFamily="monospace"
                    rows={5}
                  />
                </Box>
              </HStack>
            </VStack>
          </TabPanel>
          
          {/* Results Tab (Sprint 4) */}
          {evaluationResult && (
            <TabPanel>
              <VStack spacing={4} align="stretch">
                {/* MODIFICATION START: Display submission error prominently if it exists */}
                {evaluationResult.status === 'error' && evaluationResult.error_message && (
                  <Alert status="error" borderRadius="md">
                    <AlertIcon />
                    <VStack align="start" spacing={0}>
                      <Text fontWeight="bold">Submission Error:</Text>
                      <Text whiteSpace="pre-wrap">{evaluationResult.error_message}</Text>
                    </VStack>
                  </Alert>
                )}
                {/* MODIFICATION END */}

                <Heading size="md">Evaluation Results</Heading>
                
                {/* Overall Summary - using overall_summary from the API response */}
                {evaluationResult.overall_summary && (
                   <Box p={4} borderWidth="1px" borderRadius="md" bg={evaluationResult.overall_summary.all_tests_passed ? "green.50" : "red.50"}>
                    <Heading size="sm" mb={2}>Overall Summary</Heading>
                    <HStack justifyContent="space-around">
                      <Text>Status: <Badge colorScheme={evaluationResult.overall_summary.all_tests_passed ? "green" : "red"}>
                        {evaluationResult.overall_summary.all_tests_passed ? "All Tests Passed" : "Some Tests Failed"}
                      </Badge></Text>
                      <Text>Passed: {evaluationResult.overall_summary.pass_count || 0}</Text>
                      <Text>Failed: {evaluationResult.overall_summary.fail_count || ((evaluationResult.overall_summary.total_tests || 0) - (evaluationResult.overall_summary.pass_count || 0))}</Text>
                      <Text>Total: {evaluationResult.overall_summary.total_tests || 0}</Text>
                    </HStack>
                  </Box>
                )}

                {/* Detailed Test Case Results */}
                {evaluationResult.execution_results && evaluationResult.execution_results.detailed_results && Array.isArray(evaluationResult.execution_results.detailed_results.test_results) && evaluationResult.execution_results.detailed_results.test_results.length > 0 && (
                  <>
                    <Heading size="sm" mt={4}>Detailed Test Cases</Heading>
                    {/* Open failing tests by default */}
                    <Accordion allowMultiple defaultIndex={evaluationResult.execution_results.detailed_results.test_results.reduce((acc, tc, index) => tc.passed === false ? [...acc, index] : acc, [])}>
                      {evaluationResult.execution_results.detailed_results.test_results.map((tc_result, index) => (
                        <AccordionItem key={index}>
                          <h2>
                            <AccordionButton>
                              <HStack flex="1" justifyContent="space-between">
                                <Text>Test Case {tc_result.test_case_id || index + 1}</Text>
                                <Badge colorScheme={tc_result.passed ? "green" : "red"}>
                                  {tc_result.passed ? "Passed" : "Failed"}
                                </Badge>
                              </HStack>
                              <AccordionIcon />
                            </AccordionButton>
                          </h2>
                          <AccordionPanel pb={4}>
                            <VStack align="stretch" spacing={2}>
                              <Box>
                                <Text fontWeight="bold">Input:</Text>
                                <Text as="pre" p={2} bg="gray.50" borderRadius="md" whiteSpace="pre-wrap">
                                  {typeof tc_result.input === 'object' ? JSON.stringify(tc_result.input, null, 2) : String(tc_result.input)}
                                </Text>
                              </Box>
                              <Box>
                                <Text fontWeight="bold">Expected Output:</Text>
                                <Text as="pre" p={2} bg="gray.50" borderRadius="md" whiteSpace="pre-wrap">
                                  {typeof tc_result.expected_output === 'object' ? JSON.stringify(tc_result.expected_output, null, 2) : String(tc_result.expected_output)}
                                </Text>
                              </Box>
                              <Box>
                                <Text fontWeight="bold">Actual Output:</Text>
                                <Text as="pre" p={2} bg={tc_result.passed ? "green.50" : "red.50"} borderRadius="md" whiteSpace="pre-wrap">
                                  {typeof tc_result.output === 'object' ? JSON.stringify(tc_result.output, null, 2) : String(tc_result.output)}
                                </Text>
                              </Box>
                              {tc_result.error && (
                                <Alert status="error" mt={2}>
                                  <AlertIcon />
                                  <VStack align="start" spacing={0}>
                                    <Text fontWeight="bold">Error:</Text>
                                    <Text whiteSpace="pre-wrap">{tc_result.error}</Text>
                                  </VStack>
                                </Alert>
                              )}
                              {/* Display stdout/stderr from test case if present */}
                              {tc_result.stdout && (
                                <Box>
                                  <Text fontWeight="bold">STDOUT:</Text>
                                  <Text as="pre" p={2} bg="gray.100" borderRadius="md" whiteSpace="pre-wrap" maxHeight="100px" overflowY="auto">
                                    {tc_result.stdout}
                                  </Text>
                                </Box>
                              )}
                              {tc_result.stderr && (
                                <Box>
                                  <Text fontWeight="bold">STDERR:</Text>
                                  <Text as="pre" p={2} bg="red.50" color="red.700" borderRadius="md" whiteSpace="pre-wrap" maxHeight="100px" overflowY="auto">
                                    {tc_result.stderr}
                                  </Text>
                                </Box>
                              )}
                            </VStack>
                          </AccordionPanel>
                        </AccordionItem>
                      ))}
                    </Accordion>
                  </>
                )}
                
                {/* Feedback Section */}
                {evaluationResult.feedback && Object.keys(evaluationResult.feedback).length > 0 && (
                  <Box mt={4} p={4} borderWidth="1px" borderRadius="md" bg="blue.50">
                    <Heading size="sm" mb={2}>Feedback</Heading>
                    {typeof evaluationResult.feedback === 'string' ? (
                      <Text whiteSpace="pre-wrap">{evaluationResult.feedback}</Text>
                    ) : (
                      <VStack align="start">
                        {Object.entries(evaluationResult.feedback).map(([key, value]) => (
                          <Text key={key}><strong>{key.charAt(0).toUpperCase() + key.slice(1)}:</strong> {String(value)}</Text>
                        ))}
                      </VStack>
                    )}
                  </Box>
                )}

                {/* Detailed Test Case Results */}
                {evaluationResult.test_cases_results && evaluationResult.test_cases_results.length > 0 && (
                  <Box>
                    <Heading size="sm" mb={2} mt={4}>Detailed Test Results</Heading>
                    <Accordion allowMultiple>
                      {evaluationResult.test_cases_results.map((result, index) => (
                        <AccordionItem key={index}>
                          <h2>
                            <AccordionButton>
                              <Box flex="1" textAlign="left">
                                Test Case {index + 1}: <Badge colorScheme={result.passed ? 'green' : 'red'}>{result.passed ? 'Passed' : 'Failed'}</Badge>
                              </Box>
                              <AccordionIcon />
                            </AccordionButton>
                          </h2>
                          <AccordionPanel pb={4}>
                            <VStack align="stretch" spacing={2}>
                              <Text><strong>Input:</strong> <pre>{JSON.stringify(result.input, null, 2)}</pre></Text>
                              <Text><strong>Expected Output:</strong> <pre>{JSON.stringify(result.expected_output, null, 2)}</pre></Text>
                              <Text><strong>Actual Output:</strong> <pre>{result.actual_output !== undefined ? JSON.stringify(result.actual_output, null, 2) : (result.stdout || '(No output)')}</pre></Text>
                              {result.error && <Text><strong>Error:</strong> <pre>{result.error}</pre></Text>}
                              {result.stdout && <Text><strong>Stdout:</strong> <pre>{result.stdout}</pre></Text>}
                              {result.stderr && <Text><strong>Stderr:</strong> <pre>{result.stderr}</pre></Text>}
                              {result.reason && !result.passed && <Text><strong>Reason:</strong> {result.reason}</Text>}
                            </VStack>
                          </AccordionPanel>
                        </AccordionItem>
                      ))}
                    </Accordion>
                  </Box>
                )}
                {/* Button to return to interviewer */} 
                <Button 
                  mt={6}
                  colorScheme="blue"
                  leftIcon={<Icon as={FaCommentDots} />}
                  onClick={handleReturnToInterviewer}
                  isLoading={isSubmitting}
                  isDisabled={isSubmitting || !currentChallengeDetails}
                >
                  Return to Interviewer for Feedback
                </Button>
              </VStack>
            </TabPanel>
          )}
        </TabPanels>
      </Tabs>
    </Box>
  );
};

export default CodingChallenge; 