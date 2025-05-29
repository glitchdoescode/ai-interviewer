import React from 'react';
import { Routes, Route } from 'react-router-dom';
import { ChakraProvider, extendTheme } from '@chakra-ui/react';

// Import pages
import Home from './pages/Home';
import Interview from './pages/Interview';
import SessionHistory from './pages/SessionHistory';
import MicrophoneTest from './pages/MicrophoneTest';
import LoginPage from './pages/LoginPage';
import SignupPage from './pages/SignupPage';

// Import context providers
import { InterviewProvider } from './context/InterviewContext';
import { AuthProvider } from './context/AuthContext';

// Import ProtectedRoute component
import ProtectedRoute from './components/ProtectedRoute';

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
      <AuthProvider>
        <InterviewProvider>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route 
              path="/interview" 
              element={
                <ProtectedRoute>
                  <Interview />
                </ProtectedRoute>
              }
            />
            <Route 
              path="/interview/:sessionId" 
              element={
                <ProtectedRoute>
                  <Interview />
                </ProtectedRoute>
              }
            />
            <Route 
              path="/history" 
              element={
                <ProtectedRoute>
                  <SessionHistory />
                </ProtectedRoute>
              }
            />
            <Route path="/microphone-test" element={<MicrophoneTest />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/signup" element={<SignupPage />} />
          </Routes>
        </InterviewProvider>
      </AuthProvider>
    </ChakraProvider>
  );
}

export default App; 