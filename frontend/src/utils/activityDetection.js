/**
 * Activity Detection Utilities
 * Core utilities for detecting various screen and keyboard activities
 */

// Activity type constants
export const ACTIVITY_TYPES = {
  TAB_SWITCH: 'tab_switch',
  WINDOW_FOCUS: 'window_focus',
  WINDOW_BLUR: 'window_blur',
  COPY_ACTION: 'copy_action',
  PASTE_ACTION: 'paste_action',
  KEYBOARD_SHORTCUT: 'keyboard_shortcut',
  CONSOLE_ACCESS: 'console_access',
  SCREENSHOT_ATTEMPT: 'screenshot_attempt',
  TAB_MANAGEMENT: 'tab_management',
};

// Severity levels for activities
export const SEVERITY_LEVELS = {
  LOW: 'low',
  MEDIUM: 'medium',
  HIGH: 'high',
  CRITICAL: 'critical',
};

// Suspicious keyboard combinations
export const SUSPICIOUS_SHORTCUTS = {
  // Tab management
  'ctrl+t': { type: ACTIVITY_TYPES.TAB_MANAGEMENT, severity: SEVERITY_LEVELS.MEDIUM, description: 'New tab opened' },
  'ctrl+shift+t': { type: ACTIVITY_TYPES.TAB_MANAGEMENT, severity: SEVERITY_LEVELS.HIGH, description: 'Recently closed tab reopened' },
  'ctrl+w': { type: ACTIVITY_TYPES.TAB_MANAGEMENT, severity: SEVERITY_LEVELS.MEDIUM, description: 'Tab closed' },
  'alt+tab': { type: ACTIVITY_TYPES.WINDOW_FOCUS, severity: SEVERITY_LEVELS.HIGH, description: 'Application switch attempted' },
  
  // Developer tools
  'f12': { type: ACTIVITY_TYPES.CONSOLE_ACCESS, severity: SEVERITY_LEVELS.CRITICAL, description: 'Developer tools opened' },
  'ctrl+shift+i': { type: ACTIVITY_TYPES.CONSOLE_ACCESS, severity: SEVERITY_LEVELS.CRITICAL, description: 'Developer tools opened' },
  'ctrl+shift+j': { type: ACTIVITY_TYPES.CONSOLE_ACCESS, severity: SEVERITY_LEVELS.CRITICAL, description: 'Console opened' },
  'ctrl+u': { type: ACTIVITY_TYPES.CONSOLE_ACCESS, severity: SEVERITY_LEVELS.HIGH, description: 'View source attempted' },
  
  // Screenshot attempts
  'printscreen': { type: ACTIVITY_TYPES.SCREENSHOT_ATTEMPT, severity: SEVERITY_LEVELS.HIGH, description: 'Screenshot captured' },
  'meta+shift+s': { type: ACTIVITY_TYPES.SCREENSHOT_ATTEMPT, severity: SEVERITY_LEVELS.HIGH, description: 'Screenshot tool opened (Windows)' },
  'meta+shift+4': { type: ACTIVITY_TYPES.SCREENSHOT_ATTEMPT, severity: SEVERITY_LEVELS.HIGH, description: 'Screenshot captured (Mac)' },
  'meta+shift+3': { type: ACTIVITY_TYPES.SCREENSHOT_ATTEMPT, severity: SEVERITY_LEVELS.HIGH, description: 'Full screenshot captured (Mac)' },
  
  // Copy-paste
  'ctrl+c': { type: ACTIVITY_TYPES.COPY_ACTION, severity: SEVERITY_LEVELS.LOW, description: 'Content copied' },
  'ctrl+v': { type: ACTIVITY_TYPES.PASTE_ACTION, severity: SEVERITY_LEVELS.MEDIUM, description: 'Content pasted' },
  'meta+c': { type: ACTIVITY_TYPES.COPY_ACTION, severity: SEVERITY_LEVELS.LOW, description: 'Content copied (Mac)' },
  'meta+v': { type: ACTIVITY_TYPES.PASTE_ACTION, severity: SEVERITY_LEVELS.MEDIUM, description: 'Content pasted (Mac)' },
};

/**
 * Create a standardized activity event object
 */
export const createActivityEvent = (type, severity, description, metadata = {}) => ({
  type,
  severity,
  description,
  timestamp: new Date().toISOString(),
  metadata: {
    userAgent: navigator.userAgent,
    url: window.location.href,
    ...metadata,
  },
});

/**
 * Get key combination string from keyboard event
 */
export const getKeyCombo = (event) => {
  const keys = [];
  
  // Add the main key first
  if (event.key && event.key !== 'Control' && event.key !== 'Meta' && 
      event.key !== 'Alt' && event.key !== 'Shift') {
    keys.push(event.key.toLowerCase());
  }
  
  // If there's no main key, return empty string (modifier-only event)
  if (keys.length === 0) {
    return '';
  }
  
  // Add modifiers
  const modifiers = [];
  if (event.ctrlKey) modifiers.push('ctrl');
  if (event.metaKey) modifiers.push('meta');
  if (event.altKey) modifiers.push('alt');
  if (event.shiftKey) modifiers.push('shift');
  
  // Combine modifiers and main key
  return [...modifiers, ...keys].join('+');
};

/**
 * Check if a key combination is suspicious
 */
export const isSuspiciousKeyCombo = (keyCombo) => {
  return SUSPICIOUS_SHORTCUTS.hasOwnProperty(keyCombo);
};

/**
 * Get activity info for a key combination
 */
export const getActivityInfo = (keyCombo) => {
  return SUSPICIOUS_SHORTCUTS[keyCombo] || null;
};

/**
 * Throttle function to limit event frequency
 */
export const throttle = (func, delay) => {
  let timeoutId;
  let lastExecTime = 0;
  
  return function (...args) {
    const currentTime = Date.now();
    
    if (currentTime - lastExecTime > delay) {
      func.apply(this, args);
      lastExecTime = currentTime;
    } else {
      clearTimeout(timeoutId);
      timeoutId = setTimeout(() => {
        func.apply(this, args);
        lastExecTime = Date.now();
      }, delay - (currentTime - lastExecTime));
    }
  };
};

/**
 * Debounce function to delay execution
 */
export const debounce = (func, delay) => {
  let timeoutId;
  
  return function (...args) {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => func.apply(this, args), delay);
  };
};

/**
 * Calculate time away from tab
 */
export const calculateTimeAway = (hiddenAt, visibleAt) => {
  if (!hiddenAt || !visibleAt) return 0;
  return new Date(visibleAt) - new Date(hiddenAt);
};

/**
 * Detect if browser supports required APIs
 */
export const checkAPISupport = () => {
  return {
    visibilityAPI: typeof document.hidden !== 'undefined',
    clipboardAPI: navigator.clipboard && typeof navigator.clipboard.readText === 'function',
    keyboardAPI: typeof document.addEventListener === 'function',
    focusAPI: typeof window.addEventListener === 'function',
  };
};

/**
 * Get browser information for activity context
 */
export const getBrowserInfo = () => ({
  userAgent: navigator.userAgent,
  language: navigator.language,
  platform: navigator.platform,
  cookieEnabled: navigator.cookieEnabled,
  onLine: navigator.onLine,
  viewport: {
    width: window.innerWidth,
    height: window.innerHeight,
  },
  screen: {
    width: window.screen.width,
    height: window.screen.height,
    colorDepth: window.screen.colorDepth,
  },
});

/**
 * Activity event buffer for handling connection issues
 */
export class ActivityBuffer {
  constructor(maxSize = 100) {
    this.events = [];
    this.maxSize = maxSize;
  }

  add(event) {
    this.events.push(event);
    if (this.events.length > this.maxSize) {
      this.events.shift(); // Remove oldest event
    }
  }

  getAll() {
    return [...this.events];
  }

  clear() {
    this.events = [];
  }

  getCount() {
    return this.events.length;
  }

  getByType(type) {
    return this.events.filter(event => event.type === type);
  }

  getRecent(minutes = 5) {
    const cutoff = new Date(Date.now() - minutes * 60 * 1000);
    return this.events.filter(event => new Date(event.timestamp) > cutoff);
  }
}

/**
 * Activity patterns detector
 */
export class ActivityPatternDetector {
  constructor() {
    this.patterns = {
      rapidTabSwitching: { threshold: 5, timeWindow: 30000 }, // 5 switches in 30 seconds
      excessiveCopyPaste: { threshold: 10, timeWindow: 60000 }, // 10 copy-paste in 1 minute
      frequentConsoleAccess: { threshold: 3, timeWindow: 300000 }, // 3 console access in 5 minutes
    };
  }

  detectRapidTabSwitching(events) {
    const tabEvents = events.filter(e => e.type === ACTIVITY_TYPES.TAB_SWITCH);
    const recent = this.getRecentEvents(tabEvents, this.patterns.rapidTabSwitching.timeWindow);
    return recent.length >= this.patterns.rapidTabSwitching.threshold;
  }

  detectExcessiveCopyPaste(events) {
    const copyPasteEvents = events.filter(e => 
      e.type === ACTIVITY_TYPES.COPY_ACTION || e.type === ACTIVITY_TYPES.PASTE_ACTION
    );
    const recent = this.getRecentEvents(copyPasteEvents, this.patterns.excessiveCopyPaste.timeWindow);
    return recent.length >= this.patterns.excessiveCopyPaste.threshold;
  }

  detectFrequentConsoleAccess(events) {
    const consoleEvents = events.filter(e => e.type === ACTIVITY_TYPES.CONSOLE_ACCESS);
    const recent = this.getRecentEvents(consoleEvents, this.patterns.frequentConsoleAccess.timeWindow);
    return recent.length >= this.patterns.frequentConsoleAccess.threshold;
  }

  getRecentEvents(events, timeWindow) {
    const cutoff = Date.now() - timeWindow;
    return events.filter(event => new Date(event.timestamp).getTime() > cutoff);
  }

  analyzePatterns(events) {
    return {
      rapidTabSwitching: this.detectRapidTabSwitching(events),
      excessiveCopyPaste: this.detectExcessiveCopyPaste(events),
      frequentConsoleAccess: this.detectFrequentConsoleAccess(events),
    };
  }
}

/**
 * Detect screenshot attempts using screen capture APIs and keyboard shortcuts
 */
export const detectScreenshotAttempt = () => {
  // Check for screen capture API usage (this is a detection for modern browsers)
  if (navigator.mediaDevices && typeof navigator.mediaDevices.getDisplayMedia === 'function') {
    // Browser supports screen capture API
    return createActivityEvent(
      ACTIVITY_TYPES.SCREENSHOT_ATTEMPT, 
      SEVERITY_LEVELS.HIGH, 
      'Screen capture API detected',
      {
        method: 'screen_capture_api',
        screen_width: window.screen ? window.screen.width : 0,
        screen_height: window.screen ? window.screen.height : 0,
        browser_support: true
      }
    );
  }
  return null;
}; 