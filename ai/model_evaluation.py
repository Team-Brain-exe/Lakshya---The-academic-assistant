"""Repeatable, human-reviewable model evaluation helpers.

This module never selects a model automatically. Use candidate IDs from your
Token Factory project and manually review semantic quality in the saved report.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from itertools import combinations
from pathlib import Path
from typing import Any

from backend.app.pipeline.ppt import parse_pptx

from .agent import AgentLoop, AgentTool, ToolRegistry
from .quiz_generation import generate_quiz
from .tagging import tag_content_with_COs


def summarize_tag_runs(
    chunk_ids: Sequence[str],
    runs: Sequence[Sequence[Mapping[str, Any]]],
) -> dict[str, Any]:
    """Measure repeat consistency; this is reliability, not semantic accuracy."""
    if not runs:
        raise ValueError("at least one tag run is required")

    run_maps: list[dict[str, list[int]]] = []
    for run in runs:
        current: dict[str, list[int]] = {}
        for item in run:
            chunk_id = item.get("chunk_id")
            cos = item.get("cos")
            if isinstance(chunk_id, str) and isinstance(cos, (list, tuple)):
                current[chunk_id] = sorted({int(n) for n in cos if isinstance(n, int) and not isinstance(n, bool)})
        run_maps.append(current)

    by_chunk: dict[str, dict[str, Any]] = {}
    chunk_exact: list[bool] = []
    all_pairwise_jaccards: list[float] = []
    for chunk_id in chunk_ids:
        tags_by_run = [run.get(chunk_id, []) for run in run_maps]
        exact = all(tags == tags_by_run[0] for tags in tags_by_run[1:])
        chunk_exact.append(exact)
        pairwise: list[float] = []
        for left, right in combinations(tags_by_run, 2):
            left_set, right_set = set(left), set(right)
            union = left_set | right_set
            score = len(left_set & right_set) / len(union) if union else 1.0
            pairwise.append(score)
        all_pairwise_jaccards.extend(pairwise)
        by_chunk[chunk_id] = {
            "tags_by_run": tags_by_run,
            "exact_agreement": exact,
            "mean_pairwise_jaccard": sum(pairwise) / len(pairwise) if pairwise else None,
        }

    return {
        "repeat_count": len(runs),
        "chunk_count": len(chunk_ids),
        "exact_agreement_rate": sum(chunk_exact) / len(chunk_exact) if chunk_exact else 0.0,
        "mean_pairwise_jaccard": (
            sum(all_pairwise_jaccards) / len(all_pairwise_jaccards)
            if all_pairwise_jaccards else None
        ),
        "by_chunk": by_chunk,
        "semantic_accuracy_review_required": True,
    }


def evaluate_tagging(
    deck_paths: Sequence[str | Path],
    cos: Sequence[Mapping[str, Any]],
    client: Any,
    *,
    model: str,
    repeats: int = 3,
    batch_size: int = 20,
    usage_recorder=None,
) -> dict[str, Any]:
    """Run Nano-style tagging repeatedly over explicitly supplied slide decks."""
    if len(deck_paths) < 2:
        raise ValueError("provide at least two slide decks for the tagging evaluation")
    if repeats < 2:
        raise ValueError("repeats must be at least 2")
    decks_report: list[dict[str, Any]] = []
    for deck_path in deck_paths:
        path = Path(deck_path)
        parsed = parse_pptx(path, include_notes=True)
        chunks = [
            {"id": f"{path.name}:slide-{chunk.slide_number}", "text": chunk.text}
            for chunk in parsed.chunks
        ]
        runs: list[list[dict[str, Any]]] = []
        for _ in range(repeats):
            result = tag_content_with_COs(
                chunks,
                cos,
                client,
                model=model,
                batch_size=batch_size,
                usage_recorder=usage_recorder,
            )
            runs.append(result)
        chunk_ids = [chunk["id"] for chunk in chunks]
        consistency = summarize_tag_runs(chunk_ids, runs)
        first_run = {item["chunk_id"]: item for item in runs[0]}
        decks_report.append({
            "deck": path.name,
            "total_slides": parsed.total_slides,
            "skipped_slides": list(parsed.skipped_slides),
            "consistency": consistency,
            "manual_review": [
                {
                    "chunk_id": chunk["id"],
                    "slide_number": int(chunk["id"].rsplit("-", 1)[1]),
                    "text_preview": chunk["text"][:240],
                    "tags_first_run": first_run.get(chunk["id"], {}).get("cos", []),
                }
                for chunk in chunks
            ],
        })
    return {
        "task": "co_tagging",
        "model": model,
        "repeats": repeats,
        "decks": decks_report,
        "review_note": "Consistency is automated; semantic tag correctness must be checked by a human against each slide.",
    }


def evaluate_quiz_generation(
    module: Mapping[str, Any],
    co: Mapping[str, Any],
    difficulty: str,
    count: int,
    client: Any,
    *,
    model: str,
    usage_recorder=None,
) -> dict[str, Any]:
    """Generate structurally checked drafts for a faculty member to read."""
    drafts = generate_quiz(
        module,
        co,
        difficulty,
        count,
        client,
        model=model,
        usage_recorder=usage_recorder,
    )
    return {
        "task": "quiz_generation",
        "model": model,
        "requested_co": co.get("number", co.get("co_number")),
        "requested_difficulty": difficulty,
        "drafts": drafts,
        "manual_review_required": [
            "factual correctness against the slides",
            "exactly one defensible correct answer",
            "plausibility and distinctness of distractors",
            "CO alignment and difficulty level",
        ],
    }


def evaluate_tool_calling(client: Any, *, model: str, usage_recorder=None, tool_usage_recorder=None) -> dict[str, Any]:
    """Exercise three harmless synthetic read-only tools with a live model."""
    data = {
        "get_demo_co_attainment": {"co_number": 1, "attainment_pct": 72},
        "get_demo_deadline": {"title": "Synthetic quiz", "starts_at": "2030-01-15T10:00:00Z"},
        "get_demo_module": {"module_id": "synthetic-module", "title": "Synthetic algorithms"},
    }
    tools = [
        AgentTool(
            name=name,
            description=f"Read synthetic test data for {name.removeprefix('get_demo_')}.",
            parameters={"type": "object", "properties": {}, "additionalProperties": False},
            roles=frozenset({"faculty"}),
            handler=lambda args, user, name=name: data[name],
        )
        for name in data
    ]
    loop = AgentLoop(
        client,
        model=model,
        tools=ToolRegistry(tools),
        max_steps=6,
        usage_recorder=usage_recorder,
        tool_usage_recorder=tool_usage_recorder,
    )
    response = loop.run(
        {"user_id": "synthetic-faculty", "role": "faculty"},
        "Using the tools, tell me the demo CO1 attainment, the demo deadline, and the demo module title.",
    )
    called = [item["name"] for item in response.tool_calls if item["status"] == "ok"]
    return {
        "task": "tool_calling",
        "model": model,
        "reply": response.reply,
        "tool_calls": response.tool_calls,
        "all_three_tools_called": set(called) == set(data),
        "loop_limited": response.loop_limited,
        "synthetic_data_only": True,
    }
