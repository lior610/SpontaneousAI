"""
PostgreSQL connection module for Attractions database.
Contains vectors, embeddings, and attractions data.
"""
import psycopg2
import psycopg2.pool
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, Generator

try:
    from dotenv import load_dotenv
    _env_file = Path(__file__).resolve().parents[3] / ".env"
    if _env_file.exists():
        load_dotenv(_env_file, override=True)
except ImportError:
    pass

# Connection pool configuration
_pool: Optional[psycopg2.pool.ThreadedConnectionPool] = None

def get_db_config():
        return {
        'host': os.getenv('POSTGRES_HOST', 'db'),  # Docker service name
        'port': int(os.getenv('POSTGRES_PORT', '5432')),
        'database': os.getenv('POSTGRES_ATTRACTIONS_DB', 'attractions'),
        'user': os.getenv('POSTGRES_USER', 'postgres'),
        'password': os.getenv('POSTGRES_PASSWORD', 'postgres'),
    }

def init_pool(minconn: int = 1, maxconn: int = 20):
    """Initialize the connection pool."""
    global _pool
    if _pool is None:
        config = get_db_config()
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=minconn,
            maxconn=maxconn,
            **config
        )
    return _pool

def get_connection():
    """Get a connection from the pool (creates pool if needed)."""
    pool = init_pool()
    return pool.getconn()

def return_connection(conn):
    """Return a connection to the pool."""
    if _pool:
        _pool.putconn(conn)

@contextmanager
def get_db_connection() -> Generator[psycopg2.extensions.connection, None, None]:
    """
    Context manager for database connections.
    Automatically handles connection acquisition and return.
    
    Usage:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM attractions")
            result = cursor.fetchall()
    """
    conn = None
    try:
        conn = get_connection()
        yield conn
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            return_connection(conn)

def test_connection() -> dict:
    """
    Test database connection.
    
    Returns:
        dict: Connection test result with 'success' and either 'timestamp' or 'error'
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT NOW()')
            timestamp = cursor.fetchone()[0]
            return {'success': True, 'timestamp': str(timestamp)}
    except Exception as e:
        return {'success': False, 'error': str(e)}

def close_pool():
    """Close all connections in the pool."""
    global _pool
    if _pool:
        _pool.closeall()
        _pool = None

