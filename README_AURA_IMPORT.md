# Neo4j Aura CSV Import Guide

바탕화면의 CSV 파일을 Neo4j Aura 클라우드 데이터베이스로 임포트하는 가이드입니다.

## 사전 준비

### 1. Neo4j Aura 인스턴스 생성

1. [Neo4j Aura](https://console.neo4j.io) 접속
2. "New Instance" 클릭
3. Free tier 또는 적절한 플랜 선택
4. 인스턴스 생성 후 연결 정보 저장:
   - **URI**: `neo4j+s://xxxxx.databases.neo4j.io`
   - **Username**: `neo4j`
   - **Password**: 생성 시 제공된 비밀번호

⚠️ **중요**: 비밀번호는 인스턴스 생성 시 한 번만 표시되므로 반드시 저장하세요!

### 2. Python 패키지 설치

```powershell
# Neo4j Python 드라이버 설치
pip install neo4j

# 또는 프로젝트에 uv 사용 중이라면
uv pip install neo4j
```

## 임포트 방법

### 방법 1: 환경변수 사용 (권장)

```powershell
# 환경변수 설정
$env:NEO4J_URI = "neo4j+s://xxxxx.databases.neo4j.io"
$env:NEO4J_USERNAME = "neo4j"
$env:NEO4J_PASSWORD = "your-password-here"

# 스크립트 실행
python scripts/import_to_aura.py
```

### 방법 2: 스크립트 직접 수정

`scripts/import_to_aura.py` 파일을 열어서 다음 부분 수정:

```python
# 이 부분을 찾아서 수정
NEO4J_URI = "neo4j+s://your-actual-instance.databases.neo4j.io"
NEO4J_USERNAME = "neo4j"
NEO4J_PASSWORD = "your-actual-password"
```

그 후 실행:

```powershell
python scripts/import_to_aura.py
```

## 임포트 프로세스

스크립트는 다음 순서로 작동합니다:

1. **제약조건 생성**
   - Category, Subcategory, Item 유니크 제약조건
   - QACategory, QASubcategory, QATopic 유니크 제약조건

2. **인덱스 생성**
   - 검색 성능 향상을 위한 인덱스 생성

3. **guide.csv 임포트**
   - 배치 단위 (100 rows)로 처리
   - MERGE로 중복 자동 제거
   - 계층 관계 자동 생성

4. **qna.csv 임포트**
   - 배치 단위로 처리
   - 중복 제거 및 관계 생성

5. **관련 주제 연결**
   - 동일 이름의 다른 주제간 RELATED_TO 관계 생성

6. **결과 검증**
   - 노드 및 관계 개수 확인

## 예상 출력

```
==================================================
Neo4j Aura CSV Importer
==================================================
URI: neo4j+s://xxxxx.databases.neo4j.io
Username: neo4j
Guide CSV: C:\Users\우리집\Desktop\guide.csv
QnA CSV: C:\Users\우리집\Desktop\qna.csv
==================================================

Creating constraints...
  ✓ (c:Category)
  ✓ (s:Subcategory)
  ✓ (i:Item)
  ✓ (c:QACategory)
  ✓ (s:QASubcategory)
  ✓ (t:QATopic)

Creating indexes...
  ✓ (c:Category) ON (c.name)
  ✓ (s:Subcategory) ON (s.name)
  ✓ (i:Item) ON (i.name)
  ✓ (c:QACategory) ON (c.name)
  ✓ (s:QASubcategory) ON (s.name)
  ✓ (t:QATopic) ON (t.name)

Importing guide.csv from C:\Users\우리집\Desktop\guide.csv...
Total rows: 1373
  Processed 100/1373 rows
  Processed 200/1373 rows
  ...
  Processed 1373/1373 rows
✓ Guide data import completed!

Importing qna.csv from C:\Users\우리집\Desktop\qna.csv...
Total rows: 774
  Processed 100/774 rows
  ...
  Processed 774/774 rows
✓ QnA data import completed!

Creating related topic links...
  ✓ Created 15 related topic links

==================================================
Import Verification
==================================================
  Categories           :     3 nodes/relationships
  Subcategories        :    15 nodes/relationships
  Items                :   120 nodes/relationships
  QA Categories        :     2 nodes/relationships
  QA Subcategories     :    10 nodes/relationships
  QA Topics            :    85 nodes/relationships
  HAS_SUBCATEGORY      :    17 nodes/relationships
  HAS_ITEM             :   120 nodes/relationships
  HAS_TOPIC            :    85 nodes/relationships
  RELATED_TO           :    15 nodes/relationships

✅ Import completed successfully!
```

## Neo4j Aura에서 확인

### Neo4j Browser 접속

1. [Neo4j Aura Console](https://console.neo4j.io) 접속
2. 해당 인스턴스의 "Open" 버튼 클릭
3. Browser가 열리면 로그인

### 데이터 확인 쿼리

```cypher
// 전체 구조 시각화 (일부만)
MATCH (c:Category)-[:HAS_SUBCATEGORY]->(s:Subcategory)-[:HAS_ITEM]->(i:Item)
RETURN c, s, i
LIMIT 25;

// QnA 데이터 시각화
MATCH (c:QACategory)-[:HAS_SUBCATEGORY]->(s:QASubcategory)-[:HAS_TOPIC]->(t:QATopic)
RETURN c, s, t
LIMIT 25;

// 노드 개수 확인
MATCH (n)
RETURN labels(n)[0] as Type, count(n) as Count
ORDER BY Count DESC;

// 관계 개수 확인
MATCH ()-[r]->()
RETURN type(r) as RelationType, count(r) as Count;

// 특정 카테고리 내용 검색
MATCH (c:Category {name: "작업 안내"})-[:HAS_SUBCATEGORY]->(s)-[:HAS_ITEM]->(i)
RETURN s.name as Subcategory, i.name as Item, i.content as Content;

// 키워드 검색 (예: "이미지")
MATCH (i:Item)
WHERE i.content CONTAINS "이미지"
RETURN i.categoryName, i.subcategoryName, i.name, i.content
LIMIT 10;
```

## 문제 해결

### 연결 오류

```
neo4j.exceptions.ServiceUnavailable: Failed to establish connection
```

**해결 방법:**

1. Neo4j Aura 인스턴스가 실행 중인지 확인
2. URI가 올바른지 확인 (`neo4j+s://` 프로토콜 사용)
3. 네트워크 방화벽 확인

### 인증 오류

```
neo4j.exceptions.AuthError: The client is unauthorized
```

**해결 방법:**

1. 비밀번호가 올바른지 확인
2. Aura Console에서 비밀번호 재설정

### CSV 파일을 찾을 수 없음

```
⚠️  파일을 찾을 수 없습니다: C:\Users\우리집\Desktop\guide.csv
```

**해결 방법:**

1. CSV 파일이 바탕화면에 있는지 확인
2. 파일 이름이 정확히 `guide.csv`, `qna.csv`인지 확인
3. 스크립트에서 경로 수정:

   ```python
   GUIDE_CSV = Path("원하는/경로/guide.csv")
   QNA_CSV = Path("원하는/경로/qna.csv")
   ```

### 인코딩 오류

```
UnicodeDecodeError: 'utf-8' codec can't decode byte
```

**해결 방법:**

```powershell
# CSV 파일을 UTF-8로 재저장
$content = Get-Content "guide.csv" -Encoding Default
$content | Set-Content "guide_utf8.csv" -Encoding UTF8
```

## 재실행 및 데이터 삭제

### 전체 데이터 삭제 후 재실행

```cypher
// Neo4j Browser에서 실행
MATCH (n)
DETACH DELETE n;
```

그 후 Python 스크립트 재실행

### 특정 데이터만 삭제

```cypher
// Guide 데이터만 삭제
MATCH (n:Category)
DETACH DELETE n;

MATCH (n:Subcategory)
DETACH DELETE n;

MATCH (n:Item)
DETACH DELETE n;

// QnA 데이터만 삭제
MATCH (n:QACategory)
DETACH DELETE n;

MATCH (n:QASubcategory)
DETACH DELETE n;

MATCH (n:QATopic)
DETACH DELETE n;
```

## 고급 활용

### 스크립트 커스터마이징

배치 크기 조정 (메모리가 충분하면 더 큰 배치 사용):

```python
importer.import_guide_csv(str(GUIDE_CSV), batch_size=500)
importer.import_qna_csv(str(QNA_CSV), batch_size=500)
```

### 프로젝트 코드와 통합

```python
# 기존 프로젝트에서 사용
from scripts.import_to_aura import AuraImporter

importer = AuraImporter(uri, username, password)
importer.create_constraints()
importer.import_guide_csv("path/to/guide.csv")
importer.verify_import()
importer.close()
```

## 참고 자료

- [Neo4j Aura Documentation](https://neo4j.com/docs/aura/)
- [Neo4j Python Driver](https://neo4j.com/docs/python-manual/current/)
- [Cypher Query Language](https://neo4j.com/docs/cypher-manual/current/)
