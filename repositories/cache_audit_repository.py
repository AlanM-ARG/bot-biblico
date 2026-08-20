from database.connection import get_connection
from models.cache_audit import CacheAudit
from typing import Optional, List

class CacheAuditRepository:
    """Repository for managing study guide cache invalidation.
    
    When a new resource is ingested, all existing guides should be
    marked as stale so they can be regenerated On-Demand with the
    new intelligence integrated.
    """

    def register_guide(self, guide_key: str, file_path: str) -> CacheAudit:
        """Register a newly generated guide in the audit trail."""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO cache_audit (guide_key, generated_at, file_path, is_stale)
                VALUES (?, CURRENT_TIMESTAMP, ?, 0)
                ON CONFLICT(guide_key)
                DO UPDATE SET generated_at = CURRENT_TIMESTAMP, file_path = ?, is_stale = 0, invalidated_at = NULL
            ''', (guide_key, file_path, file_path))
            conn.commit()
            return CacheAudit(
                id=cursor.lastrowid,
                guide_key=guide_key,
                generated_at='',
                file_path=file_path,
                is_stale=False
            )
        finally:
            conn.close()

    def is_guide_fresh(self, guide_key: str) -> bool:
        """Check if a guide exists and is not stale (can be served from cache)."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT is_stale FROM cache_audit WHERE guide_key = ?",
            (guide_key,)
        )
        row = cursor.fetchone()
        conn.close()
        if row is None:
            return False  # guide doesn't exist, needs generation
        return not bool(row['is_stale'])

    def invalidate_all(self) -> int:
        """Mark ALL guides as stale. Called when a new resource is ingested.
        Returns the number of guides invalidated.
        """
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE cache_audit 
            SET is_stale = 1, invalidated_at = CURRENT_TIMESTAMP 
            WHERE is_stale = 0
        ''')
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return affected

    def invalidate_by_key(self, guide_key: str) -> None:
        """Mark a specific guide as stale."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE cache_audit SET is_stale = 1, invalidated_at = CURRENT_TIMESTAMP WHERE guide_key = ?",
            (guide_key,)
        )
        conn.commit()
        conn.close()

    def get_stale_guides(self) -> List[CacheAudit]:
        """Get all guides that need regeneration."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM cache_audit WHERE is_stale = 1 ORDER BY invalidated_at")
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_audit(row) for row in rows]

    @staticmethod
    def _row_to_audit(row) -> CacheAudit:
        return CacheAudit(
            id=row['id'],
            guide_key=row['guide_key'],
            generated_at=row['generated_at'],
            file_path=row['file_path'],
            is_stale=bool(row['is_stale']),
            invalidated_at=row['invalidated_at']
        )
