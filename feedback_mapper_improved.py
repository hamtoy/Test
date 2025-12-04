# mypy: ignore-errors
"""피드백 데이터 매핑 실행 스크립트 (개선 버전)

사용자 검토 결과 반영:
- 중복 Rule 방지 (MERGE 사용)
- priority 타입 통일 (문자열)
- Constraint 스키마 정합성 확보
- Example id는 UUID 사용
- Phase 2는 수동 샘플 검증용으로 분리
"""

import os
from typing import Dict

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")


class FeedbackMapper:
    """피드백 데이터를 기존 QA 시스템에 매핑"""

    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def phase1_create_rules(self) -> Dict:
        """Phase 1: FeedbackCategory → Rule 매핑 (중복 방지)"""
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (fc:FeedbackCategory)
                CALL {
                    WITH fc
                    MERGE (r:Rule {id: 'rule_feedback_' + toLower(replace(fc.name, '/', '_'))})
                    ON CREATE SET
                        r.text = fc.name + ' 관련 검수 기준을 준수해야 합니다',
                        r.priority = CASE
                            WHEN fc.name IN ['형식 오류', '문법/맞춤법'] THEN 'high'
                            WHEN fc.name = '사실성 오류' THEN 'critical'
                            ELSE 'medium'
                        END,
                        r.source = 'feedback_analysis',
                        r.category = fc.name,
                        r.created_at = datetime()
                    ON MATCH SET
                        r.updated_at = datetime()
                    MERGE (fc)-[:GENERATED_RULE]->(r)
                    RETURN r
                }
                RETURN count(*) AS rules_processed
                """
            )
            count = result.single()["rules_processed"]

            # 통계 조회
            stats_result = session.run(
                """
                MATCH (fc:FeedbackCategory)-[:GENERATED_RULE]->(r:Rule)
                RETURN fc.name AS category, r.priority AS priority
                ORDER BY fc.name
                """
            )
            stats = [
                (record["category"], record["priority"]) for record in stats_result
            ]

            return {"rules_processed": count, "details": stats}

    def phase3_create_constraints(self) -> Dict:
        """Phase 3: 핵심 Constraint 생성 (패턴 기반)"""
        constraints = [
            {
                "id": "temporal_expression_check",
                "type": "content_validation",
                "description": '시의성 표현(최근, 현재, 올해 등) 사용 시 "(이미지 기준)" 표기 필수',
                "pattern": "(최근|현재|올해|전일|전월|지난달)",
                "severity": "high",
                "source": "feedback_97_cases",
            },
            {
                "id": "repetition_check",
                "type": "content_validation",
                "description": "동일한 표현/서술어 반복 사용 금지",
                "max_repetition": 2,
                "severity": "medium",
                "source": "feedback_123_cases",
            },
            {
                "id": "formatting_rules",
                "type": "structure_validation",
                "description": "목록형 답변 형식 검증: 문단 구분 없음, 불릿 간격 일관성, 볼드체 규칙 등",
                "severity": "high",
                "rules": [
                    "no_paragraph_in_list",
                    "consistent_bullet_spacing",
                    "bold_for_main_items",
                ],
                "source": "feedback_196_cases",
            },
        ]

        created = []
        with self.driver.session() as session:
            for constraint in constraints:
                # 기본 필드 추출
                base_fields = {
                    "id": constraint["id"],
                    "type": constraint["type"],
                    "description": constraint["description"],
                    "severity": constraint["severity"],
                    "source": constraint["source"],
                }

                # 동적 필드 설정
                set_clauses = []
                params = base_fields.copy()

                for key, value in constraint.items():
                    if key not in base_fields and isinstance(value, (list, str, int)):
                        set_clauses.append(f"c.{key} = ${key}")
                        params[key] = value

                set_clause = ", ".join(set_clauses) if set_clauses else ""

                query = f"""
                MERGE (c:Constraint {{id: $id}})
                ON CREATE SET
                    c.type = $type,
                    c.description = $description,
                    c.severity = $severity,
                    c.source = $source,
                    c.created_at = datetime()
                    {", " + set_clause if set_clause else ""}
                ON MATCH SET
                    c.updated_at = datetime()
                RETURN c.id AS constraint_id
                """

                result = session.run(query, **params)
                created.append(result.single()["constraint_id"])

            # FeedbackCategory와 Constraint 연결
            session.run(
                """
                MATCH (fc:FeedbackCategory {name: '시의성 표현'})
                MATCH (c:Constraint {id: 'temporal_expression_check'})
                MERGE (fc)-[:SUGGESTS_CONSTRAINT]->(c)
                """
            )

            session.run(
                """
                MATCH (fc:FeedbackCategory {name: '반복 표현'})
                MATCH (c:Constraint {id: 'repetition_check'})
                MERGE (fc)-[:SUGGESTS_CONSTRAINT]->(c)
                """
            )

            session.run(
                """
                MATCH (fc:FeedbackCategory {name: '형식 오류'})
                MATCH (c:Constraint {id: 'formatting_rules'})
                MERGE (fc)-[:SUGGESTS_CONSTRAINT]->(c)
                """
            )

        return {"constraints_created": len(created), "ids": created}

    def verify_mappings(self) -> Dict:
        """매핑 결과 검증"""
        with self.driver.session() as session:
            # Rule 매핑 확인
            rule_count = session.run(
                """
                MATCH (fc:FeedbackCategory)-[:GENERATED_RULE]->(r:Rule)
                RETURN count(r) AS count
                """
            ).single()["count"]

            # Constraint 매핑 확인
            constraint_count = session.run(
                """
                MATCH (fc:FeedbackCategory)-[:SUGGESTS_CONSTRAINT]->(c:Constraint)
                RETURN count(c) AS count
                """
            ).single()["count"]

            # 통계
            stats = session.run(
                """
                MATCH (fc:FeedbackCategory)
                OPTIONAL MATCH (fc)-[:GENERATED_RULE]->(r:Rule)
                OPTIONAL MATCH (fc)-[:SUGGESTS_CONSTRAINT]->(c:Constraint)
                OPTIONAL MATCH (fc)<-[:CATEGORIZED_AS]-(f:Feedback)
                RETURN fc.name AS category,
                       count(DISTINCT r) AS rules,
                       count(DISTINCT c) AS constraints,
                       count(DISTINCT f) AS feedbacks
                ORDER BY feedbacks DESC
                """
            )

            details = [
                {
                    "category": record["category"],
                    "rules": record["rules"],
                    "constraints": record["constraints"],
                    "feedbacks": record["feedbacks"],
                }
                for record in stats
            ]

            return {
                "total_rules": rule_count,
                "total_constraints": constraint_count,
                "by_category": details,
            }


def main():
    """메인 실행 함수"""
    mapper = FeedbackMapper(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)

    try:
        print("=" * 60)
        print("피드백 데이터 매핑 실행 (개선 버전)")
        print("=" * 60)

        # Phase 1: Rule 생성
        print("\n[Phase 1] FeedbackCategory → Rule 매핑")
        print("-" * 60)
        phase1_result = mapper.phase1_create_rules()
        print(f"✅ 처리된 Rule: {phase1_result['rules_processed']}개")
        print("\n카테고리별 상세:")
        for category, priority in phase1_result["details"]:
            print(f"  • {category}: priority={priority}")

        # Phase 3: Constraint 생성
        print("\n[Phase 3] 핵심 Constraint 생성")
        print("-" * 60)
        phase3_result = mapper.phase3_create_constraints()
        print(f"✅ 생성된 Constraint: {phase3_result['constraints_created']}개")
        for cid in phase3_result["ids"]:
            print(f"  • {cid}")

        # 검증
        print("\n[검증] 매핑 결과 확인")
        print("-" * 60)
        verification = mapper.verify_mappings()
        print(f"✅ 총 Rule 매핑: {verification['total_rules']}개")
        print(f"✅ 총 Constraint 매핑: {verification['total_constraints']}개")

        print("\n카테고리별 상세 통계:")
        print(f"{'카테고리':<15} {'Rule':<8} {'Constraint':<12} {'피드백':<8}")
        print("-" * 60)
        for item in verification["by_category"]:
            print(
                f"{item['category']:<15} {item['rules']:<8} "
                f"{item['constraints']:<12} {item['feedbacks']:<8}"
            )

        print("\n" + "=" * 60)
        print("✅ 매핑 완료!")
        print("=" * 60)
        print("\n[다음 단계]")
        print("1. Neo4j Browser에서 결과 확인")
        print("   MATCH (fc:FeedbackCategory)-[:GENERATED_RULE]->(r:Rule) RETURN fc, r")
        print("2. 검증 코드에서 새로운 Constraint 활용")
        print("3. Phase 2 (Example 추가)는 선택적으로 수동 진행")

    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback

        traceback.print_exc()

    finally:
        mapper.close()


if __name__ == "__main__":
    main()
