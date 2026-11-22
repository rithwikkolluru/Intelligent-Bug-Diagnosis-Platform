"""
CLI runner for Log Analysis and Triage agents.

Usage:
  python -m app.agents.run --agent triage --text "SIGSEGV in memory allocator, core dumped"
  python -m app.agents.run --agent log_analysis --file data/samples/agents/java_crash.txt
  python -m app.agents.run --agent both --file data/samples/agents/java_crash.txt --json
  python -m app.agents.run --agent both --text "NPE in handler" --no-llm
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from app.agents.base import AgentInput
from app.agents.log_analysis.agent import LogAnalysisAgent
from app.agents.triage.agent import TriageAgent


def _make_input(args: argparse.Namespace) -> AgentInput:
    text = ""
    if args.file:
        path = Path(args.file)
        if not path.exists():
            print(f"Error: File not found: {path}", file=sys.stderr)
            sys.exit(1)
        text = path.read_text(encoding="utf-8")
    elif args.text:
        text = args.text
    else:
        print("Error: Provide --file or --text", file=sys.stderr)
        sys.exit(1)

    return AgentInput(
        bug_id=None,
        title=args.title or text[:80].replace("\n", " "),
        description=text,
        stack_trace=text if any(kw in text for kw in ["Traceback", "at ", "Exception", "Error:"]) else None,
        error_logs=None,
        programming_language=args.language,
    )


def _run(args: argparse.Namespace) -> None:
    agent_input = _make_input(args)

    if args.no_llm:
        os.environ["LLM_PROVIDER"] = "none"

    results: dict = {}

    if args.agent in ("triage", "both"):
        agent = TriageAgent()
        result = agent.run(agent_input)
        results["triage"] = {
            "status": result.status,
            "output": result.output.model_dump(mode="json") if result.output else None,
            "provenance": result.provenance,
            "duration_ms": result.duration_ms,
            "warnings": result.warnings,
        }

    if args.agent in ("log_analysis", "both"):
        agent = LogAnalysisAgent()
        result = agent.run(agent_input)
        results["log_analysis"] = {
            "status": result.status,
            "output": result.output.model_dump(mode="json") if result.output else None,
            "provenance": result.provenance,
            "duration_ms": result.duration_ms,
            "warnings": result.warnings,
        }

    if args.json:
        print(json.dumps(results, indent=2, default=str))
    else:
        for agent_name, data in results.items():
            print(f"\n{'='*60}")
            print(f"Agent: {agent_name.upper()}")
            print(f"Status: {data['status']}")
            print(f"Duration: {data['duration_ms']:.1f}ms")
            print(f"Method: {data['provenance'].get('method', 'unknown')}")
            if data["output"]:
                print("\nOutput:")
                for k, v in data["output"].items():
                    if v is not None and v != [] and v != {}:
                        print(f"  {k}: {v}")
            if data["warnings"]:
                print(f"\nWarnings: {data['warnings']}")
        print(f"\n{'='*60}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Triage or Log Analysis agents on a sample bug.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--agent",
        choices=["triage", "log_analysis", "both"],
        default="both",
        help="Which agent(s) to run",
    )
    parser.add_argument("--file", metavar="PATH", help="Path to input file")
    parser.add_argument("--text", metavar="TEXT", help="Inline text input")
    parser.add_argument("--title", metavar="TITLE", help="Bug title (optional)")
    parser.add_argument("--language", metavar="LANG", help="Programming language hint")
    parser.add_argument("--no-llm", action="store_true", help="Force rule-only mode (no LLM calls)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--bug-id", type=int, help="Bug ID (for record-keeping)")
    args = parser.parse_args()
    _run(args)


if __name__ == "__main__":
    main()
