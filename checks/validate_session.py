"""Validate a built session against core rules and forbidden patterns.

Checks:
- turn count (3~4)
- exactly one of {explanation, summary}
- reasoning included when required
- forbidden patterns in prompts
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

from checks.detect_forbidden_patterns import find_violations
from scripts.build_session import (
    SessionContext,
    build_session,
    repo_root as builder_root,
)


def validate_turns(turns, ctx: SessionContext) -> Dict:
    issues: List[str] = []
    types = [t.type for t in turns]
    calc_used_count = sum(1 for t in turns if getattr(t, "calc_used", False))

    if len(turns) not in (3, 4):
        issues.append(f"turn count must be 3 or 4, got {len(turns)}")

    expl_sum = sum(1 for t in types if t in ("explanation", "summary"))
    if expl_sum != 1:
        issues.append(f"must include exactly one explanation/summary, got {expl_sum}")

    if ctx.must_include_reasoning and "reasoning" not in types:
        issues.append("reasoning turn is required but missing")

    if ctx.used_calc_query_count + calc_used_count > 1:
        issues.append(
            f"calculation requests exceeded: ctx={ctx.used_calc_query_count}, targets={calc_used_count}"
        )

    # pattern scan (lightweight)
    for idx, t in enumerate(turns, 1):
        v = find_violations(t.prompt)
        if v:
            issues.append(f"turn {idx} ({t.type}) forbidden patterns: {v}")

    return {"ok": not issues, "issues": issues}


def main() -> None:
    default_ctx = builder_root() / "examples" / "session_input.json"

    parser = argparse.ArgumentParser(description="Validate a generated session.")
    parser.add_argument(
        "--context", default=str(default_ctx), help="Path to JSON context."
    )
    args = parser.parse_args()

    ctx_data = json.loads(Path(args.context).read_text(encoding="utf-8"))
    ctx = SessionContext(**ctx_data)
    session = build_session(ctx)

    result = validate_turns(session, ctx)
    if result["ok"]:
        print("✅ Session validation passed")
        sys.exit(0)
    else:
        print("❌ Session validation failed:")
        for issue in result["issues"]:
            print(f" - {issue}")
        sys.exit(1)


if __name__ == "__main__":
    main()
