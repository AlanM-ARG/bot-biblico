from database.connection import get_connection
from models.habit import Habit
from datetime import date
from typing import Optional
import base64

class HabitRepository:
    def _encode_notes(self, text: Optional[str]) -> Optional[str]:
        if not text:
            return text
        return base64.b64encode(text.encode('utf-8')).decode('utf-8')
        
    def _decode_notes(self, text: Optional[str]) -> Optional[str]:
        if not text:
            return text
        try:
            return base64.b64decode(text.encode('utf-8')).decode('utf-8')
        except:
            return text

    def get_habit(self, user_id: int, habit_date: date) -> Optional[Habit]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM habits WHERE user_id = ? AND date = ?", (user_id, habit_date.isoformat()))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return Habit(
                id=row['id'], 
                user_id=row['user_id'], 
                date=habit_date,
                bible_reading=bool(row['bible_reading']),
                prayer=bool(row['prayer']),
                meditation=bool(row['meditation']),
                family_worship=bool(row['family_worship']),
                notes=self._decode_notes(row['notes'])
            )
        return None

    def save_habit(self, habit: Habit) -> Habit:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO habits (user_id, date, bible_reading, prayer, meditation, family_worship, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, date) DO UPDATE SET
                    bible_reading=excluded.bible_reading,
                    prayer=excluded.prayer,
                    meditation=excluded.meditation,
                    family_worship=excluded.family_worship,
                    notes=excluded.notes
            ''', (
                habit.user_id, 
                habit.date.isoformat(), 
                int(habit.bible_reading), 
                int(habit.prayer),
                int(habit.meditation),
                int(habit.family_worship),
                self._encode_notes(habit.notes)
            ))
            conn.commit()
            if habit.id is None:
                habit.id = cursor.lastrowid
            return habit
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
