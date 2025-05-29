import axios from 'axios';

const API_BASE_URL = '/api/v1/auth'; // Adjusted to match backend auth routes

// Create a separate axios instance for auth if needed, or use a global one
// For simplicity, we'll use a new one here or assume a global one if 'api' from interviewService was exported and configured
// If interviewService.js exports its 'api' instance, we could import and use that too.
// For now, creating a specific one for auth.

const authApi = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000, // 10 seconds timeout for auth requests
});

/**
 * Logs in a user.
 * @param {string} email - User's email (which backend's /token endpoint expects as 'username').
 * @param {string} password - User's password.
 * @returns {Promise<Object>} Promise with backend response (e.g., { access_token, token_type }).
 */
export const loginUser = async (email, password) => {
  const params = new URLSearchParams();
  params.append('username', email); // FastAPI's OAuth2PasswordRequestForm expects 'username'
  params.append('password', password);

  try {
    const response = await authApi.post('/token', params, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    });
    // Log the successful login response for debugging
    console.log("Login successful, token data:", response.data); 
    return response.data; // Should contain access_token
  } catch (error) {
    console.error(
      'Login API error:', 
      error.response ? { status: error.response.status, data: error.response.data } : error.message
    );
    // Throw a more specific error message for the UI
    const errorDetail = error.response?.data?.detail || 'Login failed. Please check your credentials or network.';
    throw new Error(errorDetail);
  }
};

/**
 * Registers a new user.
 * @param {string} email - User's email.
 * @param {string} password - User's password.
 * @param {string} [fullName] - User's full name.
 * @param {string[]} [roles=['candidate']] - User's roles.
 * @returns {Promise<Object>} Promise with backend response (e.g., user details).
 */
export const signupUser = async (email, password, fullName, roles = ['candidate']) => {
  try {
    const response = await authApi.post('/register', {
      email,
      password,
      full_name: fullName, // Send fullName as full_name to match backend schema
      roles, 
      is_active: true, 
    }, {
      headers: {
        'Content-Type': 'application/json',
      },
    });
    console.log("Signup successful:", response.data);
    return response.data; // Should contain user details
  } catch (error) {
    console.error(
      'Signup API error:',
      error.response ? { status: error.response.status, data: error.response.data } : error.message
    );
    const errorDetail = error.response?.data?.detail || 'Signup failed. Please try again.';
    throw new Error(errorDetail);
  }
};

// Add other auth-related API calls here if needed (e.g., refreshToken, forgotPassword, etc.) 