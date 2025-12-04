// 피드백 경향성 분석을 위한 Cypher 쿼리 모음
// 1. 가장 많이 지적받는 피드백 유형 TOP 5
MATCH (c:FeedbackCategory)<-[:CATEGORIZED_AS]-(f:Feedback)
RETURN c.name AS 카테고리, count(f) AS 피드백수
ORDER BY 피드백수 DESC
LIMIT 5;

// 2. 전체 피드백 분포 (비율 포함)
MATCH (f:Feedback)
WITH count(f) AS total
MATCH (c:FeedbackCategory)<-[:CATEGORIZED_AS]-(fb:Feedback)
RETURN
  c.name AS 카테고리,
  count(fb) AS 개수,
  round(count(fb) * 100.0 / total, 2) AS 비율
ORDER BY 개수 DESC;

// 3. 복합 카테고리 분석 (여러 카테고리에 동시에 속하는 피드백)
MATCH (f:Feedback)-[:CATEGORIZED_AS]->(c:FeedbackCategory)
WITH f, collect(c.name) AS categories
WHERE size(categories) > 1
RETURN f.line_number AS 라인번호, categories AS 카테고리들, f.content AS 내용
ORDER BY size(categories) DESC
LIMIT 10;

// 4. 특정 카테고리의 피드백 샘플 조회 (예: 형식 오류)
MATCH (f:Feedback)-[:CATEGORIZED_AS]->(c:FeedbackCategory {name: '형식 오류'})
RETURN f.line_number AS 라인번호, f.content AS 피드백내용
ORDER BY f.line_number
LIMIT 10;

// 5. 카테고리가 없는 피드백 (일반 코멘트)
MATCH (f:Feedback)
WHERE NOT (f)-[:CATEGORIZED_AS]->()
RETURN f.line_number AS 라인번호, f.content AS 내용
LIMIT 20;

// 6. 특정 키워드가 포함된 피드백 검색 (예: "삭제")
MATCH (f:Feedback)
WHERE f.content CONTAINS '삭제'
RETURN f.line_number AS 라인번호, f.content AS 내용
LIMIT 10;

// 7. 카테고리별 평균 피드백 길이
MATCH (f:Feedback)-[:CATEGORIZED_AS]->(c:FeedbackCategory)
RETURN c.name AS 카테고리, round(avg(size(f.content)), 2) AS 평균길이, count(f) AS 피드백수
ORDER BY 평균길이 DESC;

// 8. 연관 카테고리 분석 (함께 나타나는 카테고리)
MATCH (f:Feedback)-[:CATEGORIZED_AS]->(c1:FeedbackCategory)
MATCH (f)-[:CATEGORIZED_AS]->(c2:FeedbackCategory)
WHERE c1.name < c2.name
RETURN c1.name AS 카테고리1, c2.name AS 카테고리2, count(f) AS 함께발생횟수
ORDER BY 함께발생횟수 DESC
LIMIT 10;