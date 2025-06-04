import { renderHook, act } from '@testing-library/react';
import { useProctoringWebSocket } from '../useProctoringWebSocket';

// Store for all created mock instances
let mockWebSocketInstances = [];

// Factory function to create a new mock WebSocket instance
const createMockWebSocket = () => {
  const instance = {
  send: jest.fn(),
  close: jest.fn(),
  addEventListener: jest.fn(),
  removeEventListener: jest.fn(),
    readyState: 0, // WebSocket.CONNECTING
  url: '',
  _eventListeners: {},

    // Helper to simulate server sending a message
    simulateServerMessage(data) {
      const onMessage = instance._eventListeners['message'] && instance._eventListeners['message'][0];
      if (onMessage) {
        onMessage({ data: JSON.stringify(data) });
      }
    },
    // Helper to simulate 'open' event
    simulateOpen() {
      instance.readyState = 1; // WebSocket.OPEN
      const onOpen = instance._eventListeners['open'] && instance._eventListeners['open'][0];
      if (onOpen) {
        onOpen();
      }
    },
    // Helper to simulate 'error' event
    simulateError(errorEvent) {
      instance.readyState = 3; // WebSocket.CLOSED
      const onError = instance._eventListeners['error'] && instance._eventListeners['error'][0];
      if (onError) {
        onError(errorEvent || new Event('error'));
      }
    },
    // Helper to simulate 'close' event
    simulateClose(closeEvent) {
      instance.readyState = 3; // WebSocket.CLOSED
      const onClose = instance._eventListeners['close'] && instance._eventListeners['close'][0];
      if (onClose) {
        onClose(closeEvent || { code: 1000, reason: 'Normal closure', wasClean: true });
      }
    }
  };

  instance.addEventListener.mockImplementation((type, listener) => {
    if (!instance._eventListeners[type]) {
      instance._eventListeners[type] = [];
  }
    instance._eventListeners[type].push(listener);
});

  instance.removeEventListener.mockImplementation((type, listener) => {
    if (instance._eventListeners[type]) {
      instance._eventListeners[type] = instance._eventListeners[type].filter(l => l !== listener);
    }
  });

  mockWebSocketInstances.push(instance);
  return instance;
};

global.WebSocket = jest.fn((url) => {
  const newInstance = createMockWebSocket();
  newInstance.url = url;
  return newInstance;
});

// Helper to get the last created WebSocket instance
const getCurrentWebSocketInstance = () => {
  return mockWebSocketInstances.length > 0 ? mockWebSocketInstances[mockWebSocketInstances.length - 1] : null;
};

describe('useProctoringWebSocket', () => {
  const mockProps = {
    sessionId: 'test-session',
    userId: 'test-user',
    isActive: false, // Start with false to test initialization
  };

  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
    mockWebSocketInstances = []; // Reset instances before each test
    // global.WebSocket.mockClear(); // already handled by jest.clearAllMocks
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('initializes with correct state', () => {
    const { result } = renderHook(() => useProctoringWebSocket(
      mockProps.sessionId,
      mockProps.userId,
      mockProps.isActive // false initially
    ));

    expect(result.current.connectionStatus).toBe('disconnected');
    expect(result.current.error).toBeNull();
    expect(result.current.receivedMessages).toEqual([]);
    expect(result.current.alerts).toEqual([]);
  });

  it('connects to WebSocket when active', () => {
    const { result, rerender } = renderHook(
      ({ sessionId, userId, isActive }) => useProctoringWebSocket(sessionId, userId, isActive),
      { 
        initialProps: { 
          sessionId: mockProps.sessionId, 
          userId: mockProps.userId, 
          isActive: false 
        }
      }
    );

    // Now activate it
    act(() => {
      rerender({ 
        sessionId: mockProps.sessionId, 
        userId: mockProps.userId, 
        isActive: true 
      });
    });

    expect(WebSocket).toHaveBeenCalledTimes(1);
    const currentWs = getCurrentWebSocketInstance();
    expect(currentWs).not.toBeNull();
    expect(currentWs.url).toContain(`/api/proctoring/ws/${mockProps.sessionId}?user_id=${mockProps.userId}`);
  });

  it('sends events when connected', () => {
    const { result, rerender } = renderHook(
      ({ sessionId, userId, isActive }) => useProctoringWebSocket(sessionId, userId, isActive),
      { 
        initialProps: { 
          sessionId: mockProps.sessionId, 
          userId: mockProps.userId, 
          isActive: false 
        }
      }
    );

    // Activate and connect
    act(() => {
      rerender({ 
        sessionId: mockProps.sessionId, 
        userId: mockProps.userId, 
        isActive: true 
      });
    });
    
    const currentWs = getCurrentWebSocketInstance();
    expect(currentWs).not.toBeNull();

    // Simulate connection
    act(() => {
      currentWs.simulateOpen();
    });

    // Send event
    const event = {
      type: 'tab_switch',
      activity_type: 'tab_switch',
      severity: 'medium',
      description: 'User switched tabs',
    };

    act(() => {
      result.current.sendEvent(event);
    });

    expect(currentWs.send).toHaveBeenCalledWith(
      JSON.stringify(event)
    );
  });

  it('queues events when disconnected', () => {
    const { result } = renderHook(() => useProctoringWebSocket(
      mockProps.sessionId,
      mockProps.userId,
      false // disconnected
    ));

    const event = {
      type: 'tab_switch',
      activity_type: 'tab_switch',
      severity: 'medium',
      description: 'User switched tabs',
    };

    act(() => {
      result.current.sendEvent(event);
    });

    expect(result.current.queuedEventsCount).toBe(1);
  });

  it('sends queued events when reconnected', () => {
    const { result, rerender } = renderHook(
      ({ sessionId, userId, isActive }) => useProctoringWebSocket(sessionId, userId, isActive),
      { 
        initialProps: { 
          sessionId: mockProps.sessionId, 
          userId: mockProps.userId, 
          isActive: false 
        }
      }
    );

    // Queue an event while disconnected
    const event = {
      type: 'tab_switch',
      activity_type: 'tab_switch',
      severity: 'medium',
      description: 'User switched tabs',
    };

    act(() => {
      result.current.sendEvent(event);
    });

    // Now connect
    act(() => {
      rerender({ 
        sessionId: mockProps.sessionId, 
        userId: mockProps.userId, 
        isActive: true 
      });
    });
    
    const currentWs = getCurrentWebSocketInstance();
    expect(currentWs).not.toBeNull();

    // Simulate connection
    act(() => {
      currentWs.simulateOpen();
    });
    
    // Simulate connection_confirmed message from server which triggers sending queued events
    act(() => {
      currentWs.simulateServerMessage({ type: 'connection_confirmed' });
    });

    expect(currentWs.send).toHaveBeenCalledWith(
      JSON.stringify(event)
    );
  });

  it('handles WebSocket messages', () => {
    const { result, rerender } = renderHook(
      ({ sessionId, userId, isActive }) => useProctoringWebSocket(sessionId, userId, isActive),
      { 
        initialProps: { 
          sessionId: mockProps.sessionId, 
          userId: mockProps.userId, 
          isActive: false 
        }
      }
    );

    // Connect
    act(() => {
      rerender({ 
        sessionId: mockProps.sessionId, 
        userId: mockProps.userId, 
        isActive: true 
      });
    });

    const currentWs = getCurrentWebSocketInstance();
    expect(currentWs).not.toBeNull();

    // Simulate connection
    act(() => {
      currentWs.simulateOpen();
    });

    // Simulate message
    const message = {
      type: 'alert',
      alert_type: 'suspicious_activity',
      severity: 'high',
      message: 'Suspicious activity detected',
      timestamp: new Date().toISOString(),
    };

    act(() => {
      currentWs.simulateServerMessage(message);
    });

    expect(result.current.receivedMessages.length).toBe(1);
    expect(result.current.receivedMessages[0]).toEqual(message);
    expect(result.current.alerts.length).toBe(1);
    expect(result.current.alerts[0]).toEqual(expect.objectContaining({
      type: 'suspicious_activity',
      severity: 'high',
      message: 'Suspicious activity detected',
    }));
  });

  it('handles WebSocket errors', () => {
    const { result, rerender } = renderHook(
      ({ sessionId, userId, isActive }) => useProctoringWebSocket(sessionId, userId, isActive),
      { 
        initialProps: { 
          sessionId: mockProps.sessionId, 
          userId: mockProps.userId, 
          isActive: false 
        }
      }
    );

    // Connect
    act(() => {
      rerender({ 
        sessionId: mockProps.sessionId, 
        userId: mockProps.userId, 
        isActive: true 
      });
    });

    const currentWs = getCurrentWebSocketInstance();
    expect(currentWs).not.toBeNull();

    // Simulate error
    act(() => {
      currentWs.simulateError({ message: 'Test error' });
    });

    expect(result.current.connectionStatus).toBe('disconnected'); // or 'error' depending on hook logic
    expect(result.current.error).toBe('Test error');
  });

  it('handles WebSocket close', () => {
    const { result, rerender } = renderHook(
      ({ sessionId, userId, isActive }) => useProctoringWebSocket(sessionId, userId, isActive),
      { 
        initialProps: { 
          sessionId: mockProps.sessionId, 
          userId: mockProps.userId, 
          isActive: false 
        }
      }
    );

    // Connect
    act(() => {
      rerender({ 
        sessionId: mockProps.sessionId, 
        userId: mockProps.userId, 
        isActive: true 
      });
    });

    const currentWs = getCurrentWebSocketInstance();
    expect(currentWs).not.toBeNull();

    // Simulate open then close
    act(() => {
      currentWs.simulateOpen();
    });
    act(() => {
      currentWs.simulateClose({ code: 1000, reason: 'Normal closure', wasClean: true });
    });

    expect(result.current.connectionStatus).toBe('disconnected');
  });

  it('sends heartbeats periodically', () => {
    const { rerender } = renderHook(
      ({ sessionId, userId, isActive }) => useProctoringWebSocket(sessionId, userId, isActive),
      { 
        initialProps: { 
          sessionId: mockProps.sessionId, 
          userId: mockProps.userId, 
          isActive: false 
        }
      }
    );

    act(() => {
      rerender({ 
        sessionId: mockProps.sessionId, 
        userId: mockProps.userId, 
        isActive: true 
      });
    });

    const currentWs = getCurrentWebSocketInstance();
    expect(currentWs).not.toBeNull();

    act(() => {
      currentWs.simulateOpen();
    });

    // Simulate connection_confirmed to start heartbeat
    act(() => {
      currentWs.simulateServerMessage({ type: 'connection_confirmed' });
    });

    expect(currentWs.send).not.toHaveBeenCalledWith(expect.stringContaining('"type":"heartbeat"'));

    act(() => {
      jest.advanceTimersByTime(30000); // Default heartbeat interval
    });

    expect(currentWs.send).toHaveBeenCalledWith(
      expect.stringContaining('"type":"heartbeat"')
    );

    act(() => {
      jest.advanceTimersByTime(30000); 
    });
    // Should be called twice now
    expect(currentWs.send).toHaveBeenCalledTimes(2); 
  });

  it('reconnects on unexpected close if active', () => {
    const { result, rerender } = renderHook(
      ({ sessionId, userId, isActive }) => useProctoringWebSocket(sessionId, userId, isActive),
      { 
        initialProps: { 
          sessionId: mockProps.sessionId, 
          userId: mockProps.userId, 
          isActive: true // Start active this time
        }
      }
    );

    const firstWs = getCurrentWebSocketInstance();
    expect(firstWs).not.toBeNull();
    expect(WebSocket).toHaveBeenCalledTimes(1);

    act(() => {
      firstWs.simulateOpen();
      firstWs.simulateServerMessage({ type: 'connection_confirmed' }); // To establish connection
    });
    
    expect(result.current.connectionStatus).toBe('connected');

    // Simulate unexpected close
    act(() => {
      firstWs.simulateClose({ code: 1006, reason: 'Abnormal closure', wasClean: false });
    });
    
    expect(result.current.connectionStatus).toBe('reconnecting');

    // Advance timers for reconnect delay
    act(() => {
      jest.advanceTimersByTime(1000); // Initial reconnectDelay
    });

    expect(WebSocket).toHaveBeenCalledTimes(2); // Should have attempted to create a new WebSocket
    const secondWs = mockWebSocketInstances[1];
    expect(secondWs).not.toBeNull();
    expect(secondWs.url).toBe(firstWs.url); // Should try to connect to the same URL

    act(() => {
      secondWs.simulateOpen();
      secondWs.simulateServerMessage({ type: 'connection_confirmed' });
    });
    expect(result.current.connectionStatus).toBe('connected');
  });
  
  it('does not reconnect if isActive is false', () => {
    const { result, rerender } = renderHook(
      ({ sessionId, userId, isActive }) => useProctoringWebSocket(sessionId, userId, isActive),
      { 
        initialProps: { 
          sessionId: mockProps.sessionId, 
          userId: mockProps.userId, 
          isActive: true
        }
      }
    );

    const ws = getCurrentWebSocketInstance();
    act(() => {
      ws.simulateOpen();
      ws.simulateServerMessage({ type: 'connection_confirmed' });
    });

    // Set isActive to false
    act(() => {
      rerender({ 
        sessionId: mockProps.sessionId, 
        userId: mockProps.userId, 
        isActive: false 
      });
    });

    // Simulate unexpected close
    act(() => {
      ws.simulateClose({ code: 1006, wasClean: false });
    });
    
    // Should go to disconnected, not reconnecting
    expect(result.current.connectionStatus).toBe('disconnected');

    act(() => {
      jest.advanceTimersByTime(1000); // Reconnect delay
    });
    expect(WebSocket).toHaveBeenCalledTimes(1); // No new WebSocket instance
  });

  it('handles connection timeout', () => {
    renderHook(
      ({ sessionId, userId, isActive }) => useProctoringWebSocket(sessionId, userId, isActive),
      { 
        initialProps: { 
          sessionId: mockProps.sessionId, 
          userId: mockProps.userId, 
          isActive: true
        }
      }
    );

    const currentWs = getCurrentWebSocketInstance();
    expect(currentWs).not.toBeNull();
    // Don't simulateOpen() to cause a timeout

    act(() => {
      jest.advanceTimersByTime(10000); // WS_CONFIG.connectionTimeout
    });
    
    expect(currentWs.close).toHaveBeenCalled();
    // Check hook's error state, etc. - this will depend on what the user expects to see in the UI
    // For now, just check that close was called.
    // The hook should set error to 'Connection timeout' and status to 'disconnected'
  });

  it('clears heartbeat interval on disconnect', () => {
    const { unmount, rerender } = renderHook(
      ({ sessionId, userId, isActive }) => useProctoringWebSocket(sessionId, userId, isActive),
      { 
        initialProps: { 
        sessionId: mockProps.sessionId, 
        userId: mockProps.userId, 
        isActive: true 
        }
      }
    );
    const ws = getCurrentWebSocketInstance();
    act(() => {
      ws.simulateOpen();
      ws.simulateServerMessage({ type: 'connection_confirmed' });
    });

    const clearIntervalSpy = jest.spyOn(global, 'clearInterval');
    
    act(() => {
      // Disconnect by making it inactive
      rerender({ 
        sessionId: mockProps.sessionId, 
        userId: mockProps.userId, 
        isActive: false 
      });
    });

    expect(clearIntervalSpy).toHaveBeenCalled();
    clearIntervalSpy.mockRestore();
    
    // Also test unmount
    const clearIntervalSpy2 = jest.spyOn(global, 'clearInterval');
    act(() => {
      unmount();
    });
    expect(clearIntervalSpy2).toHaveBeenCalled();
    clearIntervalSpy2.mockRestore();
  });

  it('sends raw messages correctly', () => {
    const { result, rerender } = renderHook(
      ({ sessionId, userId, isActive }) => useProctoringWebSocket(sessionId, userId, isActive),
      { 
        initialProps: { 
          sessionId: mockProps.sessionId, 
          userId: mockProps.userId, 
          isActive: true 
        }
      }
    );

    const currentWs = getCurrentWebSocketInstance();
    act(() => {
      currentWs.simulateOpen();
    });

    const rawMessage = { command: 'test_command', payload: { data: 'value' } };
    act(() => {
      result.current.sendRawMessage(rawMessage);
    });

    expect(currentWs.send).toHaveBeenCalledWith(JSON.stringify(rawMessage));
  });

  it('does not send raw messages if not connected', () => {
    const { result } = renderHook(() => useProctoringWebSocket(
      mockProps.sessionId,
      mockProps.userId,
      false // Not active, so no WS connection
    ));
    
    // No WebSocket instance should exist yet
    const currentWs = getCurrentWebSocketInstance();
    expect(currentWs).toBeNull();


    const rawMessage = { command: 'test_command' };
    let success;
    act(() => {
      success = result.current.sendRawMessage(rawMessage);
    });

    expect(success).toBe(false);
    // No WebSocket instance means no send method to have been called.
  });
  
  it('correctly processes "connection_confirmed" message', () => {
    const { result, rerender } = renderHook(
      ({ sessionId, userId, isActive }) => useProctoringWebSocket(sessionId, userId, isActive),
      { 
        initialProps: { 
          sessionId: mockProps.sessionId, 
          userId: mockProps.userId, 
          isActive: true 
        }
      }
    );
    const ws = getCurrentWebSocketInstance();
    act(() => {
      ws.simulateOpen(); // Open event first
    });
    act(() => {
      ws.simulateServerMessage({ type: 'connection_confirmed', details: 'Connected OK' });
    });

    expect(result.current.connectionStatus).toBe('connected');
    expect(result.current.error).toBeNull();
    // Add more assertions if reconnectAttempts is exposed or has side effects
  });

  it('correctly processes "error" message from server', () => {
    const { result, rerender } = renderHook(
      ({ sessionId, userId, isActive }) => useProctoringWebSocket(sessionId, userId, isActive),
      { 
        initialProps: { 
          sessionId: mockProps.sessionId, 
          userId: mockProps.userId, 
          isActive: true 
        }
      }
    );
    const ws = getCurrentWebSocketInstance();
    act(() => {
      ws.simulateOpen();
      ws.simulateServerMessage({ type: 'connection_confirmed' }); // Get to connected state
    });
    act(() => {
      ws.simulateServerMessage({ type: 'error', message: 'Server-side processing error' });
    });

    expect(result.current.error).toBe('Server-side processing error');
    // Connection status might remain 'connected' or change, depending on desired hook behavior for server-sent errors
  });
  
  // Test for max reconnection attempts
  it('stops reconnecting after max attempts', () => {
    const { result, rerender } = renderHook(
      ({ sessionId, userId, isActive }) => useProctoringWebSocket(sessionId, userId, isActive),
      { 
        initialProps: { 
          sessionId: mockProps.sessionId, 
          userId: mockProps.userId, 
          isActive: true
        }
      }
    );

    const MAX_RECONNECT_ATTEMPTS = 5; // From WS_CONFIG in the hook
    let currentWs = getCurrentWebSocketInstance();
    act(() => {
      currentWs.simulateOpen();
      currentWs.simulateServerMessage({ type: 'connection_confirmed' });
    });

    for (let i = 0; i < MAX_RECONNECT_ATTEMPTS; i++) {
      act(() => {
        currentWs.simulateClose({ code: 1006, wasClean: false }); // Unexpected close
      });
      expect(result.current.connectionStatus).toBe('reconnecting');
      act(() => {
        jest.advanceTimersByTime(1000 + i * 500); // Simulate increasing backoff, ensure it's > reconnectDelay
      });
      currentWs = getCurrentWebSocketInstance(); // Get the new instance
      expect(WebSocket).toHaveBeenCalledTimes(i + 2); // Initial + attempts
      // Simulate immediate failure of the new connection attempt by not calling simulateOpen() or simulateError() that would stop retries
    }

    // After max attempts, one more close event
    act(() => {
      currentWs.simulateClose({ code: 1006, wasClean: false }); // This instance "fails" to connect and closes
    });
    
    // Should now be disconnected and not try again
    expect(result.current.connectionStatus).toBe('disconnected');
    expect(result.current.error).toMatch(/Failed to connect after/); // Or similar error message
    
    // Try advancing time again, should be no more attempts
    act(() => {
      jest.advanceTimersByTime(30000); // A long time
    });
    expect(WebSocket).toHaveBeenCalledTimes(MAX_RECONNECT_ATTEMPTS + 1); // Initial + MAX_ATTEMPTS
  });

}); 