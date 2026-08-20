import os
import pytest
import sqlite3
from database import connection

TEST_DB_PATH = 'test_biblico.db'

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Setup a temporary database for testing and patch the connection path."""
    # Ensure starting clean
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
        
    # Patch the DB_PATH in the connection module
    original_db_path = connection.DB_PATH
    connection.DB_PATH = TEST_DB_PATH
    
    # Initialize the schema
    connection.init_db()
    
    yield
    
    # Teardown
    connection.DB_PATH = original_db_path
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except PermissionError:
            pass # File might be locked by lingering connections, fine for tests

@pytest.fixture(autouse=True)
def clear_db_tables():
    """Clear all data from tables before each test to ensure isolation."""
    conn = connection.get_connection()
    cursor = conn.cursor()
    
    # List of tables to clear
    tables = [
        'feedback', 
        'journal_entries', 'habits', 'users',
        'cache_audit', 'resources'
    ]
    
    for table in tables:
        cursor.execute(f"DELETE FROM {table}")
        
    conn.commit()
    conn.close()
