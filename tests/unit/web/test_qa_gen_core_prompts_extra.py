"""Extra tests for qa_gen_core.prompts."""

from __future__ import annotations


import pytest

from src.web.routers.qa_gen_core import prompts


class _FakeSelector:
    def __init__(self, _kg: object) -> None:
        pass

    def select_best_examples(
        self,
        qtype: str,
        _ctx: object,
        k: int = 1,  # noqa: ARG002
    ) -> list[dict[str, str]]:
        return [{"example": f"example-{qtype}"}]


def test_build_length_constraint_branches() -> None:
    reasoning, _ = prompts.build_length_constraint("reasoning", 100)
    assert "200단어" in reasoning

    explanation, max_chars = prompts.build_length_constraint(
        "global_explanation",
        1000,
        ocr_text="단어 " * 100,
    )
    assert max_chars is not None
    assert "길이 제약" in explanation

    short, _ = prompts.build_length_constraint("target_short", 100)
    assert "1-2문장" in short

    long, _ = prompts.build_length_constraint("target_long", 100)
    assert "200-400자" in long


def test_build_extra_instructions_inserts_fewshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(prompts, "DynamicExampleSelector", _FakeSelector)
    txt = prompts.build_extra_instructions("reasoning", "reasoning", kg=object())
    assert "example-reasoning" in txt

    txt = prompts.build_extra_instructions(
        "global_explanation", "explanation", kg=object()
    )
    assert "example-explanation" in txt

    txt = prompts.build_extra_instructions("target_short", "target", kg=object())
    assert "example-target_short" in txt


def test_build_formatting_text_and_priority_hierarchy() -> None:
    fmt_target = prompts.build_formatting_text(["R1"], "target")
    assert "마크다운" in fmt_target

    fmt_exp = prompts.build_formatting_text([], "explanation")
    assert "JSON" in fmt_exp

    hierarchy = prompts.build_priority_hierarchy(
        "target",
        length_constraint="최대 100단어",
        formatting_text="",
    )
    assert "100단어" in hierarchy


def test_build_answer_prompt_combines_sections() -> None:
    prompt_text = prompts.build_answer_prompt(
        query="Q?",
        truncated_ocr="OCR",
        constraints_text="C",
        rules_in_answer="R",
        priority_hierarchy="P",
        length_constraint="L",
        formatting_text="F",
        difficulty_text="D",
        extra_instructions="E",
    )
    assert "OCR" in prompt_text and "Q?" in prompt_text
