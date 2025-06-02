import { useState, useEffect, useRef, useCallback } from 'react';
import React from 'react';

// WebSocket configuration - moved outside component to avoid dependency issues
const WS_CONFIG = {
  maxReconnectAttempts: 5,
  reconnectDelay: 1000, // Start with 1 second
  maxReconnectDelay: 30000, // Max 30 seconds
  heartbeatInterval: 30000, // Send heartbeat every 30 seconds
  connectionTimeout: 10000, // 10 seconds connection timeout
};

/**
 * Custom hook for WebSocket communication with the proctoring backend
 * Handles real-time event streaming and command reception
 */
export const useProctoringWebSocket = (sessionId, userId, isActive = false) => {
  const [connectionStatus, setConnectionStatus] = useState('disconnected');
  const [error, setError] = useState(null);
  const [receivedMessages, setReceivedMessages] = useState([]);
  const [alerts, setAlerts] = useState([]);
  
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const eventQueueRef = useRef([]);
  const heartbeatIntervalRef = useRef(null);
  const reconnectAttempts = useRef(0);
  
  // Refs to break dependency loops
  const isActiveRef = useRef(isActive);
  const sendHeartbeatRef = useRef(null);
  const processMessageRef = useRef(null);
  const connectRef = useRef(null);
  const disconnectRef = useRef(null);

  // Debug logging for isActive prop changes
  React.useEffect(() => {
    console.log('🔧 useProctoringWebSocket: isActive changed to:', isActive);
    console.log('🔧 useProctoringWebSocket: sessionId:', sessionId);
    console.log('🔧 useProctoringWebSocket: userId:', userId);
    isActiveRef.current = isActive; // Update ref when isActive changes
  }, [isActive, sessionId, userId]);

  /**
   * Get WebSocket URL for proctoring session
   */
  const getWebSocketUrl = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const baseUrl = process.env.NODE_ENV === 'development' 
      ? 'ws://localhost:8000' 
      : `${protocol}//${host}`;
    
    return `${baseUrl}/api/proctoring/ws/${sessionId}?user_id=${userId}`;
  }, [sessionId, userId]);

  /**
   * Send event to backend via WebSocket
   */
  const sendEvent = useCallback((event) => {
    console.log('🔍 DEBUG: sendEvent called with:', event);
    console.log('🔍 DEBUG: event keys:', Object.keys(event));
    console.log('🔍 DEBUG: event.type:', event.type);
    console.log('🔍 DEBUG: event.activity_type:', event.activity_type);

    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      // Queue event if not connected
      eventQueueRef.current.push(event);
      console.warn('WebSocket not connected, queuing event:', event);
      return false;
    }

    try {
      // If event has __directMessage, use that format directly
      if (event.__directMessage) {
        wsRef.current.send(JSON.stringify(event.__directMessage));
        console.log('Sent direct proctoring message:', event.__directMessage);
        return true;
      }

      // Don't send monitoring status events as screen activities
      if (event.type === 'monitoring_started' || event.type === 'monitoring_stopped') {
        console.log('Skipping monitoring status event:', event.type);
        return true; // Return true to avoid errors, but don't actually send
      }

      // For screen activity events, send the activity type directly as 'type'
      const activityType = event.activity_type || event.type;
      console.log('🔍 DEBUG: Determined activityType:', activityType);
      
      const message = {
        type: activityType, // Use the specific activity type as the main type
        timestamp: event.timestamp || new Date().toISOString(),
        severity: event.severity,
        confidence: event.confidence,
        description: event.description,
        metadata: event.metadata || {},
      };

      console.log('🔍 DEBUG: Final message to send:', message);
      console.log('🔍 DEBUG: message.type:', message.type);
      console.log('🔍 DEBUG: JSON.stringify(message):', JSON.stringify(message));

      wsRef.current.send(JSON.stringify(message));
      console.log('✅ Sent proctoring event successfully');
      return true;
    } catch (err) {
      console.error('❌ Error sending event:', err);
      setError('Failed to send proctoring event');
      return false;
    }
  }, []);

  /**
   * Send raw message to backend via WebSocket
   */
  const sendRawMessage = useCallback((message) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      console.warn('WebSocket not connected, cannot send raw message:', message);
      return false;
    }

    try {
      wsRef.current.send(JSON.stringify(message));
      console.log('Sent raw WebSocket message:', message);
      return true;
    } catch (err) {
      console.error('Error sending raw message:', err);
      setError('Failed to send raw WebSocket message');
      return false;
    }
  }, []);

  /**
   * Send heartbeat to maintain connection
   */
  const sendHeartbeat = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'heartbeat',
        timestamp: new Date().toISOString(),
      }));
    }
  }, []);

  // Update ref when sendHeartbeat changes
  sendHeartbeatRef.current = sendHeartbeat;

  /**
   * Process received message from backend
   */
  const processMessage = useCallback((data) => {
    setReceivedMessages(prev => [...prev.slice(-100), data]); // Keep last 100 messages

    switch (data.type) {
      case 'connection_confirmed':
        console.log('Proctoring WebSocket connection confirmed:', data);
        setConnectionStatus('connected');
        setError(null);
        reconnectAttempts.current = 0;
        
        // Send queued events
        if (eventQueueRef.current.length > 0) {
          console.log(`Sending ${eventQueueRef.current.length} queued events`);
          eventQueueRef.current.forEach(event => sendEvent(event));
          eventQueueRef.current = [];
        }
        break;

      case 'alert':
        const alert = {
          id: data.alert_id || `alert_${Date.now()}`,
          type: data.alert_type || 'general',
          severity: data.severity || 'medium',
          message: data.message || 'Proctoring alert',
          timestamp: data.timestamp || new Date().toISOString(),
          metadata: data.metadata || {},
        };
        setAlerts(prev => [...prev.slice(-20), alert]); // Keep last 20 alerts
        console.log('Received proctoring alert:', alert);
        break;

      case 'command':
        console.log('Received proctoring command:', data);
        // Handle commands from backend (e.g., start/stop recording, capture screenshot)
        break;

      case 'heartbeat_ack':
        // Heartbeat acknowledged
        break;

      case 'error':
        console.error('Proctoring WebSocket error:', data.message);
        setError(data.message);
        break;

      default:
        console.log('Unknown message type:', data);
    }
  }, [sendEvent]);

  // Update ref when processMessage changes
  processMessageRef.current = processMessage;

  /**
   * Connect to WebSocket
   */
  const connect = useCallback(() => {
    console.log('🔧 useProctoringWebSocket: connect() called');
    console.log('🔧 Connect params - sessionId:', sessionId, 'userId:', userId, 'isActive:', isActive);
    
    if (!sessionId || !userId) {
      console.warn('Cannot connect: missing sessionId or userId');
      return;
    }

    if (wsRef.current && wsRef.current.readyState === WebSocket.CONNECTING) {
      console.log('WebSocket already connecting...');
      return;
    }

    const wsUrl = getWebSocketUrl();
    console.log('Connecting to proctoring WebSocket:', wsUrl);
    
    setConnectionStatus('connecting');
    setError(null);

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      // Connection timeout
      const timeout = setTimeout(() => {
        if (ws.readyState === WebSocket.CONNECTING) {
          ws.close();
          setError('Connection timeout');
          setConnectionStatus('disconnected');
        }
      }, WS_CONFIG.connectionTimeout);

      ws.onopen = () => {
        clearTimeout(timeout);
        console.log('Proctoring WebSocket connected');
        setConnectionStatus('connected');
        setError(null);
        reconnectAttempts.current = 0;

        // Start heartbeat using ref
        if (sendHeartbeatRef.current) {
          heartbeatIntervalRef.current = setInterval(sendHeartbeatRef.current, WS_CONFIG.heartbeatInterval);
        }
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (processMessageRef.current) {
            processMessageRef.current(data);
          }
        } catch (err) {
          console.error('Error parsing WebSocket message:', err);
        }
      };

      ws.onclose = (event) => {
        clearTimeout(timeout);
        clearInterval(heartbeatIntervalRef.current);
        
        console.log('Proctoring WebSocket closed:', event.code, event.reason);
        setConnectionStatus('disconnected');
        
        // Attempt reconnection if it wasn't a clean close
        if (event.code !== 1000 && isActiveRef.current && reconnectAttempts.current < WS_CONFIG.maxReconnectAttempts) {
          const delay = Math.min(
            WS_CONFIG.reconnectDelay * Math.pow(2, reconnectAttempts.current),
            WS_CONFIG.maxReconnectDelay
          );
          
          reconnectAttempts.current += 1;
          setConnectionStatus('reconnecting');
          
          console.log(`Attempting reconnection ${reconnectAttempts.current}/${WS_CONFIG.maxReconnectAttempts} in ${delay}ms`);
          
          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, delay);
        } else if (reconnectAttempts.current >= WS_CONFIG.maxReconnectAttempts) {
          setError('Max reconnection attempts reached');
        }
      };

      ws.onerror = (error) => {
        console.error('Proctoring WebSocket error:', error);
        setError('WebSocket connection error');
      };

    } catch (err) {
      console.error('Error creating WebSocket:', err);
      setError('Failed to create WebSocket connection');
      setConnectionStatus('disconnected');
    }
  }, [sessionId, userId, getWebSocketUrl]);

  // Update ref when connect changes
  connectRef.current = connect;

  /**
   * Disconnect WebSocket
   */
  const disconnect = useCallback(() => {
    console.log('🔧 useProctoringWebSocket: disconnect() called');
    console.log('🔧 Disconnect reason - current connection status:', connectionStatus);
    
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current);
      heartbeatIntervalRef.current = null;
    }

    if (wsRef.current) {
      console.log('🔧 Closing WebSocket with code 1000');
      wsRef.current.close(1000, 'Intentional disconnect');
      wsRef.current = null;
    }

    setConnectionStatus('disconnected');
    reconnectAttempts.current = 0;
  }, []);

  // Update ref when disconnect changes
  disconnectRef.current = disconnect;

  /**
   * Clear alerts
   */
  const clearAlerts = useCallback(() => {
    setAlerts([]);
  }, []);

  /**
   * Clear received messages
   */
  const clearMessages = useCallback(() => {
    setReceivedMessages([]);
  }, []);

  /**
   * Manual reconnection
   */
  const reconnect = useCallback(() => {
    disconnect();
    setTimeout(() => {
      reconnectAttempts.current = 0;
      connect();
    }, 1000);
  }, [disconnect, connect]);

  // Connect when component mounts and isActive is true
  useEffect(() => {
    console.log('🔧 useProctoringWebSocket: Main useEffect triggered');
    console.log('🔧 Current state - isActive:', isActive, 'sessionId:', sessionId, 'userId:', userId);
    
    if (isActive && sessionId && userId) {
      console.log('🔧 Conditions met for connection, calling connect()');
      if (connectRef.current) {
        connectRef.current();
      }
    } else {
      console.log('🔧 Conditions not met or isActive=false, calling disconnect()');
      console.log('🔧 Conditions check - isActive:', isActive, 'sessionId:', !!sessionId, 'userId:', !!userId);
      if (disconnectRef.current) {
        disconnectRef.current();
      }
    }

    return () => {
      console.log('🔧 useProctoringWebSocket: Main useEffect cleanup, calling disconnect()');
      if (disconnectRef.current) {
        disconnectRef.current();
      }
    };
  }, [isActive, sessionId, userId]); // Only depend on these three values

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      disconnect();
    };
  }, [disconnect]);

  return {
    // State
    connectionStatus,
    error,
    receivedMessages,
    alerts,
    isConnected: connectionStatus === 'connected',
    isConnecting: connectionStatus === 'connecting',
    isReconnecting: connectionStatus === 'reconnecting',
    queuedEventsCount: eventQueueRef.current.length,
    
    // Actions
    sendEvent,
    sendRawMessage,
    connect,
    disconnect,
    reconnect,
    clearAlerts,
    clearMessages,
    
    // Config
    reconnectAttempts: reconnectAttempts.current,
    maxReconnectAttempts: WS_CONFIG.maxReconnectAttempts,
  };
}; 