"""
Session builder that assembles a 3-4 turn QA flow using the Jinja2 templates.

Rules enforced:
- 3~4 turns only.
- Exactly one of: Explanation or Summary. (Use Summary if text density is "high" and 4 turns are allowed; otherwise Explanation.)
- Include reasoning if required.
- Max 1 calculation/simple numeric request (tracked via used_calc_query_count in context).
- Avoid duplicate focus hints by passing prior_focus_summary.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from scripts.render_prompt import render


@dataclass
class SessionContext:
    image_path: str
    language_hint: str
    text_density: str  # expect "low"|"medium"|"high"
    has_table_chart: bool
    session_turns: int
    must_include_reasoning: bool
    used_calc_query_count: int = 0
    prior_focus_summary: str = "N/A (first turn)"
    candidate_focus: str = "전체 본문을 골고루 커버"


@dataclass
class Turn:
    type: str  # explanation | summary | target | reasoning
    prompt: str


def choose_expl_or_summary(ctx: SessionContext) -> str:
    # Simple heuristic: use summary for 4-turn high-density sessions
    if ctx.text_density.lower() == "high" and ctx.session_turns >= 4:
        return "summary"
    return "explanation"


def validate_ctx(ctx: SessionContext) -> None:
    if ctx.session_turns not in (3, 4):
        raise ValueError("session_turns must be 3 or 4")

def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def build_session(ctx: SessionContext) -> List[Turn]:
    validate_ctx(ctx)

    turns: List[Turn] = []
    used_calc = ctx.used_calc_query_count

    root = repo_root()

    # 1) Explanation or Summary
    first_type = choose_expl_or_summary(ctx)
    first_template = f"system/text_image_qa_{first_type}_system.j2"
    turns.append(Turn(first_type, render(first_template, ctx.__dict__, root)))

    # 2) Reasoning if required
    if ctx.must_include_reasoning:
        turns.append(Turn("reasoning", render("system/text_image_qa_reasoning_system.j2", ctx.__dict__, root)))

    # 3) Fill remaining with target queries (respect calc limit metadata)
    while len(turns) < ctx.session_turns:
        uctx: Dict = {
            **ctx.__dict__,
            "prior_focus_summary": "cover different sections than previous turns",
            "used_calc_query_count": used_calc,
            "candidate_focus": "새로운 지점/항목",
        }
        turns.append(Turn("target", render("user/text_image_qa_target_user.j2", uctx, root)))

    return turns


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    ctx_path = repo_root / "examples" / "sample_image_meta.json"

    parser = argparse.ArgumentParser(description="Build a multi-turn QA session using templates.")
    parser.add_argument("--context", default=str(ctx_path), help="Path to JSON context file.")
    args = parser.parse_args()

    ctx_data = json.loads(Path(args.context).read_text(encoding="utf-8"))
    ctx = SessionContext(**ctx_data)
    session = build_session(ctx)

    for i, turn in enumerate(session, 1):
        print(f"\n--- Turn {i} ({turn.type}) ---\n")
        print(turn.prompt)


if __name__ == "__main__":
    main()
