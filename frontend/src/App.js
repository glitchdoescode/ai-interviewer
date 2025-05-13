import React from 'react';
import { Routes, Route } from 'react-router-dom';
import { ChakraProvider, extendTheme } from '@chakra-ui/react';

// Import pages
import Home from './pages/Home';
import Interview from './pages/Interview';
import SessionHistory from './pages/SessionHistory';
import MicrophoneTest from './pages/MicrophoneTest';

// Import context providers
import { InterviewProvider } from './context/InterviewContext';

// Define custom theme
const theme = extendTheme({
  colors: {
    brand: {
      50: '#e6f7ff',
      100: '#b3e0ff',
      200: '#80caff',
      300: '#4db3ff',
      400: '#1a9dff',
      500: '#0086e6',
      600: '#0069b3',
      700: '#004d80',
      800: '#00304d',
      900: '#00141f',
    },
  },
});

function App() {
  return (
    <ChakraProvider theme={theme}>
      <InterviewProvider>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/interview" element={<Interview />} />
          <Route path="/interview/:sessionId" element={<Interview />} />
          <Route path="/history" element={<SessionHistory />} />
          <Route path="/microphone-test" element={<MicrophoneTest />} />
        </Routes>
      </InterviewProvider>
    </ChakraProvider>
  );
}

export default App; 