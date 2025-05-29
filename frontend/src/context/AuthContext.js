import React, { createContext, useState, useEffect, useContext } from 'react';
// Potentially an API call to verify token or get user profile might be needed here in a real app
// import { getUserProfile } from '../api/userApi'; // Example if you have a /users/me endpoint that needs a token

const AuthContext = createContext(null);

// Helper function to decode JWT (basic, without signature verification)
// In a real app, you might not decode the token on the client for sensitive data,
// but for user_id or username for display, it can be okay.
const decodeJwt = (token) => {
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map(function (c) {
          return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
        })
        .join('')
    );
    return JSON.parse(jsonPayload);
  } catch (e) {
    console.error("Failed to decode JWT:", e);
    return null;
  }
};

export const AuthProvider = ({ children }) => {
  const [token, setToken] = useState(localStorage.getItem('authToken'));
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const attemptAutoLogin = async () => {
      const storedToken = localStorage.getItem('authToken');
      if (storedToken) {
        setToken(storedToken);
        const decodedPayload = decodeJwt(storedToken);
        if (decodedPayload) {
          // Use userId from token if available, or sub (subject), or default
          setUser({ 
            id: decodedPayload.user_id || decodedPayload.sub, 
            email: decodedPayload.email, // if email is in token
            // username: decodedPayload.username // if username is in token
          });
        } else {
          // Invalid token, clear it
          localStorage.removeItem('authToken');
          setToken(null);
          setUser(null);
        }
      } else {
        setUser(null); // Ensure user is null if no token
      }
      setIsLoading(false);
    };
    attemptAutoLogin();
  }, []);

  const login = (newToken, // userData can be passed from login page if available, or fetch after login
                 initialUserData = null ) => {
    localStorage.setItem('authToken', newToken);
    setToken(newToken);
    const decodedPayload = decodeJwt(newToken);
    if (decodedPayload) {
      setUser({ 
        id: decodedPayload.user_id || decodedPayload.sub, 
        email: decodedPayload.email || initialUserData?.email,
        // username: decodedPayload.username
      });
    } else if (initialUserData) {
      setUser(initialUserData); // Fallback to data passed from login page if token decoding fails
    } else {
      setUser(null); // Or a generic user object
    }
  };

  const logout = () => {
    localStorage.removeItem('authToken');
    setToken(null);
    setUser(null);
    // Optionally, navigate to login page or home page
    // This can be done in the component calling logout or here if preferred
  };

  return (
    <AuthContext.Provider value={{ token, user, login, logout, isLoading }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined && process.env.NODE_ENV !== 'test') { // Added test env check
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}; 