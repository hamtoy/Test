from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from neo4j.exceptions import Neo4jError

from src.gemini_model_client import GeminiModelClient
from src.qa_rag_system import QAKnowledgeGraph


class GraphEnhancedRouter:
    """
    Neo4j 그래프의 QueryType 정보를 활용해 최적 체인을 선택하고 실행합니다.
    """

    def __init__(
        self,
        kg: Optional[QAKnowledgeGraph] = None,
        llm: Optional[GeminiModelClient] = None,
    ):
        self.kg = kg or QAKnowledgeGraph()
        self.llm = llm or GeminiModelClient()

    def route_and_generate(
        self, user_input: str, handlers: Dict[str, Callable[[str], Any]]
    ) -> Dict[str, Any]:
        """
        사용자의 입력을 분석해 타입을 선택하고 해당 핸들러를 실행합니다.
        handlers: {"explanation": func, "summary": func, ...}
        """

        qtypes = self._fetch_query_types()
        prompt = self._build_router_prompt(user_input, qtypes)
        choice = self.llm.generate(prompt, role="router").strip().lower()

        # 선택 결과 정규화
        chosen: Optional[str] = None
        for qt in qtypes:
            if qt["name"].lower() in choice:
                chosen = qt["name"]
                break
        if not chosen:
            if any(q.get("name") == "explanation" for q in qtypes):
                chosen = "explanation"
            elif qtypes:
                first_name = qtypes[0].get("name")
                chosen = str(first_name) if first_name is not None else "explanation"
            else:
                chosen = "explanation"

        output = None
        if chosen in handlers:
            output = handlers[chosen](user_input)

        self._log_routing(user_input, chosen)

        return {"choice": chosen, "output": output}

    def _fetch_query_types(self) -> List[Dict[str, Any]]:
        try:
            with self.kg._graph.session() as session:  # noqa: SLF001
                rows = session.run(
                    """
                    MATCH (qt:QueryType)
                    RETURN qt.name AS name,
                           qt.korean AS korean,
                           qt.session_limit AS limit
                    """
                )
                return [dict(r) for r in rows]
        except Neo4jError:
            return []
        except Exception:
            return []

    def _build_router_prompt(
        self, user_input: str, qtypes: List[Dict[str, Any]]
    ) -> str:
        desc_lines = []
        for qt in qtypes:
            name = qt.get("name", "")
            ko = qt.get("korean", "")
            limit = qt.get("limit", "")
            desc_lines.append(f"- {name} ({ko}), limit: {limit}")
        desc_text = "\n".join(desc_lines) or "(등록된 QueryType 없음)"

        return f"""다음 사용자 입력에 가장 적합한 질의 유형을 한 단어로 선택하세요.

사용자 입력:
{user_input}

가능한 질의 유형:
{desc_text}

출력은 질의 유형 이름만 적으세요."""

    def _log_routing(self, input_text: str, chosen: str) -> None:
        try:
            with self.kg._graph.session() as session:  # noqa: SLF001
                session.run(
                    """
                    CREATE (r:RoutingLog {
                        input: $input,
                        chosen: $chosen,
                        timestamp: datetime()
                    })
                    """,
                    input=input_text,
                    chosen=chosen,
                )
        except Neo4jError:
            pass
        except Exception:
            pass
