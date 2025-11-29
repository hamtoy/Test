from src.qa.rag_system import QAKnowledgeGraph
from typing import Any, Generator


class _FakeSession:
    def __init__(self, rows: Any) -> None:
        self.rows = rows

    def __enter__(self) -> Any:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> Any:
        return False

    def run(self, cypher: Any, **params: Any) -> Generator[Any, None, None]:  # noqa: ARG002
        for r in self.rows:
            yield r


class _FakeGraph:
    def __init__(self, rows: Any) -> None:
        self.rows = rows

    def session(self) -> Any:
        return _FakeSession(self.rows)

    def close(self) -> Any:
        return None


def _make_kg(rows: Any) -> Any:
    kg = object.__new__(QAKnowledgeGraph)
    kg._graph = _FakeGraph(rows)  # type: ignore[assignment]
    kg._graph_provider = None
    kg._graph_finalizer = None
    kg._vector_store = None
    kg.neo4j_uri = "uri"
    kg.neo4j_user = "user"
    kg.neo4j_password = "pwd"
    return kg


class _UpsertFakeSession:
    """
    세션 모킹: 업서트 쿼리 테스트를 위한 fake session.
    - 실행된 Cypher 쿼리 및 파라미터를 기록
    - 노드 존재 여부 확인 쿼리에 대한 응답 설정 가능
    """

    def __init__(self, existing_nodes: Any = None) -> None:
        self.queries: list[tuple[Any, Any]] = []  # (cypher, params) 튜플 기록
        self.existing_nodes = existing_nodes or set()  # 존재하는 노드 ID 집합

    def __enter__(self) -> Any:
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> Any:
        return False

    def run(self, cypher: Any, **params: Any) -> Any:
        # 쿼리 즉시 기록 (generator 시작 전에)
        self.queries.append((cypher, params))

        # generator wrapper 반환
        return self._generate_results(cypher, params)

    def _generate_results(
        self, cypher: Any, params: Any
    ) -> Generator[dict[str, Any], None, None]:
        """결과를 yield하는 내부 generator."""
        # 존재 여부 확인 쿼리 처리
        if "MATCH (r:Rule {id: $id}) RETURN" in cypher:
            if params.get("id") in self.existing_nodes:
                yield {"existing_batch_id": "old_batch"}
            return
        if "MATCH (c:Constraint {id: $id}) RETURN" in cypher:
            if params.get("id") in self.existing_nodes:
                yield {"batch_id": "old_batch"}
            return
        if "MATCH (b:BestPractice {id: $id}) RETURN" in cypher:
            if params.get("id") in self.existing_nodes:
                yield {"batch_id": "old_batch"}
            return
        if "MATCH (e:Example {id: $id}) RETURN" in cypher:
            if params.get("id") in self.existing_nodes:
                yield {"batch_id": "old_batch"}
            return

        # count 쿼리 처리 (롤백용)
        if "RETURN count(n) as cnt" in cypher:
            yield {"cnt": 3}
            return

        # batch_id로 노드 조회 처리
        if "WHERE n.batch_id = $batch_id" in cypher and "labels(n)" in cypher:
            yield {
                "labels": ["Rule"],
                "id": "rule_001",
                "created_at": "2024-01-01T12:00:00Z",
                "updated_at": "2024-01-01T12:00:00Z",
                "auto_generated": True,
            }
            return

        # MERGE/DELETE 등 다른 쿼리는 결과 없음
        return


class _UpsertFakeGraph:
    """업서트 테스트를 위한 fake graph driver."""

    def __init__(self, existing_nodes: Any = None) -> None:
        self.existing_nodes = existing_nodes or set()
        self.sessions: list[_UpsertFakeSession] = []

    def session(self) -> Any:
        s = _UpsertFakeSession(self.existing_nodes)
        self.sessions.append(s)
        return s

    def close(self) -> Any:
        return None


def _make_upsert_kg(existing_nodes: Any = None) -> Any:
    """업서트 테스트용 QAKnowledgeGraph 생성."""
    kg = object.__new__(QAKnowledgeGraph)
    kg._graph = _UpsertFakeGraph(existing_nodes)  # type: ignore[assignment]
    kg._graph_provider = None
    kg._graph_finalizer = None
    kg._vector_store = None
    kg.neo4j_uri = "uri"
    kg.neo4j_user = "user"
    kg.neo4j_password = "pwd"
    return kg


def test_get_constraints_for_query_type() -> None:
    rows = [{"id": "1", "description": "desc", "type": "t", "pattern": None}]
    kg = _make_kg(rows)
    res = kg.get_constraints_for_query_type("explanation")
    assert res[0]["description"] == "desc"


def test_get_best_practices() -> None:
    rows = [{"id": "bp1", "text": "practice"}]
    kg = _make_kg(rows)
    res = kg.get_best_practices("summary")
    assert res[0]["text"] == "practice"


def test_get_examples() -> None:
    rows = [{"id": "ex1", "text": "example", "type": "positive"}]
    kg = _make_kg(rows)
    res = kg.get_examples(limit=1)
    assert res[0]["id"] == "ex1"


def test_find_relevant_rules_without_vector_store() -> None:
    kg = _make_kg([])
    assert kg.find_relevant_rules("q") == []


# =========================================================================
# 자동 생성 규칙 업서트 테스트
# =========================================================================


def test_upsert_auto_generated_rules_creates_new_nodes() -> None:
    """새로운 Rule, Constraint, BestPractice, Example 노드 생성 테스트."""
    kg = _make_upsert_kg()

    patterns = [
        {
            "id": "rule_001",
            "rule": "표 참조 금지",
            "type_hint": "explanation",
            "constraint": "표/그래프 인용 불가",
            "best_practice": "본문 텍스트만 인용",
            "example_before": "표에 따르면 A=100",
            "example_after": "A는 100이다",
        }
    ]

    result = kg.upsert_auto_generated_rules(patterns, batch_id="test_batch")

    assert result["success"] is True
    assert result["batch_id"] == "test_batch"
    assert result["created"]["rules"] == 1
    assert result["created"]["constraints"] == 1
    assert result["created"]["best_practices"] == 1
    assert result["created"]["examples"] == 1
    assert result["updated"]["rules"] == 0
    assert len(result["errors"]) == 0


def test_upsert_auto_generated_rules_updates_existing_nodes() -> None:
    """기존 노드가 존재할 때 업데이트 테스트."""
    # 기존 노드가 존재하는 상황 시뮬레이션
    existing_nodes = {"rule_002", "rule_002_constraint"}
    kg = _make_upsert_kg(existing_nodes)

    patterns = [
        {
            "id": "rule_002",
            "rule": "업데이트된 규칙",
            "type_hint": "summary",
            "constraint": "업데이트된 제약",
        }
    ]

    result = kg.upsert_auto_generated_rules(patterns, batch_id="update_batch")

    assert result["success"] is True
    assert result["updated"]["rules"] == 1  # 기존 노드 업데이트
    assert result["updated"]["constraints"] == 1
    assert result["created"]["best_practices"] == 0  # best_practice 없음
    assert result["created"]["examples"] == 0  # example 없음


def test_upsert_auto_generated_rules_generates_batch_id() -> None:
    """batch_id 미지정 시 자동 생성 테스트."""
    kg = _make_upsert_kg()

    patterns = [{"id": "rule_003", "rule": "자동 배치 테스트", "type_hint": "target"}]
    result = kg.upsert_auto_generated_rules(patterns)

    assert result["success"] is True
    assert result["batch_id"].startswith("batch_")
    assert len(result["batch_id"]) > 10  # batch_YYYYMMDD_HHMMSS 형식


def test_upsert_auto_generated_rules_handles_missing_fields() -> None:
    """필수 필드(id, rule) 누락 시 오류 처리 테스트."""
    kg = _make_upsert_kg()

    patterns = [
        {"type_hint": "explanation"},  # id, rule 누락
        {"id": "rule_004"},  # rule 누락
        {"id": "rule_005", "rule": "정상 규칙", "type_hint": "reasoning"},
    ]

    result = kg.upsert_auto_generated_rules(patterns, batch_id="partial_batch")

    # 2개 오류, 1개 성공
    assert len(result["errors"]) == 2
    assert result["created"]["rules"] == 1


def test_upsert_auto_generated_rules_only_rule() -> None:
    """Rule만 있고 다른 필드가 없는 경우 테스트."""
    kg = _make_upsert_kg()

    patterns = [{"id": "rule_only", "rule": "규칙만 있음", "type_hint": "explanation"}]

    result = kg.upsert_auto_generated_rules(patterns, batch_id="rule_only_batch")

    assert result["success"] is True
    assert result["created"]["rules"] == 1
    assert result["created"]["constraints"] == 0
    assert result["created"]["best_practices"] == 0
    assert result["created"]["examples"] == 0


def test_upsert_auto_generated_rules_with_example_only() -> None:
    """Example만 있는 경우 (before만, after만, 둘 다) 테스트."""
    kg = _make_upsert_kg()

    patterns = [
        {
            "id": "rule_ex1",
            "rule": "before만 있는 예시",
            "type_hint": "summary",
            "example_before": "잘못된 예시",
        },
        {
            "id": "rule_ex2",
            "rule": "after만 있는 예시",
            "type_hint": "target",
            "example_after": "수정된 예시",
        },
    ]

    result = kg.upsert_auto_generated_rules(patterns, batch_id="example_batch")

    assert result["success"] is True
    assert result["created"]["examples"] == 2


def test_get_rules_by_batch_id() -> None:
    """batch_id로 노드 조회 테스트."""
    kg = _make_upsert_kg()

    nodes = kg.get_rules_by_batch_id("some_batch_id")

    assert len(nodes) == 1
    assert nodes[0]["id"] == "rule_001"
    assert nodes[0]["auto_generated"] is True
    assert "Rule" in nodes[0]["labels"]


def test_rollback_batch() -> None:
    """batch_id로 노드 일괄 삭제 (롤백) 테스트."""
    kg = _make_upsert_kg()

    result = kg.rollback_batch("batch_to_delete")

    assert result["success"] is True
    assert result["deleted_count"] == 3  # _UpsertFakeSession에서 3 반환

    # 세션이 생성되었는지 확인
    sessions = kg._graph.sessions
    assert len(sessions) > 0

    # 모든 세션에서 실행된 쿼리들 확인
    all_queries = []
    for session in sessions:
        all_queries.extend(session.queries)

    # 카운트 쿼리와 삭제 쿼리가 실행되었는지 확인
    count_query_executed = any("count(n)" in q[0] for q in all_queries)
    delete_query_executed = any("DETACH DELETE" in q[0] for q in all_queries)

    assert count_query_executed
    assert delete_query_executed


def test_multiple_patterns_in_single_call() -> None:
    """여러 패턴을 한 번에 처리하는 테스트."""
    kg = _make_upsert_kg()

    patterns = [
        {"id": f"rule_{i}", "rule": f"규칙 {i}", "type_hint": "explanation"}
        for i in range(5)
    ]

    result = kg.upsert_auto_generated_rules(patterns, batch_id="multi_batch")

    assert result["success"] is True
    assert result["created"]["rules"] == 5
