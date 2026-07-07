"""``python -m langops`` CLI — currently: replay a captured execution.

    python -m langops replay <execution-id> --app myapp.main:graph \
        [--api-url http://localhost:8000] [--input input.json] \
        [--model gpt-5] [--temperature 0.2] [--same-thread]

``--app`` is a ``module:attribute`` pointing at an already-instrumented,
compiled graph. The graph runs locally in your environment.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
from typing import Any


def _load_graph(spec: str) -> Any:
    if ":" not in spec:
        raise SystemExit(f"--app must be 'module:attribute', got {spec!r}")
    module_name, attr = spec.split(":", 1)
    module = importlib.import_module(module_name)
    return getattr(module, attr)


def _run_replay(args: argparse.Namespace) -> int:
    from langops import replay
    from langops._replay import ReplayError

    graph = _load_graph(args.app)
    override_input = None
    if args.input:
        with open(args.input, encoding="utf-8") as fh:
            override_input = json.load(fh)
    try:
        result = replay(
            graph,
            args.execution_id,
            api_url=args.api_url,
            input=override_input,
            model=args.model,
            temperature=args.temperature,
            same_thread=args.same_thread,
        )
    except ReplayError as exc:
        print(f"replay failed: {exc}", file=sys.stderr)
        return 1
    print("replay complete. New execution captured; open the dashboard to inspect it.")
    print(json.dumps(result, default=str, indent=2)[:2000])
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="langops")
    sub = parser.add_subparsers(dest="command", required=True)

    rp = sub.add_parser("replay", help="re-run a captured execution locally")
    rp.add_argument("execution_id")
    rp.add_argument("--app", required=True, help="module:attribute of the instrumented graph")
    rp.add_argument("--api-url", default="http://localhost:8000")
    rp.add_argument("--input", help="JSON file replacing the recorded input")
    rp.add_argument("--model", help="override model id (recorded + passed via configurable)")
    rp.add_argument("--temperature", type=float, help="override temperature")
    rp.add_argument("--same-thread", action="store_true", help="reuse the recorded thread id")
    rp.set_defaults(func=_run_replay)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
