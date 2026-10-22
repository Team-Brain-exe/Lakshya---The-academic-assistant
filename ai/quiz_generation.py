"""Generate validated, faculty-reviewable AI question drafts."""

from __future__ import annotations

import json
import math
import re
from collections.abc import Callable, Mapping
from typing import Any

from .token_factory import TokenFactoryClient


class QuizGenerationError(ValueError):
    """The model response cannot safely become a question draft."""


def _field(value: object, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _parse_json(content: object) -> Any:
    if not isinstance(content, str):
        raise QuizGenerationError("Model response content is not text")
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3 and lines[-1].strip().startswith("```"):
            text = "\n".join(lines[1:-1]).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise QuizGenerationError("Model returned invalid JSON") from exc


def generate_quiz(
    module: object,
    co: object,
    difficulty: str,
    count: int,
    client: TokenFactoryClient,
    *,
    model: str,
    usage_recorder: Callable[[dict[str, Any]], None] | None = None,
) -> list[dict[str, Any]]:
    """Generate exactly ``count`` validated multiple-choice question drafts.

    Generated questions are always ``status='draft'`` and ``source='AI'``;
    this function never approves or publishes them.
    """
    if count < 1:
        raise ValueError("count must be at least 1")
    if not isinstance(difficulty, str) or not difficulty.strip():
        raise ValueError("difficulty must be a non-empty string")
    module_id = _field(module, "id")
    co_id = _field(co, "id")
    co_number = _field(co, "number", _field(co, "co_number"))
    if not isinstance(module_id, str) or not module_id:
        raise ValueError("module must have a non-empty id")
    if not isinstance(co_id, str) or not co_id:
        raise ValueError("CO must have a non-empty id")
    if not isinstance(co_number, int) or isinstance(co_number, bool) or co_number < 1:
        raise ValueError("CO must have a positive integer number")

    module_context = {
        "id": module_id,
        "title": _field(module, "title", ""),
        "description": _field(module, "description", ""),
    }
    co_context = {
        "id": co_id,
        "number": co_number,
        "description": _field(co, "description", ""),
    }
    messages = [
        {
            "role": "system",
            "content": (
                "Create faculty-reviewable multiple-choice question drafts grounded only in the supplied module and CO. "
                "Return JSON only with exactly the requested number of questions. Each question must have a clear stem, "
                "exactly four distinct options, one correct_option index from 0 to 3, and the requested co_number. "
                "Do not approve or publish questions."
            ),
        },
        {
            "role": "user",
            "content": json.dumps({
                "module": module_context,
                "co": co_context,
                "difficulty": difficulty,
                "count": count,
                "required_shape": {
                    "questions": [{
                        "stem": "string",
                        "options": ["A", "B", "C", "D"],
                        "correct_option": 0,
                        "co_number": co_number,
                        "explanation": "string or null",
                        "difficulty": difficulty,
                        "bloom_level": "string or null",
                        "marks": 1,
                    }],
                },
            }, ensure_ascii=False),
        },
    ]

    response = client.chat(model=model, messages=messages, temperature=0)
    if usage_recorder is not None:
        usage = getattr(response, "usage", {}) or {}
        try:
            usage_recorder({
                "step": "quiz_generation",
                "model": model,
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "total_tokens": usage.get("total_tokens"),
            })
        except Exception:
            pass

    payload = _parse_json(getattr(response, "content", None))
    questions = payload.get("questions") if isinstance(payload, dict) else None
    if not isinstance(questions, list) or len(questions) != count:
        raise QuizGenerationError(f"Expected exactly {count} questions")

    validated: list[dict[str, Any]] = []
    stems_seen: set[str] = set()
    for index, question in enumerate(questions, start=1):
        if not isinstance(question, dict):
            raise QuizGenerationError(f"Question {index} must be an object")
        stem = question.get("stem")
        options = question.get("options")
        correct_option = question.get("correct_option")
        response_co = question.get("co_number")
        if not isinstance(stem, str) or not stem.strip():
            raise QuizGenerationError(f"Question {index} has an empty stem")
        normalized_stem = re.sub(r"\s+", " ", stem).strip().casefold()
        if normalized_stem in stems_seen:
            raise QuizGenerationError("Generated questions contain a duplicate stem")
        stems_seen.add(normalized_stem)
        if not isinstance(options, list) or len(options) != 4 or any(not isinstance(x, str) or not x.strip() for x in options):
            raise QuizGenerationError(f"Question {index} must have exactly four non-empty options")
        if len({re.sub(r"\s+", " ", x).strip().casefold() for x in options}) != 4:
            raise QuizGenerationError(f"Question {index} has duplicate options")
        if not isinstance(correct_option, int) or isinstance(correct_option, bool) or correct_option not in range(4):
            raise QuizGenerationError(f"Question {index} must have exactly one correct option index from 0 to 3")
        if not isinstance(response_co, int) or isinstance(response_co, bool) or response_co != co_number:
            raise QuizGenerationError(f"Question {index} does not match the requested CO")
        reported_difficulty = question.get("difficulty")
        if reported_difficulty is not None and (
            not isinstance(reported_difficulty, str)
            or reported_difficulty.strip().casefold() != difficulty.strip().casefold()
        ):
            raise QuizGenerationError(f"Question {index} does not match the requested difficulty")
        marks = question.get("marks", 1.0)
        if isinstance(marks, bool) or not isinstance(marks, (int, float)) or not math.isfinite(float(marks)) or marks <= 0:
            raise QuizGenerationError(f"Question {index} marks must be a positive number")
        explanation = question.get("explanation")
        if explanation is not None and not isinstance(explanation, str):
            raise QuizGenerationError(f"Question {index} explanation must be text or null")
        bloom_level = question.get("bloom_level")
        if bloom_level is not None and not isinstance(bloom_level, str):
            raise QuizGenerationError(f"Question {index} bloom_level must be text or null")

        validated.append({
            "module_id": module_id,
            "co_id": co_id,
            "co_number": co_number,
            "stem": stem.strip(),
            "options": [option.strip() for option in options],
            "correct_option": correct_option,
            "explanation": explanation,
            "marks": float(marks),
            "difficulty": difficulty,
            "bloom_level": bloom_level,
            "status": "draft",
            "source": "AI",
        })
    return validated
