import sqlite3

def check_db():
    conn = sqlite3.connect("biblico.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print("Tables:", tables)
    for t in tables:
        cursor.execute(f"PRAGMA table_info({t[0]});")
        print(f"Table {t[0]} columns:", cursor.fetchall())
    conn.close()

if __name__ == "__main__":
    check_db()
