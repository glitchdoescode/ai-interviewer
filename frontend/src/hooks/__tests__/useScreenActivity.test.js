import { renderHook, act } from '@testing-library/react';
import { useScreenActivity } from '../useScreenActivity';

// Mock the activity detection utils
jest.mock('../../utils/activityDetection', () => {
  const originalModule = jest.requireActual('../../utils/activityDetection');
  return {
    ...originalModule, // Preserve other exports like ACTIVITY_TYPES, SEVERITY_LEVELS
    ActivityBuffer: jest.fn().mockImplementation(() => ({
      add: jest.fn(),
      getAll: jest.fn().mockReturnValue([]),
      clear: jest.fn(),
      getCount: jest.fn().mockReturnValue(0),
      getByType: jest.fn().mockReturnValue([]),
      getRecent: jest.fn().mockReturnValue([]),
    })),
    ActivityPatternDetector: jest.fn().mockImplementation(() => ({
      detectRapidTabSwitching: jest.fn().mockReturnValue(false),
      detectExcessiveCopyPaste: jest.fn().mockReturnValue(false),
      detectFrequentConsoleAccess: jest.fn().mockReturnValue(false),
      analyzePatterns: jest.fn().mockReturnValue({}), // Ensure this returns an object
    })),
    // Add any other specific named exports from activityDetection.js that need to be mocked or preserved
  };
});

// Mock WebSocket sender
const mockSendEvent = jest.fn();

// Mock DOM APIs
Object.defineProperty(document, 'hidden', {
  writable: true,
  value: false,
});

Object.defineProperty(document, 'visibilityState', {
  writable: true,
  value: 'visible',
});

// Mock event listeners
let eventListeners = {};
const originalAddEventListener = document.addEventListener;
const originalRemoveEventListener = document.removeEventListener;

beforeEach(() => {
  eventListeners = {};
  
  document.addEventListener = jest.fn((type, listener) => {
    if (!eventListeners[type]) {
      eventListeners[type] = [];
    }
    eventListeners[type].push(listener);
  });
  
  document.removeEventListener = jest.fn((type, listener) => {
    if (eventListeners[type]) {
      eventListeners[type] = eventListeners[type].filter(l => l !== listener);
    }
  });

  // Mock window focus/blur events
  window.addEventListener = jest.fn((type, listener) => {
    if (!eventListeners[type]) {
      eventListeners[type] = [];
    }
    eventListeners[type].push(listener);
  });
  
  window.removeEventListener = jest.fn((type, listener) => {
    if (eventListeners[type]) {
      eventListeners[type] = eventListeners[type].filter(l => l !== listener);
    }
  });
});

afterEach(() => {
  jest.clearAllMocks();
  document.addEventListener = originalAddEventListener;
  document.removeEventListener = originalRemoveEventListener;
});

describe('useScreenActivity', () => {
  const defaultProps = {
    sendEvent: mockSendEvent,
    isEnabled: false,
  };

  beforeEach(() => {
    jest.clearAllMocks();
    document.hidden = false;
    document.visibilityState = 'visible';
  });

  it('initializes with correct default state', () => {
    const { result } = renderHook(() => useScreenActivity(defaultProps));

    expect(result.current.isMonitoring).toBe(false);
    expect(result.current.activityCount).toBe(0);
    expect(result.current.lastActivity).toBeNull();
    expect(typeof result.current.startMonitoring).toBe('function');
    expect(typeof result.current.stopMonitoring).toBe('function');
  });

  it('starts monitoring when enabled', () => {
    const { result, rerender } = renderHook(
      ({ sendEvent, isEnabled }) => useScreenActivity({ sendEvent, isEnabled }),
      { initialProps: defaultProps }
    );

    expect(result.current.isMonitoring).toBe(false);

    // Enable monitoring
    act(() => {
      rerender({ sendEvent: mockSendEvent, isEnabled: true });
    });

    expect(result.current.isMonitoring).toBe(true);
    expect(document.addEventListener).toHaveBeenCalledWith('visibilitychange', expect.any(Function));
    expect(document.addEventListener).toHaveBeenCalledWith('keydown', expect.any(Function));
    expect(window.addEventListener).toHaveBeenCalledWith('focus', expect.any(Function));
    expect(window.addEventListener).toHaveBeenCalledWith('blur', expect.any(Function));
  });

  it('stops monitoring when disabled', () => {
    const { result, rerender } = renderHook(
      ({ sendEvent, isEnabled }) => useScreenActivity({ sendEvent, isEnabled }),
      { initialProps: { sendEvent: mockSendEvent, isEnabled: true } }
    );

    expect(result.current.isMonitoring).toBe(true);

    // Disable monitoring
    act(() => {
      rerender({ sendEvent: mockSendEvent, isEnabled: false });
    });

    expect(result.current.isMonitoring).toBe(false);
    expect(document.removeEventListener).toHaveBeenCalledWith('visibilitychange', expect.any(Function));
    expect(document.removeEventListener).toHaveBeenCalledWith('keydown', expect.any(Function));
    expect(window.removeEventListener).toHaveBeenCalledWith('focus', expect.any(Function));
    expect(window.removeEventListener).toHaveBeenCalledWith('blur', expect.any(Function));
  });

  it('detects tab switch away', () => {
    const { result } = renderHook(() => useScreenActivity({
      sendEvent: mockSendEvent,
      isEnabled: true,
    }));

    // Simulate tab becoming hidden
    act(() => {
      document.hidden = true;
      document.visibilityState = 'hidden';
      
      // Trigger visibility change event
      const visibilityHandlers = eventListeners.visibilitychange || [];
      visibilityHandlers.forEach(handler => handler());
    });

    expect(mockSendEvent).toHaveBeenCalledWith({
      type: 'tab_switch',
      activity_type: 'tab_switch',
      severity: 'medium',
      description: expect.stringContaining('Tab switched away'),
      timestamp: expect.any(String),
      metadata: expect.objectContaining({
        fromVisible: true,
        toVisible: false,
        visibilityState: 'hidden',
      }),
    });

    expect(result.current.activityCount).toBe(1);
    expect(result.current.lastActivity).toEqual({
      type: 'tab_switch',
      timestamp: expect.any(String),
    });
  });

  it('detects tab switch back', () => {
    const { result } = renderHook(() => useScreenActivity({
      sendEvent: mockSendEvent,
      isEnabled: true,
    }));

    // First switch away
    act(() => {
      document.hidden = true;
      document.visibilityState = 'hidden';
      const visibilityHandlers = eventListeners.visibilitychange || [];
      visibilityHandlers.forEach(handler => handler());
    });

    // Clear previous call
    mockSendEvent.mockClear();

    // Then switch back
    act(() => {
      document.hidden = false;
      document.visibilityState = 'visible';
      const visibilityHandlers = eventListeners.visibilitychange || [];
      visibilityHandlers.forEach(handler => handler());
    });

    expect(mockSendEvent).toHaveBeenCalledWith({
      type: 'tab_switch',
      activity_type: 'tab_switch',
      severity: 'low',
      description: expect.stringContaining('Tab switched back'),
      timestamp: expect.any(String),
      metadata: expect.objectContaining({
        fromVisible: false,
        toVisible: true,
        visibilityState: 'visible',
        timeAway: expect.any(Number),
      }),
    });
  });

  it('detects copy action', () => {
    const { result } = renderHook(() => useScreenActivity({
      sendEvent: mockSendEvent,
      isEnabled: true,
    }));

    // Simulate Ctrl+C keypress
    act(() => {
      const keyEvent = {
        type: 'keydown',
        key: 'c',
        ctrlKey: true,
        metaKey: false,
        preventDefault: jest.fn(),
      };
      
      const keyHandlers = eventListeners.keydown || [];
      keyHandlers.forEach(handler => handler(keyEvent));
    });

    expect(mockSendEvent).toHaveBeenCalledWith({
      type: 'copy_action',
      activity_type: 'copy_action',
      severity: 'medium',
      description: 'Copy action detected',
      timestamp: expect.any(String),
      metadata: expect.objectContaining({
        key: 'c',
        ctrlKey: true,
        metaKey: false,
      }),
    });

    expect(result.current.activityCount).toBe(1);
  });

  it('detects paste action', () => {
    const { result } = renderHook(() => useScreenActivity({
      sendEvent: mockSendEvent,
      isEnabled: true,
    }));

    // Simulate Ctrl+V keypress
    act(() => {
      const keyEvent = {
        type: 'keydown',
        key: 'v',
        ctrlKey: true,
        metaKey: false,
        preventDefault: jest.fn(),
      };
      
      const keyHandlers = eventListeners.keydown || [];
      keyHandlers.forEach(handler => handler(keyEvent));
    });

    expect(mockSendEvent).toHaveBeenCalledWith({
      type: 'paste_action',
      activity_type: 'paste_action',
      severity: 'high',
      description: 'Paste action detected',
      timestamp: expect.any(String),
      metadata: expect.objectContaining({
        key: 'v',
        ctrlKey: true,
        metaKey: false,
      }),
    });

    expect(result.current.activityCount).toBe(1);
  });

  it('detects window focus/blur events', () => {
    const { result } = renderHook(() => useScreenActivity({
      sendEvent: mockSendEvent,
      isEnabled: true,
    }));

    // Simulate window blur
    act(() => {
      const blurHandlers = eventListeners.blur || [];
      blurHandlers.forEach(handler => handler());
    });

    expect(mockSendEvent).toHaveBeenCalledWith({
      type: 'window_blur',
      activity_type: 'window_blur',
      severity: 'medium',
      description: 'Window lost focus',
      timestamp: expect.any(String),
      metadata: expect.objectContaining({
        hasFocus: false,
      }),
    });

    // Clear previous call
    mockSendEvent.mockClear();

    // Simulate window focus
    act(() => {
      const focusHandlers = eventListeners.focus || [];
      focusHandlers.forEach(handler => handler());
    });

    expect(mockSendEvent).toHaveBeenCalledWith({
      type: 'window_focus',
      activity_type: 'window_focus',
      severity: 'low',
      description: 'Window gained focus',
      timestamp: expect.any(String),
      metadata: expect.objectContaining({
        hasFocus: true,
      }),
    });

    expect(result.current.activityCount).toBe(2);
  });

  it('handles manual start/stop monitoring', () => {
    const { result } = renderHook(() => useScreenActivity({
      sendEvent: mockSendEvent,
      isEnabled: false,
    }));

    expect(result.current.isMonitoring).toBe(false);

    // Manually start monitoring
    act(() => {
      result.current.startMonitoring();
    });

    expect(result.current.isMonitoring).toBe(true);
    expect(document.addEventListener).toHaveBeenCalled();

    // Manually stop monitoring
    act(() => {
      result.current.stopMonitoring();
    });

    expect(result.current.isMonitoring).toBe(false);
    expect(document.removeEventListener).toHaveBeenCalled();
  });

  it('does not detect events when monitoring is disabled', () => {
    const { result } = renderHook(() => useScreenActivity({
      sendEvent: mockSendEvent,
      isEnabled: false,
    }));

    // Try to trigger events while disabled
    act(() => {
      document.hidden = true;
      const visibilityHandlers = eventListeners.visibilitychange || [];
      visibilityHandlers.forEach(handler => handler());
    });

    expect(mockSendEvent).not.toHaveBeenCalled();
    expect(result.current.activityCount).toBe(0);
  });

  it('cleans up event listeners on unmount', () => {
    const { unmount } = renderHook(() => useScreenActivity({
      sendEvent: mockSendEvent,
      isEnabled: true,
    }));

    expect(document.addEventListener).toHaveBeenCalled();

    unmount();

    expect(document.removeEventListener).toHaveBeenCalled();
    expect(window.removeEventListener).toHaveBeenCalled();
  });

  it('throttles high-frequency events', () => {
    jest.useFakeTimers();
    
    const { result } = renderHook(() => useScreenActivity({
      sendEvent: mockSendEvent,
      isEnabled: true,
    }));

    // Trigger multiple rapid keydown events
    act(() => {
      const keyEvent = {
        type: 'keydown',
        key: 'c',
        ctrlKey: true,
        metaKey: false,
        preventDefault: jest.fn(),
      };
      
      const keyHandlers = eventListeners.keydown || [];
      
      // Trigger multiple times rapidly
      keyHandlers.forEach(handler => handler(keyEvent));
      keyHandlers.forEach(handler => handler(keyEvent));
      keyHandlers.forEach(handler => handler(keyEvent));
    });

    // Should only have been called once due to throttling
    expect(mockSendEvent).toHaveBeenCalledTimes(1);

    jest.useRealTimers();
  });
}); 