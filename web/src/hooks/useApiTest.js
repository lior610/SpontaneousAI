import { useState } from 'react';
import { testAPIConnection, testEngineConnection } from '../services/api.js';

export const useApiTest = () => {
  const [status, setStatus] = useState(null);

  const testAPI = async (endpoint) => {
    const result = await testAPIConnection(endpoint);
    setStatus(result);
  };

  const testEngine = async (endpoint) => {
    const result = await testEngineConnection(endpoint);
    setStatus(result);
  };

  return {
    status,
    testAPI,
    testEngine
  };
};

