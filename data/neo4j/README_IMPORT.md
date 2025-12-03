# CSV to Neo4j Cypher Import Guide

`data/neo4j/` 디렉터리에 있는 CSV 파일들을 Neo4j로 임포트하기 위한 Cypher 스크립트입니다.

## 파일 구성

- `import_guide_data.cypher` - guide.csv 데이터 임포트 스크립트
- `import_qna_data.cypher` - qna.csv 데이터 임포트 스크립트

## 데이터 구조

### Guide Data (guide.csv)

```
Category (대분류)
  └─ Subcategory (중분류)
      └─ Item (소분류)
          └─ content (내용)
```

### QnA Data (qna.csv)

```
QACategory (대분류)
  └─ QASubcategory (중분류)
      └─ QATopic (소분류)
          └─ content (내용)
```

## 최적화 기능

### 1. 중복 제거

- **MERGE** 명령어 사용으로 동일한 노드 자동 중복 제거
- 유니크 제약조건 (Unique Constraints) 설정
  - Category/QACategory: `name` 기준
  - Subcategory/QASubcategory: `(categoryName, name)` 복합 키
  - Item/QATopic: `(categoryName, subcategoryName, name)` 복합 키

### 2. 관계 최적화

- 계층적 관계 구조 사용
  - `HAS_SUBCATEGORY`: Category → Subcategory
  - `HAS_ITEM` / `HAS_TOPIC`: Subcategory → Item/Topic
- 관계도 MERGE로 중복 방지
- QnA 데이터: 동일 이름의 다른 주제간 `RELATED_TO` 관계 자동 생성

### 3. 성능 최적화

- 인덱스 생성으로 검색 성능 향상
- 복합 키 제약조건으로 데이터 무결성 보장

## 사용 방법

### 1. CSV 파일 준비

CSV 파일을 Neo4j import 디렉토리로 복사:

**Windows:**

```powershell
# Neo4j import 디렉토리 확인
# 일반적으로: C:\Users\<username>\.Neo4jDesktop\relate-data\dbmss\<dbms-id>\import

# CSV 파일 복사
Copy-Item "C:\Users\우리집\Desktop\guide.csv" -Destination "<neo4j-import-path>"
Copy-Item "C:\Users\우리집\Desktop\qna.csv" -Destination "<neo4j-import-path>"
```

**또는 Neo4j Browser에서 직접 경로 사용:**

```cypher
// 스크립트 내의 'file:///' 경로를 절대 경로로 변경
LOAD CSV WITH HEADERS FROM 'file:///C:/Users/우리집/Desktop/guide.csv' AS row
```

### 2. Cypher 스크립트 실행

**Neo4j Browser에서:**

```cypher
// 1. guide.csv 임포트
// import_guide_data.cypher 파일의 내용을 복사하여 실행

// 2. qna.csv 임포트
// import_qna_data.cypher 파일의 내용을 복사하여 실행
```

**또는 neo4j-shell/cypher-shell에서:**

```bash
# guide.csv 임포트
cat import_guide_data.cypher | cypher-shell -u neo4j -p <password>

# qna.csv 임포트
cat import_qna_data.cypher | cypher-shell -u neo4j -p <password>
```

### 3. 데이터 확인

```cypher
// guide.csv 데이터 확인
MATCH (c:Category)-[:HAS_SUBCATEGORY]->(s:Subcategory)-[:HAS_ITEM]->(i:Item)
RETURN c.name, s.name, i.name, i.content
LIMIT 10;

// qna.csv 데이터 확인
MATCH (c:QACategory)-[:HAS_SUBCATEGORY]->(s:QASubcategory)-[:HAS_TOPIC]->(t:QATopic)
RETURN c.name, s.name, t.name, t.content
LIMIT 10;

// 전체 노드 개수 확인
MATCH (n)
RETURN labels(n) as Type, count(n) as Count;

// 관계 개수 확인
MATCH ()-[r]->()
RETURN type(r) as RelationType, count(r) as Count;
```

## 예제 쿼리

### 특정 카테고리의 모든 항목 조회

```cypher
// Guide 데이터
MATCH (c:Category {name: "작업 개요"})-[:HAS_SUBCATEGORY]->(s)-[:HAS_ITEM]->(i)
RETURN s.name, i.name, i.content;

// QnA 데이터
MATCH (c:QACategory {name: "🙅 자주 틀리는 부분"})-[:HAS_SUBCATEGORY]->(s)-[:HAS_TOPIC]->(t)
RETURN s.name, t.name, t.content;
```

### 검색 쿼리

```cypher
// 내용에 특정 키워드 포함된 항목 찾기
MATCH (i:Item)
WHERE i.content CONTAINS "이미지"
RETURN i.categoryName, i.subcategoryName, i.name
LIMIT 10;

// QnA 토픽 검색
MATCH (t:QATopic)
WHERE t.content CONTAINS "추론"
RETURN t.categoryName, t.subcategoryName, t.name
LIMIT 10;
```

### 관련 주제 찾기

```cypher
// QnA에서 관련된 주제 찾기
MATCH (t1:QATopic {name: "1. 추론 질의"})-[:RELATED_TO]-(t2:QATopic)
RETURN t1.subcategoryName, t2.subcategoryName, t2.content;
```

## 데이터 통계

### guide.csv

- 총 라인: 1,373개
- 대분류 (Category): 작업 개요, 작업 안내, 작업 규칙
- 중분류 (Subcategory): 작업 데이터 명세, 질의, 답변 등
- 소분류 (Item): 각 세부 가이드 항목

### qna.csv

- 총 라인: 774개
- 대분류 (QACategory): 🙅 자주 틀리는 부분, 🤹 자주 들어오는 질문
- 중분류 (QASubcategory): 질의, 답변, 작업 규칙 등
- 소분류 (QATopic): 각 FAQ 주제

## 주의사항

1. CSV 파일의 인코딩이 UTF-8인지 확인하세요
2. Neo4j 서버가 실행 중인지 확인하세요
3. 대용량 데이터의 경우 `USING PERIODIC COMMIT` 사용 고려
4. 제약조건과 인덱스는 한 번만 생성하면 됩니다

## 문제 해결

### CSV 파일을 찾을 수 없는 경우

```cypher
// Neo4j import 디렉토리 확인
CALL dbms.listConfig() 
YIELD name, value 
WHERE name = 'dbms.directories.import' 
RETURN value;
```

### 인코딩 문제

```powershell
# UTF-8로 변환 (PowerShell)
Get-Content "guide.csv" | Set-Content -Encoding UTF8 "guide_utf8.csv"
Get-Content "qna.csv" | Set-Content -Encoding UTF8 "qna_utf8.csv"
```

### 기존 데이터 삭제

```cypher
// 주의: 모든 데이터 삭제
MATCH (n)
DETACH DELETE n;

// 특정 레이블만 삭제
MATCH (n:Category)
DETACH DELETE n;

MATCH (n:QACategory)
DETACH DELETE n;
```
