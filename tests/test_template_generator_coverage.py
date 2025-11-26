from __future__ import annotations

from jinja2 import DictLoader, Environment
from src import dynamic_template_generator as dtg
from tests.conftest import MockDriver


def test_dynamic_template_generator_fallback_and_checklist(monkeypatch):
    # Set required environment variables for Neo4j
    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
    monkeypatch.setenv("NEO4J_USER", "neo4j")
    monkeypatch.setenv("NEO4J_PASSWORD", "password")

    # Import the actual template_generator module to patch the right namespace
    from src.processing import template_generator

    driver = MockDriver(
        [
            [
                {
                    "type_name": "설명",
                    "rules": ["r1"],
                    "constraints": ["c1"],
                    "best_practices": ["bp1"],
                    "examples": [{"text": "ex1", "type": "positive"}],
                }
            ],
            [{"item": "규칙을 따를 것", "category": "rule"}],
        ]
    )

    class _GraphDB:
        @staticmethod
        def driver(*_args, **_kwargs):
            return driver

    monkeypatch.setattr(template_generator, "GraphDatabase", _GraphDB)

    env = Environment(
        loader=DictLoader({"base_system.j2": "{{query_type_korean}}|{{rules|length}}"})
    )
    generator = dtg.DynamicTemplateGenerator("uri", "user", "pw")
    generator.jinja_env = env  # use in-memory template to trigger fallback

    prompt = generator.generate_prompt_for_query_type(
        "explanation", {"calc_allowed": False}
    )
    assert "설명" in prompt
    generator._run = lambda _cypher, _params=None: [  # noqa: SLF001
        {"item": "규칙을 따를 것", "category": "rule"}
    ]
    checklist = generator.generate_validation_checklist(
        {"turns": [{"type": "explanation"}]}
    )
    assert checklist == [
        {"item": "규칙을 따를 것", "category": "rule", "query_type": "explanation"}
    ]
    generator.close()
