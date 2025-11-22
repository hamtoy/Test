"""
Session builder that assembles a 3-4 turn QA flow using the Jinja2 templates.

Rules enforced:
- 3~4 turns only.
- Exactly one of: Explanation or Summary. (Use Summary if text density is "high" and 4 turns are allowed; otherwise Explanation.)
- Include reasoning if required.
- Max 1 calculation/simple numeric request (tracked via used_calc_query_count + target calc_used).
- Avoid duplicate focus hints by passing prior_focus_summary/focus_history.
- Validates all generated prompts for forbidden patterns.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List
import re

from checks.detect_forbidden_patterns import find_violations


# Local render import
def render(template_path: str, context: Dict, root: Path) -> str:
    """Render a Jinja2 template."""
    from jinja2 import Environment, FileSystemLoader

    env = Environment(loader=FileSystemLoader(root / "templates"))
    template = env.get_template(template_path)
    return template.render(**context)


def is_calc_query(text: str) -> bool:
    """Heuristic: detect calculation-type questions (word-boundary for EN to avoid 'summary')."""
    calc_keywords_ko = [
        "합계", "총액", "차이", "증감", "증가율", "감소율", "비율", "퍼센트",
        "더해", "빼", "곱", "나눈",
    ]
    if any(kw in text for kw in calc_keywords_ko):
        return True
    # numeric percent
    if re.search(r"\d+\s*%", text):
        return True
    # English words with boundaries
    if re.search(r"\b(sum|difference|ratio|percentage)\b", text, flags=re.IGNORECASE):
        return True
    return False


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
    focus_history: List[str] = field(default_factory=list)


@dataclass
class Turn:
    type: str  # explanation | summary | target | reasoning
    prompt: str
    violations: List[Dict] = field(default_factory=list)
    calc_used: bool = False
    focus_hint: str = ""


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


def build_session(ctx: SessionContext, validate: bool = True) -> List[Turn]:
    validate_ctx(ctx)

    turns: List[Turn] = []
    used_calc = ctx.used_calc_query_count
    focus_history = list(ctx.focus_history) if ctx.focus_history else []
    if ctx.prior_focus_summary:
        focus_history.append(ctx.prior_focus_summary)

    root = repo_root()

    # 1) Explanation or Summary
    first_type = choose_expl_or_summary(ctx)
    first_template = f"system/text_image_qa_{first_type}_system.j2"
    prompt_text = render(first_template, ctx.__dict__, root)
    violations = find_violations(prompt_text) if validate else []
    turns.append(Turn(first_type, prompt_text, violations, calc_used=False, focus_hint=first_type))
    focus_history.append(first_type)

    # 2) Reasoning if required
    if ctx.must_include_reasoning:
        prompt_text = render(
            "system/text_image_qa_reasoning_system.j2", ctx.__dict__, root
        )
        violations = find_violations(prompt_text) if validate else []
        turns.append(Turn("reasoning", prompt_text, violations, calc_used=False, focus_hint="reasoning"))
        focus_history.append("reasoning")

    # 3) Fill remaining with target queries (respect calc limit metadata)
    while len(turns) < ctx.session_turns:
        calc_allowed = used_calc < 1
        uctx: Dict = {
            **ctx.__dict__,
            "prior_focus_summary": " | ".join(focus_history[-3:]),
            "used_calc_query_count": used_calc,
            "candidate_focus": "새로운 지점/항목",
            "calc_allowed": calc_allowed,
        }
        prompt_text = render("user/text_image_qa_target_user.j2", uctx, root)
        violations = find_violations(prompt_text) if validate else []
        calc_used_flag = is_calc_query(prompt_text)

        if calc_used_flag and not calc_allowed:
            violations.append({"type": "calc_limit", "match": "calc request exceeds limit", "span": (0, 0)})

        turns.append(
            Turn(
                "target",
                prompt_text,
                violations,
                calc_used=calc_used_flag,
                focus_hint=uctx["candidate_focus"],
            )
        )
        focus_history.append(uctx["candidate_focus"])
        if calc_used_flag:
            used_calc += 1

    return turns


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    ctx_path = repo_root / "examples" / "sample_image_meta.json"

    parser = argparse.ArgumentParser(
        description="Build a multi-turn QA session using templates."
    )
    parser.add_argument(
        "--context", default=str(ctx_path), help="Path to JSON context file."
    )
    parser.add_argument(
        "--no-validate", action="store_true", help="Disable forbidden pattern checks."
    )
    args = parser.parse_args()

    ctx_data = json.loads(Path(args.context).read_text(encoding="utf-8"))
    ctx = SessionContext(**ctx_data)
    session = build_session(ctx, validate=not args.no_validate)

    for i, turn in enumerate(session, 1):
        print(f"\n--- Turn {i} ({turn.type}) ---\n")
        print(turn.prompt)

        if turn.violations:
            print(
                f"\n⚠️  WARNING: {len(turn.violations)} forbidden pattern(s) detected:"
            )
            for v in turn.violations:
                print(f"   - {v['type']}: '{v['match']}' at position {v['span']}")


if __name__ == "__main__":
    main()
