/**
 * Test script to verify tab switch detection
 * Run this in the browser console when the interview page is loaded
 */

// Simulate tab becoming hidden
function simulateTabSwitch() {
  console.log('🧪 SIMULATING TAB SWITCH...');
  
  // Create a fake visibilitychange event
  const originalHidden = document.hidden;
  
  // Override document.hidden temporarily
  Object.defineProperty(document, 'hidden', {
    value: true,
    configurable: true
  });
  
  // Trigger visibilitychange event
  const event = new Event('visibilitychange');
  document.dispatchEvent(event);
  
  console.log('🧪 Tab hidden event dispatched');
  
  // After 2 seconds, simulate tab becoming visible again
  setTimeout(() => {
    Object.defineProperty(document, 'hidden', {
      value: false,
      configurable: true
    });
    
    const event2 = new Event('visibilitychange');
    document.dispatchEvent(event2);
    
    console.log('🧪 Tab visible event dispatched');
    
    // Restore original hidden state
    setTimeout(() => {
      Object.defineProperty(document, 'hidden', {
        value: originalHidden,
        configurable: true
      });
    }, 100);
  }, 2000);
}

// Export for console use
window.simulateTabSwitch = simulateTabSwitch;

console.log('🧪 Tab switch test loaded. Run simulateTabSwitch() to test tab detection.'); 