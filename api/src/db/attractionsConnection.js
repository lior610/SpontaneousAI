import pg from 'pg';

const { Pool } = pg;


const defaultUser = process.env.POSTGRES_USER || process.env.USER || 'postgres';
const defaultPassword = process.env.POSTGRES_PASSWORD !== undefined ? process.env.POSTGRES_PASSWORD : '';

const pool = new Pool({
  host: process.env.POSTGRES_HOST || 'localhost',
  port: parseInt(process.env.POSTGRES_PORT || '5432', 10),
  database: process.env.POSTGRES_ATTRACTIONS_DB || 'attractions',
  user: defaultUser,
  password: defaultPassword,
  max: 20,
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 2000,
});

export async function testConnection() {
  try {
    const result = await pool.query('SELECT NOW()');
    return { success: true, timestamp: result.rows[0].now };
  } catch (error) {
    return { success: false, error: error.message };
  }
}

export async function closePool() {
  await pool.end();
}

export { pool };
export default pool;

