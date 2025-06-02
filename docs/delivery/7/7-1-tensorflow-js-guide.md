# TensorFlow.js Face Detection Guide

**Task ID**: 7-1  
**Date**: 2025-01-27  
**Documentation for**: Frontend face detection using TensorFlow.js

## Overview

TensorFlow.js is a powerful JavaScript library that enables machine learning in the browser. For face detection, it provides pre-trained models that can detect faces in real-time with good performance characteristics.

## Key Features

- **Browser-native execution** - No server-side processing required
- **Real-time performance** - Optimized for low-latency detection
- **Multiple model options** - BlazeFace and MediaPipe face detection models
- **Cross-platform** - Works on desktop and mobile browsers
- **Well-documented** - Extensive documentation and community support

## Installation

### NPM Installation
```bash
npm install @tensorflow/tfjs @tensorflow-models/face-detection
```

### CDN Installation
```html
<script src="https://cdn.jsdelivr.net/npm/@tensorflow/tfjs"></script>
<script src="https://cdn.jsdelivr.net/npm/@tensorflow-models/face-detection"></script>
```

## Available Models

### 1. BlazeFace (Short-range)
- **Best for**: Selfie-like images, webcam feeds
- **Input size**: 128x128 pixels
- **Performance**: ~3ms on Pixel 6 CPU
- **Accuracy**: Good for front-facing scenarios
- **Bundle size**: Relatively small

### 2. MediaPipe Face Detector
- **Best for**: More robust detection across various conditions
- **Input size**: Configurable
- **Performance**: Slightly slower but more accurate
- **Features**: 6 facial keypoints included
- **Bundle size**: Larger than BlazeFace

## Basic Implementation

### Model Initialization
```javascript
import * as faceDetection from '@tensorflow-models/face-detection';

// Initialize the BlazeFace model
const model = faceDetection.SupportedModels.MediaPipeFaceDetector;
const detectorConfig = {
  runtime: 'tfjs', // or 'mediapipe'
  maxFaces: 5,
  refineLandmarks: true,
  minDetectionConfidence: 0.5,
  minSuppressionThreshold: 0.3
};

const detector = await faceDetection.createDetector(model, detectorConfig);
```

### Face Detection
```javascript
// Detect faces in an image or video element
async function detectFaces(imageElement) {
  const faces = await detector.estimateFaces(imageElement);
  return faces;
}

// Example usage with video element
const video = document.getElementById('videoElement');
const faces = await detectFaces(video);

// Process results
faces.forEach(face => {
  const { box, keypoints } = face;
  console.log('Face bounding box:', box);
  console.log('Facial keypoints:', keypoints);
});
```

### Real-time Detection Loop
```javascript
async function detectRealTime() {
  const video = document.getElementById('video');
  
  async function detect() {
    if (video.readyState === 4) { // HAVE_ENOUGH_DATA
      const faces = await detector.estimateFaces(video);
      
      // Process faces
      faces.forEach(face => {
        drawBoundingBox(face.box);
        drawKeypoints(face.keypoints);
      });
    }
    
    requestAnimationFrame(detect);
  }
  
  detect();
}
```

## Configuration Options

### Detection Parameters
```javascript
const detectorConfig = {
  runtime: 'tfjs', // 'tfjs' or 'mediapipe'
  maxFaces: 10, // Maximum number of faces to detect
  refineLandmarks: true, // Enable landmark refinement
  minDetectionConfidence: 0.5, // Minimum confidence for detection
  minSuppressionThreshold: 0.3 // Non-maximum suppression threshold
};
```

### Performance Optimization
```javascript
// For better performance, reduce input resolution
const canvas = document.createElement('canvas');
const ctx = canvas.getContext('2d');

function resizeForDetection(video, targetWidth = 320) {
  const aspectRatio = video.videoHeight / video.videoWidth;
  canvas.width = targetWidth;
  canvas.height = targetWidth * aspectRatio;
  
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
  return canvas;
}

// Use resized canvas for detection
const resizedCanvas = resizeForDetection(video);
const faces = await detector.estimateFaces(resizedCanvas);
```

## Output Format

### Face Detection Result
```javascript
{
  box: {
    xMin: 126,
    xMax: 502,
    yMin: 102,
    yMax: 349,
    width: 376,
    height: 247
  },
  keypoints: [
    { x: 446, y: 256, name: "rightEye" },
    { x: 406, y: 255, name: "leftEye" },
    { x: 425, y: 280, name: "noseTip" },
    { x: 420, y: 310, name: "mouthCenter" },
    { x: 460, y: 265, name: "rightEarTragion" },
    { x: 390, y: 270, name: "leftEarTragion" }
  ]
}
```

## Browser Compatibility

### Supported Browsers
- **Chrome**: 58+ (recommended 80+)
- **Firefox**: 57+ (limited features)
- **Safari**: 11+ (with limitations)
- **Edge**: 79+ (Chromium-based)

### Mobile Support
- **Android Chrome**: 80+
- **iOS Safari**: 11+ (limited performance)
- **Samsung Internet**: 12+

## Performance Characteristics

### Latency Benchmarks
- **Desktop Chrome**: 20-50ms per frame
- **Mobile Chrome**: 50-150ms per frame
- **Desktop Firefox**: 30-80ms per frame

### Memory Usage
- **Model loading**: ~5-15MB
- **Runtime memory**: ~50-100MB additional

## Integration Patterns

### With WebRTC
```javascript
// Get video stream
const stream = await navigator.mediaDevices.getUserMedia({ video: true });
const video = document.getElementById('video');
video.srcObject = stream;

// Start detection when video is ready
video.addEventListener('loadedmetadata', () => {
  detectRealTime();
});
```

### Error Handling
```javascript
try {
  const detector = await faceDetection.createDetector(model, detectorConfig);
  const faces = await detector.estimateFaces(video);
} catch (error) {
  console.error('Face detection error:', error);
  
  if (error.name === 'NotSupportedError') {
    // Browser doesn't support required features
    fallbackToSimpleDetection();
  } else if (error.name === 'NetworkError') {
    // Model loading failed
    retryModelLoading();
  }
}
```

## Pros and Cons

### Advantages
✅ **No server dependency** - Runs entirely in browser  
✅ **Good performance** - Optimized for real-time use  
✅ **Active community** - Well-maintained with regular updates  
✅ **Multiple runtimes** - Can use TensorFlow.js or MediaPipe backend  
✅ **Comprehensive API** - Rich feature set and configuration options  

### Disadvantages
❌ **Bundle size** - Adds significant weight to application  
❌ **Browser variance** - Performance differs across browsers  
❌ **Limited accuracy** - Not as accurate as server-side solutions  
❌ **Resource intensive** - Can impact battery life on mobile  
❌ **Firefox limitations** - Reduced feature set in Firefox  

## Use Cases for Proctoring

### Recommended Scenarios
- **Real-time monitoring** - Continuous face tracking during interviews
- **Gaze detection** - Monitor if candidate is looking at screen
- **Presence verification** - Ensure candidate remains in frame
- **Multiple face detection** - Identify if multiple people are present

### Implementation Tips
1. **Throttle detection** - Run at 2-5 FPS to balance performance
2. **Use smaller input** - Resize video for faster processing
3. **Implement fallbacks** - Graceful degradation for unsupported browsers
4. **Monitor performance** - Track FPS and adjust accordingly

## Related Documentation
- [Official TensorFlow.js Face Detection](https://github.com/tensorflow/tfjs-models/tree/master/face-detection)
- [MediaPipe Face Detection](https://ai.google.dev/edge/mediapipe/solutions/vision/face_detector)
- [WebRTC getUserMedia Guide](./7-1-webrtc-guide.md)

## Last Updated
2025-01-27 - Initial documentation based on latest TensorFlow.js models and MediaPipe integration. 