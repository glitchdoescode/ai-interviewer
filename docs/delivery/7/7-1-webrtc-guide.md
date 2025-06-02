# WebRTC Video Streaming Guide

**Task ID**: 7-1  
**Date**: 2025-01-27  
**Documentation for**: Real-time video streaming and capture using WebRTC APIs

## Overview

WebRTC (Web Real-Time Communication) provides APIs for capturing audio and video media from user devices. The getUserMedia API is the foundation for accessing camera and microphone streams in web browsers.

## Key Features

- **Real-time media access** - Direct access to camera and microphone
- **Cross-platform support** - Works on desktop and mobile browsers
- **Secure by default** - Requires HTTPS in production
- **Constraint-based configuration** - Fine-grained control over media properties
- **No plugins required** - Native browser implementation

## Browser Compatibility

### Current Support (2024)
- **Chrome**: Excellent support (21+)
- **Firefox**: Good support (36+) 
- **Safari**: Good support (11+)
- **Edge**: Excellent support (12+)
- **Mobile Chrome**: Excellent support
- **Mobile Safari**: Good support (11+)

### Global Usage
- **Desktop**: ~96% support
- **Mobile**: ~85% support
- **Overall**: ~96.36% global compatibility

## Basic Implementation

### Getting User Media
```javascript
// Simple video and audio access
async function getMediaStream() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: true,
      audio: true
    });
    
    return stream;
  } catch (error) {
    console.error('Error accessing media devices:', error);
    throw error;
  }
}
```

### Video Element Integration
```javascript
async function initializeVideo() {
  const video = document.getElementById('videoElement');
  
  try {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: { width: 1280, height: 720 },
      audio: false
    });
    
    video.srcObject = stream;
    video.onloadedmetadata = () => {
      video.play();
    };
    
    return stream;
  } catch (error) {
    handleMediaError(error);
  }
}
```

## Advanced Constraints

### Video Constraints
```javascript
const videoConstraints = {
  video: {
    width: { min: 640, ideal: 1280, max: 1920 },
    height: { min: 480, ideal: 720, max: 1080 },
    frameRate: { ideal: 30, max: 60 },
    facingMode: 'user', // 'user' or 'environment'
    aspectRatio: 16/9
  }
};

const stream = await navigator.mediaDevices.getUserMedia(videoConstraints);
```

### Device Selection
```javascript
// Enumerate available devices
async function getAvailableDevices() {
  const devices = await navigator.mediaDevices.enumerateDevices();
  const videoDevices = devices.filter(device => device.kind === 'videoinput');
  const audioDevices = devices.filter(device => device.kind === 'audioinput');
  
  return { videoDevices, audioDevices };
}

// Select specific device
async function selectSpecificCamera(deviceId) {
  const constraints = {
    video: {
      deviceId: { exact: deviceId },
      width: { ideal: 1280 },
      height: { ideal: 720 }
    }
  };
  
  return await navigator.mediaDevices.getUserMedia(constraints);
}
```

### Performance Optimization
```javascript
// Optimized constraints for proctoring
const proctoringConstraints = {
  video: {
    width: { ideal: 640 },
    height: { ideal: 480 },
    frameRate: { ideal: 15, max: 30 }, // Lower frame rate saves bandwidth
    facingMode: 'user'
  },
  audio: false // Disable audio if not needed for processing
};
```

## Stream Management

### Starting and Stopping Streams
```javascript
class MediaStreamManager {
  constructor() {
    this.currentStream = null;
    this.videoElement = null;
  }
  
  async startStream(constraints) {
    try {
      this.currentStream = await navigator.mediaDevices.getUserMedia(constraints);
      
      if (this.videoElement) {
        this.videoElement.srcObject = this.currentStream;
      }
      
      return this.currentStream;
    } catch (error) {
      throw new Error(`Failed to start stream: ${error.message}`);
    }
  }
  
  stopStream() {
    if (this.currentStream) {
      this.currentStream.getTracks().forEach(track => {
        track.stop();
      });
      this.currentStream = null;
      
      if (this.videoElement) {
        this.videoElement.srcObject = null;
      }
    }
  }
  
  switchCamera(deviceId) {
    this.stopStream();
    return this.startStream({
      video: { deviceId: { exact: deviceId } }
    });
  }
}
```

### Track Management
```javascript
// Get video track for processing
function getVideoTrack(stream) {
  const videoTracks = stream.getVideoTracks();
  if (videoTracks.length === 0) {
    throw new Error('No video track found');
  }
  return videoTracks[0];
}

// Apply constraints to existing track
async function updateTrackConstraints(track, constraints) {
  try {
    await track.applyConstraints(constraints);
    console.log('Constraints applied successfully');
  } catch (error) {
    console.error('Failed to apply constraints:', error);
  }
}

// Get current track settings
function getTrackSettings(track) {
  const settings = track.getSettings();
  console.log('Current track settings:', settings);
  return settings;
}
```

## Error Handling

### Common Error Types
```javascript
function handleMediaError(error) {
  switch (error.name) {
    case 'NotAllowedError':
      console.error('User denied camera access');
      showPermissionPrompt();
      break;
      
    case 'NotFoundError':
      console.error('No camera device found');
      showNoDeviceMessage();
      break;
      
    case 'NotReadableError':
      console.error('Camera is already in use');
      showDeviceBusyMessage();
      break;
      
    case 'OverconstrainedError':
      console.error('Camera constraints cannot be satisfied');
      fallbackToBasicConstraints();
      break;
      
    case 'SecurityError':
      console.error('HTTPS required for camera access');
      showSecurityError();
      break;
      
    default:
      console.error('Unknown camera error:', error);
      showGenericError();
  }
}
```

### Graceful Degradation
```javascript
async function initializeMediaWithFallback() {
  const constraintSets = [
    // High quality
    { video: { width: 1280, height: 720, frameRate: 30 } },
    // Medium quality
    { video: { width: 640, height: 480, frameRate: 15 } },
    // Basic quality
    { video: true }
  ];
  
  for (const constraints of constraintSets) {
    try {
      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      console.log('Media initialized with constraints:', constraints);
      return stream;
    } catch (error) {
      console.warn('Failed with constraints:', constraints, error);
    }
  }
  
  throw new Error('Unable to initialize any media stream');
}
```

## Security Considerations

### HTTPS Requirement
```javascript
// Check if running in secure context
function checkSecureContext() {
  if (!window.isSecureContext) {
    throw new Error('WebRTC requires HTTPS in production');
  }
  
  if (!navigator.mediaDevices) {
    throw new Error('MediaDevices API not available');
  }
}
```

### Permission Management
```javascript
// Check permission status
async function checkCameraPermission() {
  try {
    const permission = await navigator.permissions.query({ name: 'camera' });
    return permission.state; // 'granted', 'denied', or 'prompt'
  } catch (error) {
    console.warn('Permission API not supported');
    return 'unknown';
  }
}

// Request permission explicitly
async function requestCameraPermission() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: true });
    stream.getTracks().forEach(track => track.stop()); // Stop immediately
    return 'granted';
  } catch (error) {
    return 'denied';
  }
}
```

## Integration with Face Detection

### Real-time Processing Pipeline
```javascript
class ProctoringVideoProcessor {
  constructor(videoElement, faceDetector) {
    this.video = videoElement;
    this.detector = faceDetector;
    this.isProcessing = false;
    this.processingFPS = 5; // Process 5 frames per second
  }
  
  async startProcessing() {
    this.isProcessing = true;
    this.processLoop();
  }
  
  stopProcessing() {
    this.isProcessing = false;
  }
  
  async processLoop() {
    if (!this.isProcessing) return;
    
    try {
      if (this.video.readyState === 4) {
        const faces = await this.detector.estimateFaces(this.video);
        this.handleDetectionResults(faces);
      }
    } catch (error) {
      console.error('Face detection error:', error);
    }
    
    // Schedule next processing cycle
    setTimeout(() => {
      this.processLoop();
    }, 1000 / this.processingFPS);
  }
  
  handleDetectionResults(faces) {
    // Emit events for proctoring system
    if (faces.length === 0) {
      this.emit('noFaceDetected');
    } else if (faces.length > 1) {
      this.emit('multipleFacesDetected', faces.length);
    } else {
      this.emit('faceDetected', faces[0]);
    }
  }
}
```

## Mobile Optimization

### Mobile-Specific Constraints
```javascript
// Detect mobile device
function isMobileDevice() {
  return /Android|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
}

// Mobile-optimized constraints
function getMobileConstraints() {
  return {
    video: {
      width: { ideal: 480 },
      height: { ideal: 640 },
      frameRate: { ideal: 15 },
      facingMode: 'user'
    },
    audio: false
  };
}
```

### Battery Optimization
```javascript
// Adaptive frame rate based on battery
async function getAdaptiveConstraints() {
  let frameRate = 30;
  
  try {
    const battery = await navigator.getBattery();
    if (battery.level < 0.2) {
      frameRate = 10; // Very low battery
    } else if (battery.level < 0.5) {
      frameRate = 15; // Low battery
    }
  } catch (error) {
    // Battery API not supported
  }
  
  return {
    video: {
      frameRate: { ideal: frameRate },
      width: { ideal: 640 },
      height: { ideal: 480 }
    }
  };
}
```

## Performance Monitoring

### Stream Quality Monitoring
```javascript
class StreamQualityMonitor {
  constructor(stream) {
    this.stream = stream;
    this.stats = {
      frameRate: 0,
      resolution: { width: 0, height: 0 },
      droppedFrames: 0
    };
  }
  
  startMonitoring() {
    const videoTrack = this.stream.getVideoTracks()[0];
    
    setInterval(async () => {
      const settings = videoTrack.getSettings();
      this.stats.resolution = {
        width: settings.width,
        height: settings.height
      };
      this.stats.frameRate = settings.frameRate;
      
      // Check for performance issues
      if (this.stats.frameRate < 10) {
        console.warn('Low frame rate detected:', this.stats.frameRate);
        this.handleLowPerformance();
      }
    }, 5000);
  }
  
  handleLowPerformance() {
    // Reduce quality automatically
    const videoTrack = this.stream.getVideoTracks()[0];
    videoTrack.applyConstraints({
      width: { ideal: 320 },
      height: { ideal: 240 },
      frameRate: { ideal: 10 }
    });
  }
}
```

## Testing and Debugging

### Debug Utilities
```javascript
// Log all available devices
async function debugDevices() {
  const devices = await navigator.mediaDevices.enumerateDevices();
  console.table(devices);
}

// Test constraints
async function testConstraints(constraints) {
  try {
    const stream = await navigator.mediaDevices.getUserMedia(constraints);
    const settings = stream.getVideoTracks()[0].getSettings();
    console.log('Applied settings:', settings);
    stream.getTracks().forEach(track => track.stop());
    return true;
  } catch (error) {
    console.error('Constraint test failed:', error);
    return false;
  }
}
```

## Pros and Cons

### Advantages
✅ **Native browser support** - No external dependencies  
✅ **Real-time performance** - Low latency media access  
✅ **Wide compatibility** - Supported across modern browsers  
✅ **Secure by design** - HTTPS requirement ensures security  
✅ **Flexible constraints** - Fine-grained control over media properties  

### Disadvantages
❌ **HTTPS requirement** - Cannot work in insecure contexts  
❌ **Permission dependent** - User must grant camera access  
❌ **Mobile limitations** - Reduced capabilities on mobile devices  
❌ **Browser differences** - Subtle differences in implementation  
❌ **No offline processing** - Requires active stream connection  

## Use Cases for Proctoring

### Core Requirements
- **Continuous monitoring** - Real-time video stream for face detection
- **Device switching** - Allow users to change cameras if needed
- **Quality adaptation** - Adjust stream quality based on network/device
- **Error recovery** - Handle camera disconnections gracefully

### Implementation Recommendations
1. **Start with basic constraints** - Use progressive enhancement
2. **Implement fallbacks** - Handle constraint failures gracefully
3. **Monitor performance** - Track frame rate and adjust accordingly
4. **Respect user privacy** - Clear permission prompts and usage notifications

## Related Documentation
- [TensorFlow.js Face Detection Guide](./7-1-tensorflow-js-guide.md)
- [MediaPipe Integration Guide](./7-1-mediapipe-guide.md)
- [MDN WebRTC Documentation](https://developer.mozilla.org/en-US/docs/Web/API/WebRTC_API)

## Last Updated
2025-01-27 - Initial documentation covering WebRTC getUserMedia API and integration patterns for proctoring applications. 