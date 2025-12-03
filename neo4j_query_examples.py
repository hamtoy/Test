"""Neo4j Aura Query Examples
Neo4j Aura에 임포트된 데이터를 확인하고 활용하는 예제 쿼리들
"""

# ====================================
# 1. 데이터 확인 쿼리
# ====================================

# 전체 구조 시각화 (Guide 데이터)
"""
MATCH (c:Category)-[:HAS_SUBCATEGORY]->(s:Subcategory)-[:HAS_ITEM]->(i:Item)
RETURN c, s, i
LIMIT 50;
"""

# 전체 구조 시각화 (QnA 데이터)
"""
MATCH (c:QACategory)-[:HAS_SUBCATEGORY]->(s:QASubcategory)-[:HAS_TOPIC]->(t:QATopic)
RETURN c, s, t
LIMIT 50;
"""

# 노드 통계
"""
MATCH (n)
RETURN labels(n)[0] as NodeType, count(n) as Count
ORDER BY Count DESC;
"""

# 관계 통계
"""
MATCH ()-[r]->()
RETURN type(r) as RelationType, count(r) as Count
ORDER BY Count DESC;
"""

# ====================================
# 2. 카테고리별 조회
# ====================================

# 특정 카테고리의 모든 항목
"""
MATCH (c:Category {name: "작업 개요"})-[:HAS_SUBCATEGORY]->(s)-[:HAS_ITEM]->(i)
RETURN s.name as Subcategory, 
       i.name as Item, 
       substring(i.content, 0, 100) as ContentPreview
ORDER BY s.name, i.name;
"""

# QA 카테고리별 주제 조회
"""
MATCH (c:QACategory)-[:HAS_SUBCATEGORY]->(s)-[:HAS_TOPIC]->(t)
RETURN c.name as Category,
       s.name as Subcategory,
       t.name as Topic,
       substring(t.content, 0, 100) as ContentPreview
ORDER BY c.name, s.name, t.name;
"""

# ====================================
# 3. 검색 쿼리
# ====================================

# 내용 키워드 검색 (Guide)
"""
MATCH (i:Item)
WHERE i.content CONTAINS "이미지"
RETURN i.categoryName as Category,
       i.subcategoryName as Subcategory,
       i.name as Item,
       i.content
LIMIT 20;
"""

# 내용 키워드 검색 (QnA)
"""
MATCH (t:QATopic)
WHERE t.content CONTAINS "추론"
RETURN t.categoryName as Category,
       t.subcategoryName as Subcategory,
       t.name as Topic,
       substring(t.content, 0, 200) as ContentPreview
LIMIT 20;
"""

# 다중 키워드 검색 (OR 조건)
"""
MATCH (i:Item)
WHERE i.content CONTAINS "설명문" 
   OR i.content CONTAINS "요약문"
RETURN i.name, 
       substring(i.content, 0, 150) as Preview
LIMIT 15;
"""

# 다중 키워드 검색 (AND 조건)
"""
MATCH (t:QATopic)
WHERE t.content CONTAINS "질의" 
  AND t.content CONTAINS "답변"
RETURN t.name,
       substring(t.content, 0, 150) as Preview
LIMIT 15;
"""

# ====================================
# 4. 계층 구조 탐색
# ====================================

# 특정 Subcategory의 모든 하위 항목
"""
MATCH (s:Subcategory {name: "질의"})-[:HAS_ITEM]->(i:Item)
RETURN i.name as Item,
       i.content as Content
ORDER BY i.name;
"""

# 전체 계층 경로 출력
"""
MATCH path = (c:Category)-[:HAS_SUBCATEGORY]->(s:Subcategory)-[:HAS_ITEM]->(i:Item)
RETURN c.name as Category,
       s.name as Subcategory,
       i.name as Item,
       length(path) as PathLength
ORDER BY c.name, s.name, i.name
LIMIT 30;
"""

# ====================================
# 5. 통계 및 분석
# ====================================

# 카테고리별 항목 개수
"""
MATCH (c:Category)-[:HAS_SUBCATEGORY]->(s:Subcategory)-[:HAS_ITEM]->(i:Item)
RETURN c.name as Category,
       count(DISTINCT s) as SubcategoryCount,
       count(i) as ItemCount
ORDER BY ItemCount DESC;
"""

# Subcategory별 항목 개수
"""
MATCH (s:Subcategory)-[:HAS_ITEM]->(i:Item)
RETURN s.categoryName as Category,
       s.name as Subcategory,
       count(i) as ItemCount
ORDER BY ItemCount DESC;
"""

# QA 주제 개수 통계
"""
MATCH (c:QACategory)-[:HAS_SUBCATEGORY]->(s:QASubcategory)-[:HAS_TOPIC]->(t:QATopic)
RETURN c.name as Category,
       s.name as Subcategory,
       count(t) as TopicCount
ORDER BY TopicCount DESC;
"""

# ====================================
# 6. 고급 쿼리
# ====================================

# 내용이 가장 긴 항목 찾기
"""
MATCH (i:Item)
WHERE i.content IS NOT NULL
RETURN i.categoryName as Category,
       i.subcategoryName as Subcategory,
       i.name as Item,
       size(i.content) as ContentLength
ORDER BY ContentLength DESC
LIMIT 10;
"""

# 특정 패턴 찾기 (정규표현식)
"""
MATCH (t:QATopic)
WHERE t.content =~ ".*❌.*"
RETURN t.name as Topic,
       substring(t.content, 0, 200) as Preview
LIMIT 10;
"""

# 중복된 이름의 항목 찾기
"""
MATCH (i1:Item), (i2:Item)
WHERE i1.name = i2.name 
  AND id(i1) < id(i2)
RETURN i1.name as DuplicateName,
       i1.categoryName as Category1,
       i2.categoryName as Category2
LIMIT 10;
"""

# ====================================
# 7. 데이터 수정/업데이트
# ====================================

# 특정 항목의 내용 업데이트
"""
MATCH (i:Item {name: "1. 이미지의 대부분이 텍스트(한국어)로 구성되어 있을 것"})
SET i.updatedAt = datetime()
RETURN i.name, i.updatedAt;
"""

# 새로운 속성 추가
"""
MATCH (i:Item)
WHERE i.content IS NOT NULL
SET i.hasContent = true
RETURN count(i) as UpdatedCount;
"""

# ====================================
# 8. 전체 텍스트 검색 인덱스 (선택사항)
# ====================================

# 전체 텍스트 인덱스 생성
"""
CREATE FULLTEXT INDEX item_content_fulltext IF NOT EXISTS
FOR (i:Item) ON EACH [i.content];

CREATE FULLTEXT INDEX topic_content_fulltext IF NOT EXISTS
FOR (t:QATopic) ON EACH [t.content];
"""

# 전체 텍스트 검색 사용
"""
CALL db.index.fulltext.queryNodes('item_content_fulltext', '이미지 AND 텍스트')
YIELD node, score
RETURN node.name as Item, 
       node.categoryName as Category,
       score
ORDER BY score DESC
LIMIT 10;
"""

# ====================================
# 9. 데이터 내보내기
# ====================================

# CSV 형식으로 결과 내보내기 (Neo4j Browser에서 실행)
"""
MATCH (c:Category)-[:HAS_SUBCATEGORY]->(s:Subcategory)-[:HAS_ITEM]->(i:Item)
RETURN c.name as 대분류,
       s.name as 중분류,
       i.name as 소분류,
       i.content as 내용
ORDER BY c.name, s.name, i.name;
"""

# ====================================
# 10. 데이터 삭제
# ====================================

# 특정 카테고리와 모든 하위 데이터 삭제
"""
MATCH (c:Category {name: "작업 개요"})
DETACH DELETE c;
"""

# 모든 Guide 데이터 삭제
"""
MATCH (n)
WHERE n:Category OR n:Subcategory OR n:Item
DETACH DELETE n;
"""

# 모든 QnA 데이터 삭제
"""
MATCH (n)
WHERE n:QACategory OR n:QASubcategory OR n:QATopic
DETACH DELETE n;
"""

# 전체 데이터베이스 삭제 (주의!)
"""
MATCH (n)
DETACH DELETE n;
"""
