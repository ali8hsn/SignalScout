import sqlite3

from backend.db.repositories.base import BaseRepository, chunked
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
        """All edges touching a person (either direction), optionally only those
        observed on or before `before` — inclusive so an edge dated exactly on a
        founder's breakout day still counts as known "as of breakout"."""
        query = "SELECT * FROM graph_edges WHERE (source_person_id = ? OR target_person_id = ?)"
        params: list = [person_id, person_id]
        if before:
            query += " AND observed_date <= ?"
            params.append(before)
        rows = self.conn.execute(query, params).fetchall()
        return [self._to_model(r) for r in rows]

    def for_people(self, person_ids: list[str]) -> dict[str, list[GraphEdge]]:
        """Batch variant of `for_person`: fetch every edge touching any of the
        given people in one query per chunk, grouped under each endpoint that was
        requested (an edge between two requested people appears under both)."""
        grouped: dict[str, list[GraphEdge]] = {pid: [] for pid in person_ids}
        for chunk in chunked(person_ids, 400):
            chunk_set = set(chunk)
            placeholders = ",".join("?" for _ in chunk)
            rows = self.conn.execute(
                f"""SELECT * FROM graph_edges
                    WHERE source_person_id IN ({placeholders})
                       OR target_person_id IN ({placeholders})""",
                tuple(chunk) + tuple(chunk),
            ).fetchall()
            # Assign only to endpoints in THIS chunk so a cross-chunk edge is not
            # double-counted when the other endpoint's chunk is processed.
            for row in rows:
                edge = self._to_model(row)
                if edge.source_person_id in chunk_set:
                    grouped[edge.source_person_id].append(edge)
                if edge.target_person_id in chunk_set and edge.target_person_id != edge.source_person_id:
                    grouped[edge.target_person_id].append(edge)
        return grouped

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
