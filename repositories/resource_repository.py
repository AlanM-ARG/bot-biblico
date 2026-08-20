from database.connection import get_connection
from models.resource import Resource
from typing import Optional, List
from datetime import datetime

class ResourceRepository:
    """Repository for managing injected resources and their audit trail.
    
    The 'category' field drives dynamic UI updates:
    - 'plan_lectura' -> enables calendar plan views
    - 'oracion'      -> injects prayer motifs into the prayer wall
    - 'inductivo'    -> updates methodological rules in the System Prompt
    """

    def create(self, resource: Resource) -> Resource:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO resources (filename, filepath, resource_type, category, md5_hash, metadata_json, is_vectorized)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                resource.filename, resource.filepath, resource.resource_type,
                resource.category, resource.md5_hash, resource.metadata_json,
                resource.is_vectorized
            ))
            conn.commit()
            resource.id = cursor.lastrowid
            return resource
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def get_by_hash(self, md5_hash: str) -> Optional[Resource]:
        """Check for duplicates by MD5 hash before ingesting a resource."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM resources WHERE md5_hash = ?", (md5_hash,))
        row = cursor.fetchone()
        conn.close()
        return self._row_to_resource(row) if row else None

    def get_by_category(self, category: str) -> List[Resource]:
        """Retrieve all resources of a specific category for UI rendering."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM resources WHERE category = ? ORDER BY created_at DESC", (category,))
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_resource(row) for row in rows]

    def get_all(self) -> List[Resource]:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM resources ORDER BY created_at DESC")
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_resource(row) for row in rows]

    def get_unvectorized(self) -> List[Resource]:
        """Get resources that haven't been chunked and vectorized yet."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM resources WHERE is_vectorized = 0 ORDER BY created_at")
        rows = cursor.fetchall()
        conn.close()
        return [self._row_to_resource(row) for row in rows]

    def mark_as_vectorized(self, resource_id: int) -> None:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE resources SET is_vectorized = 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (resource_id,)
        )
        conn.commit()
        conn.close()

    def delete_all(self) -> None:
        """Deletes all resources to allow a hard reset of the ETL pipeline."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM resources")
        conn.commit()
        conn.close()

    def get_discarded_resource_ids(self) -> List[int]:
        """Returns the IDs of resources that have been marked as 'Descartar' in the doctrinal audit."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT resource_id FROM auditoria_libros WHERE categoria = 'Descartar' AND resource_id IS NOT NULL")
        rows = cursor.fetchall()
        conn.close()
        return [row[0] for row in rows]

    @staticmethod
    def _row_to_resource(row) -> Resource:
        return Resource(
            id=row['id'],
            filename=row['filename'],
            filepath=row['filepath'],
            resource_type=row['resource_type'],
            category=row['category'],
            md5_hash=row['md5_hash'],
            metadata_json=row['metadata_json'],
            is_vectorized=bool(row['is_vectorized']),
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )
