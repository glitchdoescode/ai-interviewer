import React, { useState, useEffect } from 'react';
import {
  Box,
  Button,
  VStack,
  Text,
  Heading,
  Alert,
  AlertIcon,
  Code,
  Badge,
  SimpleGrid,
  Divider
} from '@chakra-ui/react';
import useAudioRecorder from '../hooks/useAudioRecorder';

/**
 * Microphone Test Page to diagnose audio recording issues
 */
const MicrophoneTest = () => {
  const [logs, setLogs] = useState([]);
  const [deviceInfo, setDeviceInfo] = useState([]);
  const [browserInfo, setBrowserInfo] = useState('');
  const [audioContextState, setAudioContextState] = useState('unknown');
  
  // Use the hook - replace the console.log in the hook with captured logs
  const {
    isRecording,
    error,
    permissionGranted,
    isInitializing,
    initRecording,
    startRecording,
    stopRecording,
    checkPermissionStatus
  } = useAudioRecorder();
  
  // Capture console logs
  useEffect(() => {
    const originalLog = console.log;
    const originalError = console.error;
    
    console.log = (...args) => {
      if (args[0] && typeof args[0] === 'string' && args[0].startsWith('DEBUG:')) {
        setLogs(prev => [...prev, { type: 'log', message: args.join(' ') }]);
      }
      originalLog.apply(console, args);
    };
    
    console.error = (...args) => {
      if (args[0] && typeof args[0] === 'string' && args[0].startsWith('DEBUG:')) {
        setLogs(prev => [...prev, { type: 'error', message: args.join(' ') }]);
      }
      originalError.apply(console, args);
    };
    
    return () => {
      console.log = originalLog;
      console.error = originalError;
    };
  }, []);
  
  // Get browser information
  useEffect(() => {
    const browserInfo = `${navigator.userAgent}`;
    setBrowserInfo(browserInfo);
    
    // Try to enumerate audio devices
    const getDevices = async () => {
      try {
        const devices = await navigator.mediaDevices.enumerateDevices();
        const audioDevices = devices.filter(device => device.kind === 'audioinput');
        setDeviceInfo(audioDevices.map(device => ({
          deviceId: device.deviceId,
          label: device.label || 'Unnamed device',
          groupId: device.groupId
        })));
      } catch (err) {
        console.error('Failed to enumerate devices:', err);
      }
    };
    
    getDevices();
  }, []);
  
  // Check if audio context can be created
  const checkAudioContext = async () => {
    try {
      addLog('Testing AudioContext creation...');
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      const context = new AudioContext();
      addLog(`AudioContext created with state: ${context.state}`);
      setAudioContextState(context.state);
      
      if (context.state !== 'running') {
        addLog('Trying to resume AudioContext...');
        
        // Play silent sound to unlock audio context on mobile
        const buffer = context.createBuffer(1, 1, 22050);
        const source = context.createBufferSource();
        source.buffer = buffer;
        source.connect(context.destination);
        source.start(0);
        
        try {
          await context.resume();
          addLog(`AudioContext after resume: ${context.state}`);
          setAudioContextState(context.state);
        } catch (err) {
          addLog(`Failed to resume AudioContext: ${err.message}`);
        }
      }
      
      // Clean up
      setTimeout(() => {
        context.close();
      }, 1000);
      
    } catch (err) {
      addLog(`Error creating AudioContext: ${err.message}`);
    }
  };
  
  // Helper to add logs
  const addLog = (message) => {
    setLogs(prev => [...prev, { type: 'log', message }]);
  };
  
  // Test microphone permission
  const testPermission = async () => {
    addLog('Checking microphone permission...');
    const result = await checkPermissionStatus();
    addLog(`Permission check result: ${result}`);
  };
  
  // Test recorder initialization
  const testInit = async () => {
    addLog('Initializing recorder...');
    const result = await initRecording();
    addLog(`Initialization result: ${result}`);
  };
  
  // Test full recording cycle
  const testRecording = async () => {
    if (isRecording) {
      addLog('Stopping recording...');
      const audioData = await stopRecording();
      addLog(`Recording stopped, got audio data: ${!!audioData}`);
    } else {
      addLog('Starting recording...');
      const result = await startRecording();
      addLog(`Recording start result: ${result}`);
    }
  };
  
  // Clear logs
  const clearLogs = () => {
    setLogs([]);
  };

  return (
    <Box p={6} maxWidth="1200px" mx="auto">
      <VStack spacing={6} align="stretch">
        <Heading as="h1" size="xl">Microphone Troubleshooter</Heading>
        
        <SimpleGrid columns={{ base: 1, md: 2 }} spacing={6}>
          <Box p={4} borderWidth="1px" borderRadius="lg" overflow="hidden">
            <Heading as="h2" size="md" mb={4}>System Info</Heading>
            
            <VStack align="stretch" spacing={3}>
              <Box>
                <Text fontWeight="bold">Browser:</Text>
                <Code fontSize="sm" p={2} borderRadius="md" width="100%">
                  {browserInfo}
                </Code>
              </Box>
              
              <Box>
                <Text fontWeight="bold">Audio State:</Text>
                <Badge colorScheme={audioContextState === 'running' ? 'green' : 'red'}>
                  {audioContextState}
                </Badge>
              </Box>
              
              <Box>
                <Text fontWeight="bold">Audio Devices ({deviceInfo.length}):</Text>
                {deviceInfo.length > 0 ? (
                  <VStack align="stretch" spacing={2} pl={4}>
                    {deviceInfo.map((device, i) => (
                      <Text key={i} fontSize="sm">
                        {device.label} {device.label ? '' : '(No label - permission not granted)'}
                      </Text>
                    ))}
                  </VStack>
                ) : (
                  <Text fontSize="sm">No audio devices detected.</Text>
                )}
              </Box>
              
              <Box>
                <Text fontWeight="bold">Recorder State:</Text>
                <VStack align="start" spacing={1}>
                  <Badge colorScheme={permissionGranted ? 'green' : 'red'}>
                    Permission: {permissionGranted ? 'Granted' : 'Not Granted'}
                  </Badge>
                  <Badge colorScheme={isRecording ? 'red' : 'gray'}>
                    Recording: {isRecording ? 'Active' : 'Inactive'}
                  </Badge>
                  <Badge colorScheme={isInitializing ? 'yellow' : 'gray'}>
                    Initializing: {isInitializing ? 'Yes' : 'No'}
                  </Badge>
                </VStack>
              </Box>
            </VStack>
          </Box>
          
          <Box p={4} borderWidth="1px" borderRadius="lg" overflow="hidden">
            <Heading as="h2" size="md" mb={4}>Test Functions</Heading>
            
            <VStack spacing={4} align="stretch">
              <Button colorScheme="blue" onClick={checkAudioContext}>
                Test AudioContext
              </Button>
              
              <Button colorScheme="teal" onClick={testPermission}>
                Test Microphone Permission
              </Button>
              
              <Button colorScheme="purple" onClick={testInit}>
                Initialize Recorder
              </Button>
              
              <Button 
                colorScheme={isRecording ? "red" : "green"}
                onClick={testRecording}
              >
                {isRecording ? "Stop Recording" : "Start Recording"}
              </Button>
              
              <Divider />
              
              <Button colorScheme="gray" onClick={clearLogs}>
                Clear Logs
              </Button>
            </VStack>
          </Box>
        </SimpleGrid>
        
        {error && (
          <Alert status="error">
            <AlertIcon />
            {error}
          </Alert>
        )}
        
        <Box p={4} borderWidth="1px" borderRadius="lg" overflow="auto" maxHeight="400px">
          <Heading as="h2" size="md" mb={4}>Debug Logs</Heading>
          <VStack align="stretch" spacing={1}>
            {logs.map((log, index) => (
              <Text 
                key={index} 
                fontSize="sm" 
                fontFamily="monospace"
                color={log.type === 'error' ? 'red.500' : 'inherit'}
              >
                [{new Date().toLocaleTimeString()}] {log.message}
              </Text>
            ))}
          </VStack>
        </Box>
      </VStack>
    </Box>
  );
};

export default MicrophoneTest; 