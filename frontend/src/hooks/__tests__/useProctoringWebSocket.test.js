import { renderHook, act } from '@testing-library/react-hooks';
import { useProctoringWebSocket } from '../useProctoringWebSocket';

// Mock WebSocket
const mockWebSocket = {
  send: jest.fn(),
  close: jest.fn(),
  addEventListener: jest.fn(),
  removeEventListener: jest.fn(),
};

global.WebSocket = jest.fn(() => mockWebSocket);

describe('useProctoringWebSocket', () => {
  const mockProps = {
    sessionId: 'test-session',
    userId: 'test-user',
    isActive: true,
  };

  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('initializes with correct state', () => {
    const { result } = renderHook(() => useProctoringWebSocket(
      mockProps.sessionId,
      mockProps.userId,
      mockProps.isActive
    ));

    expect(result.current.connectionStatus).toBe('disconnected');
    expect(result.current.error).toBeNull();
    expect(result.current.receivedMessages).toEqual([]);
    expect(result.current.alerts).toEqual([]);
  });

  it('connects to WebSocket when active', () => {
    const { result } = renderHook(() => useProctoringWebSocket(
      mockProps.sessionId,
      mockProps.userId,
      mockProps.isActive
    ));

    expect(WebSocket).toHaveBeenCalledWith(
      expect.stringContaining(`/api/proctoring/ws/${mockProps.sessionId}?user_id=${mockProps.userId}`)
    );
  });

  it('sends events when connected', () => {
    const { result } = renderHook(() => useProctoringWebSocket(
      mockProps.sessionId,
      mockProps.userId,
      mockProps.isActive
    ));

    // Simulate connection
    act(() => {
      const onopen = mockWebSocket.addEventListener.mock.calls.find(
        call => call[0] === 'open'
      )[1];
      onopen();
    });

    // Send event
    const event = {
      type: 'screen_activity',
      activity_type: 'tab_switch',
      severity: 'medium',
      description: 'User switched tabs',
    };

    act(() => {
      result.current.sendEvent(event);
    });

    expect(mockWebSocket.send).toHaveBeenCalledWith(
      JSON.stringify(event)
    );
  });

  it('queues events when disconnected', () => {
    const { result } = renderHook(() => useProctoringWebSocket(
      mockProps.sessionId,
      mockProps.userId,
      mockProps.isActive
    ));

    const event = {
      type: 'screen_activity',
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
    const { result } = renderHook(() => useProctoringWebSocket(
      mockProps.sessionId,
      mockProps.userId,
      mockProps.isActive
    ));

    // Queue an event
    const event = {
      type: 'screen_activity',
      activity_type: 'tab_switch',
      severity: 'medium',
      description: 'User switched tabs',
    };

    act(() => {
      result.current.sendEvent(event);
    });

    // Simulate reconnection
    act(() => {
      const onopen = mockWebSocket.addEventListener.mock.calls.find(
        call => call[0] === 'open'
      )[1];
      onopen();
    });

    expect(mockWebSocket.send).toHaveBeenCalledWith(
      JSON.stringify(event)
    );
  });

  it('handles WebSocket messages', () => {
    const { result } = renderHook(() => useProctoringWebSocket(
      mockProps.sessionId,
      mockProps.userId,
      mockProps.isActive
    ));

    // Simulate connection
    act(() => {
      const onopen = mockWebSocket.addEventListener.mock.calls.find(
        call => call[0] === 'open'
      )[1];
      onopen();
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
      const onmessage = mockWebSocket.addEventListener.mock.calls.find(
        call => call[0] === 'message'
      )[1];
      onmessage({ data: JSON.stringify(message) });
    });

    expect(result.current.alerts).toHaveLength(1);
    expect(result.current.alerts[0].message).toBe('Suspicious activity detected');
  });

  it('handles WebSocket errors', () => {
    const { result } = renderHook(() => useProctoringWebSocket(
      mockProps.sessionId,
      mockProps.userId,
      mockProps.isActive
    ));

    // Simulate error
    act(() => {
      const onerror = mockWebSocket.addEventListener.mock.calls.find(
        call => call[0] === 'error'
      )[1];
      onerror(new Error('WebSocket error'));
    });

    expect(result.current.error).toBe('WebSocket connection error');
  });

  it('handles WebSocket closure', () => {
    const { result } = renderHook(() => useProctoringWebSocket(
      mockProps.sessionId,
      mockProps.userId,
      mockProps.isActive
    ));

    // Simulate connection
    act(() => {
      const onopen = mockWebSocket.addEventListener.mock.calls.find(
        call => call[0] === 'open'
      )[1];
      onopen();
    });

    // Simulate closure
    act(() => {
      const onclose = mockWebSocket.addEventListener.mock.calls.find(
        call => call[0] === 'close'
      )[1];
      onclose({ code: 1006, reason: 'Connection lost' });
    });

    expect(result.current.connectionStatus).toBe('disconnected');
  });

  it('sends heartbeat messages', () => {
    const { result } = renderHook(() => useProctoringWebSocket(
      mockProps.sessionId,
      mockProps.userId,
      mockProps.isActive
    ));

    // Simulate connection
    act(() => {
      const onopen = mockWebSocket.addEventListener.mock.calls.find(
        call => call[0] === 'open'
      )[1];
      onopen();
    });

    // Advance time to trigger heartbeat
    act(() => {
      jest.advanceTimersByTime(30000); // 30 seconds
    });

    expect(mockWebSocket.send).toHaveBeenCalledWith(
      JSON.stringify({
        type: 'heartbeat',
        timestamp: expect.any(String),
      })
    );
  });

  it('cleans up on unmount', () => {
    const { unmount } = renderHook(() => useProctoringWebSocket(
      mockProps.sessionId,
      mockProps.userId,
      mockProps.isActive
    ));

    unmount();

    expect(mockWebSocket.close).toHaveBeenCalledWith(1000, 'Intentional disconnect');
  });

  it('handles reconnection attempts', () => {
    const { result } = renderHook(() => useProctoringWebSocket(
      mockProps.sessionId,
      mockProps.userId,
      mockProps.isActive
    ));

    // Simulate connection and closure
    act(() => {
      const onopen = mockWebSocket.addEventListener.mock.calls.find(
        call => call[0] === 'open'
      )[1];
      onopen();
    });

    act(() => {
      const onclose = mockWebSocket.addEventListener.mock.calls.find(
        call => call[0] === 'close'
      )[1];
      onclose({ code: 1006, reason: 'Connection lost' });
    });

    // Advance time to trigger reconnection
    act(() => {
      jest.advanceTimersByTime(1000);
    });

    expect(result.current.connectionStatus).toBe('reconnecting');
    expect(WebSocket).toHaveBeenCalledTimes(2);
  });
}); 