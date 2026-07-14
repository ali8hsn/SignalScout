import sqlite3

from backend.db.repositories.base import BaseRepository
from backend.domain.graph_edge import GraphEdge


class GraphEdgeRepository(BaseRepository):
    def save(self, edge: GraphEdge) -> None:
        self.conn.execute(
            """INSERT OR REPLACE INTO graph_edges
               (id, source_person_id, target_person_id, source_name, target_name,
                edge_type, observed_date, source, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                edge.id, edge.source_person_id, edge.target_person_id, edge.source_name,
                edge.target_name, edge.edge_type, edge.observed_date, edge.source,
                self.dumps(edge.metadata),
            ),
        )

    def save_many(self, edges: list[GraphEdge]) -> None:
        for e in edges:
            self.save(e)
        self.conn.commit()

    def for_person(self, person_id: str, before: str | None = None) -> list[GraphEdge]:
        """All edges touching a person (either direction), optionally only pre-`before`."""
        query = "SELECT * FROM graph_edges WHERE (source_person_id = ? OR target_person_id = ?)"
        params: list = [person_id, person_id]
        if before:
            query += " AND observed_date < ?"
            params.append(before)
        rows = self.conn.execute(query, params).fetchall()
        return [self._to_model(r) for r in rows]

    def all(self) -> list[GraphEdge]:
        rows = self.conn.execute("SELECT * FROM graph_edges").fetchall()
        return [self._to_model(r) for r in rows]

    @staticmethod
    def _to_model(row: sqlite3.Row) -> GraphEdge:
        return GraphEdge(
            id=row["id"], source_person_id=row["source_person_id"],
            target_person_id=row["target_person_id"], source_name=row["source_name"],
            target_name=row["target_name"], edge_type=row["edge_type"],
            observed_date=row["observed_date"], source=row["source"],
            metadata=BaseRepository.loads(row["metadata"], {}),
        )
