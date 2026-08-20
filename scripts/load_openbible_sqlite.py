import sqlite3
import os
import sys

# Add project root to sys path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.connection import get_connection

def load_cross_references():
    file_path = os.path.join("data", "openbible", "cross-references", "cross_references.txt")
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    conn = get_connection()
    cursor = conn.cursor()

    # Create table if not exists (in case init_db wasn't run)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cross_references (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            source_verse  TEXT NOT NULL,
            target_verse  TEXT NOT NULL,
            votes         INTEGER DEFAULT 0
        )
    ''')
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cross_ref_source ON cross_references(source_verse)")
    
    # Clear existing data for fresh load
    cursor.execute("DELETE FROM cross_references")

    print(f"Loading {file_path} into SQLite...")
    
    batch = []
    batch_size = 10000
    count = 0
    
    with open(file_path, "r", encoding="utf-8") as f:
        # Skip header if it exists
        first_line = f.readline()
        if not first_line.startswith("From Verse"):
            f.seek(0)
            
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) >= 3:
                source, target = parts[0], parts[1]
                try:
                    votes = int(parts[2])
                except ValueError:
                    votes = 0
                    
                batch.append((source, target, votes))
                
                if len(batch) >= batch_size:
                    cursor.executemany(
                        "INSERT INTO cross_references (source_verse, target_verse, votes) VALUES (?, ?, ?)",
                        batch
                    )
                    batch = []
                    count += batch_size
                    print(f"Loaded {count} rows...")

    if batch:
        cursor.executemany(
            "INSERT INTO cross_references (source_verse, target_verse, votes) VALUES (?, ?, ?)",
            batch
        )
        count += len(batch)

    conn.commit()
    conn.close()
    print(f"Success! Loaded {count} cross references.")

if __name__ == "__main__":
    load_cross_references()
