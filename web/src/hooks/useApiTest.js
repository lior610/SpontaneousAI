import { useState } from 'react';
import { testConnection as testEndpointConnection } from '../services/api.js';

export const useApiTest = () => {
  const [status, setStatus] = useState(null);

  const testConnection = async (endpoint) => {
    const result = await testEndpointConnection(endpoint);
    setStatus(result);
  };

  return {
    status,
    testConnection
  };
};

