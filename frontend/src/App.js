import React from 'react';
import { Routes, Route } from 'react-router-dom';
import { ChakraProvider, extendTheme, Text } from '@chakra-ui/react';

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
      50: '#F0F4F8', // Lightest Gray
      100: '#D9E2EC', // Lighter Gray
      200: '#BCCCDC', // Light Gray
      300: '#9FB6CD', // Gray
      400: '#829AB0', // Medium Gray
      500: '#657E94', // Dark Gray
      600: '#4F6378', // Darker Gray
      700: '#3A4B5C', // Even Darker Gray
      800: '#2C3A47', // Darkest Gray
      900: '#1A222B', // Almost Black
    },
    primary: {
      50: '#E3F2FD',
      100: '#BBDEFB',
      200: '#90CAF9',
      300: '#64B5F6',
      400: '#42A5F5',
      500: '#2196F3', // Professional Blue
      600: '#1E88E5',
      700: '#1976D2',
      800: '#1565C0',
      900: '#0D47A1',
    },
    secondary: {
      50: '#E0F7FA',
      100: '#B2EBF2',
      200: '#80DEEA',
      300: '#4DD0E1',
      400: '#26C6DA',
      500: '#00BCD4', // Professional Teal
      600: '#00ACC1',
      700: '#0097A7',
      800: '#00838F',
      900: '#006064',
    },
    success: {
      500: '#4CAF50', // Green
    },
    error: {
      500: '#F44336', // Red
    },
    warning: {
      500: '#FF9800', // Orange
    },
  },
  fonts: {
    heading: `'Roboto Slab', serif`,
    body: `'Open Sans', sans-serif`,
  },
  components: {
    Button: {
      baseStyle: {
        fontWeight: 'bold',
        borderRadius: 'md',
      },
      variants: {
        solid: (props) => ({
          bg: `${props.colorScheme}.500`,
          color: 'white',
          _hover: {
            bg: `${props.colorScheme}.600`,
          },
          _active: {
            bg: `${props.colorScheme}.700`,
          },
        }),
      },
      defaultProps: {
        colorScheme: 'primary',
      },
    },
    Input: {
      defaultProps: {
        focusBorderColor: 'primary.500',
      },
    },
    Textarea: {
      defaultProps: {
        focusBorderColor: 'primary.500',
      },
    },
    Select: {
      defaultProps: {
        focusBorderColor: 'primary.500',
      },
    }
  },
  styles: {
    global: {
      body: {
        bg: 'brand.50',
        color: 'brand.900',
        lineHeight: 'tall',
      },
      a: {
        color: 'primary.500',
        _hover: {
          textDecoration: 'underline',
        },
      },
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