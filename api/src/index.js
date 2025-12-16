import express from 'express';
import axios from 'axios';
import cors from 'cors';
import { testConnection } from './db/connection.js';
import routes from './routes/index.js';

const app = express();
app.use(cors());
app.use(express.json());

// Mount API routes
app.use('/api', routes);

const ENGINE_URL = `http://${process.env.ENGINE_HOST || 'engine'}:${process.env.ENGINE_PORT || '8000'}`;

app.get('/status', (req, res) => {
  res.json({ service: 'api', status: 'running' });
});

app.get('/engine/status', async (req, res) => {
  try {
    const engineResponse = await axios.get(`${ENGINE_URL}/status`);
    res.json(engineResponse.data);
  } catch (error) {
    res.status(500).json({
      error: error.message
    });
  }
});

app.get('/engine/health', async (req, res) => {
  try {
    const engineResponse = await axios.get(`${ENGINE_URL}/health`);
    res.json(engineResponse.data);
  } catch (error) {
    res.status(500).json({
      error: error.message,
      details: error.response ? error.response.data : 'No response from engine'
    });
  }
});

app.get('/health', async (req, res) => {
  try {
    // Test DB host connection (using default postgres database)
    const dbTest = await testConnection();
    
    // Test Engine service is running
    const engineStatusResponse = await axios.get(`${ENGINE_URL}/status`);
    
    // Test Engine database connection
    const engineHealthResponse = await axios.get(`${ENGINE_URL}/health`);
    
    res.json({
      status: 'healthy',
      db_host: dbTest.success ? 'connected' : 'disconnected',
      engine: {
        service: engineStatusResponse.data,
        db_connection: engineHealthResponse.data
      }
    });
  } catch (error) {
    res.status(500).json({
      status: 'unhealthy',
      error: error.message
    });
  }
});


const PORT = process.env.PORT || 3000;
app.listen(PORT, '0.0.0.0', () => {
  console.log(`API server running on port ${PORT}`);
});

