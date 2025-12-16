import express from 'express';
import pg from 'pg';
import axios from 'axios';

const app = express();
app.use(express.json());

const { Pool } = pg;
const pool = new Pool({
  host: process.env.DB_HOST || 'db',
  port: process.env.DB_PORT || 5432,
  database: process.env.DB_NAME || 'postgres',
  user: process.env.DB_USER || 'postgres',
  password: process.env.DB_PASSWORD || 'postgres',
});

const ENGINE_URL = `http://${process.env.ENGINE_HOST || 'engine'}:${process.env.ENGINE_PORT || '8000'}`;

app.get('/', (req, res) => {
  res.json({ service: 'api', status: 'running' });
});

app.get('/health', async (req, res) => {
  try {
    // Test DB connection
    const dbResult = await pool.query('SELECT NOW()');
    
    // Test Engine connection
    const engineResponse = await axios.get(`${ENGINE_URL}/health`);
    
    res.json({
      status: 'healthy',
      db: 'connected',
      engine: engineResponse.data
    });
  } catch (error) {
    res.status(500).json({
      status: 'unhealthy',
      error: error.message
    });
  }
});

app.get('/test-db', async (req, res) => {
  try {
    const result = await pool.query('SELECT version()');
    res.json({ status: 'success', db_version: result.rows[0].version });
  } catch (error) {
    res.status(500).json({ status: 'error', message: error.message });
  }
});

app.get('/test-engine', async (req, res) => {
  try {
    const response = await axios.get(`${ENGINE_URL}/test-db`);
    res.json({ status: 'success', engine_response: response.data });
  } catch (error) {
    res.status(500).json({ status: 'error', message: error.message });
  }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, '0.0.0.0', () => {
  console.log(`API server running on port ${PORT}`);
});

