import React, { useState, useEffect, useRef, useCallback } from 'react';
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
  useColorModeValue,
  Grid,
  GridItem,
  Avatar,
  Flex,
  Input,
  IconButton,
  Progress,
} from '@chakra-ui/react';
import { Global } from '@emotion/react';
import { FaPlay, FaCheck, FaPauseCircle, FaRedo, FaCommentDots, FaPaperPlane, FaMicrophone, FaMicrophoneSlash, FaTimes } from 'react-icons/fa';
import CodeEditor from './CodeEditor';
import { useInterview } from '../context/InterviewContext';
import { submitCodingChallengeForEvaluation, getChallengeHint, submitChallengeFeedbackToServer } from '../api/interviewService';
import ChatMessage from './ChatMessage';
import AudioControls from './video/AudioControls';
import { ConversationIndicators } from './video/ConversationIndicators';

/**
 * CodingChallenge component for handling coding challenge interactions
 * 
 * @param {Object} props Component props
 * @param {Object} props.challenge Challenge data (title, description, etc.)
 * @param {Function} props.onComplete Callback when challenge is completed
 * @param {Function} props.onRequestHint Callback to request a hint
 * @param {string} props.sessionId Session ID
 * @param {string} props.userId User ID
 * @param {boolean} props.isVideoCall Indicates if the challenge is in video call mode
 */
const CodingChallenge = ({ 
  jobRoleData, 
  onSubmit, 
  onComplete,
  isVideoCall = false,
  sessionId = null,
  userId = null 
}) => {
  const [currentChallengeDetails, setCurrentChallengeDetails] = useState(jobRoleData);
  const [code, setCode] = useState(jobRoleData?.starter_code || '');
  const [language, setLanguage] = useState(jobRoleData?.language || 'python');
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  const [isWaitingForUser, setIsWaitingForUser] = useState(true);
  const toast = useToast();
  
  // Component state
  const [results, setResults] = useState(null);
  const [showOutput, setShowOutput] = useState(false);
  const [output, setOutput] = useState({ stdout: "", stderr: "", error: "" });
  const [isRunning, setIsRunning] = useState(false);
  const [evaluationResult, setEvaluationResult] = useState(null);
  const [isWaitingForTests, setIsWaitingForTests] = useState(false);
  const [inputText, setInputText] = useState("");
  const [theme, setTheme] = useState("vs-dark");
  const [isAudioActive, setIsAudioActive] = useState(false);
  const [messages, setMessages] = useState([{
    role: 'assistant',
    content: `Hello! I'll be helping you with this coding challenge. Feel free to ask any questions about the problem. Good luck!`,
    timestamp: new Date().toISOString()
  }]);
  const [hintsRequested, setHintsRequested] = useState(0);
  const [showHintTooltip, setShowHintTooltip] = useState(false);
  const [audioTranscript, setAudioTranscript] = useState("");
  const [chatMessage, setChatMessage] = useState('');
  const [isLoadingResponse, setIsLoadingResponse] = useState(false);
  
  // Import and use the InterviewContext
  const { 
    setInterviewStage, 
    jobDetails, 
    interviewStage,
    allMessages,
    setCurrentCodingChallenge
  } = useInterview();
  
  // Refs
  const editorRef = useRef(null);
  const chatAreaRef = useRef(null);
  
  // State for Run Code functionality (Sprint 3)
  const [stdin, setStdin] = useState('');
  const [stdout, setStdout] = useState('');
  const [stderr, setStderr] = useState('');
  const [isRunningCode, setIsRunningCode] = useState(false);

  // New state for Sprint 4: Test Case Evaluation
  const [isEvaluating, setIsEvaluating] = useState(false);
  
  // Theme colors
  const bgColor = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('gray.200', 'gray.700');
  const userMessageBg = useColorModeValue('brand.100', 'brand.700');
  const aiMessageBg = useColorModeValue('gray.100', 'gray.700');
  const messageTextColor = useColorModeValue('gray.800', 'white');
  const messagesAreaBg = useColorModeValue('gray.50', 'gray.700');
  const inputBg = useColorModeValue('white', 'gray.700');
  
  // Audio/Video state
  const [audioStream, setAudioStream] = useState(null);
  const [isAudioStreamActive, setIsAudioStreamActive] = useState(false);
  const [micEnabled, setMicEnabled] = useState(true);
  const [cameraEnabled, setCameraEnabled] = useState(false);
  const [candidateAudioLevel, setCandidateAudioLevel] = useState(0);
  const [aiAudioLevel, setAiAudioLevel] = useState(0);
  const [isListening, setIsListening] = useState(false);
  const [isUserSpeaking, setIsUserSpeaking] = useState(false);
  const [candidateSpeaking, setCandidateSpeaking] = useState(false);
  const [aiSpeaking, setAiSpeaking] = useState(false);
  const [speechRecognition, setSpeechRecognition] = useState(null);
  const [recognitionState, setRecognitionState] = useState('stopped'); // 'stopped', 'starting', 'running', 'stopping'
  const [speechSupported, setSpeechSupported] = useState(true);
  const [interimTranscript, setInterimTranscript] = useState('');
  const [speechDetectionTimeout, setSpeechDetectionTimeout] = useState(null);
  const [sessionDuration, setSessionDuration] = useState(0);
  const [availableVoices, setAvailableVoices] = useState([]);
  
  // Refs for speech detection
  const isAudioStreamActiveRef = useRef(false);
  const recognitionStateRef = useRef('stopped');
  const speechDetectionTimeoutRef = useRef(null);
  
  // State for UI and code editor
  const [editorTheme, setEditorTheme] = useState('light');
  const primaryColor = useColorModeValue('primary.600', 'primary.400');
  
  // CSS for pulse animation
  const pulseAnimation = `
    @keyframes pulse {
      0% {
        transform: scale(0.95);
        opacity: 0.7;
      }
      50% {
        transform: scale(1.1);
        opacity: 1;
      }
      100% {
        transform: scale(0.95);
        opacity: 0.7;
      }
    }
  `;
  
  // Initialize with existing messages from the interview context
  useEffect(() => {
    if (allMessages && allMessages.length > 0) {
      // Take last 5 messages to provide context
      const recentMessages = allMessages.slice(-5);
      setMessages([
        ...recentMessages,
        {
          role: 'assistant',
          content: `I've prepared a coding challenge for you. Let me know if you need any clarification on the problem.`,
          timestamp: new Date().toISOString()
        }
      ]);
    }
  }, [allMessages]);
  
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
    if (!jobRoleData) {
      fetchNewChallenge();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobRoleData]); // Only re-run if jobRoleData changes

  // Update currentChallengeDetails when jobRoleData (from context/prop) changes
  useEffect(() => {
    if (jobRoleData && jobRoleData.challenge_id) { // Ensure challenge_id exists
      console.log("CodingChallenge.js: (useEffect for jobRoleData) Prop updated:", JSON.stringify(jobRoleData, null, 2));
      setCurrentChallengeDetails(jobRoleData); 
      // Ensure language and starter_code are also set from jobRoleData if they exist
      if (jobRoleData.language) {
        setLanguage(jobRoleData.language);
      }
      if (jobRoleData.starter_code) {
        const newStarterCode = jobRoleData.starter_code;
        console.log("CodingChallenge.js: (useEffect for jobRoleData) Preparing to setCode with:", newStarterCode);
        setCode(newStarterCode);
      }
      setEvaluationResult(null); // Clear previous evaluation results
    } else if (!jobRoleData && currentChallengeDetails) {
      // If jobRoleData becomes null (e.g. interview reset), clear local state if needed
      // setCurrentChallengeDetails(null); // Or handle as appropriate
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobRoleData]); // React to changes in jobRoleData from context

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
  
  const handleSendMessage = async () => {
    if (!chatMessage.trim()) return;
    
    // We now use the enhanced version with audio support
    handleSendMessageWithAudio();
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
        title: 'No submission results',
        description: 'Please submit your solution first to receive feedback.',
        status: 'warning',
        duration: 3000,
        isClosable: true,
      });
      return;
    }

    setIsSubmitting(true);
    
    try {
      console.log('Sending detailed results to AI for feedback');
      
      // Create a clear message with submission details
      const detailedMessageToAI = `I've completed the coding challenge. Here's my solution in ${language}:\n\n\`\`\`${language}\n${code}\n\`\`\`\n\nThe test results show ${evaluationResult.overall_summary.pass_count}/${evaluationResult.overall_summary.total_tests} tests passed.`;

      // Get the evaluation summary to include with the request
      const evaluationSummary = evaluationResult?.overall_summary || null;
      
      // Add submission code to the evaluation summary for better context
      if (evaluationSummary) {
        evaluationSummary.code = code;
        evaluationSummary.language = language;
      }
      
      // Show a transition toast to inform the user we're processing
      toast({
        title: 'Analyzing your code',
        description: 'Sending your solution for expert feedback...',
        status: 'info',
        duration: 3000,
        isClosable: true,
      });
      
      // Submit the feedback request with the special context
      const response = await submitChallengeFeedbackToServer(
        sessionId, 
        userId, 
        detailedMessageToAI,
        evaluationSummary,
        true,
        "coding_feedback"
      );
      
      console.log('Feedback response received:', response);

      // Only change stage if the server confirms feedback stage
      if (response && response.interview_stage === 'feedback') {
        // Set interview stage to feedback
        setInterviewStage('feedback');
        
        // Remove the challenge UI to show the feedback interface
        setCurrentCodingChallenge(null);
        
        toast({
          title: 'Feedback Ready',
          description: 'The interviewer is now reviewing your solution.',
          status: 'success',
          duration: 3000,
          isClosable: true,
        });
      } else {
        console.warn('Server did not confirm feedback stage:', response?.interview_stage);
        toast({
          title: 'Stage Sync Error',
          description: 'There was an issue transitioning to feedback. Please try again.',
          status: 'error',
          duration: 5000,
          isClosable: true,
        });
      }
      
      onComplete();
    } catch (error) {
      console.error('Error sending feedback request:', error);
      toast({
        title: 'Error',
        description: 'Failed to send feedback request. Please try again.',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setIsSubmitting(false);
    }
  };
  
  // Session duration timer
  useEffect(() => {
    const timer = setInterval(() => {
      setSessionDuration(prev => prev + 1);
    }, 1000);
    
    return () => clearInterval(timer);
  }, []);

  // Initialize audio streaming functionality
  useEffect(() => {
    let mediaStream = null;
    let audioContext = null;
    let analyser = null;
    let processor = null;
    let recognition = null;

    const initializeAudioStreaming = async () => {
      try {
        // Request microphone access
        mediaStream = await navigator.mediaDevices.getUserMedia({ 
          audio: {
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
            sampleRate: 16000
          } 
        });
        
        setAudioStream(mediaStream);
        console.log('[CodingChallenge] Microphone access granted');

        // Set up audio context for voice activity detection
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const source = audioContext.createMediaStreamSource(mediaStream);
        analyser = audioContext.createAnalyser();
        
        analyser.fftSize = 256;
        analyser.smoothingTimeConstant = 0.8;
        source.connect(analyser);

        // Set up continuous speech recognition
        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
          const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
          recognition = new SpeechRecognition();
          
          recognition.continuous = true;
          recognition.interimResults = true;
          recognition.lang = 'en-US';
          recognition.maxAlternatives = 1;
          
          let finalTranscript = '';
          let lastSpeechTime = Date.now();
          let lastRequestTime = null;
          
          recognition.onstart = () => {
            console.log('[CodingChallenge] Speech recognition started');
            setRecognitionState('running');
            setIsListening(true);
          };
          
          recognition.onresult = (event) => {
            let interim = '';
            let final = '';
            
            for (let i = event.resultIndex; i < event.results.length; i++) {
              if (event.results[i].isFinal) {
                final += event.results[i][0].transcript;
                finalTranscript += event.results[i][0].transcript;
              } else {
                interim += event.results[i][0].transcript;
              }
            }
            
            // Debug logging
            if (final) {
              console.log('[CodingChallenge] Final transcript:', final);
              setCandidateSpeaking(true);
              setIsUserSpeaking(true);
              lastSpeechTime = Date.now();
              
              // If not currently engaged in a request, and substantial content is detected,
              // send it to the interview API
              const fullTranscript = finalTranscript.trim();
              if (fullTranscript.length > 5 && 
                  (!lastRequestTime || Date.now() - lastRequestTime > 3000)) {
                
                // Set the chat message to the transcribed text and send it
                setChatMessage(fullTranscript);
                // Use setTimeout to ensure state is updated before calling
                setTimeout(() => {
                  handleSendMessageWithAudio(fullTranscript);
                  lastRequestTime = Date.now();
                  finalTranscript = ''; // Reset after sending
                }, 0);
              }
            }
            
            if (interim) {
              setInterimTranscript(interim);
              setCandidateSpeaking(true);
              setIsUserSpeaking(true);
            }
            
            // Set a timeout to reset the speaking state if no new speech
            if (speechDetectionTimeoutRef.current) {
              clearTimeout(speechDetectionTimeoutRef.current);
            }
            
            const timeout = setTimeout(() => {
              if (Date.now() - lastSpeechTime > 1500) {
                setCandidateSpeaking(false);
                setIsUserSpeaking(false);
                setInterimTranscript('');
              }
            }, 1500);
            
            speechDetectionTimeoutRef.current = timeout;
            setSpeechDetectionTimeout(timeout);
          };
          
          recognition.onerror = (event) => {
            console.error('[CodingChallenge] Recognition error:', event.error);
            
            if (event.error === 'no-speech') {
              console.log('[CodingChallenge] No speech detected, restarting...');
              if (recognitionStateRef.current === 'running') {
                try {
                  recognition.stop();
                  setTimeout(() => {
                    if (isAudioStreamActiveRef.current) {
                      recognition.start();
                    }
                  }, 100);
                } catch (error) {
                  console.error('[CodingChallenge] Error restarting recognition:', error);
                }
              }
            } else if (event.error === 'network') {
    toast({
                title: 'Network Error',
                description: 'Speech recognition network error. Please check your connection.',
                status: 'error',
                duration: 5000,
                isClosable: true,
              });
            }
          };
          
          recognition.onend = () => {
            console.log('[CodingChallenge] Recognition ended, state:', recognitionStateRef.current);
            
            // Only restart if it was running and stopped unexpectedly
            // AND we're still active AND we haven't explicitly stopped it
            if (recognitionStateRef.current === 'running' && 
                isAudioStreamActiveRef.current &&
                recognitionStateRef.current !== 'stopping') {
              
              console.log('[CodingChallenge] Restarting recognition after unexpected end');
              
              // Set stopping temporarily to prevent multiple restarts
              setRecognitionState('stopping');
              recognitionStateRef.current = 'stopping';
              
              try {
                setTimeout(() => {
                  // Double-check we still want recognition before restarting
                  if (isAudioStreamActiveRef.current && micEnabled) {
                    console.log('[CodingChallenge] Conditions still valid, restarting recognition');
                    setRecognitionState('stopped');  // Reset to stopped
                    recognitionStateRef.current = 'stopped';
                    
                    // Small additional delay to ensure clean state
                    setTimeout(() => {
                      try {
                        startRecognitionSafely(recognition);
                      } catch (error) {
                        console.error('[CodingChallenge] Error restarting recognition in onend:', error);
                        setRecognitionState('stopped');
                        recognitionStateRef.current = 'stopped';
                        setIsListening(false);
                      }
                    }, 100);
                  } else {
                    console.log('[CodingChallenge] Conditions changed, not restarting recognition');
                    setRecognitionState('stopped');
                    recognitionStateRef.current = 'stopped';
                    setIsListening(false);
                  }
                }, 300);
              } catch (error) {
                console.error('[CodingChallenge] Error restarting recognition:', error);
                setRecognitionState('stopped');
                recognitionStateRef.current = 'stopped';
                setIsListening(false);
              }
            } else {
              console.log('[CodingChallenge] Recognition ended normally, not restarting');
              setRecognitionState('stopped');
              recognitionStateRef.current = 'stopped';
              setIsListening(false);
            }
          };

          // Start continuous recognition
          startRecognitionSafely(recognition);
          setSpeechRecognition(recognition);
          setSpeechSupported(true);
        }

        // Start voice activity detection
        const detectVoiceActivity = () => {
          if (!analyser || !isAudioStreamActiveRef.current) return;

          const bufferLength = analyser.frequencyBinCount;
          const dataArray = new Uint8Array(bufferLength);
          analyser.getByteFrequencyData(dataArray);

          // Calculate average volume
          const average = dataArray.reduce((sum, value) => sum + value, 0) / bufferLength;
          
          // Update audio level state for visual indicator
          setCandidateAudioLevel(average / 255); // Normalize to 0-1
          
          // Voice activity threshold (adjust as needed)
          const voiceThreshold = 20;
          
          // Debug logging every 100 frames
          if (Math.random() < 0.01) { // 1% of frames
            console.log('[CodingChallenge] Audio level:', average, 'threshold:', voiceThreshold);
          }
          
          if (average > voiceThreshold && !isUserSpeaking) {
            console.log('[CodingChallenge] Voice activity detected, level:', average);
            setIsListening(true);
          } else if (average <= voiceThreshold && isListening) {
            // Don't immediately stop - let speech recognition handle timing
          }

          requestAnimationFrame(detectVoiceActivity);
        };

        setIsAudioStreamActive(true);
        isAudioStreamActiveRef.current = true;
        detectVoiceActivity();
        
        console.log('[CodingChallenge] Continuous audio streaming initialized');
        
      } catch (error) {
        console.error('[CodingChallenge] Failed to initialize audio streaming:', error);
        setSpeechSupported(false);
        toast({
          title: 'Microphone Error',
          description: 'Failed to access microphone. Please grant permission and refresh.',
          status: 'error',
          duration: 5000,
          isClosable: true,
        });
      }
    };

    // Auto-start audio streaming when session is ready
    if ((isVideoCall || window.location.hash.includes('voice=true')) && sessionId && userId) {
      initializeAudioStreaming();
    }

    // Cleanup function
    return () => {
      isAudioStreamActiveRef.current = false;
      setIsAudioStreamActive(false);
      setRecognitionState('stopping');
      recognitionStateRef.current = 'stopping';
      
      if (speechDetectionTimeoutRef.current) {
        clearTimeout(speechDetectionTimeoutRef.current);
        setSpeechDetectionTimeout(null);
      }
      
      if (recognition) {
        try {
          recognition.stop();
          recognition.onstart = null;
          recognition.onresult = null;
          recognition.onerror = null;
          recognition.onend = null;
        } catch (error) {
          console.log('[CodingChallenge] Recognition already stopped');
        }
      }
      
      if (processor) {
        processor.disconnect();
      }
      
      if (analyser) {
        analyser.disconnect();
      }
      
      if (audioContext) {
        audioContext.close();
      }
      
      if (mediaStream) {
        mediaStream.getTracks().forEach(track => track.stop());
      }
      
      setRecognitionState('stopped');
      setIsListening(false);
      setIsUserSpeaking(false);
      
      console.log('[CodingChallenge] Audio streaming cleaned up');
    };
  }, [isVideoCall, sessionId, userId, toast]);

  // Keep recognitionStateRef in sync with recognitionState
  useEffect(() => {
    console.log('[CodingChallenge] Recognition state changed:', recognitionState);
    recognitionStateRef.current = recognitionState;
  }, [recognitionState]);
  
  // Keep isAudioStreamActiveRef in sync with isAudioStreamActive
  useEffect(() => {
    console.log('[CodingChallenge] Audio stream active state changed:', isAudioStreamActive);
    isAudioStreamActiveRef.current = isAudioStreamActive;
  }, [isAudioStreamActive]);

  // Speech synthesis for AI responses
  const speakAIResponse = useCallback((text, voices = availableVoices) => {
    if (!('speechSynthesis' in window) || !speechSynthesis || !voices.length) {
      console.warn('[CodingChallenge] Speech synthesis not available');
      return;
    }
    
    // Cancel any current speech
    speechSynthesis.cancel();
    
    // Create utterance
    const utterance = new SpeechSynthesisUtterance(text);
    
    // Find a good voice
    const preferredVoice = voices.find(voice => 
      voice.name.includes('Daniel') || // High quality voice
      voice.name.includes('Google') ||
      voice.name.includes('Male')
    ) || voices[0];
    
    utterance.voice = preferredVoice;
    utterance.pitch = 1;
    utterance.rate = 1;
    utterance.volume = 1;
    
    // Events
    utterance.onstart = () => {
      console.log('[CodingChallenge] Speech started');
      setAiSpeaking(true);
      setAiAudioLevel(0.7); // Simulate audio level
    };
    
    utterance.onend = () => {
      console.log('[CodingChallenge] Speech ended');
      setAiSpeaking(false);
      setAiAudioLevel(0);
    };
    
    utterance.onerror = (event) => {
      console.error('[CodingChallenge] Speech error:', event);
      setAiSpeaking(false);
      setAiAudioLevel(0);
    };
    
    // Speak
    speechSynthesis.speak(utterance);
  }, [availableVoices]);

  // Manual toggle for audio streaming
  const toggleMicrophone = useCallback(() => {
    console.log('[CodingChallenge] Toggling microphone, current state:', micEnabled, 'recognition state:', recognitionState);
    
    // If turning off, stop any active speech recognition
    if (micEnabled) {
      // We're turning the mic off
      if (speechRecognition) {
        try {
          console.log('[CodingChallenge] Stopping speech recognition due to mic toggle off');
          setRecognitionState('stopping');
          recognitionStateRef.current = 'stopping';
          speechRecognition.stop();
          
          // Ensure state is completely reset after a short delay
          setTimeout(() => {
            setRecognitionState('stopped');
            recognitionStateRef.current = 'stopped';
            setIsListening(false);
          }, 100);
    } catch (error) {
          console.error('[CodingChallenge] Error stopping speech recognition during toggle:', error);
          // Reset state even if error occurs
          setRecognitionState('stopped');
          recognitionStateRef.current = 'stopped';
        }
      }
      
      // Also mute audio tracks if stream exists
      if (audioStream) {
        audioStream.getAudioTracks().forEach(track => {
          console.log('[CodingChallenge] Disabling audio track');
          track.enabled = false;
        });
      }
    } else {
      // We're turning the mic on
      
      // First, ensure all audio tracks are enabled
      if (audioStream) {
        audioStream.getAudioTracks().forEach(track => {
          console.log('[CodingChallenge] Enabling audio track');
          track.enabled = true;
        });
      }
      
      // Then restart speech recognition if needed
      if (isAudioStreamActive) {
        if (speechRecognition && 
            (recognitionState === 'stopped' && recognitionStateRef.current === 'stopped')) {
          try {
            console.log('[CodingChallenge] Starting speech recognition due to mic toggle on');
            // Use a small delay to ensure clean state
            setTimeout(() => {
              startRecognitionSafely(speechRecognition);
            }, 100);
          } catch (error) {
            console.error('[CodingChallenge] Error starting speech recognition during toggle:', error);
          }
        }
      }
    }
    
    // Finally update the mic enabled state
    setMicEnabled(prev => !prev);
  }, [micEnabled, speechRecognition, isAudioStreamActive, recognitionState, audioStream]);

  // Toggle camera (placeholder for future video implementation)
  const toggleCamera = useCallback(() => {
    setCameraEnabled(prev => !prev);
  }, []);

  // Load available voices for speech synthesis
  useEffect(() => {
    if ('speechSynthesis' in window) {
      // Force voice loading with better timing
      const loadVoices = () => {
        const voices = window.speechSynthesis.getVoices();
        console.log('[CodingChallenge] Voice loading check - Count:', voices.length);
        setAvailableVoices(voices);
        
        if (voices.length > 0) {
          console.log('[CodingChallenge] Available voices:', voices.map(v => ({
            name: v.name,
            lang: v.lang,
            localService: v.localService,
            default: v.default,
            quality: v.localService ? 'Local (Better)' : 'Network (Variable)'
          })));
        } else {
          console.warn('[CodingChallenge] No voices loaded yet, will retry...');
        }
      };

      // Check voices immediately
      loadVoices();
      
      // Also listen for voiceschanged event
      const handleVoicesChanged = () => {
        console.log('[CodingChallenge] Voices changed event triggered');
        loadVoices();
      };
      
      window.speechSynthesis.addEventListener('voiceschanged', handleVoicesChanged);
      
      // Force voice loading with a silent utterance if needed
      const forceVoiceLoad = () => {
        if (window.speechSynthesis.getVoices().length === 0) {
          console.log('[CodingChallenge] Forcing voice loading with silent utterance...');
          const silentUtterance = new SpeechSynthesisUtterance(' ');
          silentUtterance.volume = 0;
          silentUtterance.onend = () => {
            console.log('[CodingChallenge] Silent utterance completed, reloading voices...');
            setTimeout(loadVoices, 100);
          };
          silentUtterance.onerror = (error) => {
            console.error('[CodingChallenge] Silent utterance error:', error);
          };
          window.speechSynthesis.speak(silentUtterance);
        }
      };
      
      // Try loading after a short delay if voices aren't immediately available
      setTimeout(forceVoiceLoad, 500);
      
      return () => {
        window.speechSynthesis.removeEventListener('voiceschanged', handleVoicesChanged);
      };
    } else {
      console.error('[CodingChallenge] Speech synthesis not supported in this browser');
    }
  }, []);

  // Handle sending messages with audio
  const handleSendMessageWithAudio = async (transcribedText = null) => {
    // Ensure transcribedText is a string or null
    let messageToSend;
    
    if (transcribedText !== null) {
      // Convert non-string transcribed text to string if needed
      if (typeof transcribedText !== 'string') {
        console.error('handleSendMessageWithAudio received non-string transcribedText:', transcribedText);
        messageToSend = String(transcribedText);
      } else {
        messageToSend = transcribedText;
      }
    } else {
      // Use chat message from input field
      messageToSend = chatMessage || '';
    }
    
    // Early return if message is empty
    if (!messageToSend || !messageToSend.trim()) {
      console.log('Empty message, not sending:', messageToSend);
      return;
    }
    
    // Add user message to chat
    const userMessage = {
      role: 'user',
      content: messageToSend,
      timestamp: new Date().toISOString()
    };
    setMessages(prev => [...prev, userMessage]);
    
    // Clear input field if not using transcribed text
    if (!transcribedText) {
      setChatMessage('');
    }
    
    // Show loading state
    setIsLoadingResponse(true);
    
    try {
      // Request hint if message contains question or hint request
      if (messageToSend.toLowerCase().includes('hint') || 
          messageToSend.toLowerCase().includes('help') ||
          messageToSend.toLowerCase().includes('?')) {
        
        console.log("Requesting hint with parameters:", {
          challengeId: currentChallengeDetails.challenge_id || "unknown",
          code,
          sessionId,
          userId
        });
        
        const hintResponse = await getChallengeHint(
          currentChallengeDetails.challenge_id || "unknown",
          code,
          "",
          sessionId,
          userId
        );
        
        console.log("Hint response:", hintResponse);
        
        if (hintResponse && hintResponse.hints && hintResponse.hints.length > 0) {
          const aiResponse = {
            role: 'assistant',
            content: hintResponse.hints.join('\n\n'),
            timestamp: new Date().toISOString()
          };
          
          setMessages(prev => [...prev, aiResponse]);
          
          // Speak the response if audio is enabled
          if (isVideoCall && speechSynthesis) {
            speakAIResponse(aiResponse.content);
          }
        } else {
          // Fallback response if no hints are available
          const aiResponse = {
            role: 'assistant',
            content: "I'm sorry, I don't have any specific hints for this particular issue. Try breaking down the problem into smaller steps and check your logic carefully.",
            timestamp: new Date().toISOString()
          };
          
          setMessages(prev => [...prev, aiResponse]);
          
          // Speak the response if audio is enabled
          if (isVideoCall && speechSynthesis) {
            speakAIResponse(aiResponse.content);
          }
        }
      } else {
        // General response for non-hint messages
        const aiResponse = {
          role: 'assistant',
          content: `I see you're working on the coding challenge. Let me know if you need any hints or have questions about the problem statement.`,
          timestamp: new Date().toISOString()
        };
        
        setMessages(prev => [...prev, aiResponse]);
        
        // Speak the response if audio is enabled
        if (isVideoCall && speechSynthesis) {
          speakAIResponse(aiResponse.content);
        }
      }
    } catch (error) {
      console.error("Error getting response:", error);
      
      // Show error response
      const errorResponse = {
        role: 'assistant',
        content: `I'm sorry, I encountered an error while processing your request. Please try again or rephrase your question.`,
        timestamp: new Date().toISOString()
      };
      
      setMessages(prev => [...prev, errorResponse]);
      
      // Speak the error response if audio is enabled
      if (isVideoCall && speechSynthesis) {
        speakAIResponse(errorResponse.content);
      }
      
      toast({
        title: 'Error',
        description: `Failed to get a response: ${error.message}`,
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    } finally {
      setIsLoadingResponse(false);
    }
  };

  // Helper function to safely start speech recognition
  const startRecognitionSafely = useCallback((recognitionInstance) => {
    // Check both state ref and actual state to prevent "already started" errors
    if (recognitionStateRef.current === 'stopped' && recognitionState === 'stopped') {
      try {
        console.log('[CodingChallenge] Starting speech recognition safely');
        setRecognitionState('starting');
        recognitionStateRef.current = 'starting'; // Update ref immediately
        
        // Small delay to ensure state updates propagate
        setTimeout(() => {
          try {
            recognitionInstance.start();
            console.log('[CodingChallenge] Speech recognition started successfully');
          } catch (error) {
            console.error('[CodingChallenge] Failed to start recognition in timeout:', error);
            setRecognitionState('stopped');
            recognitionStateRef.current = 'stopped';
            setIsListening(false);
          }
        }, 50);
      } catch (error) {
        console.error('[CodingChallenge] Failed to start recognition:', error);
        setRecognitionState('stopped');
        recognitionStateRef.current = 'stopped';
        setIsListening(false);
      }
    } else {
      console.log('[CodingChallenge] Speech recognition already active:', recognitionStateRef.current);
    }
  }, [recognitionState]);

  console.log("CodingChallenge.js: Rendering with 'code' state:", code, "and currentChallengeDetails?.id:", currentChallengeDetails?.id);
  
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
      w="100%"
      h="100%"
      minH="70vh"
      bg={bgColor}
      borderColor={borderColor}
    >
      <Global styles={pulseAnimation} />
      {isVideoCall ? (
        // Split view with coding challenge on left and video UI on right
        <Grid templateColumns="1fr 1fr" gap={0} h="100%">
          {/* Left side: Code editor */}
          <Box
            bg={bgColor}
            borderRight="1px"
            borderColor={borderColor}
            overflowY="auto"
            h="100%"
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
      </Box>
      
            {/* Challenge Tabs */}
            <Tabs variant="enclosed">
        <TabList>
                <Tab>Problem</Tab>
                <Tab>Code</Tab>
          {evaluationResult && <Tab>Results</Tab>}
        </TabList>
        
        <TabPanels>
                {/* Problem Description Tab */}
          <TabPanel>
            <VStack align="stretch" spacing={4}>
              <Box>
                <Heading size="sm" mb={2}>Problem Statement</Heading>
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
                    {/* Example Test Cases Section */}
                    {currentChallengeDetails.test_cases && currentChallengeDetails.test_cases.length > 0 && (
                <Box>
                        <Heading size="sm" mb={2}>Example Test Cases</Heading>
                        <Accordion allowMultiple defaultIndex={[0]}>
                          {currentChallengeDetails.test_cases.map((testCase, index) => (
                            <AccordionItem key={index}>
                              <AccordionButton>
                                <Box flex="1" textAlign="left">
                                  <Text fontWeight="bold">Example {index + 1}</Text>
                                </Box>
                                <AccordionIcon />
                              </AccordionButton>
                              <AccordionPanel pb={4}>
                                <Text fontWeight="bold" mb={1}>Input:</Text>
                                <Box bg="gray.50" p={2} borderRadius="md" mb={3}>
                                  <Text fontFamily="monospace" whiteSpace="pre-wrap">{testCase.input}</Text>
                                </Box>
                                <Text fontWeight="bold" mb={1}>Expected Output:</Text>
                                <Box bg="gray.50" p={2} borderRadius="md">
                                  <Text fontFamily="monospace" whiteSpace="pre-wrap">{testCase.output}</Text>
                                </Box>
                                {testCase.explanation && (
                                  <>
                                    <Text fontWeight="bold" mt={3} mb={1}>Explanation:</Text>
                                    <Text>{testCase.explanation}</Text>
                                  </>
                                )}
                              </AccordionPanel>
                            </AccordionItem>
                          ))}
                        </Accordion>
                </Box>
              )}
                    {/* Legacy example_test_cases support */}
                    {currentChallengeDetails.example_test_cases && currentChallengeDetails.example_test_cases.length > 0 && (
                      <Box>
                        <Heading size="sm" mb={2}>Example Test Cases</Heading>
              <Accordion allowMultiple defaultIndex={[0]}>
                          {currentChallengeDetails.example_test_cases.map((testCase, index) => (
                  <AccordionItem key={index}>
                      <AccordionButton>
                        <Box flex="1" textAlign="left">
                                  <Text fontWeight="bold">Example {index + 1}</Text>
                        </Box>
                        <AccordionIcon />
                      </AccordionButton>
                    <AccordionPanel pb={4}>
                                <Text fontWeight="bold" mb={1}>Input:</Text>
                                <Box bg="gray.50" p={2} borderRadius="md" mb={3}>
                                  <Text fontFamily="monospace" whiteSpace="pre-wrap">{testCase.input}</Text>
                        </Box>
                                <Text fontWeight="bold" mb={1}>Expected Output:</Text>
                                <Box bg="gray.50" p={2} borderRadius="md">
                                  <Text fontFamily="monospace" whiteSpace="pre-wrap">{testCase.output}</Text>
                        </Box>
                                {testCase.explanation && (
                                  <>
                                    <Text fontWeight="bold" mt={3} mb={1}>Explanation:</Text>
                                    <Text>{testCase.explanation}</Text>
                                  </>
                        )}
                    </AccordionPanel>
                  </AccordionItem>
                ))}
              </Accordion>
                      </Box>
                    )}
            </VStack>
          </TabPanel>

          {/* Code Editor Tab */}
          <TabPanel>
            <VStack spacing={4} align="stretch">
                    {/* Theme Toggle */}
              <FormControl display="flex" alignItems="center" justifyContent="flex-end">
                      <FormLabel htmlFor="theme-toggle" mb="0" fontSize="sm">
                  Dark Mode
                </FormLabel>
                <Switch 
                        id="theme-toggle" 
                        isChecked={editorTheme === 'dark' || editorTheme === 'materialDark'} 
                  onChange={handleThemeChange} 
                        colorScheme="brand"
                />
              </FormControl>

                    <Box>
              <CodeEditor
                code={code}
                language={language}
                        onChange={(value) => setCode(value)}
                theme={editorTheme === 'dark' ? 'materialDark' : 'light'}
                        height="350px"
                      />
                    </Box>
                    
                    <Heading size="sm">Standard Input</Heading>
                    <Textarea 
                      value={stdin}
                      onChange={(e) => setStdin(e.target.value)}
                      placeholder="Optional: Enter test inputs here..."
                      size="sm"
                      rows={2}
              />
                    
                    <HStack>
                <Button 
                        colorScheme="brand" 
                  onClick={handleRunCode}
                  isLoading={isRunningCode}
                  leftIcon={<FaPlay />}
                        flexGrow={1}
                >
                  Run Code
                </Button>
                <Button 
                  colorScheme="green" 
                  onClick={handleSubmit}
                        isLoading={isEvaluating}
                  leftIcon={<FaCheck />}
                        flexGrow={1}
                >
                        Submit
                </Button>
              </HStack>
              
                    {/* Output Display */}
                    {(stdout || stderr) && (
                      <Box>
                        <Heading size="sm" mb={2}>Output</Heading>
                        {stdout && (
                          <Box bg="gray.50" p={3} borderRadius="md" mb={3} maxH="120px" overflowY="auto">
                            <Text fontFamily="monospace" whiteSpace="pre-wrap">{stdout}</Text>
                </Box>
                        )}
                        {stderr && (
                          <Box bg="red.50" p={3} borderRadius="md" maxH="120px" overflowY="auto">
                            <Text fontFamily="monospace" color="red.600" whiteSpace="pre-wrap">{stderr}</Text>
                </Box>
                        )}
                      </Box>
                    )}
            </VStack>
          </TabPanel>
          
                {/* Results Tab */}
          {evaluationResult && (
            <TabPanel>
                    <VStack spacing={6} align="stretch">
                      {/* Overall Result */}
                      <Box>
                        <Alert 
                          status={(evaluationResult.overall_summary && evaluationResult.overall_summary.all_tests_passed) ? 'success' : 'error'}
                          borderRadius="md"
                        >
                    <AlertIcon />
                          <VStack align="start" spacing={1}>
                            <Text fontWeight="bold">
                              {(evaluationResult.overall_summary && evaluationResult.overall_summary.all_tests_passed) 
                                ? 'All test cases passed!' 
                                : 'Some test cases failed.'}
                            </Text>
                            {evaluationResult.overall_summary && (
                              <Text fontSize="sm">
                                {evaluationResult.overall_summary.pass_count || 0} of {evaluationResult.overall_summary.total_tests || 0} tests passed
                              </Text>
                            )}
                    </VStack>
                  </Alert>
                  </Box>

                      {/* Detailed Test Cases */}
                      {evaluationResult.execution_results && evaluationResult.execution_results.detailed_results && (
                        <Box>
                          <Heading size="sm" mb={3}>Test Case Details</Heading>
                    <Accordion allowMultiple>
                      {evaluationResult.execution_results.detailed_results.test_results && evaluationResult.execution_results.detailed_results.test_results.map((result, index) => (
                        <AccordionItem key={index}>
                            <AccordionButton>
                                  <Box flex="1" textAlign="left">
                                    <HStack>
                                      <Badge colorScheme={result.passed ? 'green' : 'red'}>
                                        {result.passed ? 'PASS' : 'FAIL'}
                                </Badge>
                                      <Text>Test Case {index + 1}</Text>
                              </HStack>
                                  </Box>
                              <AccordionIcon />
                            </AccordionButton>
                          <AccordionPanel pb={4}>
                                  <Text fontWeight="bold" mb={1}>Input:</Text>
                                  <Box bg="gray.50" p={2} borderRadius="md" mb={3}>
                                    <Text fontFamily="monospace" whiteSpace="pre-wrap">{result.input}</Text>
                                  </Box>
                                  <Text fontWeight="bold" mb={1}>Expected Output:</Text>
                                  <Box bg="gray.50" p={2} borderRadius="md" mb={3}>
                                    <Text fontFamily="monospace" whiteSpace="pre-wrap">{result.expected}</Text>
                                  </Box>
                                  <Text fontWeight="bold" mb={1}>Your Output:</Text>
                                  <Box bg={result.passed ? 'green.50' : 'red.50'} p={2} borderRadius="md">
                                    <Text fontFamily="monospace" whiteSpace="pre-wrap">{result.actual}</Text>
                                  </Box>
                                  {!result.passed && result.error && (
                                    <>
                                      <Text fontWeight="bold" mt={3} mb={1} color="red.500">Error:</Text>
                                      <Text color="red.500">{result.error}</Text>
                                    </>
                                  )}
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
          
          {/* Right side: Video call UI */}
          <Box
            bg={bgColor}
            overflowY="auto"
            h="100%"
            display="flex"
            flexDirection="column"
          >
            {/* Video display */}
            <Box 
              bg="gray.900" 
              height="60%" 
              p={4}
              position="relative"
              borderBottom="1px"
              borderColor={borderColor}
            >
              {/* AI avatar/video placeholder */}
              <Box
                bg="gray.800"
                borderRadius="md"
                h="100%"
                w="100%"
                display="flex"
                justifyContent="center"
                alignItems="center"
                position="relative"
                overflow="hidden"
              >
                {/* AI avatar image */}
                <Box
                  width="100%"
                  height="100%"
                  display="flex"
                  alignItems="center"
                  justifyContent="center"
                >
                  <Avatar
                    size="xl"
                    name="AI Interviewer"
                    src="/assets/ai-avatar.png"
                    bg="brand.500"
                  />
                </Box>
                
                {/* Speaking indicator */}
                <Box
                  position="absolute"
                  bottom="4"
                  left="0"
                  right="0"
                  display="flex"
                  justifyContent="center"
                >
                  <Badge 
                    colorScheme="green" 
                    variant="solid" 
                    px={2} 
                    py={1} 
                    borderRadius="full"
                    fontSize="xs"
                  >
                    AI Interviewer
                  </Badge>
                </Box>
              </Box>
            </Box>
            
            {/* Messages area */}
            <Box 
              w="100%" 
              flexGrow={1} 
              bg={messagesAreaBg}
              borderRadius="md"
              p={3}
              overflowY="auto"
              mb={4}
            >
              {messages.length === 0 ? (
                <Text color="gray.500" textAlign="center" py={10}>
                  Your conversation with the AI interviewer about the coding challenge will appear here.
                </Text>
              ) : (
                <VStack spacing={4} align="stretch">
                  {messages.map((msg, idx) => (
                    <Box 
                      key={idx}
                      bg={msg.role === 'user' ? userMessageBg : aiMessageBg}
                      color={messageTextColor}
                      p={3}
                      borderRadius="lg"
                      maxW="80%"
                      alignSelf={msg.role === 'user' ? 'flex-end' : 'flex-start'}
                      boxShadow="sm"
                    >
                      <Text>{msg.content}</Text>
                      <Text fontSize="xs" color="gray.500" textAlign="right" mt={1}>
                        {new Date(msg.timestamp).toLocaleTimeString()}
                                </Text>
                              </Box>
                  ))}
                </VStack>
              )}
            </Box>
            
            {/* Chat input */}
            <VStack spacing={2} p={3} borderTop="1px" borderColor={borderColor}>
              <HStack w="100%">
                <Input
                  placeholder="Ask for help or clarification..."
                  value={chatMessage}
                  onChange={(e) => setChatMessage(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && handleSendMessageWithAudio()}
                  bg={inputBg}
                  flex="1"
                />
                <IconButton
                  colorScheme={micEnabled ? "brand" : "gray"}
                  aria-label={micEnabled ? "Disable microphone" : "Enable microphone"}
                  icon={micEnabled ? <Icon as={FaMicrophone} /> : <Icon as={FaMicrophoneSlash} />}
                  onClick={toggleMicrophone}
                  mr={2}
                  isDisabled={!isVideoCall}
                  title={isVideoCall ? (micEnabled ? "Disable microphone" : "Enable microphone") : "Voice mode disabled"}
                />
                <IconButton
                  colorScheme="brand"
                  aria-label="Send message"
                  icon={<FaPaperPlane />}
                  onClick={handleSendMessageWithAudio}
                  isLoading={isLoadingResponse}
                />
              </HStack>
              
              {isListening && (
                <HStack w="100%" spacing={2} alignItems="center">
                  <Box bg="red.400" h="8px" w="8px" borderRadius="full" 
                       animation="pulse 1.5s infinite" />
                  <Text fontSize="xs" color="gray.500">
                    {interimTranscript ? 'Listening: ' + interimTranscript : 'Listening...'}
                                </Text>
                </HStack>
              )}
              
              {/* Return to interviewer button */}
              {evaluationResult && evaluationResult.status === 'success' && (
                <Button
                  colorScheme="green"
                  onClick={handleReturnToInterviewer}
                  isLoading={isSubmitting}
                  leftIcon={<FaCheck />}
                  w="100%"
                >
                  Submit Solution & Return to Interview
                </Button>
              )}
            </VStack>
                              </Box>
        </Grid>
      ) : (
        // Original single-column layout
        <Box
          w="100%"
          bg={bgColor}
          borderColor="gray.200"
          overflowY="auto"
          h="100%"
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
          </Box>
          
          {/* Challenge Tabs */}
          <Tabs variant="enclosed">
            <TabList>
              <Tab>Problem</Tab>
              <Tab>Code</Tab>
              {evaluationResult && <Tab>Results</Tab>}
              <Tab>Chat</Tab>
            </TabList>
            
            <TabPanels>
              {/* Problem Description Tab */}
              <TabPanel>
                <VStack align="stretch" spacing={4}>
                              <Box>
                    <Heading size="sm" mb={2}>Problem Statement</Heading>
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
                  {/* Example Test Cases Section */}
                  {currentChallengeDetails.test_cases && currentChallengeDetails.test_cases.length > 0 && (
                    <Box>
                      <Heading size="sm" mb={2}>Example Test Cases</Heading>
                      <Accordion allowMultiple defaultIndex={[0]}>
                        {currentChallengeDetails.test_cases.map((testCase, index) => (
                          <AccordionItem key={index}>
                            <AccordionButton>
                              <Box flex="1" textAlign="left">
                                <Text fontWeight="bold">Example {index + 1}</Text>
                              </Box>
                              <AccordionIcon />
                            </AccordionButton>
                            <AccordionPanel pb={4}>
                              <Text fontWeight="bold" mb={1}>Input:</Text>
                              <Box bg="gray.50" p={2} borderRadius="md" mb={3}>
                                <Text fontFamily="monospace" whiteSpace="pre-wrap">{testCase.input}</Text>
                              </Box>
                              <Text fontWeight="bold" mb={1}>Expected Output:</Text>
                              <Box bg="gray.50" p={2} borderRadius="md">
                                <Text fontFamily="monospace" whiteSpace="pre-wrap">{testCase.output}</Text>
                              </Box>
                              {testCase.explanation && (
                                <>
                                  <Text fontWeight="bold" mt={3} mb={1}>Explanation:</Text>
                                  <Text>{testCase.explanation}</Text>
                                </>
                              )}
                          </AccordionPanel>
                        </AccordionItem>
                      ))}
                    </Accordion>
                    </Box>
                  )}
                  {/* Legacy example_test_cases support */}
                  {currentChallengeDetails.example_test_cases && currentChallengeDetails.example_test_cases.length > 0 && (
                    <Box>
                      <Heading size="sm" mb={2}>Example Test Cases</Heading>
                      <Accordion allowMultiple defaultIndex={[0]}>
                        {currentChallengeDetails.example_test_cases.map((testCase, index) => (
                          <AccordionItem key={index}>
                            <AccordionButton>
                              <Box flex="1" textAlign="left">
                                <Text fontWeight="bold">Example {index + 1}</Text>
                              </Box>
                              <AccordionIcon />
                            </AccordionButton>
                            <AccordionPanel pb={4}>
                              <Text fontWeight="bold" mb={1}>Input:</Text>
                              <Box bg="gray.50" p={2} borderRadius="md" mb={3}>
                                <Text fontFamily="monospace" whiteSpace="pre-wrap">{testCase.input}</Text>
                              </Box>
                              <Text fontWeight="bold" mb={1}>Expected Output:</Text>
                              <Box bg="gray.50" p={2} borderRadius="md">
                                <Text fontFamily="monospace" whiteSpace="pre-wrap">{testCase.output}</Text>
                              </Box>
                              {testCase.explanation && (
                                <>
                                  <Text fontWeight="bold" mt={3} mb={1}>Explanation:</Text>
                                  <Text>{testCase.explanation}</Text>
                  </>
                )}
                            </AccordionPanel>
                          </AccordionItem>
                        ))}
                      </Accordion>
                    </Box>
                  )}
                      </VStack>
              </TabPanel>
              
              {/* Code Editor Tab */}
              <TabPanel>
                <VStack spacing={4} align="stretch">
                  {/* Theme Toggle */}
                  <FormControl display="flex" alignItems="center" justifyContent="flex-end">
                    <FormLabel htmlFor="theme-toggle" mb="0" fontSize="sm">
                      Dark Mode
                    </FormLabel>
                    <Switch 
                      id="theme-toggle" 
                      isChecked={editorTheme === 'dark' || editorTheme === 'materialDark'} 
                      onChange={handleThemeChange} 
                      colorScheme="brand"
                    />
                  </FormControl>
                  
                  <Box>
                    <CodeEditor
                      code={code}
                      language={language}
                      onChange={(value) => setCode(value)}
                      theme={editorTheme === 'dark' ? 'materialDark' : 'light'}
                      height="400px"
                    />
                  </Box>
                  
                  <Heading size="sm">Standard Input</Heading>
                  <Textarea 
                    value={stdin}
                    onChange={(e) => setStdin(e.target.value)}
                    placeholder="Optional: Enter test inputs here..."
                    size="sm"
                    rows={3}
                  />
                  
                  <HStack>
                    <Button 
                      colorScheme="brand" 
                      onClick={handleRunCode} 
                      isLoading={isRunningCode}
                      leftIcon={<FaPlay />}
                      flexGrow={1}
                    >
                      Run Code
                    </Button>
                    <Button 
                      colorScheme="green" 
                      onClick={handleSubmit} 
                      isLoading={isEvaluating}
                      leftIcon={<FaCheck />}
                      flexGrow={1}
                    >
                      Submit
                    </Button>
                  </HStack>
                  
                  {/* Output Display */}
                  {(stdout || stderr) && (
                    <Box>
                      <Heading size="sm" mb={2}>Output</Heading>
                      {stdout && (
                        <Box bg="gray.50" p={3} borderRadius="md" mb={3} maxH="200px" overflowY="auto">
                          <Text fontFamily="monospace" whiteSpace="pre-wrap">{stdout}</Text>
                        </Box>
                      )}
                      {stderr && (
                        <Box bg="red.50" p={3} borderRadius="md" maxH="200px" overflowY="auto">
                          <Text fontFamily="monospace" color="red.600" whiteSpace="pre-wrap">{stderr}</Text>
                  </Box>
                )}
                    </Box>
                  )}
                </VStack>
              </TabPanel>

              {/* Results Tab */}
              {evaluationResult && (
                <TabPanel>
                  <VStack spacing={6} align="stretch">
                    {/* Overall Result */}
                  <Box>
                      <Alert 
                        status={(evaluationResult.overall_summary && evaluationResult.overall_summary.all_tests_passed) ? 'success' : 'error'}
                        borderRadius="md"
                      >
                        <AlertIcon />
                        <VStack align="start" spacing={1}>
                          <Text fontWeight="bold">
                            {(evaluationResult.overall_summary && evaluationResult.overall_summary.all_tests_passed) 
                              ? 'All test cases passed!' 
                              : 'Some test cases failed.'}
                          </Text>
                          {evaluationResult.overall_summary && (
                            <Text fontSize="sm">
                              {evaluationResult.overall_summary.pass_count || 0} of {evaluationResult.overall_summary.total_tests || 0} tests passed
                            </Text>
                          )}
                        </VStack>
                      </Alert>
                    </Box>
                    
                    {/* Detailed Test Cases */}
                    {evaluationResult.execution_results && evaluationResult.execution_results.detailed_results && (
                      <Box>
                        <Heading size="sm" mb={3}>Test Case Details</Heading>
                        {evaluationResult.execution_results.detailed_results.test_results && 
                         evaluationResult.execution_results.detailed_results.test_results.length > 0 ? (
                    <Accordion allowMultiple>
                            {evaluationResult.execution_results.detailed_results.test_results.map((result, index) => (
                        <AccordionItem key={index}>
                            <AccordionButton>
                              <Box flex="1" textAlign="left">
                                        <HStack>
                                          <Badge colorScheme={result.passed ? 'green' : 'red'}>
                                            {result.passed ? 'PASS' : 'FAIL'}
                                    </Badge>
                                          <Text>Test Case {index + 1}</Text>
                                  </HStack>
                              </Box>
                              <AccordionIcon />
                            </AccordionButton>
                          <AccordionPanel pb={4}>
                                      <Text fontWeight="bold" mb={1}>Input:</Text>
                                      <Box bg="gray.50" p={2} borderRadius="md" mb={3}>
                                        <Text fontFamily="monospace" whiteSpace="pre-wrap">{result.input}</Text>
                                      </Box>
                                      <Text fontWeight="bold" mb={1}>Expected Output:</Text>
                                      <Box bg="gray.50" p={2} borderRadius="md" mb={3}>
                                        <Text fontFamily="monospace" whiteSpace="pre-wrap">{result.expected}</Text>
                                      </Box>
                                      <Text fontWeight="bold" mb={1}>Your Output:</Text>
                                      <Box bg={result.passed ? 'green.50' : 'red.50'} p={2} borderRadius="md">
                                        <Text fontFamily="monospace" whiteSpace="pre-wrap">{result.actual}</Text>
                                      </Box>
                                      {!result.passed && result.error && (
                                        <>
                                          <Text fontWeight="bold" mt={3} mb={1} color="red.500">Error:</Text>
                                          <Text color="red.500">{result.error}</Text>
                                        </>
                                      )}
                          </AccordionPanel>
                        </AccordionItem>
                      ))}
                    </Accordion>
                            ) : (
                              <Box p={4} bg="gray.50" borderRadius="md">
                                <Text>
                                  {evaluationResult.execution_results.error || 
                                   evaluationResult.execution_results.detailed_results.error_message ||
                                   "No detailed test results available."}
                                </Text>
                  </Box>
                )}
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
                
                {/* Chat Tab */}
                <TabPanel>
                  <VStack spacing={4} align="stretch" h="500px">
                    {/* Messages area */}
                    <Box 
                      w="100%" 
                      flexGrow={1} 
                      bg={messagesAreaBg}
                      borderRadius="md"
                      p={3}
                      overflowY="auto"
                      mb={4}
                      h="400px"
                    >
                      {messages.length === 0 ? (
                        <Text color="gray.500" textAlign="center" py={10}>
                          Your conversation with the AI interviewer about the coding challenge will appear here.
                        </Text>
                      ) : (
                        <VStack spacing={4} align="stretch">
                          {messages.map((msg, idx) => (
                            <Box 
                              key={idx}
                              bg={msg.role === 'user' ? userMessageBg : aiMessageBg}
                              color={messageTextColor}
                              p={3}
                              borderRadius="lg"
                              maxW="80%"
                              alignSelf={msg.role === 'user' ? 'flex-end' : 'flex-start'}
                              boxShadow="sm"
                            >
                              <Text>{msg.content}</Text>
                              <Text fontSize="xs" color="gray.500" textAlign="right" mt={1}>
                                {new Date(msg.timestamp).toLocaleTimeString()}
                              </Text>
                            </Box>
                          ))}
                        </VStack>
                      )}
                    </Box>
                    
                    {/* Chat input */}
                    <VStack spacing={2} p={3} borderTop="1px" borderColor={borderColor}>
                      <HStack w="100%">
                        <Input
                          placeholder="Ask for help or clarification..."
                          value={chatMessage}
                          onChange={(e) => setChatMessage(e.target.value)}
                          onKeyPress={(e) => e.key === 'Enter' && handleSendMessageWithAudio()}
                          bg={inputBg}
                          flex="1"
                        />
                        <IconButton
                          colorScheme={micEnabled ? "brand" : "gray"}
                          aria-label={micEnabled ? "Disable microphone" : "Enable microphone"}
                          icon={micEnabled ? <Icon as={FaMicrophone} /> : <Icon as={FaMicrophoneSlash} />}
                          onClick={toggleMicrophone}
                          mr={2}
                          title={micEnabled ? "Disable microphone" : "Enable microphone"}
                        />
                        <IconButton
                          colorScheme="brand"
                          aria-label="Send message"
                          icon={<FaPaperPlane />}
                          onClick={handleSendMessageWithAudio}
                          isLoading={isLoadingResponse}
                        />
                      </HStack>
                      
                      {isListening && (
                        <HStack w="100%" spacing={2} alignItems="center">
                          <Box bg="red.400" h="8px" w="8px" borderRadius="full" 
                               animation="pulse 1.5s infinite" />
                          <Text fontSize="xs" color="gray.500">
                            {interimTranscript ? 'Listening: ' + interimTranscript : 'Listening...'}
                          </Text>
                        </HStack>
                      )}
                    </VStack>
                  </VStack>
                </TabPanel>
        </TabPanels>
      </Tabs>
          </Box>
        )}
    </Box>
  );
};

export default CodingChallenge; 