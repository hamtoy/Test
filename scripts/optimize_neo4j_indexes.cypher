// Neo4j Query Optimization - Index Creation
// 목표: template_rules.py의 쿼리 성능 개선 (982ms → 더 짧게)
// 1. Constraint 노드에 query_type 인덱스 생성
CREATE INDEX constraint_type_idx IF NOT EXISTS
FOR (c:Constraint)
ON (c.query_type);

// 2. FormattingRule 노드에 query_type 인덱스 생성
CREATE INDEX formatting_type_idx IF NOT EXISTS
FOR (f:FormattingRule)
ON (f.query_type);

// 3. BestPractice 노드에 query_type 인덱스 생성 (추가 최적화)
CREATE INDEX best_practice_type_idx IF NOT EXISTS
FOR (b:BestPractice)
ON (b.query_type);

// 4. Rule 노드에 query_type 인덱스 생성 (추가 최적화)
CREATE INDEX rule_type_idx IF NOT EXISTS
FOR (r:Rule)
ON (r.query_type);

// 5. 인덱스 상태 확인
SHOW INDEXES;

// 6. 쿼리 성능 프로파일링 (explanation 타입)
PROFILE
MATCH (c:Constraint {query_type: 'explanation'})
RETURN c;

// 7. 캐시 워밍업 (첫 조회를 미리 수행)
MATCH (c:Constraint)
RETURN c.query_type, count(*) AS cnt
ORDER BY cnt DESC;

MATCH (f:FormattingRule)
RETURN f.query_type, count(*) AS cnt
ORDER BY cnt DESC;

MATCH (b:BestPractice)
RETURN b.query_type, count(*) AS cnt
ORDER BY cnt DESC;

MATCH (r:Rule)
RETURN r.query_type, count(*) AS cnt
ORDER BY cnt DESC;