from database.connection import get_connection
from models.feedback import Feedback
from typing import Optional, List

class FeedbackRepository:
    """Repository for the Beta feedback module.
    Captures user suggestions, bug reports, and constructive criticism.
    """

    def create(self, feedback: Feedback) -> Feedback:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO feedback (user_id, type, message, page)
                VALUES (?, ?, ?, ?)
            ''', (feedback.user_id, feedback.type, feedback.message, feedback.page))
            conn.commit()
            feedback.id = cursor.lastrowid
            return feedback
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def get_by_status(self, status: str = 'pendiente') -> List[Feedback]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM feedback WHERE status = ? ORDER BY created_at DESC",
            (status,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_feedback(row) for row in rows]

    def get_all(self) -> List[Feedback]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM feedback ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_feedback(row) for row in rows]

    def update_status(self, feedback_id: int, status: str) -> None:
        """Update feedback status: 'pendiente', 'revisado', 'implementado'."""
        valid_statuses = ('pendiente', 'revisado', 'implementado')
        if status not in valid_statuses:
            raise ValueError(f"Invalid status '{status}'. Must be one of {valid_statuses}")
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE feedback SET status = ? WHERE id = ?", (status, feedback_id))
        conn.commit()
        conn.close()

    @staticmethod
    def _row_to_feedback(row) -> Feedback:
        return Feedback(
            id=row['id'],
            user_id=row['user_id'],
            type=row['type'],
            message=row['message'],
            page=row['page'],
            status=row['status'],
            created_at=row['created_at']
        )
