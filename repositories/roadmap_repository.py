import json
from database.connection import get_connection

class RoadmapRepository:
    def create(self, user_id: int, topic: str, roadmap_data: dict) -> int:
        """Saves a new roadmap for the user."""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO user_roadmaps (user_id, topic, roadmap_json)
            VALUES (?, ?, ?)
        ''', (user_id, topic, json.dumps(roadmap_data)))
        
        roadmap_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return roadmap_id

    def get_by_user(self, user_id: int) -> list:
        """Retrieves all roadmaps for a given user."""
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, user_id, topic, roadmap_json, created_at
            FROM user_roadmaps
            WHERE user_id = ?
            ORDER BY created_at DESC
        ''', (user_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        # Parse JSON
        result = []
        for r in rows:
            result.append({
                "id": r["id"],
                "user_id": r["user_id"],
                "topic": r["topic"],
                "roadmap_data": json.loads(r["roadmap_json"]),
                "created_at": r["created_at"]
            })
        return result

    def get_by_id(self, roadmap_id: int) -> dict:
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, user_id, topic, roadmap_json, created_at
            FROM user_roadmaps
            WHERE id = ?
        ''', (roadmap_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "id": row["id"],
                "user_id": row["user_id"],
                "topic": row["topic"],
                "roadmap_data": json.loads(row["roadmap_json"]),
                "created_at": row["created_at"]
            }
        return None

    def update_roadmap_data(self, roadmap_id: int, roadmap_data: dict):
        """Updates the roadmap JSON data (used for tracking progress)."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE user_roadmaps
            SET roadmap_json = ?
            WHERE id = ?
        ''', (json.dumps(roadmap_data), roadmap_id))
        conn.commit()
        conn.close()

    def delete(self, roadmap_id: int):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM user_roadmaps WHERE id = ?", (roadmap_id,))
        conn.commit()
        conn.close()
