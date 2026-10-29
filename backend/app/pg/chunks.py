"""ChunkStore on Postgres: the storage side of the slide-upload pipeline.

Also holds the read queries that the coverage endpoint, slide retrieval and the study
features share, so they all see the same chunks and CO links.
"""

from __future__ import annotations

from typing import Any, Sequence

from sqlalchemy import text

from ..pipeline.ppt import SlideChunk
from ..pipeline.upload import StoredChunk, TagResult
from ..services.qa import InMemoryChunkRetrievalStore, RetrievalChunk
from .common import as_uuid


class PostgresChunkStore:
    """Implements pipeline.upload.ChunkStore for one subject.

    commit_status=True commits every status change, so a client polling
    GET /modules/{id}/status sees `processing` while the work is still running.
    """

    def __init__(self, conn: Any, subject_id: str, *, commit_status: bool = False) -> None:
        self.conn = conn
        self.subject_id = as_uuid(subject_id, "Subject")
        self.commit_status = commit_status
        self._co_ids: dict[int, str] | None = None

    # -- ChunkStore protocol --------------------------------------------

    def set_module_status(self, module_id: str, status: str, error: str | None = None) -> None:
        self.conn.execute(
            text(
                "UPDATE modules SET processing_status = :st, processing_error = :err, "
                "processed_at = CASE WHEN :st IN ('done', 'failed') THEN now() ELSE NULL END "
                "WHERE id = :id"
            ),
            {"st": status, "err": error, "id": as_uuid(module_id, "Module")},
        )
        if self.commit_status:
            self.conn.commit()

    def save_chunks(self, module_id: str, chunks: Sequence[SlideChunk]) -> list[StoredChunk]:
        mid = as_uuid(module_id, "Module")
        # A re-upload replaces the old slides (chunk_cos rows go with them).
        self.conn.execute(text("DELETE FROM content_chunks WHERE module_id = :m"), {"m": mid})
        saved: list[StoredChunk] = []
        for c in chunks:
            new_id = self.conn.execute(
                text(
                    "INSERT INTO content_chunks (module_id, slide_number, text, tag_status) "
                    "VALUES (:m, :n, :t, 'untagged') RETURNING id"
                ),
                {"m": mid, "n": c.slide_number, "t": c.text},
            ).scalar_one()
            saved.append(StoredChunk(id=str(new_id), slide_number=c.slide_number, text=c.text))
        return saved

    def save_tags(self, tags: Sequence[TagResult]) -> None:
        co_ids = self._co_id_map()
        for t in tags:
            linked = False
            for number in t.cos:
                co_id = co_ids.get(number)
                if co_id is None:
                    continue
                self.conn.execute(
                    text(
                        "INSERT INTO chunk_cos (chunk_id, co_id, confidence) VALUES (:ch, :co, :cf) "
                        "ON CONFLICT (chunk_id, co_id) DO UPDATE SET confidence = EXCLUDED.confidence"
                    ),
                    {"ch": as_uuid(t.chunk_id), "co": co_id, "cf": t.confidence},
                )
                linked = True
            if linked:
                self.conn.execute(
                    text("UPDATE content_chunks SET tag_status = 'tagged' WHERE id = :id"),
                    {"id": as_uuid(t.chunk_id)},
                )

    def mark_untagged(self, chunk_ids: Sequence[str]) -> None:
        for cid in chunk_ids:
            self.conn.execute(
                text("UPDATE content_chunks SET tag_status = 'untagged' WHERE id = :id"),
                {"id": as_uuid(cid)},
            )

    # -- helpers ---------------------------------------------------------

    def _co_id_map(self) -> dict[int, str]:
        if self._co_ids is None:
            rows = self.conn.execute(
                text("SELECT number, id FROM course_outcomes WHERE subject_id = :s"),
                {"s": self.subject_id},
            ).fetchall()
            self._co_ids = {int(r[0]): str(r[1]) for r in rows}
        return self._co_ids


# ---------------------------------------------------------------------------
# Read queries
# ---------------------------------------------------------------------------

def module_status(conn: Any, module_id: str) -> dict[str, Any] | None:
    mid = as_uuid(module_id, "Module")
    row = conn.execute(
        text(
            "SELECT m.processing_status, m.processing_error, "
            "  (SELECT count(*) FROM content_chunks c WHERE c.module_id = m.id) AS total, "
            "  (SELECT count(*) FROM content_chunks c WHERE c.module_id = m.id AND c.tag_status = 'tagged') AS tagged "
            "FROM modules m WHERE m.id = :id"
        ),
        {"id": mid},
    ).mappings().fetchone()
    if row is None:
        return None
    return {
        "processing_status": row["processing_status"],
        "chunks_total": int(row["total"]),
        "chunks_tagged": int(row["tagged"]),
        "chunks_untagged": int(row["total"]) - int(row["tagged"]),
        "error": row["processing_error"],
    }


def subject_cos(conn: Any, subject_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        text(
            "SELECT id, number, description, threshold_pct FROM course_outcomes "
            "WHERE subject_id = :s ORDER BY number"
        ),
        {"s": as_uuid(subject_id, "Subject")},
    ).mappings().fetchall()
    return [
        {
            "id": str(r["id"]),
            "number": int(r["number"]),
            "description": r["description"],
            "threshold_pct": float(r["threshold_pct"]),
        }
        for r in rows
    ]


def chunk_co_links(conn: Any, subject_id: str) -> list[tuple[str, int]]:
    """(chunk_id, co_number) for every tagged chunk of a subject."""
    rows = conn.execute(
        text(
            "SELECT cc.chunk_id, co.number FROM chunk_cos cc "
            "JOIN course_outcomes co ON co.id = cc.co_id "
            "JOIN content_chunks ch ON ch.id = cc.chunk_id "
            "JOIN modules m ON m.id = ch.module_id "
            "WHERE m.subject_id = :s"
        ),
        {"s": as_uuid(subject_id, "Subject")},
    ).fetchall()
    return [(str(r[0]), int(r[1])) for r in rows]


def slide_chunks_for_subject(conn: Any, subject_id: str) -> list[dict[str, Any]]:
    """One dict per (chunk, CO) link: what the study plan needs to link slides to a CO."""
    rows = conn.execute(
        text(
            "SELECT ch.id, ch.module_id, ch.slide_number, ch.text, co.number "
            "FROM chunk_cos cc "
            "JOIN content_chunks ch ON ch.id = cc.chunk_id "
            "JOIN modules m ON m.id = ch.module_id "
            "JOIN course_outcomes co ON co.id = cc.co_id "
            "WHERE m.subject_id = :s ORDER BY co.number, cc.confidence DESC NULLS LAST, m.number, ch.slide_number"
        ),
        {"s": as_uuid(subject_id, "Subject")},
    ).fetchall()
    return [
        {
            "chunk_id": str(r[0]),
            "module_id": str(r[1]),
            "slide_number": int(r[2]),
            "text": r[3],
            "co_number": int(r[4]),
        }
        for r in rows
    ]


def module_chunks_with_co(conn: Any, module_id: str) -> list[dict[str, Any]]:
    """Chunks of one module, each with its best-matching CO id (None if untagged)."""
    rows = conn.execute(
        text(
            "SELECT ch.id, ch.slide_number, ch.text, "
            "  (SELECT cc.co_id FROM chunk_cos cc WHERE cc.chunk_id = ch.id "
            "   ORDER BY cc.confidence DESC NULLS LAST LIMIT 1) AS co_id "
            "FROM content_chunks ch WHERE ch.module_id = :m ORDER BY ch.slide_number"
        ),
        {"m": as_uuid(module_id, "Module")},
    ).fetchall()
    return [
        {"chunk_id": str(r[0]), "slide_number": int(r[1]), "text": r[2], "co_id": str(r[3]) if r[3] else None}
        for r in rows
    ]


class PostgresChunkRetrievalStore:
    """Slide search for Q&A.

    Decision (see docs/decisions.md #1): no embeddings. The corpus is a few hundred
    short chunks per subject, so the subject's chunks are loaded and scored with the
    keyword scorer in services/qa. No extension, no extra model, nothing to re-embed
    when the server restarts.
    """

    def __init__(self, conn: Any) -> None:
        self.conn = conn

    def search_chunks(self, subject_id: str, query: str, top_k: int = 3) -> list[RetrievalChunk]:
        rows = self.conn.execute(
            text(
                "SELECT ch.id, ch.module_id, ch.slide_number, ch.text "
                "FROM content_chunks ch JOIN modules m ON m.id = ch.module_id "
                "WHERE m.subject_id = :s"
            ),
            {"s": as_uuid(subject_id, "Subject")},
        ).fetchall()
        index = InMemoryChunkRetrievalStore()
        for cid, mid, slide, body in rows:
            index.add_chunk(subject_id, str(cid), str(mid), int(slide), body)
        return index.search_chunks(subject_id, query, top_k=top_k)
