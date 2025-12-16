import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:3000';

export const testConnection = async (endpoint) => {
  try {
    const response = await axios.get(`${API_URL}${endpoint}`);
    return { success: true, data: response.data };
  } catch (error) {
    return {
      success: false,
      error: error.message,
      details: error.response ? error.response.data : 'No response from server'
    };
  }
};
