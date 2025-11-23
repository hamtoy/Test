"""
Pipeline runner:
- builds a session
- validates core rules and forbidden patterns
- generates questions/answers via model client (stub by default)
- evaluates, rewrites, and fact-checks answers
"""

from __future__ import annotations

import argparse
import json
import sys
import re
from pathlib import Path
from typing import List

from checks.detect_forbidden_patterns import find_violations
from checks.validate_session import validate_turns
from scripts.build_session import (
    SessionContext,
    build_session,
    is_calc_query,
    repo_root,
)
from scripts.render_prompt import render


class ModelClient:
    """
    Simple model client with stubbed responses.
    Replace `generate` / `rewrite` / `fact_check` with real model calls as needed.
    """

    def __init__(self, stub: bool = True):
        self.stub = stub

    def generate(self, prompt: str, role: str = "default") -> str:
        if self.stub:
            return f"[{role} stub] {prompt[:200]}..."
        raise NotImplementedError("Model generation not implemented")

    def rewrite(self, text: str) -> str:
        if self.stub:
            return f"재작성: {text}"
        raise NotImplementedError("Model rewrite not implemented")

    def evaluate(self, question: str, answers: List[str]) -> dict:
        if self.stub:
            lengths = [len(a) for a in answers]
            best_idx = max(range(len(answers)), key=lambda i: lengths[i])
            return {
                "scores": lengths,
                "best_index": best_idx,
                "notes": "length heuristic",
            }
        raise NotImplementedError("Model eval not implemented")

    def fact_check(self, answer: str, has_table_chart: bool) -> dict:
        violations = find_violations(answer)
        table_refs = (
            re.findall(r"(표|그래프|table|chart)", answer, flags=re.IGNORECASE)
            if has_table_chart
            else []
        )
        if has_table_chart and table_refs:
            violations.append(
                {"type": "table_ref", "match": table_refs[0], "span": (0, 0)}
            )
        verdict = "fail" if violations else "pass"
        return {"verdict": verdict, "issues": violations}


def rerender_target(ctx_dict, root: Path, avoid_calc: bool, focus_hint: str):
    """Fallback re-render for target turns to avoid forbidden patterns or calc overuse."""
    uctx = {
        **ctx_dict,
        "prior_focus_summary": f"{ctx_dict.get('prior_focus_summary', '')} | avoid duplicates",
        "candidate_focus": focus_hint,
        "calc_allowed": not avoid_calc,
        "used_calc_query_count": ctx_dict.get("used_calc_query_count", 0),
    }
    return render("user/text_image_qa_target_user.j2", uctx, root)


def main() -> None:
    root = repo_root()
    default_ctx = root / "examples" / "session_input.json"

    parser = argparse.ArgumentParser(
        description="Run session build + validation pipeline."
    )
    parser.add_argument(
        "--context", default=str(default_ctx), help="Path to JSON context."
    )
    parser.add_argument(
        "--real-model",
        action="store_true",
        help="Use real model hooks (not implemented).",
    )
    args = parser.parse_args()

    ctx_data = json.loads(Path(args.context).read_text(encoding="utf-8"))
    ctx = SessionContext(**ctx_data)
    model = ModelClient(stub=not args.real_model)

    session = build_session(ctx, validate=True)

    used_calc = ctx.used_calc_query_count
    focus_history: List[str] = []

    # Generate content per turn; re-render targets on violations or calc overuse
    for turn in session:
        if turn.type == "target":
            attempts = 0
            while attempts < 3:
                question = model.generate(turn.prompt, role="target_question")
                turn.content = question
                calc_flag = is_calc_query(question)
                violations = find_violations(question)

                if calc_flag and used_calc >= 1:
                    turn.prompt = rerender_target(
                        ctx.__dict__,
                        root,
                        avoid_calc=True,
                        focus_hint="계산 없이 다른 부분 질문",
                    )
                    attempts += 1
                    continue

                if violations:
                    turn.prompt = rerender_target(
                        ctx.__dict__,
                        root,
                        avoid_calc=calc_flag,
                        focus_hint="표/그래프 언급 금지, 새 구역",
                    )
                    attempts += 1
                    continue

                turn.calc_used = calc_flag
                used_calc += 1 if calc_flag else 0
                focus_history.append(question[:80])
                break

        else:
            turn.content = model.generate(turn.prompt, role=turn.type)

    result = validate_turns(session, ctx)
    if result["ok"]:
        print("✅ Session validation passed")
    else:
        print("❌ Session validation failed:")
        for issue in result["issues"]:
            print(f" - {issue}")
        sys.exit(1)

    # Eval/Rewrite/Fact-check
    print("\n[Eval/Rewrite/Fact-check]")
    for idx, turn in enumerate(session, 1):
        if turn.type != "target":
            continue
        q = turn.content or turn.prompt
        answers = [model.generate(q, role=f"answer_{i}") for i in range(3)]
        eval_res = model.evaluate(q, answers)
        best_idx = eval_res.get("best_index")
        if best_idx is None or not (0 <= best_idx < len(answers)):
            print(f"- Turn {idx} ({turn.type}): best answer unavailable")
            continue

        best = answers[best_idx]
        rewritten = model.rewrite(best)
        fact_res = model.fact_check(rewritten, ctx.has_table_chart)
        print(
            f"- Turn {idx} ({turn.type}): best={best_idx}, fact={fact_res['verdict']}"
        )


if __name__ == "__main__":
    main()
