/**
 * Service for fetching system configuration from the backend.
 */

const API_BASE_URL = process.env.REACT_APP_API_URL || '';

/**
 * Fetch system configuration from the backend.
 * @returns {Promise<Object>} Configuration object containing system_name, version, and features
 * @throws {Error} If the API request fails
 */
export const fetchSystemConfig = async () => {
    try {
        const response = await fetch(`${API_BASE_URL}/api/system-config`);
        if (!response.ok) {
            throw new Error(`Failed to fetch system config: ${response.statusText}`);
        }
        return await response.json();
    } catch (error) {
        console.error('Error fetching system config:', error);
        throw error;
    }
};

export default {
    fetchSystemConfig,
}; 