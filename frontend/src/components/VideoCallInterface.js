import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Box,
  Grid,
  VStack,
  HStack,
  Text,
  Button,
  Alert,
  AlertIcon,
  useBreakpointValue,
  useToast,
  Spinner,
  Center,
  useColorModeValue,
  Textarea,
  IconButton,
  Progress,
  Avatar,
  AvatarBadge,
  Flex,
  Tooltip,
  Icon,
  Divider,
  Badge,
  Heading,
  GridItem,
  Switch,
  FormControl,
  FormLabel,
  Slider,
  SliderTrack,
  SliderFilledTrack,
  SliderThumb,
  Stat,
  StatLabel,
  StatNumber,
  StatHelpText
} from '@chakra-ui/react';
import { useLocation, useNavigate } from 'react-router-dom';
import { FiSend } from 'react-icons/fi';
import { FaMicrophone, FaVideo, FaVideoSlash, FaMicrophoneSlash, FaPause, FaPlay, FaExclamationTriangle, FaInfoCircle, FaCommentAlt, FaCheck, FaTimes, FaPaperPlane, FaCompressArrowsAlt, FaExpandArrowsAlt, FaLaughBeam, FaSadTear, FaKeyboard, FaVolumeUp, FaVolumeMute, FaVolumeOff, FaCircle, FaQuestion, FaEye } from 'react-icons/fa';
import { useInterview } from '../context/InterviewContext';
import { startInterview, continueInterview, continueInterviewStream } from '../api/interviewService';
import ProctoringPanel from './proctoring/ProctoringPanel';
import FaceAuthenticationManager from './proctoring/FaceAuthenticationManager';
import { FaGrinBeam } from 'react-icons/fa';
import ChatMessage from './ChatMessage';

// Import custom components
import CameraFeed from './video/CameraFeed';
import AudioControls from './video/AudioControls';
import ConversationIndicators, { SpeakingIndicator } from './video/ConversationIndicators';

// Import custom hooks
import useWebRTC from '../hooks/useWebRTC';
import useGeminiLiveAudio from '../hooks/useGeminiLiveAudio';

// Import existing components we need to preserve
import CodingChallenge from './CodingChallenge';

/**
 * Main video call interface component
 * Replaces the chat interface with a modern video conferencing experience
 */
const VideoCallInterface = ({ jobRoleData, sessionData, onSessionIdReceived }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const toast = useToast();
  
  // Use interview context for stage management
  const { 
    interviewStage, 
    setInterviewStage,
    setCurrentCodingChallenge,
    currentCodingChallenge,
    messages,
    setMessages
  } = useInterview();
  
  // Get responsive layout values
  const isMobile = useBreakpointValue({ base: true, md: false });
  const gridTemplate = useBreakpointValue({
    base: '"sidebar" "video" "controls"', // Mobile: stacked layout
    md: '"sidebar" "video" "controls"', // Desktop: sidebar on top, video and controls below
    lg: '"sidebar" "video" "controls"' // Large: same vertical stack layout
  });
  const gridAreas = useBreakpointValue({
    base: 'auto 1fr auto / 1fr',
    md: 'auto 1fr auto / 1fr', // Vertical stack: sidebar, video, controls
    lg: 'auto 1fr auto / 1fr'  // Same vertical layout for all screen sizes
  });

  // Component state (removed currentStage as it's now from context)
  const [sessionDuration, setSessionDuration] = useState(0);
  const [messagesCount, setMessagesCount] = useState(0);
  const [isInitialized, setIsInitialized] = useState(false);
  const [showCodingChallenge, setShowCodingChallenge] = useState(false);
  const [interviewComplete, setInterviewComplete] = useState(false);
  const [candidateAudioLevel, setCandidateAudioLevel] = useState(0);
  const [aiSpeaking, setAiSpeaking] = useState(false);
  const [currentSessionId, setCurrentSessionId] = useState(sessionData?.sessionId || '');

  // Session tracking
  const sessionStartTime = useRef(Date.now());
  const durationInterval = useRef(null);

  // Initialize WebRTC for camera and microphone
  const {
    stream,
    cameraEnabled,
    micEnabled,
    isLoading: rtcLoading,
    error: rtcError,
    initializeMedia,
    toggleCamera,
    toggleMicrophone,
    stopMedia,
    getAudioLevel
  } = useWebRTC(true, true);

  // Initialize Gemini Live API connection
  const {
    isConnected: geminiConnected,
    isConnecting: geminiConnecting,
    connectionError: geminiError,
    isSpeaking: candidateSpeaking,
    isListening: geminiListening,
    audioLevel: geminiAudioLevel,
    lastAIResponse,
    connectionQuality,
    startStreaming,
    stopStreaming,
    sendMessage,
    connect: connectGemini,
    disconnect: disconnectGemini
  } = useGeminiLiveAudio(sessionData?.sessionId, sessionData?.userId);

  // Color scheme
  const bgColor = useColorModeValue('gray.50', 'gray.900');
  const borderColor = useColorModeValue('gray.200', 'gray.700');

  // Add state to prevent duplicate API calls
  const [isInitializing, setIsInitializing] = useState(false);
  const [hasInitialized, setHasInitialized] = useState(false);

  // Temporary state for testing without WebSockets
  const [tempResponse, setTempResponse] = useState('');
  const [isSendingResponse, setIsSendingResponse] = useState(false);
  const [voiceMode, setVoiceMode] = useState(true); // Toggle between voice and text-only
  const [availableVoices, setAvailableVoices] = useState([]);
  
  // Speech recognition state
  const [isListening, setIsListening] = useState(false);
  const [speechRecognition, setSpeechRecognition] = useState(null);
  const [speechSupported, setSpeechSupported] = useState(false);

  // Audio streaming state
  const [isAudioStreamActive, setIsAudioStreamActive] = useState(false);
  const [audioStream, setAudioStream] = useState(null);
  const [isUserSpeaking, setIsUserSpeaking] = useState(false);
  const [speechDetectionTimeout, setSpeechDetectionTimeout] = useState(null);
  const [recognitionState, setRecognitionState] = useState('stopped'); // 'stopped', 'starting', 'running', 'stopping'
  const [liveTranscript, setLiveTranscript] = useState('');
  const [requestInProgress, setRequestInProgress] = useState(false); // Add request deduplication
  
  // Refs to access current values in callbacks
  const isAudioStreamActiveRef = useRef(false);
  const recognitionStateRef = useRef('stopped');
  const speechDetectionTimeoutRef = useRef(null);
  
  // Update refs when state changes
  useEffect(() => {
    isAudioStreamActiveRef.current = isAudioStreamActive;
  }, [isAudioStreamActive]);
  
  useEffect(() => {
    recognitionStateRef.current = recognitionState;
  }, [recognitionState]);
  
  useEffect(() => {
    speechDetectionTimeoutRef.current = speechDetectionTimeout;
  }, [speechDetectionTimeout]);

  // Add ref to prevent race conditions
  const initializationRef = useRef({ 
    isInitializing: false, 
    hasInitialized: false 
  });

  // Function to synthesize speech using browser's Web Speech API
  const speakText = useCallback((text, onEndCallback, onErrorCallback) => {
    if ('speechSynthesis' in window) {
      // Cancel any ongoing speech first to prevent interruptions
      window.speechSynthesis.cancel();
      
      // Small delay to ensure cancellation is processed
      setTimeout(() => {
        const utterance = new SpeechSynthesisUtterance(text);
        
        // Configure for natural Indian female speech
        utterance.rate = 0.9; // Natural conversational pace
        utterance.pitch = 1.1; // Slightly higher pitch for female voice
        utterance.volume = 0.85; // Comfortable listening volume
        
        // Enhanced voice selection for Indian female voices
        const voices = window.speechSynthesis.getVoices();
        console.log('[VideoCallInterface] All available voices:', voices.map(v => ({
          name: v.name,
          lang: v.lang,
          localService: v.localService,
          default: v.default
        })));
        
        // Prioritize Indian female voices for natural conversation
        const preferredVoice = voices.find(voice => {
          const name = voice.name.toLowerCase();
          const lang = voice.lang.toLowerCase();
          
          // First priority: Indian English female voices
          if (lang.includes('en-in') || name.includes('india')) {
            if (name.includes('female') || name.includes('woman') || 
                name.includes('samantha') || name.includes('veena') || 
                name.includes('raveena') || name.includes('priya')) {
              return true;
            }
          }
          
          // Second priority: Google female voices with Indian option
          if (name.includes('google') && lang.startsWith('en')) {
            if (name.includes('female') || name.includes('woman') || 
                name.includes('indian') || name.includes('hindi')) {
              return true;
            }
          }
          
          // Third priority: Microsoft female voices 
          if (name.includes('microsoft') && lang.startsWith('en')) {
            if (name.includes('female') || name.includes('woman')) {
              // Prefer Indian accent if available
              if (name.includes('india') || name.includes('heera') || name.includes('ravi')) {
                return true;
              }
            }
          }
          
          // Fourth priority: Any English female voice
          if (lang.startsWith('en')) {
            if (name.includes('female') || name.includes('woman') || 
                name.includes('samantha') || name.includes('alex') ||
                name.includes('susan') || name.includes('karen')) {
              return true;
            }
          }
          
          return false;
        }) || voices.find(voice => voice.lang.startsWith('en') && voice.default);
        
        if (preferredVoice) {
          utterance.voice = preferredVoice;
          console.log('[VideoCallInterface] Selected natural Indian female voice:', {
            name: preferredVoice.name,
            lang: preferredVoice.lang,
            localService: preferredVoice.localService
          });
        } else {
          console.warn('[VideoCallInterface] No preferred Indian female voice found, using default');
        }
        
        // Set up event handlers
        if (onEndCallback) {
          utterance.onend = onEndCallback;
        }
        if (onErrorCallback) {
          utterance.onerror = onErrorCallback;
        }
        
        // Speak the text
        console.log('[VideoCallInterface] Speaking AI response with natural Indian female voice');
        window.speechSynthesis.speak(utterance);
        
      }, 150); // Slightly longer delay for better voice loading
      
      return true; // Indicate speech was initiated
    } else {
      console.warn('[VideoCallInterface] Speech synthesis not supported by browser');
      return false;
    }
  }, []);

  // Initialize video call
  const initializeVideoCall = useCallback(async () => {
    try {
      setIsInitialized(false);
      
      // Initialize camera and microphone
      await initializeMedia(true, true);
      
      // Connect to Gemini Live API
      await connectGemini();
      
      setIsInitialized(true);
      
      toast({
        title: 'Video call connected',
        description: 'Your interview is ready to begin.',
        status: 'success',
        duration: 3000,
        isClosable: true,
      });

    } catch (error) {
      console.error('Failed to initialize video call:', error);
      toast({
        title: 'Connection error',
        description: 'Failed to setup video call. Please check your camera and microphone.',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    }
  }, [initializeMedia, connectGemini, toast]);

  // Handle stage transitions
  const handleStageChange = useCallback((newStage) => {
    setInterviewStage(newStage);
    
    // Handle specific stage requirements
    if (newStage === 'coding_challenge') {
      setShowCodingChallenge(true);
    } else {
      setShowCodingChallenge(false);
    }
    
    if (newStage === 'conclusion') {
      setInterviewComplete(true);
    }
  }, [setInterviewStage]);

  // Defensive wrapper for setInterviewStage to ensure only strings are set
  const safeSetInterviewStage = useCallback((stage) => {
    console.log('[VideoCallInterface] safeSetInterviewStage called with:', stage, 'type:', typeof stage);
    
    if (typeof stage === 'string') {
      handleStageChange(stage);
    } else if (stage !== null && stage !== undefined) {
      console.warn('[VideoCallInterface] Non-string value passed to setInterviewStage:', stage, 'Converting to string');
      handleStageChange(String(stage));
    } else {
      console.warn('[VideoCallInterface] null/undefined value passed to setInterviewStage, ignoring');
    }
  }, [handleStageChange]);

  // Handle ending the interview
  const handleEndInterview = useCallback(async () => {
    try {
      // Stop all media streams
      stopMedia();
      stopStreaming();
      disconnectGemini();
      
      // Clear intervals
      if (durationInterval.current) {
        clearInterval(durationInterval.current);
      }
      
      toast({
        title: 'Interview ended',
        description: 'Thank you for your time. Redirecting to results...',
        status: 'info',
        duration: 3000,
        isClosable: true,
      });
      
      // Navigate to results or thank you page
      setTimeout(() => {
        navigate('/interview-complete', { 
          state: { 
            sessionData,
            duration: sessionDuration,
            messagesCount 
          }
        });
      }, 2000);

    } catch (error) {
      console.error('Error ending interview:', error);
      toast({
        title: 'Error',
        description: 'There was an error ending the interview.',
        status: 'error',
        duration: 5000,
        isClosable: true,
      });
    }
  }, [stopMedia, stopStreaming, disconnectGemini, navigate, sessionData, sessionDuration, messagesCount, toast]);

  // Initialize session duration tracking
  useEffect(() => {
    durationInterval.current = setInterval(() => {
      const elapsed = Math.floor((Date.now() - sessionStartTime.current) / 1000);
      setSessionDuration(elapsed);
    }, 1000);

    return () => {
      if (durationInterval.current) {
        clearInterval(durationInterval.current);
      }
    };
  }, []);

  // Auto-initialize on component mount
  useEffect(() => {
    initializeVideoCall();
    
    return () => {
      // Cleanup on unmount
      stopMedia();
      stopStreaming();
      disconnectGemini();
    };
  }, [initializeVideoCall, stopMedia, stopStreaming, disconnectGemini]);

  // Start audio streaming when everything is ready
  useEffect(() => {
    if (stream && geminiConnected && !rtcError && !geminiError) {
      startStreaming(stream);
    }
  }, [stream, geminiConnected, rtcError, geminiError, startStreaming]);

  // Send initial message to start the interview when everything is ready
  useEffect(() => {
    const sendInitialMessage = async () => {
      // Prevent duplicate calls using ref (more reliable than state)
      if (initializationRef.current.isInitializing || 
          initializationRef.current.hasInitialized || 
          !sessionData?.userId) {
        console.log('[VideoCallInterface] Skipping initial message:', {
          isInitializing: initializationRef.current.isInitializing,
          hasInitialized: initializationRef.current.hasInitialized, 
          hasUserId: !!sessionData?.userId
        });
        return;
      }

      // Set initialization flag immediately
      initializationRef.current.isInitializing = true;
      setIsInitializing(true);
      
      try {
        console.log('[VideoCallInterface] Sending initial message to start interview');
        const response = await startInterview(
          "Hello, I'm ready to begin the interview.",
          sessionData.userId,
          jobRoleData
        );
        console.log('[VideoCallInterface] Initial message sent successfully, response:', response);
        
        // Extract the sessionId from the response and update the session data
        if (response.session_id && onSessionIdReceived) {
          console.log('[VideoCallInterface] Using sessionId from backend:', response.session_id);
          onSessionIdReceived(response.session_id);
        }
        
        // Handle the AI response immediately (since WebSockets are disabled for testing)
        if (response.response) {
          console.log('[VideoCallInterface] Processing AI response:', response.response);
          setMessagesCount(count => count + 1);
          
          // Force voice loading first
          if ('speechSynthesis' in window && speechSynthesis) {
            const voices = speechSynthesis.getVoices();
            console.log('[VideoCallInterface] Voices available for initial response:', voices.length);
            
            // Force voice loading if needed
            if (voices.length === 0) {
              console.log('[VideoCallInterface] No voices loaded, forcing voice loading...');
              const silentUtterance = new SpeechSynthesisUtterance(' ');
              silentUtterance.volume = 0;
              silentUtterance.onend = () => {
                console.log('[VideoCallInterface] Voice loading complete, retrying speech...');
                const newVoices = speechSynthesis.getVoices();
                setAvailableVoices(newVoices);
                // Retry speaking with loaded voices
                if (newVoices.length > 0) {
                  speakAIResponse(response.response, newVoices);
                }
              };
              speechSynthesis.speak(silentUtterance);
            } else {
              setAvailableVoices(voices);
              speakAIResponse(response.response, voices);
            }
          }
          
          // Also show text for accessibility  
          toast({
            title: '🎤 Alex Speaking',
            description: response.response,
            status: 'info',
            duration: 8000,
            isClosable: true,
            position: 'top-right'
          });
        }
        
        // Mark as initialized
        initializationRef.current.hasInitialized = true;
        setHasInitialized(true);
      } catch (error) {
        console.error('[VideoCallInterface] Error sending initial message:', error);
        toast({
          title: 'Error',
          description: 'Failed to start interview. Please try again.',
          status: 'error',
          duration: 5000,
          isClosable: true,
        });
      } finally {
        initializationRef.current.isInitializing = false;
        setIsInitializing(false);
      }
    };

    sendInitialMessage();
  }, [sessionData?.userId, jobRoleData, onSessionIdReceived, setMessagesCount, toast]); // Removed isInitializing and hasInitialized from deps

  // Update audio levels from various sources
  useEffect(() => {
    if (candidateSpeaking && geminiAudioLevel > 0) {
      setCandidateAudioLevel(geminiAudioLevel);
    } else {
      setCandidateAudioLevel(getAudioLevel());
    }
  }, [candidateSpeaking, geminiAudioLevel, getAudioLevel]);

  // Simulate AI speaking when we get responses
  useEffect(() => {
    if (lastAIResponse) {
      setAiSpeaking(true);
      setMessagesCount(count => count + 1);
      
      // Simulate speaking duration based on response length
      const speakingDuration = Math.max(2000, lastAIResponse.length * 50);
      setTimeout(() => {
        setAiSpeaking(false);
      }, speakingDuration);
    }
  }, [lastAIResponse]);

  // Initialize continuous audio streaming with voice activity detection
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
        console.log('[VideoCallInterface] Microphone access granted');

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
            console.log('[VideoCallInterface] Speech recognition started');
            setRecognitionState('running');
            setIsListening(true);
          };
          
          recognition.onresult = (event) => {
            let interimTranscript = '';
            
            for (let i = event.resultIndex; i < event.results.length; i++) {
              const transcript = event.results[i][0].transcript;
              if (event.results[i].isFinal) {
                finalTranscript += transcript + ' ';
                lastSpeechTime = Date.now();
              } else {
                interimTranscript += transcript;
              }
            }
            
            // Check for interruption - if user starts speaking while AI is talking
            if ((interimTranscript || finalTranscript) && aiSpeaking) {
              console.log('[VideoCallInterface] User interrupted AI - stopping AI speech');
              window.speechSynthesis.cancel(); // Stop AI immediately
              setAiSpeaking(false);
            }
            
            // Update UI with current speech
            if (interimTranscript || finalTranscript) {
              setTempResponse(finalTranscript + interimTranscript);
              setIsUserSpeaking(true);
              lastSpeechTime = Date.now();
              
              // Clear existing timeout
              if (speechDetectionTimeoutRef.current) {
                clearTimeout(speechDetectionTimeoutRef.current);
              }
              
              // Set timeout to detect end of speech
              const timeoutId = setTimeout(async () => {
                if (finalTranscript.trim() && !requestInProgress) {
                  console.log('[VideoCallInterface] Auto-sending response:', finalTranscript.trim());
                  
                  // Add debouncing to prevent rapid requests
                  if (lastRequestTime && Date.now() - lastRequestTime < 1000) {
                    console.log('[VideoCallInterface] Skipping request due to debouncing (too soon after last request)');
                    return;
                  }
                  
                  // Prevent duplicate requests
                  setRequestInProgress(true);
                  setIsSendingResponse(true);
                  setAiSpeaking(true);
                  lastRequestTime = Date.now();
                  
                  // Add small delay to prevent request stacking
                  await new Promise(resolve => setTimeout(resolve, 200));
                  
                  try {
                    // Use streaming for real-time response
                    console.log('[VideoCallInterface] Sending streaming response to AI...');
                    
                    let accumulatedResponse = '';
                    let accumulatedRawData = ''; // NEW: Store complete raw streaming data
                    
                    console.log('[VideoCallInterface] Starting streaming request...');
                    
                    await continueInterviewStream(
                      finalTranscript.trim(),
                      sessionData.sessionId,
                      sessionData.userId,
                      (chunk, fullResponse, metadata) => {
                        console.log('[VideoCallInterface] Received streaming chunk:', typeof chunk === 'string' ? chunk.substring(0, 50) + '...' : chunk, 'Full text length:', fullResponse.length);
                        console.log('[VideoCallInterface] Chunk details:', {
                          chunkLength: typeof chunk === 'string' ? chunk.length : 'not string',
                          fullTextLength: fullResponse.length,
                          chunkType: typeof chunk,
                          fullTextType: typeof fullResponse
                        });
                        console.log('[VideoCallInterface] Received metadata:', metadata);
                        
                        // Store the chunk text for accumulation
                        if (typeof chunk === 'string' && chunk.length > 0) {
                          accumulatedResponse += chunk;
                        }
                        
                        if (metadata) {
                          // Handle stage updates from streaming metadata
                          if (metadata && metadata.stage && metadata.stage !== interviewStage) {
                            console.log('[VideoCallInterface] =================== STAGE UPDATE DETECTED ===================');
                            console.log('[VideoCallInterface] Current interviewStage in context:', interviewStage);
                            console.log('[VideoCallInterface] New stage from metadata:', metadata.stage);
                            console.log('[VideoCallInterface] Metadata object:', metadata);
                            console.log('[VideoCallInterface] About to call setInterviewStage with:', metadata.stage);
                            
                            safeSetInterviewStage(metadata.stage);
                            
                            console.log('[VideoCallInterface] setInterviewStage called successfully');
                            console.log('[VideoCallInterface] ========================================');
                          }
                          
                          // CRITICAL FIX: Handle coding challenge details from metadata
                          if (metadata && metadata.codingChallengeDetail) {
                            console.log('[VideoCallInterface] =================== CODING CHALLENGE UPDATE DETECTED ===================');
                            console.log('[VideoCallInterface] Coding challenge details received:', metadata.codingChallengeDetail);
                            console.log('[VideoCallInterface] About to call setCurrentCodingChallenge');
                            
                            setCurrentCodingChallenge(metadata.codingChallengeDetail);
                            
                            console.log('[VideoCallInterface] setCurrentCodingChallenge called successfully');
                            console.log('[VideoCallInterface] ========================================');
                          }
                        } else {
                          console.log('[VideoCallInterface] No stage in metadata or metadata is null:', {
                            hasMetadata: !!metadata,
                            hasStage: !!(metadata && metadata.stage),
                            metadata: metadata
                          });
                        }
                        
                        console.log('[VideoCallInterface] Updated accumulatedResponse length:', accumulatedResponse.length);
                      },
                      (finalResponse, metadata) => {
                        console.log('[VideoCallInterface] Streaming complete:', typeof finalResponse === 'string' ? finalResponse.substring(0, 100) + '...' : finalResponse);
                        console.log('[VideoCallInterface] Final response length:', typeof finalResponse === 'string' ? finalResponse.length : 'not string');
                        console.log('[VideoCallInterface] Final response type:', typeof finalResponse);
                        console.log('[VideoCallInterface] Received metadata:', metadata);
                        
                        // Extract values from metadata object
                        const finalStage = metadata?.stage;
                        const finalSessionId = metadata?.sessionId;
                        
                        // Store the complete final response for fallback extraction
                        accumulatedRawData = finalResponse;
                        
                        if (finalSessionId) {
                          setCurrentSessionId(finalSessionId);
                        }
                        
                        if (finalStage) {
                          console.log('[VideoCallInterface] Setting stage to:', finalStage, 'type:', typeof finalStage);
                          safeSetInterviewStage(finalStage);
                        }
                        
                        // Check for coding challenge details in metadata first
                        if (metadata?.codingChallengeDetail) {
                          console.log('[VideoCallInterface] Found coding challenge in metadata:', metadata.codingChallengeDetail);
                          setCurrentCodingChallenge(metadata.codingChallengeDetail);
                        }
                        
                        // Process the final accumulated response for speech synthesis
                        if (accumulatedResponse.trim()) {
                          console.log('[VideoCallInterface] Synthesizing complete AI response...');
                          console.log('[VideoCallInterface] Available voices for final response:', availableVoices.length);
                            console.log('[VideoCallInterface] Calling speakAIResponse with final response');
                          speakAIResponse(accumulatedResponse, availableVoices);
                        }
                        
                        // ENHANCED FALLBACK: If we're in coding_challenge_waiting but no challenge was set,
                        // try to extract from the complete streaming data
                        if (finalStage === 'coding_challenge_waiting' && !currentCodingChallenge && !metadata?.codingChallengeDetail) {
                          console.log('[VideoCallInterface] =================== ENHANCED FALLBACK CHALLENGE EXTRACTION ===================');
                          console.log('[VideoCallInterface] Attempting to extract challenge details from complete streaming data');
                          console.log('[VideoCallInterface] Raw data length:', accumulatedRawData?.length || 0);
                          console.log('[VideoCallInterface] Raw data preview:', accumulatedRawData?.substring(0, 500) || 'No raw data');
                          
                          let challengeFound = false;
                          let challengeData = null;
                          
                          if (accumulatedRawData) {
                            try {
                              // Method 1: Look for complete challenge data using improved regex
                              const challengeDetailPattern = /"coding_challenge_detail":\s*(\{[^{}]*"problem_statement"[^{}]*(?:\{[^{}]*\}[^{}]*)*\})/g;
                              let challengeMatch = challengeDetailPattern.exec(accumulatedRawData);
                              
                              while (challengeMatch && !challengeFound) {
                                try {
                                  const candidateJson = challengeMatch[1];
                                  console.log('[VideoCallInterface] Method 1 - Trying to parse:', candidateJson.substring(0, 200) + '...');
                                  
                                  // Handle escaped JSON strings
                                  const unescapedJson = candidateJson.replace(/\\"/g, '"').replace(/\\\\/g, '\\');
                                  challengeData = JSON.parse(unescapedJson);
                                  
                                  if (challengeData.problem_statement && challengeData.test_cases) {
                                    console.log('[VideoCallInterface] Method 1 SUCCESS: Extracted challenge via regex');
                                    challengeFound = true;
                                  }
                                } catch (parseErr) {
                                  console.log('[VideoCallInterface] Method 1 parse error:', parseErr.message);
                                  challengeMatch = challengeDetailPattern.exec(accumulatedRawData);
                                }
                              }
                              
                              // Method 2: Look for the complete challenge object in a more robust way
                              if (!challengeFound) {
                                // Find all "problem_statement" occurrences and try to extract the containing object
                                const problemStatementIndices = [];
                                let match;
                                const problemRegex = /"problem_statement"/g;
                                while ((match = problemRegex.exec(accumulatedRawData)) !== null) {
                                  problemStatementIndices.push(match.index);
                                }
                                
                                console.log('[VideoCallInterface] Method 2: Found', problemStatementIndices.length, 'problem_statement occurrences');
                                
                                for (let index of problemStatementIndices) {
                                  // Find the opening brace of the object containing this problem_statement
                                  let openBrace = accumulatedRawData.lastIndexOf('{', index);
                                  let braceCount = 1;
                                  let closeBrace = -1;
                                  
                                  for (let i = openBrace + 1; i < accumulatedRawData.length && braceCount > 0; i++) {
                                    if (accumulatedRawData[i] === '{') braceCount++;
                                    else if (accumulatedRawData[i] === '}') braceCount--;
                                    if (braceCount === 0) {
                                      closeBrace = i;
                                      break;
                                    }
                                  }
                                  
                                  if (closeBrace !== -1) {
                                    try {
                                      const candidateJson = accumulatedRawData.substring(openBrace, closeBrace + 1);
                                      const candidateObj = JSON.parse(candidateJson);
                                      
                                      if (candidateObj.problem_statement && candidateObj.test_cases && candidateObj.starter_code) {
                                        challengeData = candidateObj;
                                        console.log('[VideoCallInterface] Method 2 SUCCESS: Extracted complete challenge object');
                                        challengeFound = true;
                                        break;
                                      }
                                    } catch (parseErr) {
                                      console.log('[VideoCallInterface] Method 2 parse attempt failed for position', openBrace, ':', parseErr.message);
                                    }
                                  }
                                }
                              }
                              
                            } catch (error) {
                              console.log('[VideoCallInterface] Enhanced fallback extraction error:', error.message);
                            }
                          }
                          
                          if (challengeFound && challengeData) {
                            console.log('[VideoCallInterface] SUCCESS: Challenge extracted via enhanced fallback');
                            console.log('[VideoCallInterface] Challenge data preview:', {
                              title: challengeData.title,
                              problem_statement: challengeData.problem_statement?.substring(0, 100) + '...',
                              test_cases_count: challengeData.test_cases?.length,
                              language: challengeData.language,
                              starter_code_preview: challengeData.starter_code?.substring(0, 50) + '...'
                            });
                            
                            setCurrentCodingChallenge(challengeData);
                        } else {
                            console.log('[VideoCallInterface] Enhanced fallback failed - creating temporary loading challenge');
                            setCurrentCodingChallenge({
                              problem_statement: 'Coding challenge is being prepared. Please wait...',
                              test_cases: [],
                              reference_solution: '',
                              language: 'python',
                              starter_code: '# Challenge loading...',
                              title: 'Loading Challenge',
                              challenge_id: 'loading'
                            });
                          }
                          
                          console.log('[VideoCallInterface] ========================================');
                        }
                        
                        // Complete the streaming interaction
                        console.log('[VideoCallInterface] Completing streaming interaction...');
                        
                        // Show final response in toast for debugging
                        toast({
                          title: "🎤 Alex Response Complete",
                          description: accumulatedResponse?.substring(0, 150) + (accumulatedResponse?.length > 150 ? "..." : ""),
                          status: "success",
                          duration: 5000,
                          isClosable: true,
                          position: 'top-right'
                        });
                        
                        // Complete the interaction and clear transcript
                        setIsSendingResponse(false);
                        setLiveTranscript('');
                        setTempResponse(''); // Clear the live transcript box
                        setIsUserSpeaking(false); // Reset user speaking state
                        setRequestInProgress(false);
                        setAiSpeaking(false);
                        
                        // Reset final transcript for next interaction
                        finalTranscript = '';
                      },
                      (error) => {
                        console.error('[VideoCallInterface] Streaming error:', error);
                        setIsSendingResponse(false);
                        setAiSpeaking(false);
                        setTempResponse(''); // Clear the live transcript box on error
                        setIsUserSpeaking(false); // Reset user speaking state on error
                        setRequestInProgress(false);
                        
                        // Reset final transcript for next interaction
                        finalTranscript = '';
                        
                        toast({
                          title: "Response Error",
                          description: error.message || 'Failed to get streaming response',
                          status: "error",
                          duration: 5000,
                          isClosable: true,
                        });
                      }
                    );
                    
                  } catch (error) {
                    console.error('[VideoCallInterface] Streaming error:', error);
                    setIsSendingResponse(false);
                    setAiSpeaking(false);
                    setTempResponse(''); // Clear the live transcript box on error
                    setIsUserSpeaking(false); // Reset user speaking state on error
                    setRequestInProgress(false);
                    
                    // Reset final transcript for next interaction
                    finalTranscript = '';
                    
                    toast({
                      title: "Response Error",
                      description: error.message || 'Failed to get streaming response',
                      status: "error",
                      duration: 5000,
                      isClosable: true,
                    });
                  }
                } else if (requestInProgress) {
                  console.log('[VideoCallInterface] Request already in progress, skipping duplicate');
                }
              }, 2000); // 2 second pause detection
              
              setSpeechDetectionTimeout(timeoutId);
            }
          };

          recognition.onerror = (event) => {
            console.error('[VideoCallInterface] Speech recognition error:', event.error);
            setRecognitionState('stopped');
            setIsListening(false);
            
            if (event.error !== 'aborted' && event.error !== 'not-allowed') {
              // Restart recognition on error (unless manually aborted or permission denied)
              setTimeout(() => {
                if (isAudioStreamActiveRef.current && recognitionStateRef.current === 'stopped') {
                  console.log('[VideoCallInterface] Restarting recognition after error');
                  startRecognitionSafely(recognition);
                }
              }, 1000);
            }
          };

          recognition.onend = () => {
            console.log('[VideoCallInterface] Speech recognition ended');
            setRecognitionState('stopped');
            setIsListening(false);
            
            // Restart recognition if we're still supposed to be listening
            if (isAudioStreamActiveRef.current) {
              setTimeout(() => {
                if (recognitionStateRef.current === 'stopped') {
                  console.log('[VideoCallInterface] Restarting recognition after end');
                  startRecognitionSafely(recognition);
                }
              }, 100);
            }
          };

          // Helper function to safely start recognition
          const startRecognitionSafely = (recognitionInstance) => {
            if (recognitionStateRef.current === 'stopped') {
              try {
                setRecognitionState('starting');
                recognitionInstance.start();
              } catch (error) {
                console.error('[VideoCallInterface] Failed to start recognition:', error);
                setRecognitionState('stopped');
                setIsListening(false);
              }
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
          setCandidateAudioLevel(average);
          
          // Voice activity threshold (adjust as needed)
          const voiceThreshold = 20;
          
          // Debug logging every 100 frames
          if (Math.random() < 0.01) { // 1% of frames
            console.log('[VideoCallInterface] Audio level:', average, 'threshold:', voiceThreshold);
          }
          
          if (average > voiceThreshold && !isUserSpeaking) {
            console.log('[VideoCallInterface] Voice activity detected, level:', average);
            setIsListening(true);
          } else if (average <= voiceThreshold && isListening) {
            // Don't immediately stop - let speech recognition handle timing
          }

          requestAnimationFrame(detectVoiceActivity);
        };

        setIsAudioStreamActive(true);
        detectVoiceActivity();
        
        console.log('[VideoCallInterface] Continuous audio streaming initialized');
        
      } catch (error) {
        console.error('[VideoCallInterface] Failed to initialize audio streaming:', error);
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
    if (sessionData?.sessionId && sessionData?.userId) {
      initializeAudioStreaming();
    }

    // Cleanup function
    return () => {
      setIsAudioStreamActive(false);
      setRecognitionState('stopping');
      
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
          console.log('[VideoCallInterface] Recognition already stopped');
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
      
      console.log('[VideoCallInterface] Audio streaming cleaned up');
    };
  }, [sessionData?.sessionId, sessionData?.userId, toast]);

  // Helper function to handle AI responses
  const handleAIResponse = useCallback((responseText) => {
    console.log('[VideoCallInterface] Processing AI response:', responseText);
    setMessagesCount(count => count + 2); // User message + AI response
    
    // Check if voice mode is enabled and voice quality is acceptable
    if (voiceMode && availableVoices.length > 0) {
      // Simulate AI speaking
      setAiSpeaking(true);
      
      // Calculate speaking duration based on response length
      const speakingDuration = Math.max(3000, responseText.length * 60);
      console.log('[VideoCallInterface] AI will speak for:', speakingDuration, 'ms');
      
      // Synthesize speech using Web Speech API
      const speechStarted = speakText(responseText, () => {
        console.log('[VideoCallInterface] AI finished speaking');
        setAiSpeaking(false);
      }, (event) => {
        console.error('[VideoCallInterface] Speech synthesis error:', event);
        setAiSpeaking(false);
        toast({
          title: 'Voice Error',
          description: 'Speech failed. Switching to text-only mode.',
          status: 'warning',
          duration: 3000,
          isClosable: true,
        });
        setVoiceMode(false); // Auto-disable voice on errors
      });
      
      // Show text alongside speech for accessibility
      toast({
        title: '🎤 Alex Speaking',
        description: responseText,
        status: 'info',
        duration: 8000,
        isClosable: true,
        position: 'top-right'
      });
    } else {
      // Text-only mode
      console.log('[VideoCallInterface] Text-only mode - showing AI response as text');
      toast({
        title: '💬 Alex Says',
        description: responseText,
        status: 'success',
        duration: 10000,
        isClosable: true,
        position: 'top'
      });
    }
  }, [voiceMode, availableVoices.length, setMessagesCount, speakText, setAiSpeaking, toast]);

  // Manual toggle for audio streaming
  const toggleAudioStreaming = useCallback(() => {
    // This will trigger the useEffect to reinitialize
    setIsAudioStreamActive(!isAudioStreamActive);
  }, [isAudioStreamActive]);

  // Load available voices for speech synthesis
  useEffect(() => {
    if ('speechSynthesis' in window) {
      // Force voice loading with better timing
      const loadVoices = () => {
        const voices = window.speechSynthesis.getVoices();
        console.log('[VideoCallInterface] Voice loading check - Count:', voices.length);
        setAvailableVoices(voices);
        
        if (voices.length > 0) {
          console.log('[VideoCallInterface] Available voices:', voices.map(v => ({
            name: v.name,
            lang: v.lang,
            localService: v.localService,
            default: v.default,
            quality: v.localService ? 'Local (Better)' : 'Network (Variable)'
          })));
        } else {
          console.warn('[VideoCallInterface] No voices loaded yet, will retry...');
        }
      };

      // Check voices immediately
      loadVoices();
      
      // Also listen for voiceschanged event
      const handleVoicesChanged = () => {
        console.log('[VideoCallInterface] Voices changed event triggered');
        loadVoices();
      };
      
      window.speechSynthesis.addEventListener('voiceschanged', handleVoicesChanged);
      
      // Force voice loading with a silent utterance if needed
      const forceVoiceLoad = () => {
        if (window.speechSynthesis.getVoices().length === 0) {
          console.log('[VideoCallInterface] Forcing voice loading with silent utterance...');
          const silentUtterance = new SpeechSynthesisUtterance(' ');
          silentUtterance.volume = 0;
          silentUtterance.onend = () => {
            console.log('[VideoCallInterface] Silent utterance completed, reloading voices...');
            setTimeout(loadVoices, 100);
          };
          silentUtterance.onerror = (error) => {
            console.error('[VideoCallInterface] Silent utterance error:', error);
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
      console.error('[VideoCallInterface] Speech synthesis not supported in this browser');
    }
  }, []);

  // Helper function to speak AI response
  const speakAIResponse = (text, voices) => {
    console.log('[VideoCallInterface] Starting speech synthesis for AI response');
    setAiSpeaking(true);
    
    // Temporarily pause speech recognition to prevent interruption
    if (speechRecognition) {
      console.log('[VideoCallInterface] Pausing speech recognition during AI speech');
      try {
        speechRecognition.stop();
      } catch (error) {
        console.log('[VideoCallInterface] Speech recognition already stopped:', error.message);
      }
    }
    
    // Synthesize speech using Web Speech API
    const speechStarted = speakText(text, () => {
      console.log('[VideoCallInterface] AI finished speaking');
      setAiSpeaking(false);
      
      // Resume speech recognition after a brief grace period
      setTimeout(() => {
        if (isAudioStreamActiveRef.current && speechRecognition) {
          console.log('[VideoCallInterface] Resuming speech recognition after AI speech');
          try {
            speechRecognition.start();
          } catch (error) {
            console.log('[VideoCallInterface] Could not restart recognition:', error.message);
          }
        }
      }, 500); // 500ms grace period after AI finishes speaking
    }, (event) => {
      console.error('[VideoCallInterface] Speech synthesis error:', event);
      setAiSpeaking(false);
      
      // Resume speech recognition on error too
      setTimeout(() => {
        if (isAudioStreamActiveRef.current && speechRecognition) {
          console.log('[VideoCallInterface] Resuming speech recognition after speech error');
          try {
            speechRecognition.start();
          } catch (error) {
            console.log('[VideoCallInterface] Could not restart recognition after error:', error.message);
          }
        }
      }, 500);
      
      toast({
        title: 'Voice Error',
        description: 'Speech failed. Check browser audio settings.',
        status: 'warning',
        duration: 3000,
        isClosable: true,
      });
    });
    
    if (!speechStarted) {
      console.warn('[VideoCallInterface] Speech synthesis failed to start');
      setAiSpeaking(false);
      
      // Resume speech recognition if speech failed to start
      setTimeout(() => {
        if (isAudioStreamActiveRef.current && speechRecognition) {
          console.log('[VideoCallInterface] Resuming speech recognition after failed speech start');
          try {
            speechRecognition.start();
          } catch (error) {
            console.log('[VideoCallInterface] Could not restart recognition after failed start:', error.message);
          }
        }
      }, 100);
    }
  };

  // Function to render messages with ChatMessage component
  const renderMessages = () => {
    if (!Array.isArray(messages)) {
      console.warn('[VideoCallInterface] messages is not an array in renderMessages:', messages);
      return (
        <ChatMessage
          sender="assistant"
          text="Something went wrong displaying the conversation. Please refresh the page to try again."
          isError={true}
        />
      );
    }
    
    return messages.map((message, index) => (
      <ChatMessage
        key={index}
        sender={message.sender || message.role || 'assistant'}
        text={message.text || message.content || ''}
        audioUrl={message.audioUrl}
        isFeedback={message.isFeedback}
        isHint={message.isHint}
        isGenericResponse={message.isGenericResponse}
        isError={message.isError}
        isTransition={message.isTransition}
      />
    ));
  };

  // Loading state
  if (!isInitialized || rtcLoading || geminiConnecting) {
    return (
      <Center minH="100vh" bg={bgColor}>
        <VStack spacing={4}>
          <Spinner size="xl" color="primary.500" thickness="4px" />
          <Text fontSize="lg" color="gray.600">
            Setting up your video interview...
          </Text>
          <Text fontSize="sm" color="gray.500">
            Please allow camera and microphone access
          </Text>
        </VStack>
      </Center>
    );
  }

  // Error state
  if (rtcError || geminiError) {
    return (
      <Center minH="100vh" bg={bgColor} p={6}>
        <VStack spacing={4} maxW="md" textAlign="center">
          <Alert status="error" borderRadius="lg">
            <AlertIcon />
            <Box>
              <Text fontWeight="bold">Connection Error</Text>
              <Text fontSize="sm">{rtcError || geminiError}</Text>
            </Box>
          </Alert>
          
          <Button
            colorScheme="primary"
            onClick={initializeVideoCall}
            size="lg"
          >
            Try Again
          </Button>
          
          <Button
            variant="outline"
            onClick={() => navigate('/')}
            size="sm"
          >
            Return Home
          </Button>
        </VStack>
      </Center>
    );
  }

  // Interview results state
  if (interviewComplete) {
    return (
      <Center minH="100vh" bg={bgColor}>
        <VStack spacing={4} textAlign="center">
          <Text fontSize="2xl" fontWeight="bold" color="green.600">
            Interview Complete!
          </Text>
          <Text fontSize="md" color="gray.600">
            Thank you for your time. You will be redirected shortly.
          </Text>
          <Button
            colorScheme="primary"
            onClick={() => navigate('/')}
            size="lg"
          >
            Return Home
          </Button>
        </VStack>
      </Center>
    );
  }

  return (
    <Box minH="100%" bg={bgColor} w="100%" h="100%">
      <Grid
        templateAreas={gridTemplate}
        gridTemplateRows={gridAreas.split('/')[0]}
        gridTemplateColumns={gridAreas.split('/')[1]}
        gap={4}
        h="100%"
        w="100%"
        minH="500px"
      >
        {/* Main Video Area */}
        <Box gridArea="video" position="relative" p={2}>
          <Grid
            templateColumns={isMobile ? "1fr" : "1fr 300px"}
            templateRows={isMobile ? "1fr 200px" : "1fr"}
            gap={0}
            h="100%"
            w="100%"
            position="relative"
          >
            {/* Candidate Video Feed */}
            <Box position="relative">
              <CameraFeed
                stream={stream}
                isEnabled={cameraEnabled}
                isLoading={rtcLoading}
                error={rtcError}
                placeholder="candidate"
                isSpeaking={candidateSpeaking}
                height="100%"
                borderRadius="xl"
              />
              
              {/* Speaking indicator overlay */}
              {candidateSpeaking && (
                <Box position="absolute" top={4} left={4}>
                  <SpeakingIndicator 
                    isActive={candidateSpeaking} 
                    speaker="candidate"
                    compact={isMobile}
                  />
                </Box>
              )}
            </Box>

            {/* AI Interviewer Area - Now Smaller and Right-aligned */}
            <Box position="relative" w="100%">
              <CameraFeed
                stream={null}
                isEnabled={true}
                placeholder="ai"
                isSpeaking={aiSpeaking}
                height="100%"
                borderRadius="xl"
              />
              
              {/* AI speaking indicator */}
              {aiSpeaking && (
                <Box position="absolute" top={4} left={4}>
                  <SpeakingIndicator 
                    isActive={aiSpeaking} 
                    speaker="ai"
                    compact={isMobile}
                  />
                </Box>
              )}
            </Box>
          </Grid>

          {/* Coding Challenge Overlay */}
          {showCodingChallenge && (
            <Box
              position="absolute"
              top={0}
              left={0}
              right={0}
              bottom={0}
              bg="whiteAlpha.95"
              backdropFilter="blur(10px)"
              borderRadius="xl"
              p={4}
            >
              <CodingChallenge
                jobRoleData={jobRoleData}
                onComplete={() => handleStageChange('feedback')}
                isVideoCall={true}
                sessionId={sessionData?.sessionId}
                userId={sessionData?.userId}
              />
            </Box>
          )}

          {/* Audio Level Indicator (for debugging) - Moved to bottom */}
          {isAudioStreamActive && (
            <Box position="absolute" bottom="20px" right="20px" bg="blackAlpha.700" p={2} borderRadius="md">
              <Text color="white" fontSize="sm">
                🎙️ Audio Level: {candidateAudioLevel?.toFixed(1) || '0.0'}
              </Text>
              <Progress 
                value={candidateAudioLevel || 0} 
                max={100} 
                colorScheme={candidateAudioLevel > 20 ? 'green' : 'gray'} 
                size="sm" 
                mt={1}
              />
            </Box>
          )}
        </Box>

        {/* Sidebar - Now at the top */}
        <Box gridArea="sidebar" p={2}>
          <Box w="100%" bg="white" borderRadius="lg" boxShadow="md" p={4}>
            <ConversationIndicators
              candidateSpeaking={candidateSpeaking}
              aiSpeaking={aiSpeaking}
              candidateAudioLevel={candidateAudioLevel}
              aiAudioLevel={aiSpeaking ? 0.7 : 0}
              interviewStage={interviewStage}
              connectionQuality={connectionQuality}
              sessionDuration={sessionDuration}
              messagesCount={messagesCount}
              isListening={geminiListening}
              compact={true}
            />
          </Box>
        </Box>

        {/* Controls */}
        <Box gridArea="controls" p={2}>
          <VStack spacing={3} w="100%" align="center">
            <Box w="100%" display="flex" justifyContent="center">
              <AudioControls
                micEnabled={micEnabled}
                cameraEnabled={cameraEnabled}
                onToggleMic={toggleMicrophone}
                onToggleCamera={toggleCamera}
                onEndCall={handleEndInterview}
                audioLevel={candidateAudioLevel}
                connectionStatus={geminiConnected ? 'connected' : 'connecting'}
                compact={isMobile}
              />
            </Box>
            
            {/* Continuous Audio Interface */}
            {sessionData?.sessionId && (
              <Box w="80%" maxW="700px" p={4} bg="green.50" borderRadius="lg" border="2px solid" borderColor="green.200">
                {/* Audio Status */}
                <HStack spacing={4} mb={3} justify="space-between" wrap="wrap">
                  <VStack align="start" spacing={1}>
                    <Text fontSize="sm" fontWeight="bold" color="green.700">
                      🎤 Continuous Audio Active
                    </Text>
                    <HStack spacing={2}>
                      <Button
                        size="xs"
                        colorScheme={voiceMode ? "green" : "gray"}
                        variant={voiceMode ? "solid" : "outline"}
                        onClick={() => setVoiceMode(!voiceMode)}
                      >
                        {voiceMode ? "AI Voice ON" : "AI Voice OFF"}
                      </Button>
                      <Button
                        size="xs"
                        colorScheme="blue"
                        variant="outline"
                        onClick={() => {
                          // Test voice synthesis immediately
                          if ('speechSynthesis' in window) {
                            const testText = "Namaste! I'm your AI interviewer. I'm excited to conduct your interview today. How are you feeling about the process?";
                            console.log('[VideoCallInterface] Testing Indian female voice synthesis...');
                            
                            const voices = speechSynthesis.getVoices();
                            console.log('[VideoCallInterface] Voices available for test:', voices.length);
                            
                            if (voices.length > 0) {
                              const testUtterance = new SpeechSynthesisUtterance(testText);
                              
                              // Use the same Indian female voice selection logic as speakText
                              const preferredVoice = voices.find(voice => {
                                const name = voice.name.toLowerCase();
                                const lang = voice.lang.toLowerCase();
                                
                                // First priority: Indian English female voices
                                if (lang.includes('en-in') || name.includes('india')) {
                                  if (name.includes('female') || name.includes('woman') || 
                                      name.includes('samantha') || name.includes('veena') || 
                                      name.includes('raveena') || name.includes('priya')) {
                                    return true;
                                  }
                                }
                                
                                // Second priority: Google female voices with Indian option
                                if (name.includes('google') && lang.startsWith('en')) {
                                  if (name.includes('female') || name.includes('woman') || 
                                      name.includes('indian') || name.includes('hindi')) {
                                    return true;
                                  }
                                }
                                
                                // Third priority: Microsoft female voices 
                                if (name.includes('microsoft') && lang.startsWith('en')) {
                                  if (name.includes('female') || name.includes('woman')) {
                                    return true;
                                  }
                                }
                                
                                return false;
                              }) || voices.find(voice => {
                                const name = voice.name.toLowerCase();
                                const lang = voice.lang.toLowerCase();
                                return lang.startsWith('en') && (name.includes('female') || name.includes('woman'));
                              }) || voices.find(voice => voice.lang.startsWith('en'));
                              
                              if (preferredVoice) {
                                testUtterance.voice = preferredVoice;
                                console.log('[VideoCallInterface] Test using Indian female voice:', {
                                  name: preferredVoice.name,
                                  lang: preferredVoice.lang,
                                  isLocal: preferredVoice.localService
                                });
                              }
                              
                              // Use same natural settings as speakText
                              testUtterance.rate = 0.9; // Natural conversational pace
                              testUtterance.pitch = 1.1; // Slightly higher pitch for female voice
                              testUtterance.volume = 0.85; // Comfortable listening volume
                              
                              testUtterance.onstart = () => {
                                console.log('[VideoCallInterface] Indian female voice test started');
                                toast({
                                  title: "🎙️ Testing Indian Female Voice",
                                  description: `Voice: ${preferredVoice?.name || 'Default'} | Natural conversational tone`,
                                  status: "info",
                                  duration: 4000,
                                  isClosable: true,
                                });
                              };
                              
                              testUtterance.onend = () => {
                                console.log('[VideoCallInterface] Indian female voice test completed');
                                toast({
                                  title: "✅ Voice Test Complete",
                                  description: `Used: ${preferredVoice?.name || 'Default'} | Did this sound natural and pleasant?`,
                                  status: "success",
                                  duration: 8000,
                                  isClosable: true,
                                });
                              };
                              
                              testUtterance.onerror = (error) => {
                                console.error('[VideoCallInterface] Voice test error:', error);
                                toast({
                                  title: "❌ Voice Test Failed",
                                  description: `Error: ${error.error || 'Unknown error'} | Try refreshing the page`,
                                  status: "error",
                                  duration: 5000,
                                  isClosable: true,
                                });
                              };
                              
                              speechSynthesis.speak(testUtterance);
                            } else {
                              console.error('[VideoCallInterface] No voices available for test');
                              toast({
                                title: "❌ No Voices Available",
                                description: "Browser voices are not loaded. Try refreshing the page.",
                                status: "error",
                                duration: 5000,
                                isClosable: true,
                              });
                            }
                          } else {
                            console.error('[VideoCallInterface] Speech synthesis not supported');
                            toast({
                              title: "❌ Not Supported",
                              description: "Speech synthesis is not supported in this browser.",
                              status: "error",
                              duration: 5000,
                              isClosable: true,
                            });
                          }
                        }}
                      >
                        🔊 Test Indian Voice
                      </Button>
                      <Button
                        size="xs"
                        colorScheme={isAudioStreamActive ? "red" : "green"}
                        variant="solid"
                        onClick={toggleAudioStreaming}
                        isDisabled={isSendingResponse}
                        leftIcon={<Box>{isAudioStreamActive ? "🔇" : "🎙️"}</Box>}
                      >
                        {isAudioStreamActive ? "Stop Listening" : "Start Listening"}
                      </Button>
                    </HStack>
                  </VStack>
                  
                  <VStack align="end" spacing={1}>
                    <Text fontSize="xs" color="gray.600">
                      🎧 Voices: {availableVoices.length} available
                    </Text>
                    <Text fontSize="xs" color="gray.600">
                      🎤 Audio Stream: {isAudioStreamActive ? "✅ Active" : "❌ Inactive"}
                    </Text>
                    <Text fontSize="xs" color="gray.600">
                      🔊 Voice Mode: {voiceMode ? "✅ Enabled" : "❌ Disabled"}
                    </Text>
                    <Text fontSize="xs" color={aiSpeaking ? "green.600" : "gray.600"}>
                      🤖 AI Speaking: {aiSpeaking ? "✅ Yes" : "❌ No"}
                    </Text>
                  </VStack>
                </HStack>

                <Alert status="success" size="sm" borderRadius="md" mb={3}>
                  <AlertIcon />
                  <VStack align="start" spacing={1}>
                    <Text fontSize="sm" fontWeight="bold">
                      🎯 Natural Video Call Mode Active!
                    </Text>
                    <Text fontSize="xs">
                      Just speak naturally - your voice is automatically detected and responses are sent to Alex. 
                      No buttons needed!
                    </Text>
                  </VStack>
                </Alert>
                
                {/* Live Speech Status */}
                {isAudioStreamActive && (
                  <Box mb={3}>
                    {isUserSpeaking && (
                      <Alert status="info" size="sm" borderRadius="md" mb={2}>
                        <AlertIcon />
                        <HStack spacing={2}>
                          <Spinner size="sm" />
                          <Text fontSize="sm">
                            🗣️ You're speaking... (auto-sending when you pause)
                          </Text>
                        </HStack>
                      </Alert>
                    )}
                    
                    {isSendingResponse && (
                      <Alert status="warning" size="sm" borderRadius="md" mb={2}>
                        <AlertIcon />
                        <HStack spacing={2}>
                          <Spinner size="sm" />
                          <Text fontSize="sm">
                            📤 Sending your response to Alex...
                          </Text>
                        </HStack>
                      </Alert>
                    )}
                    
                    {aiSpeaking && (
                      <Alert status="info" size="sm" borderRadius="md" mb={2}>
                        <AlertIcon />
                        <HStack spacing={2}>
                          <Spinner size="sm" />
                          <Text fontSize="sm">
                            🤖 Alex is responding... (you can interrupt anytime)
                          </Text>
                        </HStack>
                      </Alert>
                    )}
                  </Box>
                )}

                {/* Live Transcript Display */}
                {isAudioStreamActive && (
                  <VStack spacing={3}>
                    <Box w="100%" p={3} bg="white" borderRadius="md" border="1px solid" borderColor="green.300" minHeight="100px">
                      <Text fontSize="xs" color="gray.500" mb={2}>
                        Live Transcript (automatically sent when you pause):
                      </Text>
                      <Text fontSize="sm" color={tempResponse.trim() ? "gray.800" : "gray.400"}>
                        {tempResponse.trim() || "Start speaking and your words will appear here..."}
                      </Text>
                    </Box>
                    
                    <HStack spacing={2} w="100%" justify="center">
                      <Text fontSize="xs" color="gray.500" textAlign="center">
                        💡 Speak naturally • Pause for 2 seconds to auto-send • You can interrupt Alex anytime
                      </Text>
                    </HStack>
                  </VStack>
                )}
                
                {!isAudioStreamActive && (
                  <Box textAlign="center" p={4}>
                    <Text fontSize="md" color="gray.600" mb={2}>
                      🎤 Click "Start Listening" to begin the natural conversation
                    </Text>
                    <Text fontSize="xs" color="gray.500">
                      Grant microphone permission when prompted
                    </Text>
                  </Box>
                )}
              </Box>
            )}
          </VStack>
        </Box>
      </Grid>
    </Box>
  );
};

export default VideoCallInterface; 