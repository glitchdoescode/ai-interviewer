const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000'; // Adjust if your backend runs elsewhere

/**
 * Calls the backend API to log in a user.
 * @param {string} username - The user's email (as username for the backend).
 * @param {string} password - The user's password.
 * @returns {Promise<object>} The response data from the API (e.g., { access_token, token_type }).
 * @throws {Error} If the API request fails.
 */
export const loginUser = async (username, password) => {
  const formData = new URLSearchParams();
  formData.append('username', username); // Backend expects 'username' for OAuth2PasswordRequestForm
  formData.append('password', password);

  const response = await fetch(`${API_BASE_URL}/api/v1/auth/token`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: formData.toString(),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: 'Login failed' }));
    throw new Error(errorData.detail || 'Failed to log in');
  }
  return response.json();
};

/**
 * Calls the backend API to sign up a new user.
 * @param {object} userData - User data for registration.
 * @param {string} userData.username
 * @param {string} userData.email
 * @param {string} [userData.fullName] - Optional full name.
 * @param {string} userData.password
 * @returns {Promise<object>} The response data from the API (the created user details).
 * @throws {Error} If the API request fails.
 */
export const signupUser = async (userData) => {
  const response = await fetch(`${API_BASE_URL}/api/v1/auth/signup`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      username: userData.username,
      email: userData.email,
      full_name: userData.fullName, // Match Pydantic model field name in backend
      password: userData.password,
    }),
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ detail: 'Signup failed' }));
    throw new Error(errorData.detail || 'Failed to sign up');
  }
  return response.json();
}; 