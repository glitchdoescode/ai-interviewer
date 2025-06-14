import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Container,
  Grid,
  GridItem,
  Heading,
  Text,
  Badge,
  Button,
  Alert,
  AlertIcon,
  useToast,
  useDisclosure,
  Modal,
  ModalOverlay,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  ModalCloseButton,
  HStack,
  VStack,
  Icon,
  IconButton,
  Tooltip,
  Switch,
} from '@chakra-ui/react';
import { FaInfoCircle, FaHistory, FaCheckCircle, FaChevronRight, FaChevronLeft } from 'react-icons/fa';
import Navbar from '../components/Navbar';
import ChatInterface from '../components/ChatInterface';
import CodingChallenge from '../components/CodingChallenge';
import ProctoringPanel from '../components/proctoring/ProctoringPanel';
import { useInterview } from '../context/InterviewContext';
import { checkVoiceAvailability, submitChallengeFeedbackToServer, continueInterview } from '../api/interviewService';
import InterviewSetupWizard from '../components/InterviewSetupWizard';
import FaceAuthenticationManager from '../components/proctoring/FaceAuthenticationManager';
import VideoCallInterface from '../components/VideoCallInterface';
import InterviewResults from '../components/InterviewResults';
import ChatMessage from '../components/ChatMessage';
import './Interview.css';

/**
 * Interview page component
 */
const Interview = () => {
  const { sessionId: urlSessionId } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const { 
    isOpen: isEndInterviewModalOpen, 
    onOpen: onOpenEndInterviewModal, 
    onClose: onCloseEndInterviewModal 
  } = useDisclosure();

  const { 
    isOpen: isEnrollmentModalOpen, 
    onOpen: onOpenEnrollmentModal, 
    onClose: onCloseEnrollmentModal 
  } = useDisclosure();
  
  const {
    userId,
    sessionId,
    messages,
    loading,
    error,
    interviewStage,
    jobRoleData: selectedJobRole,
    currentCodingChallenge,
    addMessage,
    setSessionId,
    setLoading,
    setError,
    setInterviewStage,
    resetInterview,
    setVoiceMode,
    voiceMode,
    setJobRoleData,
    setCurrentCodingChallenge,
    setMessages,
  } = useInterview();

  const [isVoiceAvailable, setIsVoiceAvailable] = useState(true);
  const [showJobSelector, setShowJobSelector] = useState(true);
  const [isInfoModalOpen, setIsInfoModalOpen] = useState(false);
  const [proctoringStatus, setProctoringStatus] = useState({
    isActive: false,
    hasCamera: false,
    hasDetection: false,
    hasWebSocket: false,
  });
  const [currentAudioUrl, setCurrentAudioUrl] = useState(null);
  const [autoPlayAudio, setAutoPlayAudio] = useState(true);

  // Sidebar collapse state
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [sidebarHovered, setSidebarHovered] = useState(false);

  // New state variables for enrollment flow
  const [isEnrolling, setIsEnrolling] = useState(false);
  const [enrollmentProcessComplete, setEnrollmentProcessComplete] = useState(false);
  const [temporaryEmbedding, setTemporaryEmbedding] = useState(null);
  const [proctoringEffectivelyEnabled, setProctoringEffectivelyEnabled] = useState(false);
  
  // Ref for the video element used by face authentication
  const videoRef = React.useRef(null); 
  const proctoringToastShownRef = React.useRef(false);

  // New combined state for enabling the ProctoringPanel and its underlying WebcamMonitor's camera
  const proctoringIsEnabledForPanel = proctoringEffectivelyEnabled || (isEnrollmentModalOpen && isEnrolling);

  // Audio playback function
  const playAudioResponse = (audioUrl) => {
    if (!audioUrl) return;
    
    const audio = new Audio(audioUrl);
    audio.play().catch(err => {
      console.error('Error playing audio:', err);
      toast({
        title: 'Audio Playback Failed',
        description: 'Could not play audio response',
        status: 'warning',
        duration: 3000,
        isClosable: true,
      });
    });
  };

  // Check if the requested session ID should be loaded
  useEffect(() => {
    if (urlSessionId && urlSessionId !== sessionId) {
      // Set the session ID from the URL
      setSessionId(urlSessionId);
      
      // Show toast notification
      toast({
        title: 'Session Loaded',
        description: `Resuming interview session: ${urlSessionId}`,
        status: 'info',
        duration: 3000,
        isClosable: true,
      });
    }
  }, [urlSessionId, sessionId, setSessionId, toast]);

  // Check if voice processing is available
  useEffect(() => {
    const checkVoice = async () => {
      try {
        const isAvailable = await checkVoiceAvailability();
        setIsVoiceAvailable(isAvailable);
        
        // If voice is not available but voice mode is enabled, disable it
        if (!isAvailable && voiceMode) {
          setVoiceMode(false);
          toast({
            title: 'Voice Mode Disabled',
            description: 'Voice processing is not available on the server.',
            status: 'warning',
            duration: 5000,
            isClosable: true,
          });
        }
      } catch (err) {
        setError('Error checking voice availability');
        setIsVoiceAvailable(false);
      }
    };
    
    checkVoice();
  }, [setError, setVoiceMode, voiceMode, toast]);

  // Debug: Track interview stage changes
  useEffect(() => {
    console.log('[Interview] =================== INTERVIEW STAGE CHANGED ===================');
    console.log('[Interview] New interview stage:', interviewStage);
    console.log('[Interview] Stage type:', typeof interviewStage);
    console.log('[Interview] Component re-rendered due to stage change');
    
    // Add debugging for conclusion stage
    if (interviewStage === 'conclusion') {
      console.log('[Interview] CONCLUSION STAGE DETECTED');
      console.log('[Interview] Current session ID:', sessionId);
      console.log('[Interview] Current messages count:', messages.length);
      
      // Store the session ID in localStorage for fallback use
      if (sessionId) {
        localStorage.setItem('lastSessionId', sessionId);
        console.log('[Interview] Session ID saved to localStorage:', sessionId);
      }
    }
    
    console.log('[Interview] ========================================');
  }, [interviewStage, sessionId, messages.length]);

  // Defensive wrapper for setInterviewStage to ensure only strings are set
  const safeSetInterviewStage = useCallback((stage) => {
    console.log('[Interview] safeSetInterviewStage called with:', stage, 'type:', typeof stage);
    
    if (typeof stage === 'string') {
      setInterviewStage(stage);
    } else if (stage !== null && stage !== undefined) {
      console.warn('[Interview] Non-string value passed to setInterviewStage:', stage, 'Converting to string');
      setInterviewStage(String(stage));
    } else {
      console.warn('[Interview] null/undefined value passed to setInterviewStage, ignoring');
    }
  }, [setInterviewStage]);

  // Handle job role selection
  const handleRoleSelect = (roleData) => {
    setJobRoleData(roleData);
  };
  
  // Handle starting interview with selected role
  const handleStartInterview = () => {
    setShowJobSelector(false);
    setIsEnrolling(true);
    setEnrollmentProcessComplete(false); 
    setTemporaryEmbedding(null);        
    setProctoringEffectivelyEnabled(false); // This will be true later, after session ID and enrollment
    
    // Don't generate sessionId here - it should come from the backend API response
    // The sessionId will be set when the first API call is made in VideoCallInterface
    
    // Open enrollment modal to start face authentication
    onOpenEnrollmentModal(); 
    
      toast({
        title: "Interview Started",
      description: `Your interview for ${selectedJobRole.role_name} (${selectedJobRole.seniority_level}) has begun.`,
        status: "success",
        duration: 3000,
        isClosable: true,
      });
  };

  // Handle wizard completion
  const handleWizardComplete = (roleData) => {
    console.log('Wizard completed with role data:', roleData);
    setJobRoleData(roleData);
    handleStartInterview();
  };

  // Handle wizard cancellation
  const handleWizardCancel = () => {
    // Reset state and potentially navigate away
    setShowJobSelector(true);
    setJobRoleData(null);
  };

  // Sidebar toggle function
  const toggleSidebar = () => {
    setSidebarCollapsed(!sidebarCollapsed);
  };

  // New callbacks for enrollment process
  const handleInitialEnrollmentSuccess = (embedding) => {
    toast({
      title: 'Enrollment Successful',
      description: 'Your face has been enrolled.',
      status: 'success',
      duration: 3000,
      isClosable: true,
    });
    setTemporaryEmbedding(embedding);
    setEnrollmentProcessComplete(true);
    setIsEnrolling(false);
    onCloseEnrollmentModal();
  };

  const handleInitialEnrollmentFailure = (errorMsg) => {
    toast({
      title: 'Enrollment Failed',
      description: (errorMsg?.message || String(errorMsg)) || 'Could not enroll face. Please try again.',
      status: 'error',
      duration: 5000,
      isClosable: true,
    });
    // Modal remains open for retry, FaceEnrollment component handles retries
  };
  
  const handleEnrollmentModalClose = () => {
    if (isEnrolling && !enrollmentProcessComplete) { // Check if still enrolling and not completed
      toast({
        title: 'Enrollment Cancelled',
        description: 'Face enrollment was not completed. Proctoring will be disabled.',
        status: 'warning',
        duration: 3000,
        isClosable: true,
      });
      setIsEnrolling(false); // Stop enrollment process
      // Optionally, reset interview or prevent progress if enrollment is mandatory
    }
    onCloseEnrollmentModal();
  };

  // Corrected useEffect for proctoringEffectivelyEnabled. 
  // This enables the *continuous proctoring part* after enrollment and session ID exist.
  useEffect(() => {
    if (sessionId && enrollmentProcessComplete && temporaryEmbedding) {
      setProctoringEffectivelyEnabled(true);
      // Toast moved to ProctoringPanel for when it actually becomes active
      // Reset toast shown flag when proctoring becomes effectively enabled, so it can show again for this session.
      proctoringToastShownRef.current = false; 
    } else {
      setProctoringEffectivelyEnabled(false);
    }
  }, [sessionId, enrollmentProcessComplete, temporaryEmbedding]);

  // Handle proctoring status changes
  const handleProctoringStatusChange = (status) => {
    setProctoringStatus(status);
    
    if (status.isActive && status.hasCamera && status.hasDetection && status.hasWebSocket && !proctoringToastShownRef.current) {
      toast({
        title: 'Proctoring Active',
        description: 'AI proctoring is now monitoring the interview',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });
      proctoringToastShownRef.current = true; // Mark toast as shown for this session
    }
  };
  
  // Handle ending the interview
  const handleEndInterview = () => {
    onCloseEndInterviewModal();
    setProctoringEffectivelyEnabled(false);
    proctoringToastShownRef.current = false; // Reset for next interview
    
    // Store the session ID in localStorage
    if (sessionId) {
      localStorage.setItem('lastSessionId', sessionId);
      console.log('[Interview] handleEndInterview - Session ID saved to localStorage:', sessionId);
    }
    
    // Set interview stage to conclusion instead of resetting the interview
    safeSetInterviewStage('conclusion');
    
    toast({
      title: 'Interview Ended',
      description: 'Your interview has been completed.',
      status: 'info',
      duration: 3000,
      isClosable: true,
    });
  };

  // New handler to be passed to CodingChallenge for when feedback is submitted
  const handleCodingFeedbackSubmitted = async (detailedMessageToAI, evaluationSummary) => {
    try {
      console.log('handleCodingFeedbackSubmitted called with message length:', detailedMessageToAI?.length || 0);
      console.log('evaluationSummary:', evaluationSummary);
      
      setLoading(true);
      
      // Force reset messages array if it's not already an array
      if (!Array.isArray(messages)) {
        console.warn('[Interview] messages is not an array in handleCodingFeedbackSubmitted, resetting to empty array');
        setMessages([]);
      }
      
      // Create a better formatted message for the AI with clear indicators
      const formattedMessage = `SYSTEM: The candidate has completed the coding challenge and is now returning for feedback.
Challenge ID: ${evaluationSummary?.challenge_id || 'unknown'}
Language: ${evaluationSummary?.language || 'python'}
Code:
\`\`\`${evaluationSummary?.language || 'python'}
${evaluationSummary?.code || '// No code provided'}
\`\`\`

Execution Results: ${evaluationSummary?.all_tests_passed ? 'ALL TESTS PASSED' : 'SOME TESTS FAILED'}
Pass Rate: ${evaluationSummary?.pass_count || 0}/${evaluationSummary?.total_tests || 0}

IMPORTANT INSTRUCTIONS:
1. DO NOT provide a generic greeting or introduction
2. DO NOT ask how you can help
3. DO NOT mention "continuing from where we left off"
4. IMMEDIATELY provide specific, detailed feedback on the code submission
5. FOCUS ONLY on the code quality, efficiency, and test results
6. Use the test results data above to inform your feedback`;

      // Force the transition to feedback mode before submitting
      setInterviewStage('feedback');
      
      // Add a "transitioning" message to the UI to show we're processing
      const transitionMessage = {
        sender: 'assistant',
        text: 'Analyzing your code submission...',
        isLoading: true,
        isFeedback: true,
      };
      
      // Add transition message safely
      setMessages(prev => {
        // Ensure prev is an array
        const prevMessages = Array.isArray(prev) ? prev : [];
        return [...prevMessages, transitionMessage];
      });
      
      // Submit the feedback request to the server
      const response = await submitChallengeFeedbackToServer(
        sessionId,
        userId,
        formattedMessage,
        evaluationSummary,
        true
      );
      
      if (response?.data) {
        console.log('Feedback response:', response.data);
        
        // Check if this is a generic greeting
        const responseText = response.data.response?.toLowerCase() || '';
        const isGenericGreeting = /^(hello|hi|greetings|welcome|i see you|let me continue|good to see you|thank you for completing)/i.test(responseText.trim());
        
        // Remove the loading transition message safely
        setMessages(prev => {
          const prevMessages = Array.isArray(prev) ? prev : [];
          return prevMessages.filter(msg => !msg.isLoading);
        });
        
        if (isGenericGreeting) {
          console.warn('DETECTED GENERIC GREETING in feedback! Showing error message instead.');
          
          // Add a message explaining the issue to the user safely
          const feedbackErrorMessage = {
            sender: 'assistant',
            text: `I've received your code submission, but instead of giving specific feedback, the AI provided a generic greeting. 
            
Please send a message asking for specific feedback on your code.`,
            isGenericResponse: true,
            isFeedback: true
          };
          
          setMessages(prev => {
            const prevMessages = Array.isArray(prev) ? prev : [];
            return [...prevMessages, feedbackErrorMessage];
          });
        } else {
          // Add the proper feedback message safely
          const feedbackMessage = {
            sender: 'assistant',
            text: response.data.response,
            audioUrl: response.data.audio_response_url,
            isFeedback: response.data.isFeedback || true
          };
          
          setMessages(prev => {
            const prevMessages = Array.isArray(prev) ? prev : [];
            return [...prevMessages, feedbackMessage];
          });
        }
        
        // Update session context and UI
        setInterviewStage(response.data.interview_stage || 'feedback');
        setLoading(false);
      } else {
        console.error('Invalid response from submitChallengeFeedbackToServer:', response);
        setLoading(false);
        
        // Handle error by showing error message safely
        const serverErrorMessage = {
          sender: 'assistant',
          text: 'I encountered an error analyzing your code. Please try sending a message asking for specific feedback.',
          isError: true
        };
        
        setMessages(prev => {
          const prevMessages = Array.isArray(prev) ? prev : [];
          // Remove any loading messages
          const filteredMessages = prevMessages.filter(msg => !msg.isLoading);
          return [...filteredMessages, serverErrorMessage];
        });
      }
    } catch (error) {
      console.error('Error submitting coding feedback:', error);
      setLoading(false);
      
      // Handle error by showing error message safely
      const clientErrorMessage = {
        sender: 'assistant',
        text: 'I encountered an error analyzing your code. Please try sending a message to ask for feedback.',
        isError: true
      };
      
      setMessages(prev => {
        const prevMessages = Array.isArray(prev) ? prev : [];
        // Remove any loading messages
        const filteredMessages = prevMessages.filter(msg => !msg.isLoading);
        return [...filteredMessages, clientErrorMessage];
      });
    }
  };

  // Handle sessionId received from backend API
  const handleSessionIdReceived = useCallback((newSessionId) => {
    if (newSessionId && newSessionId !== sessionId) {
      console.log(`Updating sessionId from ${sessionId} to ${newSessionId}`);
      setSessionId(newSessionId);
    }
  }, [sessionId]);

  // Get stage badge color based on interview stage
  const getStageBadgeColor = (stage) => {
    switch (stage) {
      case 'introduction':
        return 'blue';
      case 'technical_questions':
        return 'purple';
      case 'coding_challenge':
      case 'coding_challenge_waiting':
        return 'orange';
      case 'feedback':
        return 'green';
      case 'conclusion':
        return 'red';
      default:
        return 'gray';
    }
  };

  // Set up interview view switching based on stage
  useEffect(() => {
    console.log('[Interview] Stage effect triggered with stage:', interviewStage);
    
    if (interviewStage === 'coding_challenge' || interviewStage === 'coding_challenge_waiting') {
      if (currentCodingChallenge) {
        console.log('[Interview] Showing coding challenge interface');
      } else {
        console.log('[Interview] Coding challenge stage but no challenge data yet');
      }
    } else if (interviewStage === 'feedback') {
      // If we're in feedback stage, hide coding challenge UI
      console.log('[Interview] Entered feedback stage, hiding coding challenge UI');
      setCurrentCodingChallenge(null);

      // Only show the toast if we're transitioning from coding_challenge or coding_challenge_waiting
      const lastStage = localStorage.getItem('lastInterviewStage');
      if (lastStage && (lastStage === 'coding_challenge' || lastStage === 'coding_challenge_waiting')) {
        toast({
          title: 'Code Review',
          description: 'The interviewer is now providing feedback on your code.',
          status: 'info',
          duration: 3000,
          isClosable: true,
        });
      }
      
      // Store current stage for future reference
      localStorage.setItem('lastInterviewStage', 'feedback');
    } else {
      // Store current stage for future reference
      localStorage.setItem('lastInterviewStage', interviewStage);
    }
  }, [interviewStage, currentCodingChallenge, toast]);
  
  // Special effect to monitor transitions to feedback stage
  useEffect(() => {
    // This specifically watches for the case where we're transitioning to feedback
    // from a coding challenge
    if (interviewStage === 'feedback' && sessionId) {
      console.log('[Interview] Monitoring feedback stage after coding challenge');
      
      // Check if we need to send an initial message to trigger proper feedback
      const hasRecentFeedbackMessage = messages.slice(-5).some(msg => 
        msg.sender === 'assistant' && (msg.isFeedback || /code|solution|review|feedback/i.test(msg.text))
      );
      
      if (!hasRecentFeedbackMessage) {
        console.log('[Interview] No feedback detected yet, preparing to request specific feedback');
        
        // Only show this if we don't already have a transition message
        const hasTransitionMessage = messages.some(msg => msg.isTransition);
        
        if (!hasTransitionMessage) {
          // Add a user-facing message explaining the situation
          const helpMessage = {
            sender: 'assistant',
            text: 'I\'m preparing feedback on your code submission. If you don\'t see specific code feedback shortly, please send a message asking "Can you provide feedback on my code solution?"',
            isTransition: true,
          };
          
          setMessages(prev => {
            const prevMessages = Array.isArray(prev) ? prev : [];
            return [...prevMessages, helpMessage];
          });
        }
      }
    }
  }, [interviewStage, sessionId, messages]);

  // Initialize messages as an array if it's not already one
  useEffect(() => {
    if (!Array.isArray(messages)) {
      console.warn('[Interview] messages is not an array in initial mount, initializing as empty array');
      setMessages([]);
    }
  }, []);  // Empty dependency array means this runs once on mount

  // Special handler for ensuring messages display properly during stage transitions
  useEffect(() => {
    // Fix for message property inconsistency (some components use text, others use content)
    const normalizeMessages = () => {
      // Only process if we have messages and messages is an array
      if (!messages || !Array.isArray(messages) || messages.length === 0) {
        console.warn('[Interview] messages is not an array or is empty:', messages);
        return;
      }
      
      let needsUpdate = false;
      const normalized = messages.map(msg => {
        // Create a new object to avoid mutating the original
        const normalizedMsg = { ...msg };
        
        // Ensure sender property exists (instead of role)
        if (!normalizedMsg.sender && normalizedMsg.role) {
          normalizedMsg.sender = normalizedMsg.role;
          needsUpdate = true;
        }
        
        // Ensure text property exists (instead of content)
        if (!normalizedMsg.text && normalizedMsg.content) {
          normalizedMsg.text = normalizedMsg.content;
          needsUpdate = true;
        }
        
        return normalizedMsg;
      });
      
      if (needsUpdate) {
        console.log('[Interview] Normalized messages to ensure consistent properties');
        setMessages(normalized);
      }
    };
    
    normalizeMessages();
  }, [messages]);

  // Ensure stage synchronization immediately after returning from coding challenge
  useEffect(() => {
    // Check if messages is an array before proceeding
    if (!Array.isArray(messages)) {
      console.warn('[Interview] Stage sync effect: messages is not an array:', messages);
      return;
    }
    
    // Only run this when we have a session but no current coding challenge
    // and we're not already in feedback stage
    if (sessionId && 
        !currentCodingChallenge && 
        interviewStage !== 'feedback' && 
        messages.length > 0 && 
        messages[messages.length - 1].sender === 'assistant') {
      
      // Check if the last message appears to be feedback-related
      const lastMessage = messages[messages.length - 1];
      const lastMessageText = lastMessage.text?.toLowerCase() || '';
      
      // More robust feedback detection
      const containsFeedbackSignals = 
        lastMessageText.includes('your solution') || 
        lastMessageText.includes('your code') || 
        lastMessageText.includes('your implementation') ||
        lastMessageText.includes('correctness:') ||
        lastMessageText.includes('efficiency:') ||
        lastMessageText.includes('readability:') ||
        lastMessageText.includes('style:') ||
        lastMessageText.includes('test case') ||
        lastMessageText.includes('complexity') ||
        lastMessage.isFeedback === true;
      
      console.log('[Interview] Last message contains feedback signals:', containsFeedbackSignals);
      
      if (containsFeedbackSignals) {
        console.log('[Interview] Detected feedback content in message. Forcing stage to feedback');
        
        // Force transition to feedback stage and mark message as feedback
        setInterviewStage('feedback');
        
        // Update this message to be explicitly marked as feedback
        const updatedMessages = [...messages];
        updatedMessages[updatedMessages.length - 1] = {
          ...lastMessage,
          isFeedback: true
        };
        
        setMessages(updatedMessages);
      }
    }
    
    // If we're in feedback stage but the challenge is still showing,
    // clear it to show the feedback interface
    if (interviewStage === 'feedback' && currentCodingChallenge) {
      console.log('[Interview] In feedback stage but challenge still showing - clearing challenge UI');
      setCurrentCodingChallenge(null);
    }
    
  }, [interviewStage, sessionId, messages, currentCodingChallenge, setInterviewStage, setMessages, setCurrentCodingChallenge]);

  // Function to send a message and get a response
  const sendMessage = async (message) => {
    if (!message || loading) return;
    
    try {
      console.log('Sending message:', message);
      setLoading(true);
      
      // Add user message to UI
      setMessages(prev => {
        const prevMessages = Array.isArray(prev) ? prev : [];
        return [...prevMessages, { sender: 'user', text: message }];
      });
      
      // Start or continue interview
      let response;
      
      if (sessionId) {
        console.log('Continuing session:', sessionId);
        // Check if we're in feedback stage and add special handling
        if (interviewStage === 'feedback') {
          console.log('Detected feedback stage message - adding special context');
          
          // Send message with coding_feedback context
          const feedbackMessage = `SYSTEM INSTRUCTION: User is in feedback stage after coding challenge.
CRITICAL INSTRUCTIONS:
1. DO NOT send any form of greeting or welcome message
2. DO NOT say "I see you've already started an interview" or similar
3. DO NOT start a new conversation
4. MAINTAIN feedback stage and provide detailed code review
5. FOCUS on the code-related question below
6. RESPOND with specific code feedback ONLY

USER QUESTION: ${message}`;
          
          // Try to use the challenge complete endpoint with feedback context
          try {
            console.log('Attempting to use challenge-complete endpoint with feedback context');
            response = await submitChallengeFeedbackToServer(
              sessionId,
              userId,
              feedbackMessage,
              null, // No evaluation summary for follow-up questions
              true,  // Challenge was completed
              "coding_feedback" // Special context flag
            );
            
            // Force feedback stage regardless of response
            if (response) {
              response.interview_stage = 'feedback';
              response.isFeedback = true;
              
              // Check and override any generic responses
              const responseText = response.response?.toLowerCase() || '';
              if (/^(hello|hi|greetings|welcome|i see you|let me continue|good to see you|thank you for completing)/i.test(responseText.trim())) {
                console.warn('[Interview] Detected and overriding generic greeting in feedback stage');
                response.response = "I understand you're asking about your code submission. Let me provide specific feedback on the aspects you're interested in. What particular part of your solution would you like me to elaborate on?";
                response.isGenericResponse = true;
              }
            }
          } catch (feedbackError) {
            console.warn('Could not use challenge-complete endpoint, falling back to continue interview:', feedbackError);
            response = await continueInterview(feedbackMessage, sessionId, userId);
            
            // Force feedback stage for fallback response too
            if (response) {
              response.interview_stage = 'feedback';
              response.isFeedback = true;
            }
          }
        } else {
          // Normal continuation for non-feedback stages
          response = await continueInterview(message, sessionId, userId);
        }
      } else {
        console.log('Starting new session with role:', selectedJobRole);
        response = await continueInterview(message, userId, selectedJobRole);
        
        if (response && response.session_id) {
          setSessionId(response.session_id);
        }
      }
      
      if (response) {
        console.log('Received response:', response);
        
        // Handle audio response if available
        let audioUrl = null;
        if (response.audio_response_url) {
          console.log('Audio response available at:', response.audio_response_url);
          audioUrl = response.audio_response_url;
          setCurrentAudioUrl(audioUrl);
          
          // Use a safer approach to auto-play audio that doesn't rely on the state variable
          const shouldAutoPlay = true; // Default to true if user hasn't explicitly disabled it
          if (shouldAutoPlay) {
            setTimeout(() => playAudioResponse(audioUrl), 500);
          }
        }
        
        // Handle stage transitions - but maintain feedback stage if we're in it
        if (response.interview_stage && response.interview_stage !== interviewStage) {
          if (interviewStage === 'feedback') {
            console.log('Maintaining feedback stage despite response suggesting:', response.interview_stage);
            // Don't change the stage, keep it as feedback
          } else {
            console.log(`Stage transition: ${interviewStage} -> ${response.interview_stage}`);
            setInterviewStage(response.interview_stage);
          }
        }
        
        // Handle coding challenge
        if (response.coding_challenge_detail) {
          console.log('Received coding challenge:', response.coding_challenge_detail);
          setCurrentCodingChallenge(response.coding_challenge_detail);
        }
        
        // Check if the response is a generic greeting in feedback stage
        let isGenericResponse = response.isGenericResponse === true;
        if (interviewStage === 'feedback' && !isGenericResponse) {
          const responseText = response.response?.toLowerCase() || '';
          isGenericResponse = /^(hello|hi|greetings|welcome|i see you|let me continue|good to see you|thank you for completing)/i.test(responseText.trim());
          
          if (isGenericResponse) {
            console.warn('[Interview] Detected generic greeting in feedback stage');
            // Override the generic response with a more helpful message
            response.response = "I understand you're asking about your code submission. Let me provide specific feedback on the aspects you're interested in. What particular part of your solution would you like me to elaborate on?";
          }
        }
        
        // Add AI response to messages with any special flags from the backend
        setMessages(prev => {
          const prevMessages = Array.isArray(prev) ? prev : [];
          return [...prevMessages, { 
            sender: 'assistant', 
            text: response.response,
            audioUrl,
            // Preserve any special flags from the backend
            isFeedback: response.isFeedback === true || interviewStage === 'feedback',
            isGenericResponse: isGenericResponse
          }];
        });
      }
    } catch (error) {
      console.error('Error sending message:', error);
      toast({
        title: 'Error',
        description: error.message || 'An error occurred while communicating with the AI',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
      
      // Add error message
      setMessages(prev => {
        const prevMessages = Array.isArray(prev) ? prev : [];
        return [...prevMessages, { 
          sender: 'assistant', 
          text: 'Sorry, I encountered an error. Please try again or refresh the page.',
          isError: true
        }];
      });
    } finally {
      setLoading(false);
    }
  };

  // Render messages with any feedback-specific styling
  const renderMessages = () => {
    // Ensure messages is an array before attempting to render
    if (!Array.isArray(messages)) {
      console.warn('[Interview] messages is not an array in renderMessages, value:', messages);
      return (
        <ChatMessage
          sender="assistant"
          text="Something went wrong displaying the conversation. Please refresh the page to try again."
          isError={true}
        />
      );
    }
    
    return messages.map((message, index) => {
      // Debug the message object to ensure we have the right properties
      if (index === messages.length - 1) {
        console.log('[Interview] Last message properties:', {
          sender: message.sender,
          isFeedback: message.isFeedback,
          isGenericResponse: message.isGenericResponse,
          isHint: message.isHint,
          isError: message.isError,
          isTransition: message.isTransition
        });
      }
      
      return (
        <ChatMessage
          key={index}
          sender={message.sender}
          text={message.text}
          audioUrl={message.audioUrl}
          isFeedback={message.isFeedback}
          isHint={message.isHint}
          isGenericResponse={message.isGenericResponse}
          isError={message.isError}
          isTransition={message.isTransition}
        />
      );
    });
  };

  return (
    <Box minH="100vh" bg="gray.50" className="interview-container">
      <Navbar />
      
      <Container maxW="100%" px={4} py={6}>
        <Grid
          templateColumns={{ 
            base: '1fr', 
            lg: sidebarCollapsed ? '80px 1fr' : '350px 1fr' 
          }}
          gap={sidebarCollapsed ? 2 : 4}
          h={{ base: 'auto', md: 'calc(100vh - 140px)' }}
          minH="600px"
          transition="all 0.3s ease-in-out"
        >
          {/* Collapsible Sidebar/Info Panel */}
          <GridItem 
            display={{ base: 'none', lg: 'block' }}
            className="sidebar-container"
            onMouseEnter={() => setSidebarHovered(true)}
            onMouseLeave={() => setSidebarHovered(false)}
          >
            <Box
              bg="white"
              borderRadius="md"
              boxShadow="md"
              h="100%"
              position="relative"
              width={sidebarCollapsed ? "80px" : "350px"}
              transition="all 0.3s ease-in-out"
              overflow="hidden"
              className={`sidebar ${sidebarCollapsed ? 'collapsed' : 'expanded'}`}
            >
              {/* Toggle Button */}
              <Box
                position="absolute"
                top="50%"
                right={sidebarCollapsed ? "-15px" : "15px"}
                transform="translateY(-50%)"
                zIndex={10}
                className="sidebar-toggle"
              >
                <Tooltip 
                  label={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"} 
                  placement="right"
                >
                  <IconButton
                    aria-label={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
                    icon={sidebarCollapsed ? <FaChevronRight /> : <FaChevronLeft />}
                    size="sm"
                    colorScheme="blue"
                    borderRadius="full"
                    onClick={toggleSidebar}
                    opacity={sidebarHovered || !sidebarCollapsed ? 1 : 0.3}
                    transition="all 0.2s ease-in-out"
                    _hover={{ opacity: 1, transform: "scale(1.1)" }}
                    boxShadow="md"
                  />
                </Tooltip>
              </Box>

              {/* Sidebar Content */}
              <Box 
                p={sidebarCollapsed ? 2 : 6}
                opacity={sidebarCollapsed ? 0 : 1}
                transition="opacity 0.3s ease-in-out"
                height="100%"
                overflow="auto"
              >
                <Heading as="h2" size="lg" mb={6} color="brand.600">
                  Technical Interview
                </Heading>
                
                {/* Session Info */}
                <Box mb={6}>
                  <Text fontWeight="bold" mb={2}>Session Info</Text>
                  <Text fontSize="sm" color="gray.600" mb={1}>
                    User ID: {userId || 'Not set'}
                  </Text>
                  <Text fontSize="sm" color="gray.600" mb={1}>
                    Session ID: {sessionId || 'New session'}
                  </Text>
                  {interviewStage && (
                    <Box mt={3}>
                      <Text fontSize="sm" fontWeight="bold">Current Stage:</Text>
                      <Badge 
                        colorScheme={getStageBadgeColor(interviewStage)} 
                        fontSize="sm"
                        mt={1}
                      >
                        {interviewStage.replace(/_/g, ' ')}
                      </Badge>
                    </Box>
                  )}
                </Box>
                
                {/* Settings */}
                <Box mb={6}>
                  <Text fontWeight="bold" mb={2}>Settings</Text>
                  
                  {/* Voice Mode Toggle */}
                  <HStack spacing={2} mb={2}>
                    <Switch 
                      isChecked={voiceMode} 
                      onChange={(e) => setVoiceMode(e.target.checked)}
                      isDisabled={!isVoiceAvailable}
                      colorScheme="brand"
                    />
                    <Text fontSize="sm">Voice Mode</Text>
                  </HStack>
                  
                  {/* Auto-play Toggle */}
                  <HStack spacing={2} mb={2}>
                    <Switch 
                      isChecked={autoPlayAudio} 
                      onChange={(e) => setAutoPlayAudio(e.target.checked)}
                      colorScheme="brand"
                    />
                    <Text fontSize="sm">Auto-play Audio</Text>
                  </HStack>
                </Box>
                
                {/* Voice Mode Info */}
                <Box mb={6}>
                  <Text fontWeight="bold" mb={2}>Voice Mode</Text>
                  {isVoiceAvailable ? (
                    <Badge colorScheme="green">Available</Badge>
                  ) : (
                    <Alert status="warning" size="sm" borderRadius="md">
                      <AlertIcon />
                      Voice processing is not available
                    </Alert>
                  )}
                </Box>
                
                {/* Proctoring Info */}
                <Box mb={6}>
                  <Text fontWeight="bold" mb={2}>Proctoring</Text>
                  {proctoringEffectivelyEnabled ? (
                    <Badge colorScheme="green">Active</Badge>
                  ) : (
                    <Badge colorScheme="red">Inactive</Badge>
                  )}
                </Box>
                
                {/* Help/Info */}
                <Box mb={6}>
                  <Text fontWeight="bold" mb={2}>Interview Tips</Text>
                  <Text fontSize="sm" color="gray.600" mb={3}>
                    Speak clearly and think through your answers. The AI will guide you through technical questions and coding challenges.
                  </Text>
                  <Button
                    size="sm"
                    leftIcon={<FaInfoCircle />}
                    colorScheme="blue"
                    variant="outline"
                    onClick={() => setIsInfoModalOpen(true)}
                  >
                    How It Works
                  </Button>
                </Box>
                
                {/* History Button */}
                <Box mt="auto">
                  <Button
                    width="full"
                    leftIcon={<FaHistory />}
                    onClick={() => navigate('/history')}
                    variant="outline"
                  >
                    View Interview History
                  </Button>
                </Box>
                
                {/* Proctoring Panel */}
                {!showJobSelector && (
                  <Box mt={4}>
                    {/* Render the shared video element here for ProctoringPanel */}
                    {proctoringIsEnabledForPanel && ( 
                      <video
                        ref={videoRef}
                        autoPlay
                        playsInline
                        muted 
                        style={{
                          width: '100%',
                          maxWidth: '320px', // Max width for sidebar
                          height: 'auto',
                          borderRadius: '8px', // chakra 'md'
                          marginBottom: '1rem', // chakra '4'
                          backgroundColor: '#1A202C', // chakra gray.800 - dark placeholder
                          aspectRatio: '16/9', // Maintain aspect ratio
                          display: proctoringEffectivelyEnabled || isEnrolling ? 'block' : 'none', // Show if proctoring or enrolling
                        }}
                      />
                    )}
                    <ProctoringPanel
                      sessionId={sessionId}
                      userId={userId}
                      isEnabled={proctoringIsEnabledForPanel}
                      onStatusChange={handleProctoringStatusChange}
                      temporaryEmbedding={temporaryEmbedding}
                      videoRef={videoRef}
                    />
                  </Box>
                )}
              </Box>
            </Box>
          </GridItem>
          
          {/* Main Chat Interface */}
          <GridItem className="interview-main-content">
            {error && (
              <Alert status="error" mb={4} borderRadius="md">
                <AlertIcon />
                {error}
              </Alert>
            )}
            
            <Grid
              templateRows="auto 1fr"
              templateColumns="1fr"
              gap={4}
              height="100%"
              p={4}
              className="interview-layout"
              bg="white"
              borderRadius="md"
              boxShadow="md"
            >
              <GridItem className="interview-header">
                <Box 
                  display="flex" 
                  justifyContent="space-between" 
                  alignItems="center"
                  p={6}
                  borderBottom="1px solid"
                  borderColor="gray.200"
                  bg="white"
                >
                  <Box>
                    <Heading size="lg" color="brand.700" fontWeight="600">
                      Technical Interview
                    </Heading>
                    {selectedJobRole && (
                      <Badge 
                        colorScheme="green" 
                        fontSize="0.8em" 
                        ml={2}
                        borderRadius="full"
                        px={3}
                        py={1}
                      >
                        {selectedJobRole.role_name} ({selectedJobRole.seniority_level})
                      </Badge>
                    )}
                    {sessionId && (
                      <Text fontSize="sm" color="gray.500" mt={1}>
                        Session ID: {sessionId}
                      </Text>
                    )}
                  </Box>
                  
                  <Button 
                    colorScheme="red" 
                    variant="outline" 
                    size="sm"
                    onClick={onOpenEndInterviewModal}
                    borderRadius="md"
                    fontWeight="500"
                    _hover={{ 
                      transform: "translateY(-1px)",
                      boxShadow: "0 4px 12px rgba(245, 101, 101, 0.2)"
                    }}
                  >
                    End Interview
                  </Button>
                </Box>
              </GridItem>
              
              <GridItem overflow="hidden" className="interview-content">
                {showJobSelector ? (
                  <InterviewSetupWizard 
                    onComplete={handleWizardComplete}
                    onCancel={handleWizardCancel}
                  />
                ) : interviewStage === 'conclusion' ? (
                  <InterviewResults 
                    sessionData={{ 
                      session_id: sessionId,
                      sessionId: sessionId // Adding both formats to ensure compatibility
                    }} 
                    duration={messages.length > 0 ? Math.floor((new Date() - new Date(messages[0].timestamp)) / 1000) : 0}
                    messagesCount={messages.length}
                  />
                ) : (
                  (interviewStage === 'coding_challenge' || interviewStage === 'coding_challenge_waiting') && currentCodingChallenge ? (
                    <CodingChallenge 
                      jobRoleData={currentCodingChallenge}
                      onComplete={handleCodingFeedbackSubmitted}
                      onRequestHint={() => { /* Implement hint request if needed */ }}
                      sessionId={sessionId}
                      userId={userId}
                      isVideoCall={true}
                    />
                  ) : (interviewStage === 'coding_challenge' || interviewStage === 'coding_challenge_waiting') && !currentCodingChallenge ? (
                    <Box p={6} textAlign="center" className="loading-state">
                      <Text fontSize="xl" color="gray.600">Loading coding challenge details...</Text>
                    </Box>
                  ) : (
                    <VideoCallInterface
                      jobRoleData={selectedJobRole}
                      sessionData={{ sessionId, userId }}
                      onSessionIdReceived={handleSessionIdReceived}
                    />
                  )
                )}
              </GridItem>
            </Grid>
          </GridItem>
        </Grid>
      </Container>
      
      {/* Info Modal */}
      <Modal isOpen={isInfoModalOpen} onClose={() => setIsInfoModalOpen(false)} size="lg">
        <ModalOverlay />
        <ModalContent>
          <ModalHeader color="brand.700">How AI Interviewer Works</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <Text mb={4}>
              The AI Interviewer conducts technical interviews simulating real-world scenarios. Here's what to expect:
            </Text>
            
            <Box mb={4}>
              <Heading as="h4" size="sm" mb={2} color="brand.600">
                Interview Stages
              </Heading>
              <Text fontSize="sm" mb={1}>• <b>Introduction:</b> Get comfortable and introduce yourself</Text>
              <Text fontSize="sm" mb={1}>• <b>Technical Questions:</b> Answer questions about software development concepts</Text>
              <Text fontSize="sm" mb={1}>• <b>Coding Challenge:</b> Solve programming problems</Text>
              <Text fontSize="sm" mb={1}>• <b>Feedback:</b> Receive constructive evaluation of your performance</Text>
              <Text fontSize="sm">• <b>Conclusion:</b> Wrap up the interview with final thoughts</Text>
            </Box>
            
            <Box mb={4}>
              <Heading as="h4" size="sm" mb={2} color="brand.600">
                Voice Interaction
              </Heading>
              <Text fontSize="sm">
                You can interact using text or voice (if available). Voice mode lets you speak naturally, just like in a real interview.
              </Text>
            </Box>
            
            <Box>
              <Heading as="h4" size="sm" mb={2} color="brand.600">
                Tips for Success
              </Heading>
              <Text fontSize="sm" mb={1}>• Explain your thought process clearly</Text>
              <Text fontSize="sm" mb={1}>• Ask clarifying questions when needed</Text>
              <Text fontSize="sm" mb={1}>• Take your time with technical problems</Text>
              <Text fontSize="sm">• Learn from feedback to improve for next time</Text>
            </Box>
          </ModalBody>
          <ModalFooter>
            <Button colorScheme="brand" onClick={() => setIsInfoModalOpen(false)}>
              Got it
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
      
      {/* End Interview Confirmation Modal */}
      <Modal isOpen={isEndInterviewModalOpen} onClose={onCloseEndInterviewModal}>
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>End Interview</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <Text>Are you sure you want to end this interview session?</Text>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" onClick={onCloseEndInterviewModal}>Cancel</Button>
            <Button colorScheme="red" onClick={handleEndInterview} ml={3}>
              End Interview
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
      
      {/* Enrollment Modal */}
      <Modal isOpen={isEnrollmentModalOpen} onClose={handleEnrollmentModalClose} size="xl" closeOnOverlayClick={false}>
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Face Enrollment</ModalHeader>
          {/* Prevent closing via X button if mid-enrollment and not complete */}
          { !(isEnrolling && !enrollmentProcessComplete) && <ModalCloseButton /> }
          <ModalBody>
            <Box>
              {/* Hidden video element for the hook, if FaceAuthManager doesn't render its own visible one */}
              {/* <video ref={videoRef} style={{ display: 'none' }} playsInline /> */}
              
              {/* 
                WebcamMonitor will render the video feed.
                FaceAuthenticationManager will contain FaceEnrollment and the auth logic.
                WebcamMonitor (via ProctoringPanel's isEnabled) needs to be active to put a stream on videoRef.
              */}
              {isEnrolling && (
                <FaceAuthenticationManager
                  videoRef={videoRef} // Pass the ref here
                  isActive={isEnrolling} 
                  onAuthenticationEvent={(event) => { // This needs refinement in FaceAuthManager
                    if (event.type === 'enrollment_success' && event.embedding) {
                      handleInitialEnrollmentSuccess(event.embedding);
                    } else if (event.type === 'enrollment_failed') {
                      handleInitialEnrollmentFailure(event.message || 'Enrollment attempt failed.');
                    } else if (event.type === 'error' && event.context === 'enrollment') {
                       handleInitialEnrollmentFailure(event.message || 'An error occurred during enrollment.');
                    }
                  }}
                  // To be implemented in FaceAuthenticationManager:
                  // isEnrollmentOnlyMode={true} 
                  onInitialEnrollmentSuccess={handleInitialEnrollmentSuccess} 
                  onInitialEnrollmentFailure={handleInitialEnrollmentFailure} 
                  showEnrollmentUI={true} 
                />
              )}
              {!isEnrolling && enrollmentProcessComplete && (
                <VStack spacing={4} py={6} textAlign="center">
                  <Icon as={FaCheckCircle} boxSize={12} color="green.500" />
                  <Text fontSize="lg" fontWeight="bold">Enrollment Complete!</Text>
                  <Text>You can now proceed with the interview.</Text>
                </VStack>
              )}
               {!isEnrolling && !enrollmentProcessComplete && !isEnrollmentModalOpen && (
                 <Text>Enrollment was not started or was cancelled. Proctoring may be limited.</Text>
               )}
            </Box>
          </ModalBody>
          <ModalFooter>
            <Button 
              onClick={handleEnrollmentModalClose}
              isDisabled={isEnrolling && !enrollmentProcessComplete} // Disable if enrolling and not yet complete
            >
              {enrollmentProcessComplete ? 'Continue to Interview' : 'Cancel Enrollment'}
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </Box>
  );
};

export default Interview; 