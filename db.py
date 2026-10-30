# utils/db.py - Database connection manager

import mysql.connector
from mysql.connector import pooling, Error
from flask import current_app, g
import logging

logger = logging.getLogger(__name__)

# Connection pool for reuse across requests
_pool = None

def init_pool(app):
    """Initialize MySQL connection pool on app startup."""
    global _pool
    try:
        _pool = pooling.MySQLConnectionPool(
            pool_name="med_pool",
            pool_size=5,
            host=app.config['DB_HOST'],
            port=app.config['DB_PORT'],
            user=app.config['DB_USER'],
            password=app.config['DB_PASSWORD'],
            database=app.config['DB_NAME'],
            autocommit=False,
            charset='utf8mb4'
        )
        logger.info("Database connection pool initialized successfully.")
    except Error as e:
        # give more helpful advice when the database does not exist
        if hasattr(e, 'errno') and e.errno == 1049:
            logger.error(
                "Database '%s' not found. "
                "Have you run database.sql or set DB_NAME correctly?",
                app.config['DB_NAME']
            )
        else:
            logger.error(f"Failed to initialize DB pool: {e}")
        raise

def get_db():
    """
    Get a database connection scoped to the current Flask request.
    Stores connection in Flask's 'g' object so same connection is reused
    within one request and properly closed at the end.
    """
    if 'db' not in g:
        try:
            g.db = _pool.get_connection()
        except Error as e:
            logger.error(f"Failed to get DB connection: {e}")
            raise
    return g.db

def close_db(e=None):
    """Release DB connection back to pool at end of request."""
    db = g.pop('db', None)
    if db is not None and db.is_connected():
        db.close()

def query(sql, params=None, fetch='all', commit=False):
    """
    Central query helper — parameterized to prevent SQL injection.

    Args:
        sql     : SQL string with %s placeholders
        params  : Tuple/list of values for placeholders
        fetch   : 'all' | 'one' | None (for INSERT/UPDATE/DELETE)
        commit  : Whether to commit the transaction

    Returns:
        list of dicts | dict | lastrowid | rowcount
    """
    conn = get_db()
    cursor = conn.cursor(dictionary=True)  # Returns rows as dicts
    try:
        cursor.execute(sql, params or ())
        if fetch == 'all':
            result = cursor.fetchall()
        elif fetch == 'one':
            result = cursor.fetchone()
        else:
            result = None

        if commit:
            conn.commit()
            # Return lastrowid for INSERT, rowcount for UPDATE/DELETE
            return cursor.lastrowid if cursor.lastrowid else cursor.rowcount

        return result
    except Error as e:
        conn.rollback()
        logger.error(f"Query error: {e}\nSQL: {sql}\nParams: {params}")
        raise
    finally:
        cursor.close()
