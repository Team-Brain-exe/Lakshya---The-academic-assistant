"""Slide retrieval and slide-grounded Q&A service.

Implements slide retrieval, slide citations, and strict refusal logic when questions
are not covered in the course slides, matching arya.md task 8 and docs/api-contract.md section 9.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Callable, Protocol, Sequence


@dataclass(frozen=True)
class RetrievalChunk:
    chunk_id: str
    module_id: str
    slide_number: int
    text: str
    score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "module_id": self.module_id,
            "slide_number": self.slide_number,
            "text": self.text,
            "score": round(self.score, 4),
        }


@dataclass(frozen=True)
class QAResult:
    answer: str
    citations: list[dict[str, Any]]
    refused: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "answer": self.answer,
            "citations": self.citations,
            "refused": self.refused,
        }


class ChunkRetrievalStore(Protocol):
    """Protocol for fetching and querying content chunks."""

    def search_chunks(
        self, subject_id: str, query: str, top_k: int = 3
    ) -> list[RetrievalChunk]: ...


_STOPWORDS = frozenset(
    "a an and are as at be but by can do does for from how i if in into is it its me my "
    "of on or so than that the their them then there these they this to us was we were "
    "what when where which who why will with you your explain define describe tell about "
    "give please difference between meaning".split()
)


def _tokenize(text: str) -> list[str]:
    """Tokenize and normalize words, dropping punctuation and question filler words."""
    words = re.findall(r"\b[a-zA-Z0-9_-]{2,}\b", text.lower())
    return [w for w in words if w not in _STOPWORDS]


class NotInSlidesError(Exception):
    """The AI client says the retrieved slides do not answer the question."""


class InMemoryChunkRetrievalStore:
    """Fast keyword/BM25-style in-memory chunk search index for slides."""

    def __init__(self) -> None:
        # subject_id -> list of chunk dicts
        self._chunks: dict[str, list[dict[str, Any]]] = {}

    def add_chunk(
        self,
        subject_id: str,
        chunk_id: str,
        module_id: str,
        slide_number: int,
        text: str,
    ) -> None:
        self._chunks.setdefault(subject_id, []).append({
            "chunk_id": chunk_id,
            "module_id": module_id,
            "slide_number": slide_number,
            "text": text,
            "tokens": _tokenize(text),
        })

    def search_chunks(
        self, subject_id: str, query: str, top_k: int = 3
    ) -> list[RetrievalChunk]:
        chunks = self._chunks.get(subject_id, [])
        query_tokens = _tokenize(query)
        if not query_tokens or not chunks:
            return []

        results: list[RetrievalChunk] = []
        for ch in chunks:
            text_tokens = ch["tokens"]
            if not text_tokens:
                continue

            # Term frequency matching
            match_count = sum(1 for qt in query_tokens if qt in text_tokens)
            if match_count == 0:
                continue

            # Normalized score based on matched query terms
            score = match_count / math.sqrt(len(query_tokens) * len(set(text_tokens)))
            results.append(
                RetrievalChunk(
                    chunk_id=ch["chunk_id"],
                    module_id=ch["module_id"],
                    slide_number=ch["slide_number"],
                    text=ch["text"],
                    score=score,
                )
            )

        results.sort(key=lambda r: (-r.score, r.slide_number))
        return results[:top_k]


REFUSAL_MESSAGE = (
    "I cannot answer this question because it is not covered in the course slides."
)


def retrieve_chunks(
    store: ChunkRetrievalStore,
    subject_id: str,
    query: str,
    *,
    top_k: int = 3,
    min_score: float = 0.05,
) -> list[RetrievalChunk]:
    """Retrieve top chunks for a question, filtered by min_score."""
    chunks = store.search_chunks(subject_id, query, top_k=top_k)
    return [c for c in chunks if c.score >= min_score]


# Danwin AI Client protocol or callable: (prompt: str, context: str) -> str
AIClient = Callable[[str, str], str]


def answer_from_course_material(
    store: ChunkRetrievalStore,
    subject_id: str,
    question: str,
    *,
    ai_client: AIClient | None = None,
    min_score: float = 0.08,
    top_k: int = 3,
) -> QAResult:
    """Answer student question grounded strictly in course slides.
    
    If no chunks match or confidence is below min_score, refuses cleanly.
    Every non-refused answer includes slide citations.
    """
    matching_chunks = retrieve_chunks(
        store, subject_id, question, top_k=top_k, min_score=min_score
    )

    if not matching_chunks:
        return QAResult(
            answer=REFUSAL_MESSAGE,
            citations=[],
            refused=True,
        )

    # Build structured citations
    seen_citations: set[tuple[str, int]] = set()
    citations: list[dict[str, Any]] = []
    for c in matching_chunks:
        key = (c.module_id, c.slide_number)
        if key not in seen_citations:
            seen_citations.add(key)
            citations.append({
                "module_id": c.module_id,
                "slide_number": c.slide_number,
            })

    # Prepare context for AI generation or deterministic fallback
    context_blocks = [
        f"[Slide {c.slide_number}]: {c.text}" for c in matching_chunks
    ]
    context_str = "\n".join(context_blocks)

    if ai_client is not None:
        try:
            answer_text = ai_client(question, context_str)
        except Exception as exc:
            # The name check also matches when this module was imported under two
            # package names (as the test suite does), where isinstance would miss.
            if isinstance(exc, NotInSlidesError) or type(exc).__name__ == "NotInSlidesError":
                return QAResult(answer=REFUSAL_MESSAGE, citations=[], refused=True)
            # Fall back cleanly if the AI call fails
            answer_text = f"Based on the slides:\n{context_blocks[0]}"
    else:
        # Grounded fallback: return summary citing the highest-scoring slide
        primary = matching_chunks[0]
        answer_text = (
            f"According to Slide {primary.slide_number}: {primary.text}"
        )

    return QAResult(
        answer=answer_text,
        citations=citations,
        refused=False,
    )

