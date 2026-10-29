"""Adapters that connect AI functions to the existing upload and question APIs."""

from __future__ import annotations

from functools import partial
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from .quiz_generation import generate_quiz
from .tagging import tag_content_with_COs
from .token_factory import TokenFactoryClient


QUESTION_BATCH_FIELDS = (
    "module_id",
    "co_id",
    "stem",
    "options",
    "correct_option",
    "explanation",
    "marks",
    "difficulty",
    "bloom_level",
)


def build_upload_tagger(
    client: TokenFactoryClient,
    *,
    model: str,
    usage_recorder: Callable[[dict[str, Any]], None] | None = None,
    batch_size: int = 20,
) -> Callable[[Sequence[object], Sequence[object]], list[dict[str, Any]]]:
    """Bind the shared Token Factory client to the upload pipeline's tagger seam."""
    if not model:
        raise ValueError("A selected tagging model ID is required")
    return partial(
        tag_content_with_COs,
        client=client,
        model=model,
        usage_recorder=usage_recorder,
        batch_size=batch_size,
    )


def build_quiz_generator(
    client: TokenFactoryClient,
    *,
    model: str,
    usage_recorder: Callable[[dict[str, Any]], None] | None = None,
) -> Callable[..., list[dict[str, Any]]]:
    """Bind the generation model for a faculty draft-review workflow."""
    if not model:
        raise ValueError("A selected generation model ID is required")
    return partial(
        generate_quiz,
        client=client,
        model=model,
        usage_recorder=usage_recorder,
    )


def build_question_batch_payload(drafts: Sequence[Mapping[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Adapt generated drafts to ``POST /questions/batch`` without status changes.

    The endpoint sets source=AI and the database default keeps the question in
    draft status. The caller must never pass approved/published model output.
    """
    if not drafts:
        raise ValueError("At least one quiz draft is required")
    questions: list[dict[str, Any]] = []
    for index, draft in enumerate(drafts, start=1):
        if not isinstance(draft, Mapping):
            raise ValueError(f"Question {index} must be an object")
        if draft.get("status") != "draft":
            raise ValueError(f"Question {index} must remain a draft")
        if draft.get("source") != "AI":
            raise ValueError(f"Question {index} must have source AI")
        required = ("module_id", "co_id", "stem", "options", "correct_option")
        missing = [key for key in required if key not in draft or draft[key] is None]
        if missing:
            raise ValueError(f"Question {index} is missing required fields: {', '.join(missing)}")
        for key in ("module_id", "co_id", "stem"):
            if not isinstance(draft[key], str) or not draft[key].strip():
                raise ValueError(f"Question {index} field {key} must be non-empty text")
        question = {key: draft[key] for key in QUESTION_BATCH_FIELDS if key in draft}
        if (
            not isinstance(question.get("options"), list)
            or len(question["options"]) != 4
            or any(not isinstance(option, str) or not option.strip() for option in question["options"])
        ):
            raise ValueError(f"Question {index} must have four non-empty options")
        if not isinstance(question.get("correct_option"), int) or isinstance(question.get("correct_option"), bool) or question["correct_option"] not in range(4):
            raise ValueError(f"Question {index} has an invalid correct option")
        questions.append(question)
    return {"questions": questions}


def generate_and_save_quiz_drafts(
    module: object,
    co: object,
    difficulty: str,
    count: int,
    generator: Callable[..., list[dict[str, Any]]],
    save_batch: Callable[[dict[str, list[dict[str, Any]]]], Any],
) -> Any:
    """Generate validated questions, then hand only drafts to the batch endpoint adapter."""
    drafts = generator(module, co, difficulty, count)
    payload = build_question_batch_payload(drafts)
    return save_batch(payload)
