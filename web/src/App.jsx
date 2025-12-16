import { useState } from 'react';
import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:3000';

function App() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);

  const testConnection = async (endpoint) => {
    setLoading(true);
    try {
      const response = await axios.get(`${API_URL}${endpoint}`);
      setStatus({ success: true, data: response.data });
    } catch (error) {
      setStatus({ success: false, error: error.message });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: '20px', fontFamily: 'Arial, sans-serif' }}>
      <h1>Spontaneous AI - Connection Test</h1>
      
      <div style={{ display: 'flex', gap: '10px', marginBottom: '20px' }}>
        <button onClick={() => testConnection('/')} disabled={loading}>
          Test API
        </button>
        <button onClick={() => testConnection('/health')} disabled={loading}>
          Test Health (API + DB + Engine)
        </button>
        <button onClick={() => testConnection('/test-db')} disabled={loading}>
          Test DB Connection
        </button>
        <button onClick={() => testConnection('/test-engine')} disabled={loading}>
          Test Engine Connection
        </button>
      </div>

      {loading && <p>Loading...</p>}
      
      {status && (
        <div style={{ 
          padding: '15px', 
          backgroundColor: status.success ? '#d4edda' : '#f8d7da',
          border: `1px solid ${status.success ? '#c3e6cb' : '#f5c6cb'}`,
          borderRadius: '5px',
          marginTop: '20px'
        }}>
          <h3>{status.success ? 'Success' : 'Error'}</h3>
          <pre style={{ whiteSpace: 'pre-wrap' }}>
            {JSON.stringify(status.data || status.error, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}

export default App;

