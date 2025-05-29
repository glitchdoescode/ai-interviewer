import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Spinner, Flex } from '@chakra-ui/react'; // For loading indicator

const ProtectedRoute = ({ children }) => {
  const { token, isLoading, user } = useAuth(); // Get user as well for a more robust check
  const location = useLocation();

  if (isLoading) {
    // Show a loading spinner or some placeholder while checking auth state
    return (
      <Flex justify="center" align="center" height="100vh">
        <Spinner size="xl" />
      </Flex>
    );
  }

  // If not loading and there's no token (or user), redirect to login
  // We check for token, but user check is also good practice if token might exist but user data failed to load
  if (!token || !user) { 
    // Pass the current location to redirect back after login
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // If authenticated, render the child components
  return children;
};

export default ProtectedRoute; 