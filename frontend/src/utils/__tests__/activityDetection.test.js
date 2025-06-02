import {
  createActivityEvent,
  getKeyCombo,
  isSuspiciousKeyCombo,
  getActivityInfo,
  throttle,
  debounce,
  calculateTimeAway,
  checkAPISupport,
  getBrowserInfo,
  ActivityBuffer,
  ActivityPatternDetector,
  detectScreenshotAttempt,
  ACTIVITY_TYPES,
  SEVERITY_LEVELS,
  SUSPICIOUS_SHORTCUTS
} from '../activityDetection';

describe('Activity Detection Utilities', () => {
  describe('createActivityEvent', () => {
    it('should create an activity event with all required fields', () => {
      const event = createActivityEvent(
        ACTIVITY_TYPES.TAB_SWITCH,
        SEVERITY_LEVELS.MEDIUM,
        'User switched tabs',
        { tabId: '123' }
      );

      expect(event).toHaveProperty('type', ACTIVITY_TYPES.TAB_SWITCH);
      expect(event).toHaveProperty('severity', SEVERITY_LEVELS.MEDIUM);
      expect(event).toHaveProperty('description', 'User switched tabs');
      expect(event).toHaveProperty('metadata');
      expect(event.metadata).toHaveProperty('tabId', '123');
      expect(event).toHaveProperty('timestamp');
    });
  });

  describe('getKeyCombo', () => {
    it('should handle single key press', () => {
      const event = new KeyboardEvent('keydown', { key: 'a' });
      expect(getKeyCombo(event)).toBe('a');
    });

    it('should handle modifier keys', () => {
      const event = new KeyboardEvent('keydown', {
        key: 'c',
        ctrlKey: true,
        metaKey: true
      });
      expect(getKeyCombo(event)).toBe('ctrl+meta+c');
    });

    it('should ignore modifier-only events', () => {
      const event = new KeyboardEvent('keydown', {
        key: 'Control',
        ctrlKey: true
      });
      expect(getKeyCombo(event)).toBe('');
    });
  });

  describe('isSuspiciousKeyCombo', () => {
    it('should identify known suspicious shortcuts', () => {
      const suspiciousShortcut = Object.keys(SUSPICIOUS_SHORTCUTS)[0];
      expect(isSuspiciousKeyCombo(suspiciousShortcut)).toBe(true);
    });

    it('should reject unknown shortcuts', () => {
      expect(isSuspiciousKeyCombo('unknown+combo')).toBe(false);
    });
  });

  describe('getActivityInfo', () => {
    it('should return activity info for known shortcuts', () => {
      const suspiciousShortcut = Object.keys(SUSPICIOUS_SHORTCUTS)[0];
      expect(getActivityInfo(suspiciousShortcut)).toBe(SUSPICIOUS_SHORTCUTS[suspiciousShortcut]);
    });

    it('should return null for unknown shortcuts', () => {
      expect(getActivityInfo('unknown+combo')).toBeNull();
    });
  });

  describe('throttle', () => {
    jest.useFakeTimers();

    it('should limit function execution rate', () => {
      const mockFn = jest.fn();
      const throttledFn = throttle(mockFn, 1000);

      // Call multiple times
      throttledFn();
      throttledFn();
      throttledFn();

      expect(mockFn).toHaveBeenCalledTimes(1);

      // Advance time
      jest.advanceTimersByTime(1000);
      expect(mockFn).toHaveBeenCalledTimes(2);
    });
  });

  describe('debounce', () => {
    jest.useFakeTimers();

    it('should delay function execution', () => {
      const mockFn = jest.fn();
      const debouncedFn = debounce(mockFn, 1000);

      debouncedFn();
      expect(mockFn).not.toHaveBeenCalled();

      jest.advanceTimersByTime(1000);
      expect(mockFn).toHaveBeenCalledTimes(1);
    });
  });

  describe('calculateTimeAway', () => {
    it('should calculate time difference correctly', () => {
      const hiddenAt = new Date('2024-01-01T10:00:00Z');
      const visibleAt = new Date('2024-01-01T10:01:00Z');
      expect(calculateTimeAway(hiddenAt, visibleAt)).toBe(60000); // 1 minute in milliseconds
    });

    it('should return 0 for invalid inputs', () => {
      expect(calculateTimeAway(null, new Date())).toBe(0);
      expect(calculateTimeAway(new Date(), null)).toBe(0);
      expect(calculateTimeAway(null, null)).toBe(0);
    });
  });

  describe('checkAPISupport', () => {
    it('should check browser API support', () => {
      const support = checkAPISupport();
      expect(support).toHaveProperty('visibilityAPI');
      expect(support).toHaveProperty('clipboardAPI');
      expect(support).toHaveProperty('keyboardAPI');
      expect(support).toHaveProperty('focusAPI');
    });
  });

  describe('getBrowserInfo', () => {
    it('should return browser information', () => {
      const info = getBrowserInfo();
      expect(info).toHaveProperty('userAgent');
      expect(info).toHaveProperty('language');
      expect(info).toHaveProperty('platform');
      expect(info).toHaveProperty('viewport');
      expect(info).toHaveProperty('screen');
    });
  });

  describe('ActivityBuffer', () => {
    let buffer;

    beforeEach(() => {
      buffer = new ActivityBuffer(3);
    });

    it('should add and retrieve events', () => {
      const event = { type: 'test', timestamp: new Date() };
      buffer.add(event);
      expect(buffer.getAll()).toHaveLength(1);
      expect(buffer.getAll()[0]).toBe(event);
    });

    it('should respect max size', () => {
      buffer.add({ type: '1' });
      buffer.add({ type: '2' });
      buffer.add({ type: '3' });
      buffer.add({ type: '4' });
      expect(buffer.getAll()).toHaveLength(3);
      expect(buffer.getAll()[0].type).toBe('2');
    });

    it('should filter events by type', () => {
      buffer.add({ type: 'test1' });
      buffer.add({ type: 'test2' });
      buffer.add({ type: 'test1' });
      expect(buffer.getByType('test1')).toHaveLength(2);
    });

    it('should get recent events', () => {
      const oldEvent = { type: 'old', timestamp: new Date(Date.now() - 3600000) };
      const newEvent = { type: 'new', timestamp: new Date() };
      buffer.add(oldEvent);
      buffer.add(newEvent);
      expect(buffer.getRecent(1)).toHaveLength(1);
    });
  });

  describe('ActivityPatternDetector', () => {
    let detector;

    beforeEach(() => {
      detector = new ActivityPatternDetector();
    });

    it('should detect rapid tab switching', () => {
      const events = Array(6).fill({ type: ACTIVITY_TYPES.TAB_SWITCH, timestamp: new Date() });
      expect(detector.detectRapidTabSwitching(events)).toBe(true);
    });

    it('should detect excessive copy-paste', () => {
      const events = Array(11).fill({ type: ACTIVITY_TYPES.COPY_ACTION, timestamp: new Date() });
      expect(detector.detectExcessiveCopyPaste(events)).toBe(true);
    });

    it('should detect frequent console access', () => {
      const events = Array(4).fill({ type: ACTIVITY_TYPES.CONSOLE_ACCESS, timestamp: new Date() });
      expect(detector.detectFrequentConsoleAccess(events)).toBe(true);
    });
  });

  describe('detectScreenshotAttempt', () => {
    it('should detect screenshot attempt when API is available', () => {
      // Mock screen capture API
      Object.defineProperty(navigator, 'mediaDevices', {
        value: {
          getDisplayMedia: jest.fn()
        },
        writable: true
      });

      const event = detectScreenshotAttempt();
      expect(event).not.toBeNull();
      expect(event.type).toBe(ACTIVITY_TYPES.SCREENSHOT_ATTEMPT);
      expect(event.severity).toBe(SEVERITY_LEVELS.HIGH);
    });

    it('should return null when API is not available', () => {
      // Remove screen capture API
      Object.defineProperty(navigator, 'mediaDevices', {
        value: undefined,
        writable: true
      });

      const event = detectScreenshotAttempt();
      expect(event).toBeNull();
    });
  });
}); 