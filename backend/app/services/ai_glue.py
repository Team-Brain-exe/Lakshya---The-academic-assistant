"""Connects Arya's features to Danwin's Token Factory client.

Every function here is optional glue: if Token Factory is not configured, or a call
fails, the caller falls back to the grounded, code-only path (slide text, no LLM), so
a missing key never breaks the demo and no answer is ever invented. Every provider
call is written to agent_logs with its token counts, which feeds the cost page.

Step names written to agent_logs: tagging, qa, flashcards, study_plan.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any, Callable, Sequence

from ..pg.usage import PostgresUsageStore
from .qa import NotInSlidesError
from .usage import log_ai_call

log = logging.getLogger(__name__)

# step -> env vars to try, in order
_MODEL_ENV = {
    "tagging": ("MODEL_TAGGING", "MODEL_GENERATION", "MODEL_AGENT"),
    "qa": ("MODEL_REASONING", "MODEL_AGENT", "MODEL_GENERATION"),
    "flashcards": ("MODEL_GENERATION", "MODEL_AGENT"),
    "study_plan": ("MODEL_GENERATION", "MODEL_AGENT"),
}


def model_for(step: str) -> str | None:
    for name in _MODEL_ENV.get(step, ("MODEL_GENERATION",)):
        value = (os.getenv(name) or "").strip()
        if value:
            return value
    return None


def get_client() -> Any | None:
    """A TokenFactoryClient, or None when the key or base URL is not set."""
    key = (os.getenv("TOKEN_FACTORY_API_KEY") or "").strip()
    base = (os.getenv("TOKEN_FACTORY_BASE_URL") or "").strip()
    if not key or not base:
        return None
    from ai.token_factory import TokenFactoryClient  # imported late: optional dependency

    return TokenFactoryClient(api_key=key, base_url=base)


class UsageRecorder:
    """Writes provider calls to agent_logs through the shared connection."""

    def __init__(self, conn: Any, user: dict | None) -> None:
        self.store = PostgresUsageStore(conn)
        self.user_id = (user or {}).get("user_id")
        self.role = (user or {}).get("role")

    def ai_call(
        self,
        step: str,
        model: str,
        usage: dict[str, Any] | None,
        *,
        latency_ms: int | None = None,
        error: str | None = None,
        summary: str | None = None,
    ) -> None:
        usage = usage or {}
        try:
            log_ai_call(
                self.store,
                step,
                model,
                int(usage.get("prompt_tokens") or 0),
                int(usage.get("completion_tokens") or 0),
                user_id=self.user_id,
                role=self.role,
                latency_ms=latency_ms,
                result_summary=summary,
                error=error,
            )
        except Exception:  # logging must never break the feature
            log.exception("could not write agent_logs row")

    def tagging_hook(self) -> Callable[[dict[str, Any]], None]:
        """usage_recorder for ai.tagging.tag_content_with_COs (one call per provider attempt)."""

        def record(item: dict[str, Any]) -> None:
            self.ai_call(
                "tagging",
                item.get("model") or model_for("tagging") or "unknown",
                item,
                error=item.get("error"),
                summary=f"batch {item.get('batch_number')} attempt {item.get('attempt')}",
            )

        return record


def _parse_json(content: str | None) -> Any:
    text_ = (content or "").strip()
    if text_.startswith("```"):
        lines = text_.splitlines()
        if len(lines) >= 3:
            text_ = "\n".join(lines[1:-1]).strip()
    match = re.search(r"[\[{].*[\]}]", text_, flags=re.DOTALL)
    if not match:
        raise ValueError("model did not return JSON")
    return json.loads(match.group(0))


def _chat(client: Any, recorder: UsageRecorder, step: str, system: str, user: str, *, max_tokens: int, temperature: float) -> str:
    model = model_for(step)
    if not model:
        raise RuntimeError(f"No model configured for step {step!r}")
    started = time.monotonic()
    try:
        result = client.chat(
            model=model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except Exception as exc:
        recorder.ai_call(step, model, None, latency_ms=int((time.monotonic() - started) * 1000), error=str(exc)[:300])
        raise
    recorder.ai_call(step, model, result.usage, latency_ms=int((time.monotonic() - started) * 1000))
    if not result.content:
        raise ValueError("empty model response")
    return result.content


# ---------------------------------------------------------------------------
# Tagging (upload pipeline)
# ---------------------------------------------------------------------------

def make_tagger(client: Any | None, recorder: UsageRecorder):
    """Tagger for process_module_upload. Without a client, nothing is tagged (never fails)."""
    model = model_for("tagging")
    if client is None or not model:
        log.warning("Token Factory not configured: chunks will be saved untagged")
        return lambda chunks, cos: []

    from ai.tagging import tag_content_with_COs

    def tagger(chunks: Sequence[Any], cos: Sequence[Any]):
        return tag_content_with_COs(chunks, cos, client, model=model, usage_recorder=recorder.tagging_hook())

    return tagger


# ---------------------------------------------------------------------------
# Slide-grounded Q&A
# ---------------------------------------------------------------------------

QA_SYSTEM = (
    "You answer a student's question using ONLY the slide excerpts provided. "
    "Cite slides as [Slide N]. If the excerpts do not contain the answer, reply exactly: "
    "NOT_IN_SLIDES. Do not use outside knowledge. Keep the answer under 150 words."
)


def make_qa_client(client: Any | None, recorder: UsageRecorder):
    """ai_client for answer_from_course_material: (question, context) -> answer text."""
    if client is None or not model_for("qa"):
        return None

    def ask(question: str, context: str) -> str:
        reply = _chat(
            client, recorder, "qa", QA_SYSTEM,
            f"Slide excerpts:\n{context}\n\nQuestion: {question}",
            max_tokens=400, temperature=0.1,
        ).strip()
        if "NOT_IN_SLIDES" in reply:
            raise NotInSlidesError()  # the Q&A service turns this into a refusal
        return reply

    return ask


# ---------------------------------------------------------------------------
# Flashcards and notes (once per module)
# ---------------------------------------------------------------------------

MATERIAL_SYSTEM = (
    "You write study material from lecture slides. Use ONLY the slide text given. "
    "Return JSON only: {\"flashcards\": [{\"slide_number\": int, \"front\": str, \"back\": str}], "
    "\"notes\": [{\"slide_number\": int, \"title\": str, \"body\": str}]}. "
    "Write 1 flashcard and at most 1 note per content-bearing slide. Keep each back/body under 60 words."
)


def make_material_generator(client: Any | None, recorder: UsageRecorder, chunks_for_co: Sequence[dict[str, Any]]):
    """generator for generate_module_study_material, or None to use the grounded fallback."""
    if client is None or not model_for("flashcards"):
        return None
    co_by_slide = {c["slide_number"]: c.get("co_id") for c in chunks_for_co}

    def generator(module_title: str, chunks: Sequence[dict[str, Any]]):
        blocks = "\n\n".join(
            f"[Slide {c['slide_number']}]\n{(c.get('text') or '')[:600]}" for c in list(chunks)[:40]
        )
        raw = _chat(
            client, recorder, "flashcards", MATERIAL_SYSTEM,
            f"Module: {module_title}\n\n{blocks}", max_tokens=3000, temperature=0.3,
        )
        data = _parse_json(raw)
        cards = [
            {"co_id": co_by_slide.get(c.get("slide_number")), "front": str(c["front"]).strip(), "back": str(c["back"]).strip()}
            for c in data.get("flashcards", [])
            if isinstance(c, dict) and c.get("front") and c.get("back") and c.get("slide_number") in co_by_slide
        ]
        notes = [
            {"co_id": co_by_slide.get(n.get("slide_number")), "title": str(n["title"]).strip(), "body": str(n["body"]).strip()}
            for n in data.get("notes", [])
            if isinstance(n, dict) and n.get("title") and n.get("body") and n.get("slide_number") in co_by_slide
        ]
        if not cards:
            raise ValueError("model returned no usable flashcards")
        return cards, notes

    return generator


# ---------------------------------------------------------------------------
# Study plan
# ---------------------------------------------------------------------------

PLAN_SYSTEM = (
    "You are a study coach. For each weak Course Outcome, write a short, specific study "
    "recommendation (max 40 words) that refers only to the slide summaries given. "
    "Return JSON only: {\"CO3\": \"recommendation\", ...}."
)


def make_plan_generator(
    client: Any | None,
    recorder: UsageRecorder,
    co_configs: dict[int, dict[str, Any]],
):
    """ai_generator for build_study_plan, or None to use the grounded builder.

    Slides and flashcards are always linked in code from the database; the model only
    writes the recommendation text, so it can never invent a slide.
    """
    if client is None or not model_for("study_plan"):
        return None

    def generator(weak_cos: list[int], slides: list[dict[str, Any]], cards: list[dict[str, Any]]):
        steps: list[dict[str, Any]] = []
        digest: dict[str, str] = {}
        for co in weak_cos:
            cfg = co_configs.get(co, {})
            rel_slides = [
                {"module_id": s.get("module_id"), "slide_number": s.get("slide_number"), "summary": (s.get("text") or "")[:120]}
                for s in slides if s.get("co_number") == co
            ][:5]
            rel_cards = [
                {"id": c.get("id"), "front": c.get("front"), "back": c.get("back")}
                for c in cards if c.get("co_number") == co
            ][:5]
            steps.append({
                "co_number": co,
                "goal": f"Master CO{co}: {cfg.get('description', '')}".strip(),
                "recommendation": (
                    f"Review the {len(rel_slides)} linked slides, then practise with the "
                    f"{len(rel_cards)} flashcards to reach the {cfg.get('threshold_pct', 60)}% threshold."
                ),
                "slides": rel_slides,
                "flashcards": rel_cards,
            })
            digest[f"CO{co}"] = f"{cfg.get('description', '')} | slides: " + "; ".join(
                f"slide {s['slide_number']}: {s['summary']}" for s in rel_slides
            )
        try:
            raw = _chat(
                client, recorder, "study_plan", PLAN_SYSTEM,
                json.dumps(digest), max_tokens=900, temperature=0.3,
            )
            advice = _parse_json(raw)
            for step in steps:
                text_ = advice.get(f"CO{step['co_number']}")
                if isinstance(text_, str) and text_.strip():
                    step["recommendation"] = text_.strip()
        except Exception:  # keep the code-built recommendations
            log.warning("study plan AI call failed; using grounded recommendations", exc_info=True)
        return steps

    return generator
