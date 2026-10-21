"""Coverage: how many slide chunks are mapped to each CO.

A CO with no chunks gets a warning, because no quiz question can be grounded in
slides for it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence


@dataclass(frozen=True)
class COCoverage:
    co: int
    chunk_count: int
    warning: bool
    message: str | None


def coverage(
    co_numbers: Sequence[int], links: Iterable[tuple[str, int]]
) -> list[COCoverage]:
    """links is (chunk_id, co_number) pairs. Each chunk counts once per CO."""
    chunks_by_co: dict[int, set[str]] = {co: set() for co in co_numbers}
    for chunk_id, co in links:
        if co in chunks_by_co:
            chunks_by_co[co].add(chunk_id)

    out: list[COCoverage] = []
    for co in sorted(chunks_by_co):
        count = len(chunks_by_co[co])
        warn = count == 0
        out.append(
            COCoverage(
                co=co,
                chunk_count=count,
                warning=warn,
                message=f"No slides are mapped to CO{co}." if warn else None,
            )
        )
    return out
