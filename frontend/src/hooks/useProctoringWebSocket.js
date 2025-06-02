import { useState, useEffect, useRef, useCallback } from 'react';

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

  // WebSocket configuration
  const WS_CONFIG = {
    maxReconnectAttempts: 5,
    reconnectDelay: 1000, // Start with 1 second
    maxReconnectDelay: 30000, // Max 30 seconds
    heartbeatInterval: 30000, // Send heartbeat every 30 seconds
    connectionTimeout: 10000, // 10 seconds connection timeout
  };

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
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      // Queue event if not connected
      eventQueueRef.current.push(event);
      console.warn('WebSocket not connected, queuing event:', event);
      return false;
    }

    try {
      const message = {
        type: 'proctoring_event',
        event_type: event.type,
        timestamp: event.timestamp,
        severity: event.severity,
        confidence: event.confidence,
        description: event.description,
        metadata: event.metadata,
      };

      wsRef.current.send(JSON.stringify(message));
      console.log('Sent proctoring event:', message);
      return true;
    } catch (err) {
      console.error('Error sending event:', err);
      setError('Failed to send proctoring event');
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

  /**
   * Connect to WebSocket
   */
  const connect = useCallback(() => {
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

        // Start heartbeat
        heartbeatIntervalRef.current = setInterval(sendHeartbeat, WS_CONFIG.heartbeatInterval);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          processMessage(data);
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
        if (event.code !== 1000 && isActive && reconnectAttempts.current < WS_CONFIG.maxReconnectAttempts) {
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
  }, [sessionId, userId, isActive, getWebSocketUrl, sendHeartbeat, processMessage]);

  /**
   * Disconnect WebSocket
   */
  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current);
      heartbeatIntervalRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.close(1000, 'Intentional disconnect');
      wsRef.current = null;
    }

    setConnectionStatus('disconnected');
    reconnectAttempts.current = 0;
  }, []);

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
    if (isActive && sessionId && userId) {
      connect();
    } else {
      disconnect();
    }

    return () => {
      disconnect();
    };
  }, [isActive, sessionId, userId, connect, disconnect]);

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