import React, { useState } from 'react';
import {
  Box,
  VStack,
  HStack,
  Text,
  Button,
  Badge,
  Collapse,
  useDisclosure,
} from '@chakra-ui/react';
import { FaShieldAlt, FaChevronDown, FaChevronUp } from 'react-icons/fa';
import WebcamMonitor from './WebcamMonitor';
import ScreenActivityMonitor from './ScreenActivityMonitor';

/**
 * ProctoringPanel component that houses all proctoring functionality
 * Designed to be integrated into the Interview page
 */
const ProctoringPanel = ({ 
  sessionId, 
  userId, 
  isEnabled = false,
  onStatusChange = () => {},
  temporaryEmbedding,
  videoRef,
}) => {
  const { isOpen, onToggle } = useDisclosure({ defaultIsOpen: true });
  const [proctoringStatus, setProctoringStatus] = useState({
    isActive: false,
    hasCamera: false,
    hasDetection: false,
    hasWebSocket: false,
    hasScreenMonitoring: false,
  });
  const [eventCount, setEventCount] = useState(0);

  const handleWebcamStatusChange = (status) => {
    setProctoringStatus(prevStatus => ({
      ...prevStatus,
      isActive: status.isActive,
      hasCamera: status.hasCamera,
      hasDetection: status.hasDetection,
      hasWebSocket: status.hasWebSocket,
    }));
    onStatusChange({
      ...proctoringStatus,
      isActive: status.isActive,
      hasCamera: status.hasCamera,
      hasDetection: status.hasDetection,
      hasWebSocket: status.hasWebSocket,
    });
  };

  const handleScreenActivityStatusChange = (status) => {
    setProctoringStatus(prevStatus => ({
      ...prevStatus,
      hasScreenMonitoring: status.isMonitoring,
    }));
    onStatusChange({
      ...proctoringStatus,
      hasScreenMonitoring: status.isMonitoring,
    });
  };

  const handleEventGenerated = (event) => {
    setEventCount(prev => prev + 1);
    console.log('Proctoring event generated:', event);
  };

  const getOverallStatus = () => {
    if (!proctoringStatus.isActive) return { color: 'gray', text: 'Inactive' };
    
    const hasWebcam = proctoringStatus.hasCamera && proctoringStatus.hasDetection;
    const hasScreenActivity = proctoringStatus.hasScreenMonitoring;
    const hasConnection = proctoringStatus.hasWebSocket;
    
    if (hasWebcam && hasScreenActivity && hasConnection) {
      return { color: 'green', text: 'Full Monitor' };
    }
    if (hasWebcam || hasScreenActivity) {
      return { color: 'yellow', text: 'Partial Monitor' };
    }
    if (proctoringStatus.hasCamera) return { color: 'yellow', text: 'Starting' };
    return { color: 'red', text: 'Error' };
  };

  const status = getOverallStatus();

  return (
    <Box
      bg="white"
      border="2px solid"
      borderColor={isEnabled ? 'blue.200' : 'gray.200'}
      borderRadius="lg"
      p={4}
      shadow="sm"
    >
      <VStack spacing={3} align="stretch">
        {/* Header */}
        <HStack justify="space-between" align="center">
          <HStack spacing={2}>
            <FaShieldAlt color={isEnabled ? 'blue' : 'gray'} size="20px" />
            <Text fontSize="lg" fontWeight="bold" color={isEnabled ? 'blue.600' : 'gray.500'}>
              AI Proctoring
            </Text>
            <Badge colorScheme={status.color} variant="solid">
              {status.text}
            </Badge>
            {eventCount > 0 && (
              <Badge colorScheme="orange" variant="outline">
                {eventCount} events
              </Badge>
            )}
          </HStack>
          
          <Button
            size="sm"
            variant="ghost"
            rightIcon={isOpen ? <FaChevronUp /> : <FaChevronDown />}
            onClick={onToggle}
          >
            {isOpen ? 'Hide' : 'Show'}
          </Button>
        </HStack>

        {/* Status Summary */}
        {!isOpen && isEnabled && (
          <Text fontSize="sm" color="gray.600">
            {proctoringStatus.isActive ? 
              `Webcam: ${proctoringStatus.hasCamera ? '✓' : '✗'} | Activity: ${proctoringStatus.hasScreenMonitoring ? '✓' : '✗'}` : 
              'Click to configure proctoring'
            }
          </Text>
        )}

        {/* Content */}
        <Collapse in={isOpen} animateOpacity>
          <VStack spacing={4} align="stretch">
            {!isEnabled ? (
              <Box p={4} bg="gray.50" borderRadius="md" textAlign="center">
                <Text color="gray.600" mb={2}>
                  Proctoring is currently disabled for this interview.
                </Text>
                <Text fontSize="sm" color="gray.500">
                  This feature helps ensure interview integrity through webcam monitoring, face detection, and screen activity analysis.
                </Text>
              </Box>
            ) : (
              <>
                {/* Webcam Monitoring */}
                <WebcamMonitor
                  sessionId={sessionId}
                  userId={userId}
                  isEnabled={isEnabled}
                  onStatusChange={handleWebcamStatusChange}
                  onEventGenerated={handleEventGenerated}
                  initialEmbedding={temporaryEmbedding}
                  videoRef={videoRef}
                />

                {/* Screen Activity Monitoring */}
                <ScreenActivityMonitor
                  sessionId={sessionId}
                  userId={userId}
                  isEnabled={isEnabled}
                  onStatusChange={handleScreenActivityStatusChange}
                  onEventGenerated={handleEventGenerated}
                />
              </>
            )}
          </VStack>
        </Collapse>
      </VStack>
    </Box>
  );
};

export default ProctoringPanel; 