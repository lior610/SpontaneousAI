import pg from 'pg';

const { Pool } = pg;

const defaultUser = process.env.POSTGRES_USER || process.env.USER || 'postgres';
const defaultPassword = process.env.POSTGRES_PASSWORD !== undefined ? process.env.POSTGRES_PASSWORD : '';

const pool = new Pool({
  host: process.env.POSTGRES_HOST || 'localhost',
  port: parseInt(process.env.POSTGRES_PORT || '5432', 10),
  database: process.env.POSTGRES_DB || 'postgres',
  user: defaultUser,
  password: defaultPassword,
  max: 20, // Maximum number of clients in the pool
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 2000,
});

/**
 * Test database connection
 * @returns {Promise<Object>} Connection test result
 */
export async function testConnection() {
  try {
    const result = await pool.query('SELECT NOW()');
    return { success: true, timestamp: result.rows[0].now };
  } catch (error) {
    return { success: false, error: error.message };
  }
}

/**
 * Close all connections in the pool
 */
export async function closePool() {
  await pool.end();
}

// Export the pool for advanced usage
export { pool };

// Default export
export default pool;

