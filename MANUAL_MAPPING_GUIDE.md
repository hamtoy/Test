# 수동 매핑 분석 결과

## 📊 분석 결과 요약

### 현재 상태

- 자동 매핑 실행 결과: **0개 관계 생성**
- 이유: CSV 데이터와 기존 Neo4j 데이터 간의 **직접적인 이름 매칭이 없음**

### 발견된 데이터 구조

#### 기존 Neo4j 데이터

- **Block**: 1,692개
- **Rule**: 126개  
- **Example**: 51개
- **Constraint**: 16개
- **QueryType**: 6개
- **BestPractice**: 4개
- **Template**: 4개
- **ErrorPattern**: 4개

#### 새로 임포트된 CSV 데이터

- **Guide 데이터**: Category(3) → Subcategory(5) → Item(25)
- **QnA 데이터**: QACategory(2) → QASubcategory(7) → QATopic(22)

## 💡 수동 매핑 제안

### 1. Item (질의 관련) → QueryType

**대상 Item:**

- 1. 설명문 질의
- 2. 요약문 질의
- 3. 이미지 내 타겟 질의
- 4. 추론 질의
- 5. 내용 분석 질의
- 7. 계산 요청 질의

**매핑 방법:**

```cypher
// 수동으로 각 질의 타입과 QueryType 연결
MATCH (i:Item {name: "1. 설명문 질의"})
MATCH (qt:QueryType {name: "explanation"})
MERGE (i)-[:DESCRIBES_QUERY_TYPE]->(qt);

MATCH (i:Item {name: "4. 추론 질의"})
MATCH (qt:QueryType {name: "reasoning"})
MERGE (i)-[:DESCRIBES_QUERY_TYPE]->(qt);
```

### 2. Item (작업 규칙) → Rule

**대상 Item:**

- 1. 답변 구조 ⭐
- 2. 반복 문구 사용 지양 ⭐
- 3. 시의성 표현
- 6. 기호 사용 규칙
- 1. 목록 형식
- 등...

**매핑 방법:**

```cypher
// 작업 규칙 Item을 Rule로 직접 연결
MATCH (i:Item)
WHERE i.categoryName = "작업 규칙"
WITH i
MATCH (r:Rule)
WHERE toLower(r.content) CONTAINS toLower(i.name)
   OR toLower(i.content) CONTAINS toLower(r.name)
MERGE (i)-[:DEFINES_RULE]->(r);
```

### 3. QATopic (FAQ) → Example

**대상 QATopic:**

- 1. 문장이 부자연스러운 경우
- 2. 설명문/요약문 답변
- 3. 내용 분석 답변
- 등 (예시가 포함된 모든 Topic)

**매핑 방법:**

```cypher
// FAQ 내용에 예시가 포함된 경우 Example과 연결
MATCH (t:QATopic)
WHERE t.content CONTAINS "예시" 
   OR t.content CONTAINS "❌"
   OR t.content CONTAINS "⭕"
WITH t
MATCH (e:Example)
MERGE (t)-[:CONTAINS_EXAMPLE]->(e);
```

### 4. Item → Constraint (제약조건)

**대상 Item:**

- "불가", "금지", "반드시" 포함한 항목들

**매핑 방법:**

```cypher
// 제약조건 관련 키워드가 포함된 Item
MATCH (i:Item)
WHERE i.content CONTAINS "불가" 
   OR i.content CONTAINS "금지"
   OR i.content CONTAINS "반드시"
   OR i.content CONTAINS "지양"
WITH i
MATCH (c:Constraint)
WHERE c.queryType IN ["explanation", "reasoning", "target_short", "target_long"]
MERGE (i)-[:ENFORCES_CONSTRAINT]->(c);
```

### 5. Item → BestPractice

**대상 Item:**

- "지향", "권장", "주의사항" 포함한 항목들

**매핑 방법:**

```cypher
// Best Practice 관련 키워드가 포함된 Item
MATCH (i:Item)
WHERE i.content CONTAINS "지향"
   OR i.content CONTAINS "권장"
   OR i.name CONTAINS "주의사항"
WITH i
MATCH (bp:BestPractice)
MERGE (i)-[:RECOMMENDS_PRACTICE]->(bp);
```

## 🎯 실행 가능한 매핑 스크립트

### 전체 매핑을 한 번에 실행

```cypher
// === 1. QueryType 매핑 ===
// 설명문 질의
MATCH (i:Item)
WHERE i.name CONTAINS "설명문 질의"
WITH i LIMIT 1
MATCH (qt:QueryType {name: "explanation"})
MERGE (i)-[:DESCRIBES_QUERY_TYPE]->(qt);

// 추론 질의
MATCH (i:Item)
WHERE i.name CONTAINS "추론 질의"
WITH i LIMIT 1
MATCH (qt:QueryType {name: "reasoning"})
MERGE (i)-[:DESCRIBES_QUERY_TYPE]->(qt);

// 타겟 질의
MATCH (i:Item)
WHERE i.name CONTAINS "타겟 질의"
WITH i LIMIT 1
MATCH (qt:QueryType {name: "target_short"})
MERGE (i)-[:DESCRIBES_QUERY_TYPE]->(qt);

// === 2. 모든 작업 규칙 Item을 Rule 태그 추가 ===
MATCH (i:Item)
WHERE i.categoryName = "작업 규칙"
SET i:GuideRule;

// === 3. 예시 포함 QATopic에 태그 추가 ===
MATCH (t:QATopic)
WHERE t.content CONTAINS "예시"
   OR t.content CONTAINS "❌"
   OR t.content CONTAINS "⭕"
SET t:ContainsExample;

// === 4. 제약조건 관련 Item 태그 ===
MATCH (i:Item)
WHERE i.content CONTAINS "불가" 
   OR i.content CONTAINS "금지"
   OR i.content CONTAINS "반드시"
SET i:ConstraintRelated;

// === 5. Best Practice 관련 Item 태그 ===
MATCH (i:Item)
WHERE i.content CONTAINS "지향"
   OR i.content CONTAINS "권장"
SET i:BestPracticeRelated;
```

## 📋 추가 매핑 제안

### 내용 기반 유사도 매핑

현재는 정확한 이름 매칭이 없어서 자동 매핑이 0개였습니다.
대신 **의미적 유사도**나 **키워드 기반** 매핑을 고려할 수 있습니다.

```cypher
// 키워드 기반 관계 생성
MATCH (i:Item), (r:Rule)
WHERE i.categoryName = "작업 규칙"
  AND (
    i.content CONTAINS "답변" AND r.content CONTAINS "답변"
    OR i.content CONTAINS "질의" AND r.content CONTAINS "질의"
    OR i.content CONTAINS "마크다운" AND r.content CONTAINS "markdown"
  )
MERGE (i)-[:RELATED_TO_RULE {matchType: "keyword"}]->(r);
```

## 🔧 Neo4j Browser에서 실행할 쿼리들

### 1. 현재 매핑 가능한 항목 확인

```cypher
// QueryType과 연결 가능한 Item 찾기
MATCH (i:Item)
WHERE i.name CONTAINS "질의"
RETURN i.categoryName, i.subcategoryName, i.name
ORDER BY i.name;
```

### 2. 작업 규칙 Item 확인

```cypher
// 작업 규칙 카테고리의 모든 Item
MATCH (i:Item {categoryName: "작업 규칙"})
RETURN i.subcategoryName, i.name, substring(i.content, 0, 100) as preview
ORDER BY i.subcategoryName, i.name;
```

### 3. 예시가 포함된 QATopic 확인

```cypher
// 예시가 포함된 모든 Topic
MATCH (t:QATopic)
WHERE t.content CONTAINS "예시"
RETURN t.categoryName, t.subcategoryName, t.name, 
       substring(t.content, 0, 150) as preview
LIMIT 20;
```

## ✅ 권장 작업 순서

1. **태그 먼저 추가** (위의 전체 매핑 스크립트 실행)
   - GuideRule, ContainsExample, ConstraintRelated 등

2. **수동으로 중요한 연결 생성**
   - Item (질의 타입) → QueryType
   - 특히 명확한 매핑이 있는 것들

3. **검증 및 확인**

   ```cypher
   // 새로 생성된 관계 확인
   MATCH (i)-[r:DESCRIBES_QUERY_TYPE]->(qt)
   RETURN i.name, type(r), qt.name;
   ```

4. **필요시 추가 매핑**
   - 키워드 기반 또는 수작업으로 추가

## 📝 참고사항

- **0개 관계 생성**이 나온 이유: CSV 데이터와 기존 데이터의 명명 규칙이 달라서 자동 매칭이 안됨
- **해결 방법**: 위의 수동 매핑 스크립트를 Neo4j Browser에서 직접 실행
- **장점**: 명시적이고 정확한 매핑 가능
- **단점**: 수작업 필요
