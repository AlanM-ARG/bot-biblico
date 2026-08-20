from database.connection import get_connection
from models.journal import JournalEntry
from datetime import date
from typing import Optional

class JournalRepository:
    def get_entry(self, user_id: int, entry_date: date) -> Optional[JournalEntry]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM journal_entries WHERE user_id = ? AND date = ?", (user_id, entry_date.isoformat()))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            entry = JournalEntry(
                id=row['id'], 
                user_id=row['user_id'], 
                date=entry_date,
                humiliation=row['humiliation'],
                christ=row['christ'],
                practical_application=row['practical_application']
            )
            # Add created_at dynamically since it's not strictly required in the dataclass
            entry.created_at = row['created_at'] 
            return entry
        return None

    def save_entry(self, entry: JournalEntry) -> JournalEntry:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            if entry.id is None:
                cursor.execute('''
                    INSERT INTO journal_entries (user_id, date, humiliation, christ, practical_application)
                    VALUES (?, ?, ?, ?, ?)
                ''', (entry.user_id, entry.date.isoformat(), entry.humiliation, entry.christ, entry.practical_application))
                entry.id = cursor.lastrowid
            else:
                cursor.execute('''
                    UPDATE journal_entries SET humiliation = ?, christ = ?, practical_application = ?
                    WHERE id = ?
                ''', (entry.humiliation, entry.christ, entry.practical_application, entry.id))
            conn.commit()
            return entry
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
