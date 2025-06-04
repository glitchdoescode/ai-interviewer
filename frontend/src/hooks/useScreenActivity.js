import { useState, useEffect, useRef, useCallback } from 'react';
import {
  ACTIVITY_TYPES,
  SEVERITY_LEVELS,
  createActivityEvent,
  getKeyCombo,
  isSuspiciousKeyCombo,
  getActivityInfo,
  throttle,
  debounce,
  calculateTimeAway,
  checkAPISupport,
  getBrowserInfo,
  ActivityBuffer as ActivityBufferClass,
  ActivityPatternDetector as ActivityPatternDetectorClass,
} from '../utils/activityDetection';

/**
 * Custom hook for screen activity monitoring
 * Handles tab switches, copy-paste, keyboard shortcuts, and window focus events
 */
export const useScreenActivity = (isEnabled = false, onActivityDetected = () => {}) => {
  const [isMonitoring, setIsMonitoring] = useState(false);
  const [activityCount, setActivityCount] = useState(0);
  const [suspiciousCount, setSuspiciousCount] = useState(0);
  const [apiSupport, setApiSupport] = useState({});
  const [recentPatterns, setRecentPatterns] = useState({});

  // Refs for managing state and cleanup
  const activityBufferRef = useRef(new ActivityBufferClass());
  const patternDetectorRef = useRef(new ActivityPatternDetectorClass());
  const tabHiddenAtRef = useRef(null);
  const isTabVisibleRef = useRef(true);
  const lastActivityTimeRef = useRef(Date.now());
  const isMonitoringRef = useRef(false); // Track monitoring state

  // Throttled functions to prevent spam
  const throttledKeyboardHandler = useRef(null);
  const throttledVisibilityHandler = useRef(null);
  const throttledFocusHandler = useRef(null);

  /**
   * Process and emit activity event
   */
  const processActivity = useCallback((type, severity, description, metadata = {}) => {
    console.log('🔥 Processing activity:', { type, severity, description, metadata });

    const event = createActivityEvent(type, severity, description, {
      ...metadata,
      browserInfo: getBrowserInfo(),
    });

    console.log('📦 Created activity event:', event);

    // Add to buffer
    activityBufferRef.current.add(event);

    // Update counts
    setActivityCount(prev => prev + 1);
    if (severity === SEVERITY_LEVELS.HIGH || severity === SEVERITY_LEVELS.CRITICAL) {
      setSuspiciousCount(prev => prev + 1);
    }

    // Analyze patterns
    const allEvents = activityBufferRef.current.getAll();
    const patterns = patternDetectorRef.current.analyzePatterns(allEvents);
    setRecentPatterns(patterns);

    // Update last activity time
    lastActivityTimeRef.current = Date.now();

    // Emit to parent component
    console.log('📡 Emitting to parent component via onActivityDetected');
    onActivityDetected(event);

    console.log('✅ Activity processing completed for:', type);
  }, [onActivityDetected]);

  /**
   * Handle keyboard events
   */
  const handleKeyDown = useCallback((event) => {
    if (!isMonitoringRef.current) return;

    const keyCombo = getKeyCombo(event);
    
    if (isSuspiciousKeyCombo(keyCombo)) {
      const activityInfo = getActivityInfo(keyCombo);
      processActivity(
        activityInfo.type,
        activityInfo.severity,
        activityInfo.description,
        {
          keyCombo,
          key: event.key,
          code: event.code,
          ctrlKey: event.ctrlKey,
          altKey: event.altKey,
          shiftKey: event.shiftKey,
          metaKey: event.metaKey,
        }
      );
    }
  }, [processActivity]);

  /**
   * Handle tab visibility changes
   */
  const handleVisibilityChange = useCallback(() => {
    console.log('🔥🔥🔥 VISIBILITY CHANGE EVENT FIRED! 🔥🔥🔥');
    console.log('🔥 document.hidden:', document.hidden);
    console.log('🔥 isMonitoringRef.current:', isMonitoringRef.current);
    console.log('🔥 isTabVisibleRef.current:', isTabVisibleRef.current);
    
    if (!isMonitoringRef.current) {
      console.log('🔥 EXITING: Not monitoring');
      return;
    }

    const isVisible = !document.hidden;
    const timestamp = new Date().toISOString();

    console.log('🔥 isVisible:', isVisible);
    console.log('🔥 Current tab state - isTabVisibleRef.current:', isTabVisibleRef.current);

    if (!isVisible && isTabVisibleRef.current) {
      // Tab became hidden
      console.log('🔍💥 Tab switched AWAY - sending TAB_SWITCH event');
      tabHiddenAtRef.current = timestamp;
      isTabVisibleRef.current = false;
      
      const activityEvent = {
        type: ACTIVITY_TYPES.TAB_SWITCH,
        severity: SEVERITY_LEVELS.MEDIUM,
        description: 'Tab switched away from interview',
        timestamp,
        metadata: {
          direction: 'away',
          timestamp
        }
      };
      
      console.log('🔥 About to call processActivity with:', activityEvent);
      
      processActivity(
        ACTIVITY_TYPES.TAB_SWITCH,
        SEVERITY_LEVELS.MEDIUM,
        'Tab switched away from interview',
        { direction: 'away', timestamp }
      );
    } else if (isVisible && !isTabVisibleRef.current) {
      // Tab became visible
      console.log('🔍💥 Tab switched BACK - sending TAB_SWITCH event');
      const timeAway = calculateTimeAway(tabHiddenAtRef.current, timestamp);
      isTabVisibleRef.current = true;
      tabHiddenAtRef.current = null;

      const activityEvent = {
        type: ACTIVITY_TYPES.TAB_SWITCH,
        severity: timeAway > 30000 ? SEVERITY_LEVELS.HIGH : SEVERITY_LEVELS.MEDIUM,
        description: 'Tab switched back to interview',
        timestamp,
        metadata: {
          direction: 'back', 
          timeAway,
          timeAwayFormatted: `${Math.round(timeAway / 1000)}s`,
          timestamp
        }
      };
      
      console.log('🔥 About to call processActivity with:', activityEvent);

      processActivity(
        ACTIVITY_TYPES.TAB_SWITCH,
        timeAway > 30000 ? SEVERITY_LEVELS.HIGH : SEVERITY_LEVELS.MEDIUM,
        'Tab switched back to interview',
        { 
          direction: 'back', 
          timeAway,
          timeAwayFormatted: `${Math.round(timeAway / 1000)}s`,
          timestamp 
        }
      );
    } else {
      console.log('🔥 NO ACTION: isVisible:', isVisible, 'isTabVisibleRef.current:', isTabVisibleRef.current);
    }
  }, [processActivity]);

  /**
   * Handle window focus/blur events
   */
  const handleWindowFocus = useCallback((event) => {
    if (!isMonitoringRef.current) return;

    const eventType = event.type;
    const timestamp = new Date().toISOString();

    if (eventType === 'blur') {
      console.log('🔍 Window BLUR detected');
      processActivity(
        ACTIVITY_TYPES.WINDOW_BLUR,
        SEVERITY_LEVELS.MEDIUM,
        'Window lost focus (switched to another application)',
        { timestamp }
      );
    } else if (eventType === 'focus') {
      console.log('🔍 Window FOCUS detected');
      processActivity(
        ACTIVITY_TYPES.WINDOW_FOCUS,
        SEVERITY_LEVELS.LOW,
        'Window regained focus',
        { timestamp }
      );
    }
  }, [processActivity]);

  /**
   * Handle copy-paste detection
   */
  const handleCopyPaste = useCallback((event) => {
    if (!isMonitoringRef.current) return;

    const isCtrlC = (event.ctrlKey || event.metaKey) && event.key === 'c';
    const isCtrlV = (event.ctrlKey || event.metaKey) && event.key === 'v';

    if (isCtrlC) {
      console.log('🔍 COPY detected - sending COPY_ACTION event');
      processActivity(
        ACTIVITY_TYPES.COPY_ACTION,
        SEVERITY_LEVELS.LOW,
        'Content copied to clipboard',
        {
          source: 'keyboard',
          timestamp: new Date().toISOString(),
        }
      );
    } else if (isCtrlV) {
      console.log('🔍 PASTE detected - sending PASTE_ACTION event');
      processActivity(
        ACTIVITY_TYPES.PASTE_ACTION,
        SEVERITY_LEVELS.MEDIUM,
        'Content pasted from clipboard',
        {
          source: 'keyboard',
          timestamp: new Date().toISOString(),
        }
      );
    }
  }, [processActivity]);

  /**
   * Start monitoring
   */
  const startMonitoring = useCallback(() => {
    console.log('🚀 START MONITORING: Function called');
    console.log('🚀 START MONITORING: isMonitoring:', isMonitoring, 'isMonitoringRef.current:', isMonitoringRef.current);
    
    if (isMonitoringRef.current) {
      console.log('🚀 START MONITORING: Already monitoring, exiting early');
      return;
    }

    console.log('🚀 START MONITORING: Starting screen activity monitoring...');

    // Check API support
    const support = checkAPISupport();
    console.log('🚀 START MONITORING: API support:', support);
    setApiSupport(support);

    // Create throttled handlers
    console.log('🚀 START MONITORING: Creating throttled handlers...');
    throttledKeyboardHandler.current = throttle(handleKeyDown, 100);
    throttledVisibilityHandler.current = throttle(handleVisibilityChange, 100);
    throttledFocusHandler.current = throttle(handleWindowFocus, 1000);
    console.log('🚀 START MONITORING: Throttled handlers created');
    
    // Test the handlers to make sure they work
    console.log('🚀 START MONITORING: Testing handler functions...');
    console.log('🚀 START MONITORING: handleKeyDown function:', typeof handleKeyDown);
    console.log('🚀 START MONITORING: handleCopyPaste function:', typeof handleCopyPaste);
    console.log('🚀 START MONITORING: handleVisibilityChange function:', typeof handleVisibilityChange);

    // Add event listeners
    if (support.keyboardAPI) {
      console.log('🚀 START MONITORING: Adding keyboard event listeners...');
      document.addEventListener('keydown', throttledKeyboardHandler.current);
      document.addEventListener('keydown', handleCopyPaste);
      console.log('🚀 START MONITORING: Keyboard listeners added');
    } else {
      console.log('🚀 START MONITORING: Keyboard API not supported');
    }

    if (support.visibilityAPI) {
      console.log('🚀 START MONITORING: Adding visibility event listener...');
      // Use direct handler for immediate response to tab switches
      document.addEventListener('visibilitychange', handleVisibilityChange);
      console.log('🚀 START MONITORING: Visibility listener added');
    } else {
      console.log('🚀 START MONITORING: Visibility API not supported');
    }

    if (support.focusAPI) {
      console.log('🚀 START MONITORING: Adding focus event listeners...');
      window.addEventListener('focus', throttledFocusHandler.current);
      window.addEventListener('blur', throttledFocusHandler.current);
      console.log('🚀 START MONITORING: Focus listeners added');
    } else {
      console.log('🚀 START MONITORING: Focus API not supported');
    }

    // Initialize state
    console.log('🚀 START MONITORING: Initializing state...');
    setIsMonitoring(true);
    isMonitoringRef.current = true;
    isTabVisibleRef.current = !document.hidden;
    lastActivityTimeRef.current = Date.now();

    console.log('🚀 START MONITORING: Final state - isMonitoring: true, isTabVisibleRef.current:', isTabVisibleRef.current);
    console.log('🚀 START MONITORING: Screen activity monitoring started with API support:', support);
  }, [isMonitoring, handleKeyDown, handleVisibilityChange, handleWindowFocus, handleCopyPaste]);

  /**
   * Stop monitoring
   */
  const stopMonitoring = useCallback(() => {
    if (!isMonitoringRef.current) return;

    console.log('Stopping screen activity monitoring...');

    // Remove event listeners
    if (throttledKeyboardHandler.current) {
      document.removeEventListener('keydown', throttledKeyboardHandler.current);
      document.removeEventListener('keydown', handleCopyPaste);
    }

    if (throttledVisibilityHandler.current) {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    }

    if (throttledFocusHandler.current) {
      window.removeEventListener('focus', throttledFocusHandler.current);
      window.removeEventListener('blur', throttledFocusHandler.current);
    }

    // Don't send monitoring_stopped as a screen activity event  
    console.log('Screen activity monitoring stopped. Total events:', activityBufferRef.current.getCount());

    setIsMonitoring(false);
    isMonitoringRef.current = false;
  }, []);

  /**
   * Get activity statistics
   */
  const getActivityStats = useCallback(() => {
    const allEvents = activityBufferRef.current.getAll();
    const recentEvents = activityBufferRef.current.getRecent(5); // Last 5 minutes

    return {
      total: allEvents.length,
      recent: recentEvents.length,
      suspicious: allEvents.filter(e => 
        e.severity === SEVERITY_LEVELS.HIGH || e.severity === SEVERITY_LEVELS.CRITICAL
      ).length,
      byType: {
        tabSwitches: allEvents.filter(e => e.type === ACTIVITY_TYPES.TAB_SWITCH).length,
        copyPaste: allEvents.filter(e => 
          e.type === ACTIVITY_TYPES.COPY_ACTION || e.type === ACTIVITY_TYPES.PASTE_ACTION
        ).length,
        consoleAccess: allEvents.filter(e => e.type === ACTIVITY_TYPES.CONSOLE_ACCESS).length,
        screenshots: allEvents.filter(e => e.type === ACTIVITY_TYPES.SCREENSHOT_ATTEMPT).length,
      },
      patterns: recentPatterns,
    };
  }, [recentPatterns]);

  /**
   * Clear activity buffer
   */
  const clearActivityBuffer = useCallback(() => {
    activityBufferRef.current.clear();
    setActivityCount(0);
    setSuspiciousCount(0);
    setRecentPatterns({});
  }, []);

  /**
   * Get all buffered events
   */
  const getAllEvents = useCallback(() => {
    return activityBufferRef.current.getAll();
  }, []);

  // Effect to handle enable/disable
  useEffect(() => {
    console.log('🔥 useScreenActivity: isEnabled changed to:', isEnabled);
    console.log('🔥 useScreenActivity: isMonitoring currently:', isMonitoring);
    console.log('🔥 useScreenActivity: isMonitoringRef.current:', isMonitoringRef.current);
    
    if (isEnabled && !isMonitoringRef.current) {
      console.log('🔥 useScreenActivity: Should start monitoring - calling startMonitoring()');
      startMonitoring();
    } else if (!isEnabled && isMonitoringRef.current) {
      console.log('🔥 useScreenActivity: Should stop monitoring - calling stopMonitoring()');
      stopMonitoring();
    } else {
      console.log('🔥 useScreenActivity: No action needed');
    }
  }, [isEnabled, isMonitoring, startMonitoring, stopMonitoring]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (isMonitoringRef.current) {
        // Clean up event listeners on unmount
        if (throttledKeyboardHandler.current) {
          document.removeEventListener('keydown', throttledKeyboardHandler.current);
          document.removeEventListener('keydown', handleCopyPaste);
        }

        if (throttledVisibilityHandler.current) {
          document.removeEventListener('visibilitychange', handleVisibilityChange);
        }

        if (throttledFocusHandler.current) {
          window.removeEventListener('focus', throttledFocusHandler.current);
          window.removeEventListener('blur', throttledFocusHandler.current);
        }

        isMonitoringRef.current = false;
      }
    };
  }, [handleCopyPaste]);

  return {
    // State
    isMonitoring,
    activityCount,
    suspiciousCount,
    apiSupport,
    recentPatterns,

    // Actions
    startMonitoring,
    stopMonitoring,
    clearActivityBuffer,

    // Data access
    getActivityStats,
    getAllEvents,
  };
}; 