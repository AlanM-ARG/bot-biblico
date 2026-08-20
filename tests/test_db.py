import os
import pytest
from database.connection import get_connection, init_db

# Use an in-memory DB or temporary file for tests if needed, 
# but for now we just verify we can import and run the init.

def test_db_connection():
    conn = get_connection()
    assert conn is not None
    conn.close()

def test_init_db():
    try:
        init_db()
        success = True
    except Exception:
        success = False
    assert success
