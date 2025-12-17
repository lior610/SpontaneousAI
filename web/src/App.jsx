import { useApiTest } from './hooks/useApiTest.js';
import { TestButton } from './components/TestButton.jsx';
import { StatusDisplay } from './components/StatusDisplay.jsx';

function App() {
  const { status, testConnection } = useApiTest();

  return (
    <div style={{ padding: '20px', fontFamily: 'Arial, sans-serif' }}>
      <h1>Spontaneous AI - Connection Test</h1>
      
      <div style={{ display: 'flex', flexDirection: 'column', gap: '15px', marginBottom: '20px' }}>
        <TestButton
          onClick={() => testConnection('/status')}
          label="Test API Service"
          description="Tests if the API service is running and responding"
        />
        
        <TestButton
          onClick={() => testConnection('/engine/status')}
          label="Test Engine Service"
          description="Tests if the Engine service is running and responding"
        />
        
        <TestButton
          onClick={() => testConnection('/engine/health')}
          label="Test Engine DB Connection"
          description="Tests Engine → Database connection"
        />
        
        <TestButton
          onClick={() => testConnection('/health')}
          label="Test Full System Health"
          description="Tests API → Database connection and API → Engine connection (complete system check)"
        />
      </div>

      <StatusDisplay status={status} />
    </div>
  );
}

export default App;
