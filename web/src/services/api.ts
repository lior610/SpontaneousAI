import axios from 'axios';
import type { components } from '../types/api';

const API_URL = (import.meta as any).env?.VITE_API_URL || 'http://localhost:3000';
const ENGINE_URL = (import.meta as any).env?.VITE_ENGINE_URL || 'http://localhost:8000';

export const testConnection = async (endpoint: string) => {
  try {
    const response = await axios.get(`${API_URL}${endpoint}`);
    return { success: true, data: response.data };
  } catch (error: any) {
    return {
      success: false,
      error: error.message,
      details: error.response ? error.response.data : 'No response from server'
    };
  }
};

// EXAMPLE: Get recommendations from Engine (via API)
export const getRecommendation = async (query: string): Promise<components['schemas']['AttractionResponse'][]> => {
  const response = await axios.get(`${ENGINE_URL}/attractions/search/${encodeURIComponent(query)}`);
  return response.data.results || [];
};
