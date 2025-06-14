import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * Custom hook for integrating with Gemini Live API for real-time audio
 * This is a frontend-ready implementation that will connect to our backend
 * services when they become available
 */
// Temporary flag to disable WebSocket for testing
const DISABLE_WEBSOCKET = true;

const useGeminiLiveAudio = (sessionId, userId) => {
  // Generate unique instance ID to track this hook instance
  const instanceId = useRef(`gemini-audio-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`);
  
  const [isConnected, setIsConnected] = useState(DISABLE_WEBSOCKET ? true : false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [connectionError, setConnectionError] = useState(null);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [audioLevel, setAudioLevel] = useState(0);
  const [lastTranscription, setLastTranscription] = useState('');
  const [lastAIResponse, setLastAIResponse] = useState('');
  const [connectionQuality, setConnectionQuality] = useState('excellent');
  
  const websocketRef = useRef(null);
  const audioContextRef = useRef(null);
  const audioStreamRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const reconnectAttempts = useRef(0);
  const connectionStateRef = useRef('idle'); // 'idle', 'connecting', 'connected', 'disconnected'
  const connectFnRef = useRef(null); // Store connect function to avoid stale closures
  const maxReconnectAttempts = 5;

  /**
   * Initialize connection to backend Gemini Live API service
   */
  const connect = useCallback(async () => {
    // Prevent multiple simultaneous connection attempts
    if (connectionStateRef.current === 'connecting' || connectionStateRef.current === 'connected') {
      console.log(`[${instanceId.current}] Connection already in progress or established, skipping connect attempt`);
      return;
    }

    // Skip WebSocket connection if disabled (for testing)
    if (DISABLE_WEBSOCKET) {
      console.log(`[${instanceId.current}] WebSocket disabled for testing - returning mock connection`);
      connectionStateRef.current = 'connected';
      setIsConnected(true);
      setIsConnecting(false);
      setConnectionError(null);
      return;
    }

    connectionStateRef.current = 'connecting';
    setIsConnecting(true);
    setConnectionError(null);

    try {
      // Connect to the actual Gemini Live API WebSocket endpoint
      // WebSocket connections can't use the proxy, so use direct connection
      const wsUrl = `ws://localhost:8000/api/gemini-live/ws/gemini-live/${sessionId}?user_id=${userId}`;
      
      console.log(`[${instanceId.current}] Attempting to connect to Gemini Live API service...`);
      
      const websocket = new WebSocket(wsUrl);
      websocketRef.current = websocket;
      
      websocket.onopen = () => {
        // Check if we were disconnected during the async operation
        if (connectionStateRef.current !== 'connecting') {
          console.log(`[${instanceId.current}] Connection cancelled during attempt`);
          websocket.close();
          return;
        }
        
        connectionStateRef.current = 'connected';
        setIsConnected(true);
        setConnectionQuality('excellent');
        reconnectAttempts.current = 0;
        
        console.log(`[${instanceId.current}] Connected to Gemini Live API service`);
      };
      
      websocket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          
          switch (message.type) {
            case 'connection_established':
              console.log(`[${instanceId.current}] Connection established:`, message);
              break;
              
            case 'listening_started':
              setIsListening(true);
              break;
              
            case 'listening_stopped':
              setIsListening(false);
              break;
              
            case 'ai_response':
              setLastAIResponse(message.response || '');
              setIsSpeaking(false); // AI finished speaking
              break;
              
            case 'transcription':
              setLastTranscription(message.text || '');
              break;
              
            case 'error':
              console.error(`[${instanceId.current}] WebSocket error:`, message.message);
              setConnectionError(message.message);
              break;
              
            case 'pong':
              // Health check response
              break;
              
            default:
              console.log(`[${instanceId.current}] Unknown message type:`, message.type);
          }
        } catch (error) {
          console.error(`[${instanceId.current}] Error parsing WebSocket message:`, error);
        }
      };
      
      websocket.onerror = (error) => {
        console.error(`[${instanceId.current}] WebSocket connection error:`, error);
        connectionStateRef.current = 'disconnected';
        setConnectionError('WebSocket connection failed');
        setIsConnected(false);
        setIsConnecting(false);
      };
      
      websocket.onclose = (event) => {
        console.log(`[${instanceId.current}] WebSocket connection closed:`, event.code, event.reason);
        connectionStateRef.current = 'disconnected';
        setIsConnected(false);
        setIsConnecting(false);
        
        // Don't auto-reconnect to prevent loops during development
        if (event.code !== 1000) { // 1000 = normal closure
          setConnectionError(`Connection closed unexpectedly: ${event.reason || event.code}`);
        }
      };

    } catch (error) {
      console.error('Failed to connect to Gemini Live API:', error);
      connectionStateRef.current = 'disconnected';
      setConnectionError(error.message || 'Connection failed');
      setIsConnecting(false);
    }
  }, [sessionId, userId]);

  // Store connect function in ref to avoid stale closures
  connectFnRef.current = connect;

  /**
   * Disconnect from the service
   */
  const disconnect = useCallback(() => {
    console.log(`[${instanceId.current}] Disconnecting from Gemini Live API service...`);
    
    connectionStateRef.current = 'disconnected';
    
    if (websocketRef.current) {
      websocketRef.current.close();
      websocketRef.current = null;
    }
    
    if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
    
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    
    setIsConnected(false);
    setIsConnecting(false);
    setIsSpeaking(false);
    setIsListening(false);
    setAudioLevel(0);
    
    console.log(`[${instanceId.current}] Disconnected from Gemini Live API service`);
  }, []);

  /**
   * Start streaming audio to Gemini Live API
   */
  const startStreaming = useCallback(async (audioStream) => {
    if (!isConnected || !audioStream || !websocketRef.current) return;

    try {
      audioStreamRef.current = audioStream;
      setIsListening(true);
      
      // Initialize Web Audio API for audio processing
      if (!audioContextRef.current) {
        audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)();
      }
      
      const source = audioContextRef.current.createMediaStreamSource(audioStream);
      const analyser = audioContextRef.current.createAnalyser();
      const processor = audioContextRef.current.createScriptProcessor(4096, 1, 1);
      
      analyser.fftSize = 256;
      source.connect(analyser);
      source.connect(processor);
      processor.connect(audioContextRef.current.destination);
      
      // Send audio data to backend
      let lastSpeakingState = false;
      
      processor.onaudioprocess = (event) => {
        if (connectionStateRef.current !== 'connected' || !websocketRef.current) return;
        
        const inputBuffer = event.inputBuffer;
        const inputData = inputBuffer.getChannelData(0);
        
        // Convert float32 to int16 for transmission
        const int16Data = new Int16Array(inputData.length);
        for (let i = 0; i < inputData.length; i++) {
          int16Data[i] = Math.max(-1, Math.min(1, inputData[i])) * 0x7FFF;
        }
        
        // Send audio data as base64
        const audioBase64 = btoa(String.fromCharCode(...new Uint8Array(int16Data.buffer)));
        
        try {
          websocketRef.current.send(JSON.stringify({
            type: 'audio_data',
            data: audioBase64,
            timestamp: Date.now()
          }));
        } catch (error) {
          console.error(`[${instanceId.current}] Error sending audio data:`, error);
        }
      };
      
      // Monitor audio levels
      const dataArray = new Uint8Array(analyser.frequencyBinCount);
      const updateAudioLevel = () => {
        if (connectionStateRef.current !== 'connected') return;
        
        analyser.getByteFrequencyData(dataArray);
        const average = dataArray.reduce((sum, value) => sum + value, 0) / dataArray.length;
        const normalizedLevel = Math.min(average / 128, 1);
        
        setAudioLevel(normalizedLevel);
        
        // Detect if user is speaking
        const isSpeakingNow = normalizedLevel > 0.1;
        setIsSpeaking(isSpeakingNow);
        
        // Notify backend when speaking starts/stops
        if (isSpeakingNow !== lastSpeakingState) {
          lastSpeakingState = isSpeakingNow;
          try {
            websocketRef.current.send(JSON.stringify({
              type: isSpeakingNow ? 'start_listening' : 'stop_listening',
              timestamp: Date.now()
            }));
          } catch (error) {
            console.error(`[${instanceId.current}] Error sending speaking state:`, error);
          }
        }
        
        requestAnimationFrame(updateAudioLevel);
      };
      
      updateAudioLevel();
      
      console.log('Started audio streaming to Gemini Live API');

    } catch (error) {
      console.error('Failed to start audio streaming:', error);
      setConnectionError('Failed to start audio streaming');
    }
  }, [isConnected]);

  /**
   * Stop streaming audio
   */
  const stopStreaming = useCallback(() => {
    if (audioStreamRef.current) {
      audioStreamRef.current = null;
    }
    
    setIsListening(false);
    setIsSpeaking(false);
    setAudioLevel(0);
    
    console.log('Stopped audio streaming');
  }, []);

  /**
   * Send a text message to the AI (fallback mode)
   */
  const sendMessage = useCallback(async (message) => {
    if (!isConnected || !websocketRef.current) {
      throw new Error('Not connected to Gemini Live API');
    }

    try {
      console.log('Sending text message to AI:', message);
      
      websocketRef.current.send(JSON.stringify({
        type: 'text_message',
        message: message,
        timestamp: Date.now()
      }));
      
      return true;

    } catch (error) {
      console.error('Failed to send message:', error);
      throw error;
    }
  }, [isConnected]);

  /**
   * Get connection statistics
   */
  const getConnectionStats = useCallback(() => {
    return {
      isConnected,
      connectionQuality,
      reconnectAttempts: reconnectAttempts.current,
      lastError: connectionError
    };
  }, [isConnected, connectionQuality, connectionError]);

  // Initialize connection only once when sessionId and userId are first provided
  useEffect(() => {
    console.log(`[${instanceId.current}] useGeminiLiveAudio effect - sessionId: ${sessionId}, userId: ${userId}, connectionState: ${connectionStateRef.current}`);
    
    // Only proceed if we have valid string values for both sessionId and userId
    if (sessionId && userId && 
        typeof sessionId === 'string' && typeof userId === 'string' &&
        sessionId.length > 0 && userId.length > 0 &&
        sessionId !== 'null' && sessionId !== 'undefined' &&
        connectionStateRef.current === 'idle') {
      console.log(`[${instanceId.current}] Initializing Gemini Live Audio connection for session: ${sessionId}`);
      connectFnRef.current?.();
    } else if (sessionId && userId && connectionStateRef.current === 'disconnected') {
      // If we get a valid sessionId after being disconnected, reset to idle and try to connect
      console.log(`[${instanceId.current}] Received valid sessionId after disconnect, resetting to idle state`);
      connectionStateRef.current = 'idle';
      if (typeof sessionId === 'string' && typeof userId === 'string' &&
          sessionId.length > 0 && userId.length > 0 &&
          sessionId !== 'null' && sessionId !== 'undefined') {
        connectFnRef.current?.();
      }
    } else {
      console.log(`[${instanceId.current}] Skipping connection - sessionId: '${sessionId}' (type: ${typeof sessionId}), userId: '${userId}' (type: ${typeof userId}), connectionState: '${connectionStateRef.current}'`);
    }
  }, [sessionId, userId]); // This will re-run when sessionId changes

  // Cleanup on unmount only
  useEffect(() => {
    return () => {
      console.log(`[${instanceId.current}] useGeminiLiveAudio cleanup - performing disconnect`);
      if (connectionStateRef.current !== 'idle' && connectionStateRef.current !== 'disconnected') {
        disconnect();
      }
    };
  }, []); // Empty dependency array to run only on mount/unmount

  // Mock AI speaking simulation for development
  useEffect(() => {
    if (lastAIResponse) {
      setIsSpeaking(false); // Stop user speaking
      
      // Simulate AI speaking for the duration of the response
      const speakingDuration = Math.max(2000, lastAIResponse.length * 50); // ~50ms per character
      
      setTimeout(() => {
        if (connectionStateRef.current === 'connected') {
          setIsListening(true);
        }
      }, speakingDuration);
    }
  }, [lastAIResponse]);

  return {
    // Connection state
    isConnected,
    isConnecting,
    connectionError,
    connectionQuality,
    
    // Audio state
    isSpeaking,
    isListening,
    audioLevel,
    
    // Conversation state
    lastTranscription,
    lastAIResponse,
    
    // Methods
    connect,
    disconnect,
    startStreaming,
    stopStreaming,
    sendMessage,
    getConnectionStats,
    
    // Computed values
    canStream: isConnected && !isConnecting,
    hasError: connectionError !== null
  };
};

export default useGeminiLiveAudio; 