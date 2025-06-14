import React from 'react';
import { Routes, Route } from 'react-router-dom';
import { ChakraProvider } from '@chakra-ui/react';

// Import the new professional theme
import theme from './theme';

// Import design system styles
import './styles/designSystem.css';

// Import pages
import Home from './pages/Home';
import Interview from './pages/Interview';
import SessionHistory from './pages/SessionHistory';
import MicrophoneTest from './pages/MicrophoneTest';
import FaceAuthTest from './components/FaceAuthTest';
import LoginPage from './pages/LoginPage';
import SignupPage from './pages/SignupPage';
import ReportPage from './pages/ReportPage';

// Import context providers
import { InterviewProvider } from './context/InterviewContext';
import { AuthProvider } from './context/AuthContext';

// Import ProtectedRoute component
import ProtectedRoute from './components/ProtectedRoute';

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
            <Route 
              path="/report/:sessionId" 
              element={
                <ProtectedRoute>
                  <ReportPage />
                </ProtectedRoute>
              }
            />
            <Route path="/microphone-test" element={<MicrophoneTest />} />
            <Route path="/face-auth-test" element={<FaceAuthTest />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/signup" element={<SignupPage />} />
          </Routes>
        </InterviewProvider>
      </AuthProvider>
    </ChakraProvider>
  );
}

export default App; 