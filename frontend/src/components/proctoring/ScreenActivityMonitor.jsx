import React, { useState, useEffect, useCallback } from 'react';
import {
  Box,
  VStack,
  HStack,
  Text,
  Badge,
  Button,
  Collapse,
  useDisclosure,
  Alert,
  AlertIcon,
  AlertTitle,
  AlertDescription,
  Icon,
} from '@chakra-ui/react';
import {
  FaKeyboard,
  FaWindowMaximize,
  FaClipboard,
  FaExclamationTriangle,
  FaChevronDown,
  FaChevronUp,
  FaShieldAlt,
} from 'react-icons/fa';
import { useScreenActivity } from '../../hooks/useScreenActivity';
import { useProctoringWebSocket } from '../../hooks/useProctoringWebSocket';
import { SEVERITY_LEVELS } from '../../utils/activityDetection';

/**
 * Screen Activity Monitor Component
 * 
 * Monitors user screen activities including:
 * - Tab switches and window focus changes
 * - Copy-paste activities
 * - Suspicious keyboard shortcuts (dev tools, etc.)
 * - Screenshot attempts
 * 
 * Features real-time activity detection, pattern analysis, and WebSocket communication
 */
const ScreenActivityMonitor = ({
  sessionId,
  userId,
  isEnabled = false,
  onStatusChange = () => {},
  onEventGenerated = () => {},
}) => {
  const { isOpen, onToggle } = useDisclosure({ defaultIsOpen: false });
  const [alerts, setAlerts] = useState([]);

  // Debug logging for isEnabled prop changes
  React.useEffect(() => {
    console.log('🔧 ScreenActivityMonitor: isEnabled changed to:', isEnabled);
    console.log('🔧 ScreenActivityMonitor: sessionId:', sessionId);
    console.log('🔧 ScreenActivityMonitor: userId:', userId);
  }, [isEnabled, sessionId, userId]);

  // Initialize WebSocket connection for sending activity data
  const { sendEvent: sendWebSocketEvent, connectionStatus: wsConnectionStatus } = useProctoringWebSocket(
    sessionId,
    userId,
    isEnabled
  );

  /**
   * Handle activity detection from the hook
   */
  const handleActivityDetected = useCallback((event) => {
    console.log('🎯 Screen activity event detected:', event);
    console.log('🔍 Event type:', event.type);
    console.log('🔍 Event properties:', Object.keys(event));

    // Send screen activity data via WebSocket using the correct format
    if (wsConnectionStatus === 'connected') {
      try {
        const eventToSend = {
          activity_type: event.type,
          severity: event.severity,
          confidence: event.severity === SEVERITY_LEVELS.CRITICAL ? 0.9 : 
                     event.severity === SEVERITY_LEVELS.HIGH ? 0.8 : 
                     event.severity === SEVERITY_LEVELS.MEDIUM ? 0.6 : 0.4,
          description: event.description,
          timestamp: event.timestamp,
          metadata: {
            ...event.metadata,
          },
        };

        console.log('🚀 Sending to WebSocket:', eventToSend);
        console.log('🔗 Connection status:', wsConnectionStatus);
        console.log('🔍 Activity type being sent:', eventToSend.activity_type);

        const success = sendWebSocketEvent(eventToSend);

        if (success) {
          console.log('✅ Sent screen activity event successfully');
        } else {
          console.warn('⚠️ Failed to send screen activity event');
        }
      } catch (error) {
        console.error('❌ Error sending screen activity event:', error);
      }
    } else {
      console.warn('⚠️ WebSocket not connected, cannot send event. Status:', wsConnectionStatus);
    }

    // Handle alerts for suspicious activity
    if (event.severity === SEVERITY_LEVELS.HIGH || event.severity === SEVERITY_LEVELS.CRITICAL) {
      const alert = {
        id: `alert_${Date.now()}`,
        type: event.type,
        severity: event.severity,
        description: event.description,
        timestamp: event.timestamp,
      };

      setAlerts(prev => [...prev.slice(-9), alert]); // Keep last 10 alerts
      console.log('🚨 Generated alert:', alert);
    }

    // Notify parent components
    onEventGenerated(event);
  }, [wsConnectionStatus, sendWebSocketEvent, onEventGenerated]);

  // Initialize screen activity monitoring
  const {
    isMonitoring,
    activityCount,
    suspiciousCount,
    apiSupport,
    recentPatterns,
    getActivityStats,
  } = useScreenActivity(isEnabled, handleActivityDetected);

  /**
   * Handle activity status changes and notify parent
   */
  useEffect(() => {
    if (!onStatusChange) return;
    
    onStatusChange({
      isMonitoring,
      hasAPISupport: Object.values(apiSupport).some(Boolean),
      activityCount,
      suspiciousCount,
      connectionStatus: wsConnectionStatus,
      hasPatterns: Object.values(recentPatterns).some(Boolean),
    });
  }, [isMonitoring, apiSupport, activityCount, suspiciousCount, wsConnectionStatus, recentPatterns, onStatusChange]);

  /**
   * Get status color and text based on monitoring state
   */
  const getStatusDisplay = () => {
    if (!isEnabled) return { color: 'gray', text: 'Disabled' };
    if (!isMonitoring) return { color: 'yellow', text: 'Starting' };
    if (wsConnectionStatus !== 'connected') return { color: 'orange', text: 'No Connection' };
    if (alerts.length > 0) return { color: 'red', text: 'Alerts Active' };
    return { color: 'green', text: 'Monitoring' };
  };

  const status = getStatusDisplay();

  /**
   * Get activity statistics for display
   */
  const activityStats = getActivityStats();

  /**
   * Get severity color for badges
   */
  const getSeverityColor = (severity) => {
    switch (severity) {
      case SEVERITY_LEVELS.CRITICAL: return 'red';
      case SEVERITY_LEVELS.HIGH: return 'orange';
      case SEVERITY_LEVELS.MEDIUM: return 'yellow';
      case SEVERITY_LEVELS.LOW: return 'blue';
      default: return 'gray';
    }
  };

  /**
   * Get icon for activity type
   */
  const getActivityIcon = (type) => {
    if (type.includes('keyboard') || type.includes('copy') || type.includes('paste')) {
      return FaKeyboard;
    }
    if (type.includes('window') || type.includes('tab')) {
      return FaWindowMaximize;
    }
    if (type.includes('clipboard')) {
      return FaClipboard;
    }
    return FaShieldAlt;
  };

  return (
    <Box
      bg="white"
      border="1px solid"
      borderColor={isEnabled ? 'blue.200' : 'gray.200'}
      borderRadius="md"
      p={3}
    >
      <VStack spacing={3} align="stretch">
        {/* Header */}
        <HStack justify="space-between" align="center">
          <HStack spacing={2}>
            <Icon as={FaKeyboard} color={isEnabled ? 'blue.500' : 'gray.400'} />
            <Text fontSize="md" fontWeight="semibold" color={isEnabled ? 'blue.600' : 'gray.500'}>
              Screen Activity
            </Text>
            <Badge colorScheme={status.color} variant="solid" fontSize="xs">
              {status.text}
            </Badge>
          </HStack>

          <HStack spacing={2}>
            {activityStats.byType.tabSwitches > 0 && (
              <Badge colorScheme="blue" variant="outline" fontSize="xs">
                {activityStats.byType.tabSwitches} events
              </Badge>
            )}
            {alerts.length > 0 && (
              <Badge colorScheme="red" variant="outline" fontSize="xs">
                {alerts.length} alerts
              </Badge>
            )}
            <Button
              size="xs"
              variant="ghost"
              rightIcon={isOpen ? <FaChevronUp /> : <FaChevronDown />}
              onClick={onToggle}
            >
              {isOpen ? 'Hide' : 'Details'}
            </Button>
          </HStack>
        </HStack>

        {/* Quick Status */}
        {!isOpen && isEnabled && (
          <HStack spacing={4} fontSize="sm" color="gray.600">
            <HStack spacing={1}>
              <Icon as={FaWindowMaximize} boxSize="3" />
              <Text>{activityStats.byType.tabSwitches} tab switches</Text>
            </HStack>
            <HStack spacing={1}>
              <Icon as={FaClipboard} boxSize="3" />
              <Text>{activityStats.byType.copyPaste} copy/paste</Text>
            </HStack>
            {activityStats.byType.consoleAccess > 0 && (
              <HStack spacing={1}>
                <Icon as={FaExclamationTriangle} boxSize="3" color="red.500" />
                <Text color="red.500">{activityStats.byType.consoleAccess} console access</Text>
              </HStack>
            )}
          </HStack>
        )}

        {/* Detailed View */}
        <Collapse in={isOpen} animateOpacity>
          <VStack spacing={3} align="stretch">
            {!isEnabled ? (
              <Alert status="info" size="sm">
                <AlertIcon />
                <Box>
                  <AlertTitle fontSize="sm">Screen Activity Monitoring Disabled</AlertTitle>
                  <AlertDescription fontSize="xs">
                    Enable proctoring to monitor tab switches, copy-paste, and keyboard shortcuts.
                  </AlertDescription>
                </Box>
              </Alert>
            ) : (
              <>
                {/* API Support Status */}
                <Box bg="gray.50" p={2} borderRadius="md">
                  <Text fontSize="xs" fontWeight="semibold" mb={1}>Browser Support</Text>
                  <HStack spacing={4} fontSize="xs">
                    <Text color={apiSupport.visibilityAPI ? 'green.600' : 'red.600'}>
                      Tab Detection: {apiSupport.visibilityAPI ? '✓' : '✗'}
                    </Text>
                    <Text color={apiSupport.keyboardAPI ? 'green.600' : 'red.600'}>
                      Keyboard: {apiSupport.keyboardAPI ? '✓' : '✗'}
                    </Text>
                    <Text color={apiSupport.focusAPI ? 'green.600' : 'red.600'}>
                      Focus: {apiSupport.focusAPI ? '✓' : '✗'}
                    </Text>
                  </HStack>
                </Box>

                {/* Activity Statistics */}
                <Box>
                  <Text fontSize="sm" fontWeight="semibold" mb={2}>Activity Summary</Text>
                  <VStack spacing={2} align="stretch">
                    <HStack justify="space-between">
                      <HStack spacing={2}>
                        <Icon as={FaWindowMaximize} boxSize="4" color="blue.500" />
                        <Text fontSize="sm">Tab Switches</Text>
                      </HStack>
                      <Badge colorScheme="blue" variant="outline">
                        {activityStats.byType.tabSwitches}
                      </Badge>
                    </HStack>

                    <HStack justify="space-between">
                      <HStack spacing={2}>
                        <Icon as={FaClipboard} boxSize="4" color="green.500" />
                        <Text fontSize="sm">Copy/Paste Actions</Text>
                      </HStack>
                      <Badge colorScheme="green" variant="outline">
                        {activityStats.byType.copyPaste}
                      </Badge>
                    </HStack>

                    {activityStats.byType.consoleAccess > 0 && (
                      <HStack justify="space-between">
                        <HStack spacing={2}>
                          <Icon as={FaExclamationTriangle} boxSize="4" color="red.500" />
                          <Text fontSize="sm" color="red.600">Developer Tools Access</Text>
                        </HStack>
                        <Badge colorScheme="red" variant="solid">
                          {activityStats.byType.consoleAccess}
                        </Badge>
                      </HStack>
                    )}

                    {activityStats.byType.screenshots > 0 && (
                      <HStack justify="space-between">
                        <HStack spacing={2}>
                          <Icon as={FaExclamationTriangle} boxSize="4" color="orange.500" />
                          <Text fontSize="sm" color="orange.600">Screenshot Attempts</Text>
                        </HStack>
                        <Badge colorScheme="orange" variant="solid">
                          {activityStats.byType.screenshots}
                        </Badge>
                      </HStack>
                    )}
                  </VStack>
                </Box>

                {/* Pattern Detection Alerts */}
                {Object.values(recentPatterns).some(Boolean) && (
                  <Alert status="warning" size="sm">
                    <AlertIcon />
                    <Box>
                      <AlertTitle fontSize="sm">Suspicious Patterns Detected</AlertTitle>
                      <AlertDescription fontSize="xs">
                        {recentPatterns.rapidTabSwitching && 'Rapid tab switching detected. '}
                        {recentPatterns.excessiveCopyPaste && 'Excessive copy-paste activity. '}
                        {recentPatterns.frequentConsoleAccess && 'Frequent developer console access. '}
                      </AlertDescription>
                    </Box>
                  </Alert>
                )}

                {/* Recent Alerts */}
                {alerts.length > 0 && (
                  <Box>
                    <Text fontSize="sm" fontWeight="semibold" mb={2}>Recent Alerts</Text>
                    <VStack spacing={1} align="stretch" maxH="120px" overflowY="auto">
                      {alerts.slice(-5).map((alert, index) => (
                        <HStack
                          key={alert.id}
                          justify="space-between"
                          p={2}
                          bg="red.50"
                          borderRadius="sm"
                          fontSize="xs"
                        >
                          <HStack spacing={2}>
                            <Icon as={getActivityIcon(alert.type)} color="red.500" boxSize="3" />
                            <Text>{alert.description}</Text>
                          </HStack>
                          <Badge colorScheme={getSeverityColor(alert.severity)} variant="solid" fontSize="xs">
                            {alert.severity}
                          </Badge>
                        </HStack>
                      ))}
                    </VStack>
                  </Box>
                )}

                {/* Connection Status */}
                <Box fontSize="xs" color="gray.600">
                  <Text>
                    Connection: <Badge colorScheme={wsConnectionStatus === 'connected' ? 'green' : 'red'} variant="outline" fontSize="xs">
                      {wsConnectionStatus}
                    </Badge>
                  </Text>
                </Box>
              </>
            )}
          </VStack>
        </Collapse>
      </VStack>
    </Box>
  );
};

export default ScreenActivityMonitor; 