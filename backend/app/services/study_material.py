"""Flashcard and note generation and retrieval service.

Generates study materials once per module upload (not per student)
using Danwin's client or grounded chunk extraction, matching arya.md task 10.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Protocol, Sequence


@dataclass(frozen=True)
class Flashcard:
    id: str
    module_id: str
    co_id: str | None
    front: str
    back: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "module_id": self.module_id,
            "co_id": self.co_id,
            "front": self.front,
            "back": self.back,
        }


@dataclass(frozen=True)
class Note:
    id: str
    module_id: str
    co_id: str | None
    title: str
    body: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "module_id": self.module_id,
            "co_id": self.co_id,
            "title": self.title,
            "body": self.body,
        }


class StudyMaterialStore(Protocol):
    """Protocol for flashcard and note storage."""

    def save_flashcards(self, cards: Sequence[Flashcard]) -> None: ...

    def save_notes(self, notes: Sequence[Note]) -> None: ...

    def list_flashcards(self, module_id: str) -> list[Flashcard]: ...

    def list_notes(self, module_id: str) -> list[Note]: ...

    def has_material_for_module(self, module_id: str) -> bool: ...


class InMemoryStudyMaterialStore:
    """In-memory store for unit testing."""

    def __init__(self) -> None:
        self._cards: dict[str, list[Flashcard]] = {}
        self._notes: dict[str, list[Note]] = {}

    def save_flashcards(self, cards: Sequence[Flashcard]) -> None:
        for c in cards:
            self._cards.setdefault(c.module_id, []).append(c)

    def save_notes(self, notes: Sequence[Note]) -> None:
        for n in notes:
            self._notes.setdefault(n.module_id, []).append(n)

    def list_flashcards(self, module_id: str) -> list[Flashcard]:
        return list(self._cards.get(module_id, []))

    def list_notes(self, module_id: str) -> list[Note]:
        return list(self._notes.get(module_id, []))

    def has_material_for_module(self, module_id: str) -> bool:
        return bool(self._cards.get(module_id) or self._notes.get(module_id))


# Material generator signature: (module_title, chunks) -> (flashcards_data, notes_data)
MaterialGenerator = Callable[[str, Sequence[dict[str, Any]]], tuple[list[dict[str, Any]], list[dict[str, Any]]]]


def generate_module_study_material(
    store: StudyMaterialStore,
    module_id: str,
    module_title: str,
    chunks: Sequence[dict[str, Any]],
    *,
    generator: MaterialGenerator | None = None,
    force_regenerate: bool = False,
) -> tuple[list[Flashcard], list[Note]]:
    """Generate flashcards and notes once per module.
    
    If material already exists and force_regenerate is False, returns existing material.
    """
    if not force_regenerate and store.has_material_for_module(module_id):
        return store.list_flashcards(module_id), store.list_notes(module_id)

    raw_cards: list[dict[str, Any]] = []
    raw_notes: list[dict[str, Any]] = []

    if generator is not None:
        raw_cards, raw_notes = generator(module_title, chunks)
    else:
        # Grounded fallback: extract from slide chunks
        for idx, ch in enumerate(chunks, start=1):
            text = ch.get("text", "").strip()
            if not text:
                continue
            slide_no = ch.get("slide_number", idx)
            co_id = ch.get("co_id")

            # Extract first sentence/line as question and remainder as answer
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            header = lines[0] if lines else f"Slide {slide_no}"
            details = " ".join(lines[1:]) if len(lines) > 1 else text

            raw_cards.append({
                "co_id": co_id,
                "front": f"What are key concepts in: {header}?",
                "back": details,
            })
            raw_notes.append({
                "co_id": co_id,
                "title": f"Summary: {header}",
                "body": text,
            })

    created_cards = [
        Flashcard(
            id=c.get("id") or str(uuid.uuid4()),
            module_id=module_id,
            co_id=c.get("co_id"),
            front=c["front"],
            back=c["back"],
        )
        for c in raw_cards
    ]
    created_notes = [
        Note(
            id=n.get("id") or str(uuid.uuid4()),
            module_id=module_id,
            co_id=n.get("co_id"),
            title=n["title"],
            body=n["body"],
        )
        for n in raw_notes
    ]

    store.save_flashcards(created_cards)
    store.save_notes(created_notes)
    return created_cards, created_notes


def get_module_flashcards(store: StudyMaterialStore, module_id: str) -> list[dict[str, Any]]:
    return [c.to_dict() for c in store.list_flashcards(module_id)]


def get_module_notes(store: StudyMaterialStore, module_id: str) -> list[dict[str, Any]]:
    return [n.to_dict() for n in store.list_notes(module_id)]

