"""Store embeddings and search with PostgreSQL and pgvector."""

import json
import math
from typing import Any

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .models import Chunk


class PgVectorStore:
    FILTER_FIELDS = {"chapter", "language"}

    def __init__(self, database_url: str, dimensions: int) -> None:
        if not database_url:
            raise ValueError("DATABASE_URL is missing")
        if dimensions <= 0:
            raise ValueError("Embedding dimensions must be positive")

        self.database_url = database_url
        self.dimensions = dimensions

    def create_schema(self) -> None:
        statement = sql.SQL("""
            CREATE TABLE IF NOT EXISTS day6_chunks (
                strategy TEXT NOT NULL,
                chunk_id TEXT NOT NULL,
                document_id TEXT NOT NULL,
                source TEXT NOT NULL,
                page INTEGER NOT NULL,
                text TEXT NOT NULL,
                metadata JSONB NOT NULL,
                embedding vector({dimensions}) NOT NULL,
                PRIMARY KEY (strategy, chunk_id)
            )
        """).format(dimensions=sql.Literal(self.dimensions))

        with psycopg.connect(self.database_url) as connection:
            connection.execute(statement)

    def _vector_value(self, vector: list[float]) -> str:
        if len(vector) != self.dimensions:
            raise ValueError(f"Expected {self.dimensions} embedding dimensions")
        if not all(math.isfinite(value) for value in vector) or not any(vector):
            raise ValueError("Cosine search requires a finite, nonzero vector")
        return json.dumps(vector, allow_nan=False)

    def upsert(
        self, strategy: str, chunks: list[Chunk], vectors: list[list[float]]
    ) -> None:
        """Replace the full set of chunks for one strategy in one transaction."""
        if not chunks or len(chunks) != len(vectors):
            raise ValueError("Expected a nonempty set with one vector per chunk")
        if len({chunk.chunk_id for chunk in chunks}) != len(chunks):
            raise ValueError("Duplicate chunk IDs")

        rows = [
            (
                strategy,
                chunk.chunk_id,
                chunk.document_id,
                chunk.source,
                chunk.page,
                chunk.text,
                Jsonb(chunk.metadata),
                self._vector_value(vector),
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]

        with psycopg.connect(self.database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute("LOCK TABLE day6_chunks IN SHARE ROW EXCLUSIVE MODE")
                cursor.execute(
                    "DELETE FROM day6_chunks WHERE strategy = %s",
                    (strategy,),
                )
                cursor.executemany(
                    """
                    INSERT INTO day6_chunks
                        (strategy, chunk_id, document_id, source, page,
                         text, metadata, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::vector)
                    """,
                    rows,
                )

    def count_rows(self, strategy: str) -> dict[str, int]:
        """Row and distinct-ID counts, used to prove a reload does not duplicate."""
        with psycopg.connect(self.database_url) as connection:
            total, distinct = connection.execute(
                "SELECT count(*), count(DISTINCT chunk_id) "
                "FROM day6_chunks WHERE strategy = %s",
                (strategy,),
            ).fetchone()
        return {"rows": total, "distinct_chunk_ids": distinct}

    def delete_strategies_except(self, keep: set[str]) -> list[str]:
        """Remove stale strategies (e.g. old smoke tests) left in the table."""
        with psycopg.connect(self.database_url) as connection:
            removed = connection.execute(
                "SELECT DISTINCT strategy FROM day6_chunks "
                "WHERE NOT (strategy = ANY(%s))",
                (sorted(keep),),
            ).fetchall()
            connection.execute(
                "DELETE FROM day6_chunks WHERE NOT (strategy = ANY(%s))",
                (sorted(keep),),
            )
        return [row[0] for row in removed]

    def server_versions(self) -> dict[str, str]:
        with psycopg.connect(self.database_url) as connection:
            postgres, pgvector = connection.execute(
                "SELECT current_setting('server_version'), extversion "
                "FROM pg_extension WHERE extname = 'vector'"
            ).fetchone()
        return {
            "postgresql": postgres,
            "pgvector": pgvector,
            "psycopg": psycopg.__version__,
            "search": "exact (sequential scan, no ANN index), cosine distance <=>",
        }

    def search(
        self,
        strategy: str,
        query_vector: list[float],
        top_k: int = 3,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        if top_k <= 0:
            raise ValueError("top_k must be positive")

        filters = filters or {}
        if filters.keys() - self.FILTER_FIELDS:
            raise ValueError("Supported filter fields are chapter and language")

        statement = """
            SELECT chunk_id, document_id, source, page, text, metadata,
                   1 - (embedding <=> %s::vector) AS score
            FROM day6_chunks
            WHERE strategy = %s AND metadata @> %s::jsonb
            ORDER BY score DESC, chunk_id
            LIMIT %s
        """
        params = (self._vector_value(query_vector), strategy, Jsonb(filters), top_k)

        with psycopg.connect(self.database_url, row_factory=dict_row) as connection:
            return connection.execute(statement, params).fetchall()