"""CLI for manual Token Factory model selection and quality evaluation.

Examples:
  python -m ai.evaluate_models tagging --decks deck1.pptx deck2.pptx --cos-file cos.json
  python -m ai.evaluate_models quiz --module-json module.json --co-json co.json --difficulty medium --count 5
  python -m ai.evaluate_models tool-calling

The CLI reads credentials from the project .env/process environment and writes
only evaluation output to the selected report path. It never chooses model IDs.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .config import AIConfig, AIConfigurationError
from .model_evaluation import evaluate_quiz_generation, evaluate_tagging, evaluate_tool_calling


def _read_json(path: str) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Could not read valid JSON from {path}") from exc


def _write_report(report: dict[str, Any], output: str | None) -> None:
    text = json.dumps(report, indent=2, ensure_ascii=False)
    if output:
        destination = Path(output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text + "\n", encoding="utf-8")
        print(f"Wrote evaluation report: {destination}")
    else:
        print(text)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate candidate Nebius Token Factory models")
    commands = parser.add_subparsers(dest="task", required=True)

    tagging = commands.add_parser("tagging", help="Repeat CO tagging over at least two slide decks")
    tagging.add_argument("--decks", nargs="+", required=True, help="Paths to 2+ .pptx decks")
    tagging.add_argument("--cos-file", required=True, help="JSON file containing [{number, description}, ...]")
    tagging.add_argument("--repeats", type=int, default=3)
    tagging.add_argument("--batch-size", type=int, default=20)
    tagging.add_argument("--model", help="Candidate model ID; defaults to MODEL_TAGGING")
    tagging.add_argument("--output", help="Optional JSON report path")

    quiz = commands.add_parser("quiz", help="Generate structurally validated quiz drafts for faculty review")
    quiz.add_argument("--module-json", required=True, help="JSON object with id/title/description")
    quiz.add_argument("--co-json", required=True, help="JSON object with id/number/description")
    quiz.add_argument("--difficulty", choices=["easy", "medium", "hard"], required=True)
    quiz.add_argument("--count", type=int, default=3)
    quiz.add_argument("--model", help="Candidate model ID; defaults to MODEL_GENERATION")
    quiz.add_argument("--output", help="Optional JSON report path")

    tool = commands.add_parser("tool-calling", help="Try three harmless synthetic tools with the agent model")
    tool.add_argument("--model", help="Candidate model ID; defaults to MODEL_AGENT")
    tool.add_argument("--output", help="Optional JSON report path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    usage: list[dict[str, Any]] = []
    client = None
    try:
        config = AIConfig.from_env()
        task_key = {"tagging": "tagging", "quiz": "generation", "tool-calling": "agent"}[args.task]
        model = args.model or config.model_for(task_key)
        client = config.create_client()

        if args.task == "tagging":
            cos = _read_json(args.cos_file)
            if not isinstance(cos, list) or not all(isinstance(item, dict) for item in cos):
                raise ValueError("CO file must contain a JSON array of objects")
            report = evaluate_tagging(
                args.decks,
                cos,
                client,
                model=model,
                repeats=args.repeats,
                batch_size=args.batch_size,
                usage_recorder=usage.append,
            )
        elif args.task == "quiz":
            module = _read_json(args.module_json)
            co = _read_json(args.co_json)
            if not isinstance(module, dict) or not isinstance(co, dict):
                raise ValueError("Module and CO JSON files must each contain an object")
            report = evaluate_quiz_generation(
                module,
                co,
                args.difficulty,
                args.count,
                client,
                model=model,
                usage_recorder=usage.append,
            )
        else:
            report = evaluate_tool_calling(client, model=model, usage_recorder=usage.append)
        report["usage"] = usage
        report["live_provider_test"] = True
        _write_report(report, args.output)
        return 0
    except (AIConfigurationError, ValueError, OSError) as exc:
        print(f"Evaluation could not run: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        # Do not print request headers, credentials, or provider response bodies.
        print(f"Evaluation failed: {type(exc).__name__}", file=sys.stderr)
        return 1
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    raise SystemExit(main())
