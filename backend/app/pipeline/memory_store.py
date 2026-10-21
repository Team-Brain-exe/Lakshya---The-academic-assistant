"""An in-memory ChunkStore. Used by tests and by local demos; not the real database."""

from __future__ import annotations

from typing import Sequence

from .ppt import SlideChunk
from .upload import StoredChunk, TagResult


class InMemoryChunkStore:
    def __init__(self) -> None:
        self.status_history: list[tuple[str, str, str | None]] = []
        self.chunks: dict[str, StoredChunk] = {}
        self.tags: dict[str, TagResult] = {}
        self.untagged: set[str] = set()
        self._next_id = 1

    def set_module_status(self, module_id: str, status: str, error: str | None = None) -> None:
        self.status_history.append((module_id, status, error))

    def save_chunks(self, module_id: str, chunks: Sequence[SlideChunk]) -> list[StoredChunk]:
        saved = []
        for c in chunks:
            chunk = StoredChunk(id=f"chunk-{self._next_id}", slide_number=c.slide_number, text=c.text)
            self._next_id += 1
            self.chunks[chunk.id] = chunk
            saved.append(chunk)
        return saved

    def save_tags(self, tags: Sequence[TagResult]) -> None:
        for t in tags:
            self.tags[t.chunk_id] = t
            self.untagged.discard(t.chunk_id)

    def mark_untagged(self, chunk_ids: Sequence[str]) -> None:
        self.untagged.update(chunk_ids)

    def chunk_co_links(self) -> list[tuple[str, int]]:
        """(chunk_id, co_number) pairs, ready for coverage()."""
        return [(t.chunk_id, co) for t in self.tags.values() for co in t.cos]

    @property
    def final_status(self) -> str | None:
        return self.status_history[-1][1] if self.status_history else None
