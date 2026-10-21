"""The module-upload pipeline: parse slides, save chunks, tag them with COs.

This is a plain function with no web framework or database inside it, so it can run
from an API request, a background worker, or later a Nebius Serverless Job. It talks
to the outside world through two things the caller passes in:

  store   saves chunks and tags (the database layer; Aparna's schema)
  tagger  tags chunks with COs (Danwin's tag_content_with_COs)

Rules:
- AI runs once per module upload, here, and never per student.
- A tagging failure never fails the upload. Chunks that could not be tagged are
  saved as untagged and reported.
- A file that cannot be read, or that has no text at all, fails the upload cleanly:
  the module is marked failed with a message, and nothing is raised.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import BinaryIO, Callable, Iterable, Mapping, Protocol, Sequence

from .ppt import PptParseError, SlideChunk, parse_pptx

STATUS_PROCESSING = "processing"
STATUS_DONE = "done"
STATUS_FAILED = "failed"

DEFAULT_BATCH_SIZE = 20


@dataclass(frozen=True)
class COInfo:
    number: int
    description: str = ""


@dataclass(frozen=True)
class StoredChunk:
    id: str
    slide_number: int
    text: str


@dataclass(frozen=True)
class TagResult:
    chunk_id: str
    cos: tuple[int, ...]
    confidence: float | None = None


class ChunkStore(Protocol):
    """What the pipeline needs from the database layer."""

    def set_module_status(self, module_id: str, status: str, error: str | None = None) -> None: ...

    def save_chunks(self, module_id: str, chunks: Sequence[SlideChunk]) -> list[StoredChunk]: ...

    def save_tags(self, tags: Sequence[TagResult]) -> None: ...

    def mark_untagged(self, chunk_ids: Sequence[str]) -> None: ...


# A tagger gets a batch of chunks and the COs, and returns one result per chunk it
# could tag, either as TagResult objects or as {"chunk_id", "cos", "confidence"} dicts.
Tagger = Callable[[Sequence[StoredChunk], Sequence[COInfo]], Iterable[object]]


@dataclass(frozen=True)
class UploadReport:
    module_id: str
    status: str  # "done" or "failed"
    error: str | None
    total_slides: int
    chunks_saved: int
    tagged: int
    untagged: int
    skipped_slides: tuple[int, ...]
    tagging_errors: tuple[str, ...]


def _co_number(value: object) -> int | None:
    """Accept 3, "3" or "CO3". Anything else is not a CO."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        match = re.fullmatch(r"\s*(?:CO)?\s*(\d+)\s*", value, flags=re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def _confidence(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if 0 <= value <= 1 else None


def _to_tag_result(item: object, valid_cos: set[int]) -> TagResult | None:
    """Normalise one tagger output item. Returns None if it cannot be used."""
    if isinstance(item, TagResult):
        chunk_id, raw_cos, conf = item.chunk_id, item.cos, item.confidence
    elif isinstance(item, Mapping):
        chunk_id, raw_cos, conf = item.get("chunk_id"), item.get("cos"), item.get("confidence")
    else:
        return None
    if not isinstance(chunk_id, str) or not isinstance(raw_cos, (list, tuple, set)):
        return None
    numbers = {n for n in (_co_number(c) for c in raw_cos) if n is not None and n in valid_cos}
    if not numbers:
        return None
    return TagResult(chunk_id=chunk_id, cos=tuple(sorted(numbers)), confidence=_confidence(conf))


def process_module_upload(
    module_id: str,
    source: str | BinaryIO,
    cos: Sequence[COInfo],
    tagger: Tagger,
    store: ChunkStore,
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
    include_notes: bool = True,
) -> UploadReport:
    """Parse the deck, save its chunks, tag them, and report what happened."""
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")

    store.set_module_status(module_id, STATUS_PROCESSING)

    def failed(message: str, total_slides: int = 0, skipped: tuple[int, ...] = ()) -> UploadReport:
        store.set_module_status(module_id, STATUS_FAILED, message)
        return UploadReport(module_id, STATUS_FAILED, message, total_slides, 0, 0, 0, skipped, ())

    try:
        deck = parse_pptx(source, include_notes=include_notes)
    except PptParseError as exc:
        return failed(str(exc))
    if not deck.chunks:
        return failed(
            "No text was found in the slides. Slides that are only pictures cannot be tagged.",
            deck.total_slides,
            deck.skipped_slides,
        )

    try:
        stored = store.save_chunks(module_id, deck.chunks)
        valid_cos = {c.number for c in cos}

        tags: dict[str, TagResult] = {}
        errors: list[str] = []
        if not valid_cos:
            errors.append("No COs are defined for this subject, so nothing could be tagged.")
        else:
            for start in range(0, len(stored), batch_size):
                batch = stored[start : start + batch_size]
                batch_ids = {c.id for c in batch}
                try:
                    output = list(tagger(batch, cos))
                except Exception as exc:  # a tagging failure must never fail the upload
                    errors.append(f"Tagging failed for slides in batch starting at slide "
                                  f"{batch[0].slide_number}: {exc}")
                    continue
                for item in output:
                    result = _to_tag_result(item, valid_cos)
                    if result is not None and result.chunk_id in batch_ids:
                        tags[result.chunk_id] = result

        if tags:
            store.save_tags(list(tags.values()))
        untagged_ids = [c.id for c in stored if c.id not in tags]
        if untagged_ids:
            store.mark_untagged(untagged_ids)
    except Exception as exc:
        store.set_module_status(module_id, STATUS_FAILED, f"Upload failed: {exc}")
        raise

    store.set_module_status(module_id, STATUS_DONE)
    return UploadReport(
        module_id=module_id,
        status=STATUS_DONE,
        error=None,
        total_slides=deck.total_slides,
        chunks_saved=len(stored),
        tagged=len(tags),
        untagged=len(untagged_ids),
        skipped_slides=deck.skipped_slides,
        tagging_errors=tuple(errors),
    )
