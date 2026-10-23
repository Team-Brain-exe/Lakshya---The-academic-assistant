"""Load the versioned agent-tool contracts and bind only implemented handlers."""

from __future__ import annotations

import json
from pathlib import Path
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from .agent import AgentTool, ToolRegistry


DEFAULT_MANIFEST = Path(__file__).resolve().parent / "schemas" / "agent-tools.json"
VALID_MUTATIONS = {"read_only", "draft_review", "confirm"}


class ToolManifestError(ValueError):
    pass


def load_tool_manifest(path: str | Path = DEFAULT_MANIFEST) -> list[dict[str, Any]]:
    """Read and sanity-check the shared contracts used by server/tool owners."""
    try:
        manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ToolManifestError("Could not read the agent-tool manifest") from exc
    if not isinstance(manifest, dict) or manifest.get("version") != 1:
        raise ToolManifestError("Unsupported or malformed agent-tool manifest")
    specs = manifest.get("tools")
    if not isinstance(specs, list):
        raise ToolManifestError("Agent-tool manifest must contain a tools array")

    seen: set[str] = set()
    for spec in specs:
        if not isinstance(spec, dict):
            raise ToolManifestError("Each tool contract must be an object")
        name = spec.get("name")
        if not isinstance(name, str) or not name or name in seen:
            raise ToolManifestError("Tool names must be unique non-empty strings")
        seen.add(name)
        if not isinstance(spec.get("description"), str) or not spec["description"].strip():
            raise ToolManifestError(f"{name}: description is required")
        if not isinstance(spec.get("roles"), list) or not spec["roles"]:
            raise ToolManifestError(f"{name}: at least one role is required")
        if not set(spec["roles"]) <= {"student", "faculty"}:
            raise ToolManifestError(f"{name}: unsupported role")
        if spec.get("mutation") not in VALID_MUTATIONS:
            raise ToolManifestError(f"{name}: unknown mutation policy")
        parameters = spec.get("parameters")
        if not isinstance(parameters, dict) or parameters.get("type") != "object":
            raise ToolManifestError(f"{name}: parameters must use an object schema")
    return specs


def build_tool_registry(
    handlers: Mapping[str, Callable[[dict[str, Any], dict[str, Any]], Any]],
    *,
    proposal_executors: Sequence[str] = (),
    strict: bool = False,
    manifest_path: str | Path = DEFAULT_MANIFEST,
) -> ToolRegistry:
    """Bind installed server functions to contracts without exposing stubs.

    Missing collaborator handlers are omitted when ``strict=False``. A confirm
    proposal is enabled only when its confirmation executor is configured.
    """
    specs = load_tool_manifest(manifest_path)
    executors = set(proposal_executors)
    tools: list[AgentTool] = []
    missing: list[str] = []
    for spec in specs:
        mutation = spec["mutation"]
        if mutation == "confirm":
            if spec["name"] not in executors:
                missing.append(spec["name"])
                continue
            handler = None
        else:
            handler = handlers.get(spec["name"])
            if handler is None:
                missing.append(spec["name"])
                continue
        tools.append(AgentTool(
            name=spec["name"],
            description=spec["description"],
            parameters=spec["parameters"],
            roles=frozenset(spec["roles"]),
            handler=handler,
            mutates=mutation != "read_only",
            confirmation_required=mutation == "confirm",
            review_required=mutation == "draft_review",
        ))
    if strict and missing:
        raise ToolManifestError(f"Handlers are not configured for: {', '.join(missing)}")
    return ToolRegistry(tools)
