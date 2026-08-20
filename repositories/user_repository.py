from database.connection import get_connection
from models.user import User
from typing import Optional, List

class UserRepository:
    """Repository for user CRUD operations and preference management."""

    def create_user(self, username: str, display_name: Optional[str] = None) -> User:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (username, display_name) VALUES (?, ?)",
                (username, display_name or username)
            )
            conn.commit()
            user_id = cursor.lastrowid
            return self.get_user_by_id(user_id)
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def get_user_by_username(self, username: str) -> Optional[User]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        conn.close()
        return self._row_to_user(row) if row else None

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        conn.close()
        return self._row_to_user(row) if row else None

    def get_all_users(self) -> List[User]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users ORDER BY created_at")
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_user(row) for row in rows]

    def update_study_level(self, user_id: int, level: str) -> None:
        """Update the study difficulty level for a user.
        Valid levels: 'principiante', 'moderado', 'complejo'
        """
        valid_levels = ('principiante', 'moderado', 'complejo')
        if level not in valid_levels:
            raise ValueError(f"Invalid study level '{level}'. Must be one of {valid_levels}")
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET study_level = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (level, user_id)
        )
        conn.commit()
        conn.close()

    def toggle_family_mode(self, user_id: int, enabled: bool) -> None:
        """Enable or disable family discipleship mode for a user."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET family_mode = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (enabled, user_id)
        )
        conn.commit()
        conn.close()

    def update_display_name(self, user_id: int, display_name: str) -> None:
        """Update the visible display name for a user."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET display_name = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (display_name, user_id)
        )
        conn.commit()
        conn.close()

    def update_vital_context(self, user_id: int, context: str) -> None:
        """Update the vital context for a user."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET vital_context = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (context, user_id)
        )
        conn.commit()
        conn.close()

    @staticmethod
    def _row_to_user(row) -> User:
        return User(
            id=row['id'],
            username=row['username'],
            display_name=row['display_name'],
            study_level=row['study_level'],
            family_mode=bool(row['family_mode']),
            vital_context=row['vital_context'] if 'vital_context' in row.keys() else None,
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )
