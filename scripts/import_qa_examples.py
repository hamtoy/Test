"""
통과된 QA 질문-답변을 Neo4j Example 노드로 저장하는 스크립트
"""

import hashlib
import re
from typing import Dict, List

from dotenv import load_dotenv

from src.neo4j_utils import get_neo4j_driver_from_env

load_dotenv()


class QAExampleImporter:
    def __init__(self):
        self._safe_driver = get_neo4j_driver_from_env()
        self.driver = self._safe_driver.driver

    def parse_qa_text(self, text: str) -> List[Dict]:
        """
        텍스트에서 질문-답변 쌍 추출

        Format:
        Q: 질문
        A: 답변
        ---
        """
        qa_pairs = []

        # 간단한 패턴: Q:/A: 구분
        pattern = r"Q[:\s]+(.*?)\s+A[:\s]+(.*?)(?=Q:|$)"
        matches = re.finditer(pattern, text, re.DOTALL | re.MULTILINE)

        for match in matches:
            question = match.group(1).strip()
            answer = match.group(2).strip()

            if question and answer:
                qa_pairs.append({"question": question, "answer": answer})

        return qa_pairs

    def save_to_neo4j(
        self,
        qa_pairs: List[Dict],
        query_type: str = "general",
        status: str = "approved",
    ):
        """
        QA 쌍을 Neo4j Example 노드로 저장

        Args:
            qa_pairs: 질문-답변 쌍 리스트
            query_type: 질의 유형 (explanation, summary, target, etc.)
            status: approved/rejected
        """
        with self.driver.session() as session:
            for qa in qa_pairs:
                # 해시 기반 ID
                qa_text = f"{qa['question']}|{qa['answer']}"
                example_id = (
                    f"example_{hashlib.sha256(qa_text.encode()).hexdigest()[:16]}"
                )

                # Example 노드 생성
                session.run(
                    """
                    MERGE (e:Example {id: $id})
                    SET e.question = $question,
                        e.answer = $answer,
                        e.query_type = $query_type,
                        e.status = $status,
                        e.type = 'positive',
                        e.success_rate = 1.0,
                        e.usage_count = 0,
                        e.created_at = datetime(),
                        e.source = 'manual_import'
                """,
                    id=example_id,
                    question=qa["question"],
                    answer=qa["answer"],
                    query_type=query_type,
                    status=status,
                )

                # QueryType 노드와 연결
                session.run(
                    """
                    MATCH (e:Example {id: $example_id})
                    MERGE (qt:QueryType {name: $query_type})
                    MERGE (e)-[:FOR_TYPE]->(qt)
                """,
                    example_id=example_id,
                    query_type=query_type,
                )

            print(f"✅ {len(qa_pairs)}개 Example 저장 완료!")

    def close(self):
        self._safe_driver.close()


# 사용 예시
if __name__ == "__main__":
    # 샘플 QA 텍스트
    sample_text = """
    Q: 미국 증시 동향을 설명해줘
    A: 본문에 따르면, 미국 증시는 다음과 같은 동향을 보였습니다.
    
    * 다우지수: 1.51% 하락
    * 나스닥: 2.60% 하락
    * S&P500: 1.84% 하락
    
    금리 급등과 인플레이션 우려로 인해 투자심리가 위축되었습니다.
    
    ---
    
    Q: 설명문과 요약문의 차이는?
    A: 설명문은 사례와 구체적 수치를 포함하여 자료의 80% 이상을 다루며,
    요약문은 함축적으로 작성하여 설명문 분량의 약 20% 수준으로 작성합니다.
    """

    importer = QAExampleImporter()

    # 파싱
    qa_pairs = importer.parse_qa_text(sample_text)
    print(f"📝 {len(qa_pairs)}개 QA 쌍 추출")

    # 저장
    importer.save_to_neo4j(qa_pairs, query_type="explanation", status="approved")

    importer.close()
