import sqlite3
from typing import List, Dict

class Defect:
    TABLE = 'defects'

    @staticmethod
    def create(conn: sqlite3.Connection, data: Dict) -> int:
        cur = conn.execute(
            f"INSERT INTO {Defect.TABLE} "
            "(material_id, defect_type, description, reported_by) "
            "VALUES (?, ?, ?, ?)",
            (data['material_id'], data['defect_type'], data.get('description', ''), data.get('reported_by', ''))
        )
        conn.commit()
        return cur.lastrowid

    @staticmethod
    def list_all(conn: sqlite3.Connection) -> List[Dict]:
        # JOIN с Grades, используя поле grade
        q = f"""
        SELECT
            d.id,
            d.material_id,
            g.grade AS material_grade,
            d.defect_type,
            d.description,
            d.reported_by,
            d.timestamp
        FROM {Defect.TABLE} d
        JOIN Materials m ON d.material_id = m.id
        JOIN Grades g    ON m.grade_id    = g.id
        WHERE d.to_delete = 0
        ORDER BY d.timestamp DESC
        """
        cur = conn.execute(q)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    @staticmethod
    def soft_delete(conn: sqlite3.Connection, defect_id: int):
        conn.execute(
            f"UPDATE {Defect.TABLE} SET to_delete = 1 WHERE id = ?", (defect_id,)
        )
        conn.commit()